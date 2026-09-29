"""hwpx_redact.py — biz-redact 의 HWPX(한글) 경로 (#17). stdlib only.

설계:
- **본문(Contents/section*.xml)** 은 문단 단위로 매칭한다. `<hp:t>` 조각을 문서 순서로 이어 붙인 글자열에서
  용어집 표면형을 찾으므로, 글자모양이 달라 run 이 갈린 "현대" + "엘리베이터" 도 잡는다. 치환은 원래 XML 의
  글자 조각만 바꾸는 splice 다(DOM 재직렬화 없음) — 서식·표·그림은 그대로이고, 토큰은 매치가 시작된 조각에
  들어간다. 문단 경계는 `\\n`, 탭은 `\\t` 로 두어 표면형이 문단을 넘어 매칭되지 않게 한다.
- **본문 밖** — 미리보기 글자(Preview/PrvText.txt)·메타데이터(content.hpf 등) 같은 XML/텍스트 엔트리는 글자 조각·
  속성값마다 같은 규칙으로 치환하고, 미리보기 **그림**(Preview/PrvImage.*)은 흰 1px PNG 로 바꾼다(한글이 저장할 때
  다시 만든다). 문서 속 그림(BinData)의 글자는 볼 수 없다 — 그 수를 리포트에 싣는다.
- **게이트** — 치환 뒤 **컨테이너의 모든 텍스트 엔트리**를 다시 훑어 원문 잔존이 0 이어야 산출한다. 본문만 보는
  게이트는 미리보기·메타데이터로 새는 기밀을 못 본다.
- 매칭 규칙·토큰·우선순위(길이 내림차순 → 정의 순서)는 텍스트 경로(`biz_redact.mask`)와 같다. 본문 글자열에 대해
  두 경로의 결과가 같은지 실행 중에 대조한다(갈리면 멈춘다).
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from html import unescape

from safe_archive import Budget, UnsafeArchiveError, open_zip, read_entry, read_prefix  # noqa: F401 — #27 가드

SECTION_RE = re.compile(r"^Contents/section\d+\.xml$")
TEXT_ENTRY_RE = re.compile(r"\.(xml|hpf|rdf|txt|json)$", re.IGNORECASE)
PREVIEW_IMAGE_RE = re.compile(r"^Preview/PrvImage\.[A-Za-z0-9]+$")
TAG_RE = re.compile(r"<(/?)([A-Za-z_][\w:.\-]*)((?:\s+[\w:.\-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*)\s*(/?)>|<\?.*?\?>|<!--.*?-->", re.S)
ATTR_RE = re.compile(r"([\w:.\-]+)(\s*=\s*)(\"[^\"]*\"|'[^']*')")

# 흰 1×1 PNG — 미리보기 그림 대체(기밀이 그려진 첫 쪽 그림을 남기지 않는다)
BLANK_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c63f8ffff3f0005fe02fea7d6a4b30000000049454e44ae426082"
)


def xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class Piece:
    """본문 글자 조각 — XML 원문 [start, end) 의 이스케이프된 텍스트."""
    start: int
    end: int
    text: str  # 이스케이프를 푼 글자(NFC)
    raw_text: str = ""  # 이스케이프를 푼 원래 글자 — NFC 와 다르면 되쓸 때 정규화한다


@dataclass
class Stream:
    text: str = ""
    pieces: list[Piece] = field(default_factory=list)
    # 스트림 위치 → (조각 번호, 조각 안 위치). 경계 문자(\n·\t)는 -1
    owner: list[tuple[int, int]] = field(default_factory=list)


def build_stream(xml: str) -> Stream:
    """section XML → 매칭용 글자열. `<hp:t>` 안의 글자만 담고, 문단 경계는 \\n, 탭은 \\t, 줄바꿈은 \\n."""
    st = Stream()
    chars: list[str] = []
    in_t = 0
    last = 0
    for m in TAG_RE.finditer(xml):
        if in_t and m.start() > last:
            raw = unescape(xml[last:m.start()])
            txt = unicodedata.normalize("NFC", raw)
            idx = len(st.pieces)
            st.pieces.append(Piece(last, m.start(), txt, raw))
            for k, ch in enumerate(txt):
                chars.append(ch)
                st.owner.append((idx, k))
        last = m.end()
        closing, name, _attrs, self_close = m.group(1), m.group(2), m.group(3), m.group(4)
        if name is None:
            continue
        local = name.split(":")[-1]
        if local == "t":
            if self_close:
                continue
            in_t += -1 if closing else 1
            in_t = max(in_t, 0)
        elif local == "p" and not self_close:
            chars.append("\n")
            st.owner.append((-1, -1))
        elif local == "tab":
            chars.append("\t")
            st.owner.append((-1, -1))
        elif local == "lineBreak":
            chars.append("\n")
            st.owner.append((-1, -1))
    st.text = "".join(chars)
    return st


def plan(text: str, surfaces: list) -> list[tuple[int, int, dict]]:
    """`biz_redact.mask` 와 같은 우선순위로 치환 구간을 정한다 — (시작, 끝, 표면형 디스크립터) 목록(위치순)."""
    free: list[tuple[int, int]] = [(0, len(text))]
    taken: list[tuple[int, int, dict]] = []
    for s in surfaces:
        new_free: list[tuple[int, int]] = []
        for a, b in free:
            cursor = a
            for m in s["matcher"].finditer(text[a:b]):
                sa, sb = a + m.start(), a + m.end()
                if sa > cursor:
                    new_free.append((cursor, sa))
                taken.append((sa, sb, s))
                cursor = sb
            if cursor < b:
                new_free.append((cursor, b))
        free = new_free
    return sorted(taken, key=lambda t: t[0])


def apply_plan(xml: str, st: Stream, spans: list[tuple[int, int, dict]]) -> str:
    """치환 구간을 XML 글자 조각에 반영한다. 토큰은 구간이 시작된 조각에, 나머지 조각에서는 겹친 글자만 지운다."""
    new_text = [p.text for p in st.pieces]
    # 조각 안 편집을 뒤에서부터 — 앞 편집이 뒤 위치를 흔들지 않게 조각별 (시작, 끝, 대체) 모음
    edits: dict[int, list[tuple[int, int, str]]] = {}
    for a, b, s in spans:
        owners = [st.owner[i] for i in range(a, b) if st.owner[i][0] >= 0]
        if not owners:
            continue
        first_piece = owners[0][0]
        by_piece: dict[int, list[int]] = {}
        for pi, k in owners:
            by_piece.setdefault(pi, []).append(k)
        for pi, ks in by_piece.items():
            edits.setdefault(pi, []).append((min(ks), max(ks) + 1, s["token"] if pi == first_piece else ""))
    for pi, items in edits.items():
        t = new_text[pi]
        for ka, kb, rep in sorted(items, reverse=True):
            t = t[:ka] + rep + t[kb:]
        new_text[pi] = t
    out: list[str] = []
    cursor = 0
    for p, t in zip(st.pieces, new_text):
        out.append(xml[cursor:p.start])
        out.append(xml_escape(t) if t != p.raw_text else xml[p.start:p.end])
        cursor = p.end
    out.append(xml[cursor:])
    return "".join(out)


def mask_plain(text: str, surfaces: list) -> str:
    """평문 한 조각 마스킹 — plan 과 같은 규칙(텍스트 경로와 동일해야 한다)."""
    text = unicodedata.normalize("NFC", text)
    out: list[str] = []
    cursor = 0
    for a, b, s in plan(text, surfaces):
        out.append(text[cursor:a])
        out.append(s["token"])
        cursor = b
    out.append(text[cursor:])
    return "".join(out)


def fragments(xml: str) -> list[str]:
    """본문 밖 XML 의 글자 조각·속성값(이스케이프 해제) — mask_fragments 가 치환하는 단위와 같다."""
    out = [unescape(t) for t in re.split(r"<[^>]*>", xml) if t]
    out += [unescape(v[2][1:-1]) for v in ATTR_RE.findall(xml)]
    return out


def mask_fragments(xml: str, mask_str) -> str:
    """본문 밖 XML — 글자 조각과 속성값을 각각 `mask_str` 로 치환(조각을 넘는 매칭은 게이트가 잡는다)."""
    out: list[str] = []
    last = 0
    for m in TAG_RE.finditer(xml):
        if m.start() > last:
            out.append(xml_escape(mask_str(unescape(xml[last:m.start()]))))
        tag = m.group(0)
        if m.group(2) is not None and m.group(3):
            def attr(am: re.Match) -> str:
                quote = am.group(3)[0]
                value = unescape(am.group(3)[1:-1])
                masked = mask_str(value)
                if masked == value:
                    return am.group(0)
                return f"{am.group(1)}{am.group(2)}{quote}{xml_escape(masked).replace(quote, '&quot;' if quote == chr(34) else '&apos;')}{quote}"
            tag = tag[: m.start(3) - m.start()] + ATTR_RE.sub(attr, m.group(3)) + tag[m.end(3) - m.start():]
        out.append(tag)
        last = m.end()
    if last < len(xml):
        out.append(xml_escape(mask_str(unescape(xml[last:]))))
    return "".join(out)


T_BLOCK_RE = re.compile(r"<hp:t(?:\s[^>]*)?>.*?</hp:t>", re.S)


def entry_texts(name: str, data: bytes) -> list[str]:
    """잔존 게이트가 훑을 글자열들 — 치환 단위보다 **넓게** 본다(fail-closed).

    - 본문: 매칭용 스트림(문단 단위) + `<hp:t>` 밖 글자(필드 명령 등)를 태그 제거로 이은 것 + 속성값
    - 그 밖 XML: 조각·속성값 각각 + 태그를 지우고 **이어 붙인** 글자 — `현대<x/>엘리베이터` 처럼 태그로 쪼개진 기밀은
      조각 단위 치환이 못 바꾸는데, 이어 붙여 보면 잡힌다. 이웃 요소끼리 우연히 이어져 거짓 양성이 날 수 있지만
      기밀 게이트는 놓치는 쪽보다 멈추는 쪽이 낫다.
    - 텍스트(.txt): 통째로
    """
    try:
        s = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            s = data.decode("utf-16")
        except UnicodeDecodeError:
            return []
    attrs = [unescape(v[2][1:-1]) for v in ATTR_RE.findall(s)]
    if SECTION_RE.match(name):
        outside = unescape(re.sub(r"<[^>]*>", "", T_BLOCK_RE.sub("\n", s)))
        return [build_stream(s).text, outside] + attrs
    if name.lower().endswith(".txt"):
        return [s]
    return fragments(s) + [unescape(re.sub(r"<[^>]*>", "", s))]


def extract_text(sections: list[str]) -> str:
    """AI 에 넘길 평문 — 본문 스트림을 문단 단위로. 빈 줄은 하나로 접는다."""
    joined = "\n".join(build_stream(x).text for x in sections)
    return re.sub(r"\n{3,}", "\n\n", joined).strip() + "\n"


def read_zip(data: bytes) -> list[tuple[zipfile.ZipInfo, bytes]]:
    """전 엔트리를 메모리로. 압축 폭탄·위조 CD·경로 탐색·DOCTYPE 는 UnsafeArchiveError(#27).

    DOCTYPE 거부는 파서 보호만이 아니다 — 이 경로는 정규식으로 글자를 찾으므로, DTD 엔티티(`&x;`)에 숨긴
    기밀은 마스킹도 잔존 게이트도 못 본다. 정상 HWPX 에 없는 형태라 통째로 거부한다.
    """
    with open_zip(data) as zf:
        budget = Budget()
        return [(info, read_entry(zf, info, budget)) for info in zf.infolist()]


def write_zip(entries: list[tuple[zipfile.ZipInfo, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for info, data in entries:
            zf.writestr(info, data, compress_type=zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def is_hwpx(data: bytes) -> bool:
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        # 엔트리 수를 목록 전에 세고, mimetype 은 앞부분만 푼다 — 판별이 자원을 쓰지 않게(#27)
        with open_zip(data) as zf:
            names = set(zf.namelist())
            mt = read_prefix(zf, "mimetype").strip() if "mimetype" in names else b""
    except zipfile.BadZipFile:
        return False
    return mt in (b"application/hwp+zip", b"application/haansofthwp+zip") or "Contents/section0.xml" in names
