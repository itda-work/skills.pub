"""사용자 ZIP(HWPX)·zlib(HWP5) 입력의 자원 고갈·XXE·경로 탐색 가드 — 표준 라이브러리만 (#27).

사용자가 받은 파일(공고·메일 첨부)을 그대로 여는 경로라, 악성·손상 파일 하나가 메모리를 고갈시키거나
세션을 멈추게 할 수 있다. 여기서는 **풀기 전에** 선언값으로 거르고, **푸는 동안** 실제 바이트로 다시 잰다
(Central Directory 값은 위조될 수 있다).

- 엔트리 수: EOCD(끝 레코드)에서 `ZipFile` 이 목록을 만들기 **전에** 센다 — 목록 자체가 메모리를 먹는다.
- 비압축 합계·단일 엔트리 크기: Central Directory 선언값으로 사전 검사 + 읽는 중 누적 바이트로 재검사.
- 압축률: 정상 HWPX 는 STORED·DEFLATED 만 쓴다. 다른 방식(bzip2·lzma — 비율 상한이 사실상 없다)은 거부하고,
  STORED 는 선언 크기 = 압축 크기, DEFLATED 는 deflate 가 물리적으로 낼 수 없는 비율(>1100:1)이면 CD 위조로 본다.
  실 공고 첨부에 77MB BMP 가 92:1 로 들어 있어(실측) 수십~수백 배 비율 상한은 정상 파일을 막는다.
- XML: DOCTYPE 선언이 있으면 거부한다(XXE·Billion Laughs) — 정상 HWPX 에 없다(실측 99건 0건).
  파이썬·expat 버전의 완화에 기대지 않고, 루트 요소 전에 멈추는 expat 판독으로 인코딩과 무관하게 잡는다.
- 엔트리 이름: NUL·`..`·절대경로·드라이브 문자를 거부한다.

상한은 환경변수로 조절한다: `ITDA_MAX_UNZIP_MB`(기본 256, 1~8192) · `ITDA_MAX_ZIP_ENTRIES`(기본 500, 1~65535).
같은 파일이 세 곳에 있다 — itda-doc `hwpx/reader/hwpx_native/` · itda-data `biz-redact/scripts/` ·
`synthetic-data/scripts/`. 고치면 셋을 함께 고친다(스킬별로 배포되고 hwpx 리더는 패키지라 shared 평면 주입이 닿지 않는다).
"""
from __future__ import annotations

import io
import os
import struct
import zipfile
import zlib
from pathlib import Path
from typing import BinaryIO
from xml.parsers import expat

DEFAULT_MAX_UNZIP_MB = 256
DEFAULT_MAX_ENTRIES = 500
MAX_UNZIP_MB_CEILING = 8192
MAX_ENTRIES_CEILING = 65535
ENV_MAX_UNZIP_MB = "ITDA_MAX_UNZIP_MB"
ENV_MAX_ENTRIES = "ITDA_MAX_ZIP_ENTRIES"
DEFLATE_MAX_RATIO = 1100  # deflate 의 이론 상한은 약 1032:1 — 이를 넘는 선언은 CD 위조다
ALLOWED_METHODS = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
XML_SUFFIXES = (".xml", ".hpf", ".rdf")
_CHUNK = 1 << 20


class UnsafeArchiveError(ValueError):
    """상한 초과·위조·위험 구조 — 무엇이 걸렸는지와 조절 방법을 말한다."""


def _env_int(name: str, default: int, ceiling: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise UnsafeArchiveError(f"환경변수 {name}={raw!r} 는 정수여야 합니다(1~{ceiling})") from exc
    if not 1 <= value <= ceiling:
        raise UnsafeArchiveError(f"환경변수 {name}={value} 는 1~{ceiling} 범위여야 합니다")
    return value


def max_unzip_bytes() -> int:
    return _env_int(ENV_MAX_UNZIP_MB, DEFAULT_MAX_UNZIP_MB, MAX_UNZIP_MB_CEILING) * 1024 * 1024


def max_entries() -> int:
    return _env_int(ENV_MAX_ENTRIES, DEFAULT_MAX_ENTRIES, MAX_ENTRIES_CEILING)


def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):.1f}MB"


def _size_hint() -> str:
    return f"정상 문서가 맞다면 환경변수 {ENV_MAX_UNZIP_MB}(MB, 기본 {DEFAULT_MAX_UNZIP_MB})로 상한을 올릴 수 있습니다"


class Budget:
    """한 문서를 푸는 동안 실제로 만든 바이트의 누적 — 선언값이 아니라 결과로 잰다."""

    def __init__(self, limit: int | None = None) -> None:
        self.limit = max_unzip_bytes() if limit is None else limit
        self.used = 0

    def charge(self, n: int, what: str) -> None:
        self.used += n
        if self.used > self.limit:
            raise UnsafeArchiveError(
                f"압축을 푼 크기가 상한 {_mb(self.limit)} 을 넘었습니다({what}) — 압축 폭탄이거나 매우 큰 문서입니다. {_size_hint()}"
            )


# ── ZIP ─────────────────────────────────────────────────────────────────────


def _declared_entry_count(fh: BinaryIO) -> int | None:
    """EOCD(ZIP64 포함)에 적힌 전체 엔트리 수. 끝 레코드를 못 찾으면 None(판정은 zipfile 에 맡긴다)."""
    fh.seek(0, os.SEEK_END)
    size = fh.tell()
    span = min(size, 22 + 0xFFFF)
    fh.seek(size - span)
    tail = fh.read(span)
    pos = tail.rfind(b"PK\x05\x06")
    if pos < 0 or len(tail) - pos < 22:
        return None
    count = struct.unpack_from("<H", tail, pos + 10)[0]
    if count != 0xFFFF:
        return count
    loc = pos - 20  # ZIP64 EOCD locator 는 EOCD 바로 앞 20바이트
    if loc < 0 or tail[loc:loc + 4] != b"PK\x06\x07":
        return count
    z64_offset = struct.unpack_from("<Q", tail, loc + 8)[0]
    if z64_offset + 56 > size:
        return None
    fh.seek(z64_offset)
    rec = fh.read(56)
    if rec[:4] != b"PK\x06\x06":
        return None
    return struct.unpack_from("<Q", rec, 32)[0]


def _unsafe_name(name: str) -> bool:
    if "\x00" in name:
        return True
    norm = name.replace("\\", "/")
    if norm.startswith("/") or (len(norm) >= 2 and norm[1] == ":"):
        return True
    return ".." in norm.split("/")


def check_infos(zf: zipfile.ZipFile) -> None:
    """Central Directory 선언값으로 거른다 — 아무것도 풀기 전에."""
    infos = zf.infolist()
    limit_entries = max_entries()
    if len(infos) > limit_entries:
        raise UnsafeArchiveError(
            f"ZIP 엔트리가 {len(infos)}개로 상한 {limit_entries}개를 넘습니다 — 정상 한글 문서는 수십 개입니다. "
            f"정상 문서가 맞다면 환경변수 {ENV_MAX_ENTRIES} 로 올릴 수 있습니다"
        )
    limit = max_unzip_bytes()
    total = 0
    for info in infos:
        if _unsafe_name(info.filename):
            raise UnsafeArchiveError(f"경로 탐색 위험이 있는 엔트리 이름입니다({info.filename!r}) — 정상 한글 문서에 없는 형태라 거부합니다")
        if info.compress_type not in ALLOWED_METHODS:
            raise UnsafeArchiveError(
                f"지원하지 않는 압축 방식입니다({info.filename}: method {info.compress_type}) — 한글 문서는 저장·deflate 만 씁니다"
            )
        if info.file_size > limit:
            raise UnsafeArchiveError(f"엔트리 {info.filename} 의 크기 {_mb(info.file_size)} 가 상한 {_mb(limit)} 을 넘습니다. {_size_hint()}")
        if info.compress_type == zipfile.ZIP_STORED and info.file_size != info.compress_size:
            raise UnsafeArchiveError(f"엔트리 {info.filename} 의 크기 정보가 서로 다릅니다(무압축인데 선언 크기 ≠ 저장 크기) — 손상·위조된 ZIP 입니다")
        if info.compress_type == zipfile.ZIP_DEFLATED and info.file_size > DEFLATE_MAX_RATIO * max(info.compress_size, 1):
            raise UnsafeArchiveError(
                f"엔트리 {info.filename} 의 선언 압축률이 {info.file_size // max(info.compress_size, 1)}:1 로 deflate 가 낼 수 없는 값입니다 — 위조된 ZIP 입니다"
            )
        total += info.file_size
        if total > limit:
            raise UnsafeArchiveError(f"압축을 푼 합계가 상한 {_mb(limit)} 을 넘습니다(선언값 기준) — 압축 폭탄이거나 매우 큰 문서입니다. {_size_hint()}")


def _check_declared_entries(fh: BinaryIO) -> None:
    declared = _declared_entry_count(fh)
    limit_entries = max_entries()
    if declared is not None and declared > limit_entries:
        raise UnsafeArchiveError(
            f"ZIP 엔트리가 {declared}개로 상한 {limit_entries}개를 넘습니다(목록을 읽기 전 판정) — 정상 한글 문서는 수십 개입니다. "
            f"정상 문서가 맞다면 환경변수 {ENV_MAX_ENTRIES} 로 올릴 수 있습니다"
        )


def open_zip(source: str | Path | bytes) -> zipfile.ZipFile:
    """엔트리 수를 EOCD 로 먼저 세고, 연 뒤 Central Directory 를 검사한 ZipFile. 형식 오류는 BadZipFile 그대로."""
    if isinstance(source, (bytes, bytearray)):
        buf = io.BytesIO(source)
        _check_declared_entries(buf)
        buf.seek(0)
        zf = zipfile.ZipFile(buf)
    else:
        with open(source, "rb") as fh:
            _check_declared_entries(fh)
        zf = zipfile.ZipFile(source)
    try:
        check_infos(zf)
    except BaseException:
        zf.close()
        raise
    return zf


def reject_dtd(data: bytes, name: str) -> None:
    """루트 요소 전에 DOCTYPE 이 있으면 거부. 형식이 깨진 XML 은 여기서 판정하지 않는다(본 파서가 말한다)."""
    parser = expat.ParserCreate()

    class _Root(Exception):
        pass

    def on_doctype(*_args) -> None:
        raise UnsafeArchiveError(f"{name} 에 DOCTYPE(DTD·엔티티) 선언이 있습니다 — 정상 한글 문서에 없고 XXE·엔티티 폭탄에 쓰이는 형태라 거부합니다")

    def on_root(*_args) -> None:
        raise _Root

    parser.StartDoctypeDeclHandler = on_doctype
    parser.StartElementHandler = on_root
    try:
        parser.Parse(data, True)
    except _Root:
        return
    except expat.ExpatError:
        return


def read_entry(zf: zipfile.ZipFile, name: str | zipfile.ZipInfo, budget: Budget) -> bytes:
    """엔트리를 조각으로 읽으며 실제 바이트를 잰다. XML 엔트리는 DOCTYPE 을 거부한다."""
    info = name if isinstance(name, zipfile.ZipInfo) else zf.getinfo(name)
    chunks: list[bytes] = []
    # CPython ZipExtFile 은 선언 크기(file_size)에서 출력을 자르고 CRC 를 대조한다 — 선언을 줄인 위조는
    # 잘린 데이터의 CRC 불일치(BadZipFile)로 드러난다. 여기서는 실제로 만든 바이트를 문서 예산에 올린다.
    try:
        with zf.open(info) as fh:
            while True:
                chunk = fh.read(_CHUNK)
                if not chunk:
                    break
                budget.charge(len(chunk), info.filename)
                chunks.append(chunk)
    except zipfile.BadZipFile as exc:
        raise UnsafeArchiveError(f"엔트리 {info.filename} 를 풀 수 없습니다 — 손상됐거나 크기 정보가 위조된 ZIP 입니다({exc})") from exc
    except (zlib.error, EOFError) as exc:
        raise UnsafeArchiveError(f"엔트리 {info.filename} 의 압축 데이터가 깨졌습니다({exc})") from exc
    data = b"".join(chunks)
    if info.filename.lower().endswith(XML_SUFFIXES):
        reject_dtd(data, info.filename)
    return data


def read_prefix(zf: zipfile.ZipFile, name: str, limit: int = 256) -> bytes:
    """형식 판별용 — 앞 `limit` 바이트만 푼다(mimetype 이 폭탄이어도 안전)."""
    with zf.open(name) as fh:
        return fh.read(limit)


# ── HWP5 zlib ───────────────────────────────────────────────────────────────


def inflate(data: bytes, wbits: int, budget: Budget, what: str) -> bytes:
    """`zlib.decompress(data, wbits)` 와 같은 결과를 내되, 출력이 남은 예산을 넘으면 그 자리에서 멈춘다.

    미완결 스트림은 zlib.decompress 처럼 zlib.error 로 알린다(호출자의 raw/zlib 헤더 재시도 의미를 지킨다).
    """
    remaining = budget.limit - budget.used
    d = zlib.decompressobj(wbits)
    out = d.decompress(data, remaining + 1)
    if len(out) > remaining:
        budget.charge(len(out), what)
    if not d.eof:
        raise zlib.error("incomplete or truncated stream")
    budget.charge(len(out), what)
    return out
