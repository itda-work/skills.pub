"""page_input.py — itda-hyve 가 저장한 페이지 파일을 읽어 문자열로 푼다. 네트워크 없음.

web-reader 8.0.0(itda-work/skills#46): 페이지는 itda-hyve ``http_request`` 가 ``save_as`` 로 저장한다.
저장 파일에는 **본문 바이트만** 있다 — 상태·Content-Type 은 도구 응답에만 있어, 모델이 그 값을
``--status``·``--content-type`` 으로 넘긴다(사용자 결정 D5-A. itda-hyve 에 저장 메타가 생기면 그것으로 바꾼다).

입력 세 형태는 공용 ``shared/hyve_input.py`` 가 가른다: (a) 본문 그대로 (b) 응답 JSON 전체 (c) 실패 자리.

인코딩 순서: Content-Type charset → BOM → ``<meta charset>``(앞 4KB) → UTF-8 엄격 → CP949 엄격 → UTF-8 대체(경고).
EUC-KR 은 CP949(상위 집합)로 푼다.
"""
from __future__ import annotations

import codecs
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from hyve_input import HyveHTTPError, HyveInputError, unwrap


class PageInputError(Exception):
    """페이지로 쓸 수 없는 입력. ``kind`` 는 출력 JSON 의 ``error`` 값, ``exit_code`` 는 CLI 종료 코드."""

    def __init__(self, kind: str, message: str, exit_code: int = 1, hint: str = ""):
        super().__init__(message)
        self.kind = kind
        self.exit_code = exit_code
        self.hint = hint


BROWSER_ROUTE = "브라우저 경로 — itda-web:aside-browser-mcp(Aside), 없으면 Claude in Chrome 등 연결된 브라우저 도구"

# 첫 바이트로 가르는 비HTML 형식
_MAGIC = (
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", "application/zip(docx·xlsx·pptx·hwpx 포함)"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "application/x-ole(hwp·doc·xls)"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"\x1f\x8b", "application/gzip"),
    (b"OggS", "audio/ogg"),
    (b"ID3", "audio/mpeg"),
    (b"fLaC", "audio/flac"),
    (b"\x1a\x45\xdf\xa3", "video/webm·mkv"),
    (b"7z\xbc\xaf\x27\x1c", "application/x-7z-compressed"),
    (b"Rar!\x1a\x07", "application/x-rar"),
    (b"%!PS", "application/postscript"),
    (b"{\\rtf", "application/rtf"),
    (b"\x00\x00\x01\x00", "image/x-icon"),
    (b"BM", None),  # 비트맵은 아래 길이 검사와 함께(짧은 텍스트 "BM…" 오탐 방지)
)
# 오프셋이 있는 서명 — RIFF 컨테이너(webp·wav·avi), ISO BMFF(mp4·mov·heic·avif)
_RIFF_KINDS = {b"WEBP": "image/webp", b"WAVE": "audio/wav", b"AVI ": "video/avi"}
_TEXT_TYPES = ("text/", "application/xhtml+xml", "application/xml", "application/rss+xml", "application/atom+xml")
_CHARSET_RE = re.compile(r"charset\s*=\s*[\"']?([A-Za-z0-9_.:\-]+)", re.IGNORECASE)
_META_CHARSET_RE = re.compile(rb"<meta[^>]+charset\s*=\s*[\"']?([A-Za-z0-9_.:\-]+)", re.IGNORECASE)
_ALIASES = {"euc-kr": "cp949", "euckr": "cp949", "ks_c_5601-1987": "cp949", "ksc5601": "cp949", "x-windows-949": "cp949"}


@dataclass
class Page:
    text: str
    raw_sha256: str
    encoding: str
    encoding_source: str
    status: Optional[int] = None
    content_type: str = ""
    form: str = "raw"
    warnings: list[str] = field(default_factory=list)


def _codec(name: str) -> Optional[str]:
    name = name.strip().lower()
    name = _ALIASES.get(name, name)
    try:
        return codecs.lookup(name).name
    except LookupError:
        return None


def _is_western_single_byte(codec: str) -> bool:
    return codec.startswith(("iso8859-", "cp125", "latin", "mac-roman")) or codec in ("ascii",)


def charset_of(content_type: str) -> Optional[str]:
    m = _CHARSET_RE.search(content_type or "")
    return m.group(1) if m else None


def non_html_kind(data: bytes, content_type: str = "") -> Optional[str]:
    """비HTML 이면 그 종류 문자열, HTML·텍스트로 보이면 None."""
    head = data[:16]
    for magic, kind in _MAGIC:
        if kind and head.startswith(magic):
            return kind
    if head.startswith(b"BM") and len(data) > 26 and data[6:10] == b"\x00\x00\x00\x00":
        return "image/bmp"
    if head[:4] == b"RIFF" and head[8:12] in _RIFF_KINDS:
        return _RIFF_KINDS[head[8:12]]
    if head[4:8] == b"ftyp":
        return "video/mp4·mov·heic(ISO BMFF)"
    # 서명 없는 바이너리 — BOM 없는 앞 4KB 에 NUL 이 1% 넘게 있으면 텍스트가 아니다(W14 리뷰 m9)
    sample = data[:4096]
    if sample and not sample.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)) and sample.count(b"\x00") * 100 > len(sample):
        return "application/octet-stream(NUL 바이트 — 서명 없는 바이너리)"
    base = (content_type or "").split(";", 1)[0].strip().lower()
    if base and not base.startswith(_TEXT_TYPES) and "xml" not in base and "html" not in base:
        return base
    return None


def decode(data: bytes, content_type: str = "") -> tuple[str, str, str, list[str]]:
    """``(text, 쓴 코덱, 출처, 경고)``. 출처는 header·bom·meta·utf8·cp949·fallback 중 하나."""
    warnings: list[str] = []
    declared = charset_of(content_type)
    if declared:
        codec = _codec(declared)
        if codec is not None and _is_western_single_byte(codec) and any(b >= 0x80 for b in data):
            # latin-1·cp1252 류는 어떤 바이트든 풀린다 — 헤더만 믿으면 한글이 경고 없이 깨진다(W14 리뷰 m8).
            # meta 가 다른 코덱을 말하고 그것으로 엄격히 풀리면 그쪽, 아니면 UTF-8 엄격 디코드가 되면 그쪽.
            m = _META_CHARSET_RE.search(data[:4096])
            meta_codec = _codec(m.group(1).decode("ascii", "replace")) if m else None
            for alt, why in ((meta_codec, "meta"), ("utf-8", "utf8")):
                if alt and alt != codec and not _is_western_single_byte(alt):
                    try:
                        text = data.decode(alt)
                    except UnicodeDecodeError:
                        continue
                    warnings.append(f"Content-Type 은 {declared} 인데 본문이 {alt} 로 깨끗이 풀려 그쪽을 씁니다")
                    return text, alt, why, warnings
        if codec is None:
            warnings.append(f"Content-Type 의 charset({declared})을 모릅니다 — 본문에서 다시 판단합니다")
        else:
            try:
                return data.decode(codec), codec, "header", warnings
            except UnicodeDecodeError:
                warnings.append(f"Content-Type 은 {declared} 인데 그 코덱으로 풀리지 않습니다 — 본문에서 다시 판단합니다")
    for bom, codec in ((codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16")):
        if data.startswith(bom):
            return data.decode(codec, errors="replace"), codec, "bom", warnings
    m = _META_CHARSET_RE.search(data[:4096])
    if m:
        codec = _codec(m.group(1).decode("ascii", "replace"))
        if codec:
            try:
                return data.decode(codec), codec, "meta", warnings
            except UnicodeDecodeError:
                warnings.append(f"<meta charset={m.group(1).decode('ascii', 'replace')}> 로 풀리지 않습니다 — 다른 코덱을 시도합니다")
    for codec, source in (("utf-8", "utf8"), ("cp949", "cp949")):
        try:
            return data.decode(codec), codec, source, warnings
        except UnicodeDecodeError:
            continue
    text = data.decode("utf-8", errors="replace")
    warnings.append(f"어떤 코덱으로도 깨끗이 풀리지 않아 UTF-8 대체 문자로 풀었습니다(U+FFFD {text.count(chr(0xFFFD))}개)")
    return text, "utf-8", "fallback", warnings


def from_bytes(raw: bytes, *, content_type: str = "", status: Optional[int] = None, source: Optional[Path] = None) -> Page:
    """파일 바이트 → :class:`Page`. 쓸 수 없는 입력이면 :class:`PageInputError`."""
    try:
        body = unwrap(raw, source=source)
    except HyveHTTPError as exc:
        # (b) 응답 JSON 에 오류 상태 — 상태 판정은 아래 check_status 와 같은 규칙
        check_status(int(exc.status))
        raise PageInputError("http", str(exc)) from exc
    except HyveInputError as exc:
        raise PageInputError(exc.kind, str(exc)) from exc
    data = body.data
    if body.form == "envelope":
        if status is None:
            status = body.status
        if not content_type:
            content_type = body.content_type
    if status is not None:
        check_status(status)
    kind = non_html_kind(data, content_type)
    if kind:
        raise PageInputError(
            "non_html_content",
            f"HTML 이 아닙니다({kind}) — 웹 페이지 추출기로 읽지 않습니다",
            exit_code=3,
            hint="PDF 는 itda-doc:pdf-context-refinery, 한글 문서(hwpx)는 itda-doc:hwpx 로 읽으세요. 저장한 파일은 그대로 넘길 수 있습니다.",
        )
    text, codec, enc_source, warnings = decode(data, content_type)
    return Page(
        text=text,
        raw_sha256=hashlib.sha256(data).hexdigest(),
        encoding=codec,
        encoding_source=enc_source,
        status=status,
        content_type=content_type,
        form=body.form,
        warnings=warnings,
    )


def check_status(status: int) -> None:
    """페이지 HTTP 상태를 판정한다. 2xx 가 아니면 :class:`PageInputError`."""
    if 200 <= status < 300:
        return
    if 300 <= status < 400:
        raise PageInputError(
            "redirect_not_followed", f"HTTP {status} — 리다이렉트 응답입니다(본문이 아닙니다)",
            hint="plan.py next 에 --status 와 --location 을 넘겨 다음 홉을 계획하세요.",
        )
    if status in (401, 403, 407):
        raise PageInputError(
            "blocked_or_auth", f"HTTP {status} — 로그인이 필요하거나 봇 차단으로 거부됐습니다", exit_code=4,
            hint=f"정적 요청으로는 받을 수 없습니다. {BROWSER_ROUTE} 에서 사용자가 직접 열어 보세요.",
        )
    if status in (404, 410):
        raise PageInputError("not_found", f"HTTP {status} — 페이지가 없습니다. URL 을 확인하세요.")
    if status == 429:
        raise PageInputError("rate_limited", "HTTP 429 — 요청이 많다고 거부됐습니다(itda-hyve 가 이미 재시도했습니다). 잠시 뒤 다시 하세요.")
    if status >= 500:
        raise PageInputError("server_error", f"HTTP {status} — 사이트 서버 오류입니다(itda-hyve 가 이미 재시도했습니다).")
    raise PageInputError("http", f"HTTP {status} — 페이지를 받지 못했습니다.")


def read_page(path: Optional[str], *, content_type: str = "", status: Optional[int] = None) -> Page:
    """``path`` 파일(없으면 stdin 바이트)을 읽는다."""
    if path:
        p = Path(path).expanduser()
        if not p.is_file():
            raise PageInputError("input", f"입력 파일이 없습니다: {p}")
        try:
            raw = p.read_bytes()
        except OSError as exc:
            raise PageInputError("input", f"입력 파일을 읽을 수 없습니다: {p} ({exc})") from exc
        return from_bytes(raw, content_type=content_type, status=status, source=p)
    raw = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
    return from_bytes(raw, content_type=content_type, status=status)
