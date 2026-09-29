#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""brain-fixture 한글 문서 렌더러 — HWPX·HWP 5·HWP 3 서명 파일을 원장에서 결정론 조립한다(#31).

외부 저장소·다른 팩의 파일(한글 픽스처·itda-doc:hwpx 생성 엔진)에 기대지 않는다. 배포본 스킬이
다른 팩 테스트 픽스처를 복사하면 그 팩이 없는 설치에서 깨지고, 그 픽스처는 실제 공공 문서라
"가상 명칭만" 원칙과도 맞지 않는다. 그래서 필요한 최소 구조를 여기서 직접 쓴다.

- HWPX  : ZIP(OCF) 패키지 — mimetype(무압축·첫 항목)·version.xml·container.xml·content.hpf·
          header.xml·section0.xml. 타임스탬프·생성 OS 를 고정해 같은 원장이면 같은 바이트.
- HWP 5 : OLE 복합 문서(CFB v3) — FileHeader(256B)·DocInfo·BodyText/Section0(raw deflate 레코드).
          배포용(distribution=true)이면 속성 0x04 를 켜고 본문 자리(ViewText/Section0)는 의사난수로 채운다
          — 실제 배포용 문서처럼 BodyText 가 없어, 어떤 도구로도 본문을 꺼낼 수 없다.
- HWP 3 : `HWP Document File V3.00` 머리 + 고정 시드 의사난수. 본문 없는 서명 흉내.

한컴오피스에서 열리는지는 보장하지 않는다(최소 DocInfo·header 만 쓴다). 이 파일들의 계약은
**판독기(itda-doc:hwpx 리더)가 무엇으로 판정하는가**이고, 그 판정은 tests/test_hangul.py 가 잰다.
표(table 블록)는 셀을 ' | ' 로 이은 문단으로 렌더한다(v1 — 한글 표 구조는 비대상).
"""
from __future__ import annotations

import hashlib
import random
import struct
import zipfile
import zlib
from pathlib import Path

HWP_SIGNATURE = b"HWP Document File"
HWP5_VERSION = 0x05000304  # 5.0.3.4
HWP5_FLAG_COMPRESSED = 0x01
HWP5_FLAG_DISTRIBUTION = 0x04
HWP3_HEAD = b"HWP Document File V3.00 \x1a\x01\x02\x03\x04\x05"

# HWP 5 레코드 태그(한/글 문서 파일 형식 5.0 — HWPTAG_BEGIN=0x10)
TAG_DOCUMENT_PROPERTIES = 0x10
TAG_ID_MAPPINGS = 0x11
TAG_PARA_HEADER = 0x42
TAG_PARA_TEXT = 0x43
TAG_PARA_CHAR_SHAPE = 0x44

CELL_SEP = " | "


# ---------------------------------------------------------------- 공통

def paragraphs(doc: dict) -> list[str]:
    """원장 문서(title+blocks) → 문단 문자열 목록. 표 행은 셀을 CELL_SEP 로 잇는다."""
    from bf_common import _cell_text  # 셀 표기(정수형 float → 정수) 규칙을 공유한다

    out = [doc["title"]]
    for blk in doc["blocks"]:
        if blk["kind"] in ("p", "h"):
            out.append(blk["text"])
        elif blk["kind"] == "table":
            for row in blk["rows"]:
                out.append(CELL_SEP.join(_cell_text(c) for c in row))
    # 문단 안 줄바꿈은 문단 경계로 나눈다(HWP 문단 텍스트에 개행 문자를 넣지 않는다)
    flat: list[str] = []
    for p in out:
        flat.extend(p.split("\n"))
    return flat


def _noise(seed_src: str, n: int) -> bytes:
    seed = int.from_bytes(hashlib.sha256(seed_src.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    return bytes(rng.randrange(256) for _ in range(n))


def _deflate_raw(data: bytes) -> bytes:
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


# ---------------------------------------------------------------- HWP 3

def render_hwp3(path: Path, doc: dict) -> None:
    path.write_bytes(HWP3_HEAD + _noise("hwp3|" + doc["path"], 480))


# ---------------------------------------------------------------- HWP 5

def _record(tag: int, level: int, payload: bytes) -> bytes:
    size = len(payload)
    if size < 0xFFF:
        return struct.pack("<I", tag | (level << 10) | (size << 20)) + payload
    return struct.pack("<II", tag | (level << 10) | (0xFFF << 20), size) + payload


def _section_stream(paras: list[str]) -> bytes:
    out = bytearray()
    for i, text in enumerate(paras):
        body = text.encode("utf-16-le") + struct.pack("<H", 0x000D)
        nchars = len(body) // 2
        if i == len(paras) - 1:
            nchars |= 0x80000000  # 목록의 마지막 문단 표시
        # nChars·controlMask·paraShapeId·styleId·divideSort·charShapeCount·rangeTag·lineAlign·instanceId
        header = struct.pack("<IIHBBHHHI", nchars, 0, 0, 0, 0, 1, 0, 0, 0)
        out += _record(TAG_PARA_HEADER, 0, header)
        out += _record(TAG_PARA_TEXT, 1, body)
        out += _record(TAG_PARA_CHAR_SHAPE, 1, struct.pack("<II", 0, 0))
    return bytes(out)


def _docinfo_stream() -> bytes:
    # 구역 1개·시작 번호 6종 1·캐럿 위치 0 / 아이디 매핑 개수 18종 0 — 판독기가 요구하는 최소
    props = struct.pack("<H6HIII", 1, 1, 1, 1, 1, 1, 1, 0, 0, 0)
    return _record(TAG_DOCUMENT_PROPERTIES, 0, props) + _record(TAG_ID_MAPPINGS, 0, b"\x00" * 72)


def render_hwp5(path: Path, doc: dict) -> None:
    distribution = bool(doc.get("distribution"))
    flags = HWP5_FLAG_COMPRESSED | (HWP5_FLAG_DISTRIBUTION if distribution else 0)
    file_header = HWP_SIGNATURE.ljust(32, b"\x00") + struct.pack("<II", HWP5_VERSION, flags)
    file_header = file_header.ljust(256, b"\x00")
    streams: dict[tuple[str, ...], bytes] = {
        ("FileHeader",): file_header,
        ("DocInfo",): _deflate_raw(_docinfo_stream()),
    }
    if distribution:
        # 실제 배포용 문서는 본문을 BodyText 가 아니라 ViewText 에 암호화해 둔다 — 여기선 복호화할
        # 원문이 없는 의사난수라, 판독기·대체 도구 어느 쪽도 본문을 꺼낼 수 없다.
        body = _section_stream(paragraphs(doc))
        streams[("ViewText", "Section0")] = _noise("hwp5-dist|" + doc["path"], len(body) + 256)
    else:
        streams[("BodyText", "Section0")] = _deflate_raw(_section_stream(paragraphs(doc)))
    path.write_bytes(build_cfb(streams))


# ---------------------------------------------------------------- CFB(OLE 복합 문서) v3 작성기

_SECTOR = 512
_MINI = 64
_MINI_CUTOFF = 4096
_FREE = 0xFFFFFFFF
_END = 0xFFFFFFFE
_FATSECT = 0xFFFFFFFD
_NOSTREAM = 0xFFFFFFFF
_CFB_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"


class _Entry:
    def __init__(self, name: str, kind: int, data: bytes = b""):
        self.name = name
        self.kind = kind  # 1 storage · 2 stream · 5 root
        self.data = data
        self.children: list[_Entry] = []
        self.sid = 0
        self.left = self.right = self.child = _NOSTREAM
        self.start = _END
        self.size = 0


def _cfb_key(e: "_Entry"):
    # CFB 형제 정렬: 이름 길이 → 대문자 비교
    return (len(e.name), e.name.upper())


def _balanced(nodes: list["_Entry"]) -> int:
    if not nodes:
        return _NOSTREAM
    mid = len(nodes) // 2
    root = nodes[mid]
    root.left = _balanced(nodes[:mid])
    root.right = _balanced(nodes[mid + 1 :])
    return root.sid


def _chain(fat: list[int], start: int, count: int) -> None:
    for i in range(count):
        fat[start + i] = start + i + 1 if i < count - 1 else _END


def build_cfb(streams: dict[tuple[str, ...], bytes]) -> bytes:
    """경로 튜플 → 바이트 사전으로 OLE 복합 문서를 만든다(결정론 — 시각·CLSID 0)."""
    root = _Entry("Root Entry", 5)
    for parts, data in sorted(streams.items()):
        node = root
        for storage in parts[:-1]:
            found = next((c for c in node.children if c.name == storage and c.kind == 1), None)
            if found is None:
                found = _Entry(storage, 1)
                node.children.append(found)
            node = found
        node.children.append(_Entry(parts[-1], 2, data))

    entries: list[_Entry] = []

    def _number(e: _Entry) -> None:
        e.sid = len(entries)
        entries.append(e)
        for c in e.children:
            _number(c)

    _number(root)
    for e in entries:
        if e.children:
            e.child = _balanced(sorted(e.children, key=_cfb_key))

    small = [e for e in entries if e.kind == 2 and len(e.data) < _MINI_CUTOFF]
    big = [e for e in entries if e.kind == 2 and len(e.data) >= _MINI_CUTOFF]

    # 미니 스트림(64B 단위) 조립
    mini = bytearray()
    minifat: list[int] = []
    for e in small:
        e.size = len(e.data)
        n = -(-len(e.data) // _MINI)
        if n == 0:
            e.start = _END
            continue
        e.start = len(minifat)
        minifat.extend(range(e.start + 1, e.start + n))
        minifat.append(_END)
        mini += e.data.ljust(n * _MINI, b"\x00")

    def _sectors(nbytes: int) -> int:
        return -(-nbytes // _SECTOR)

    n_dir = _sectors(len(entries) * 128)
    n_minifat = _sectors(len(minifat) * 4)
    n_mini = _sectors(len(mini))
    n_big = sum(_sectors(len(e.data)) for e in big)
    n_fat = 1
    while n_fat * (_SECTOR // 4) < n_fat + n_dir + n_minifat + n_mini + n_big:
        n_fat += 1
    if n_fat > 109:
        raise ValueError("CFB: 문서가 너무 큽니다(FAT 109 섹터 초과)")

    total = n_fat + n_dir + n_minifat + n_mini + n_big
    fat = [_FREE] * (n_fat * (_SECTOR // 4))
    for i in range(n_fat):
        fat[i] = _FATSECT
    cur = n_fat
    dir_start = cur
    _chain(fat, cur, n_dir)
    cur += n_dir
    minifat_start = cur if n_minifat else _END
    _chain(fat, cur, n_minifat)
    cur += n_minifat
    if n_mini:
        root.start = cur
        root.size = len(mini)
        _chain(fat, cur, n_mini)
        cur += n_mini
    for e in big:
        n = _sectors(len(e.data))
        e.start, e.size = cur, len(e.data)
        _chain(fat, cur, n)
        cur += n
    assert cur == total

    header = bytearray(_SECTOR)
    header[0:8] = _CFB_MAGIC
    struct.pack_into("<HHHHH", header, 24, 0x003E, 0x0003, 0xFFFE, 9, 6)
    struct.pack_into("<IIII", header, 40, 0, n_fat, dir_start, 0)
    struct.pack_into("<IIIII", header, 56, _MINI_CUTOFF, minifat_start, n_minifat, _END, 0)
    difat = list(range(n_fat)) + [_FREE] * (109 - n_fat)
    struct.pack_into("<109I", header, 76, *difat)

    body = bytearray()
    body += struct.pack(f"<{len(fat)}I", *fat)
    dir_bytes = bytearray()
    for e in entries:
        ent = bytearray(128)
        name = e.name.encode("utf-16-le")
        ent[0 : len(name)] = name
        struct.pack_into("<HBB", ent, 64, len(name) + 2, e.kind, 1)  # 전부 검정 노드
        struct.pack_into("<III", ent, 68, e.left, e.right, e.child)
        struct.pack_into("<II", ent, 116, e.start if e.kind != 1 else 0, e.size)
        dir_bytes += ent
    while len(dir_bytes) < n_dir * _SECTOR:  # 빈 디렉토리 항목
        ent = bytearray(128)
        struct.pack_into("<III", ent, 68, _NOSTREAM, _NOSTREAM, _NOSTREAM)
        dir_bytes += ent
    body += dir_bytes
    if n_minifat:
        mf = minifat + [_FREE] * (n_minifat * (_SECTOR // 4) - len(minifat))
        body += struct.pack(f"<{len(mf)}I", *mf)
    body += bytes(mini).ljust(n_mini * _SECTOR, b"\x00")
    for e in big:
        body += e.data.ljust(_sectors(len(e.data)) * _SECTOR, b"\x00")
    return bytes(header) + bytes(body)


# ---------------------------------------------------------------- HWPX

_NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_NS_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
_XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _hwpx_parts(doc: dict) -> list[tuple[str, bytes]]:
    paras = "".join(
        f'<hp:p id="{i}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="0"><hp:t>{_esc(text)}</hp:t></hp:run></hp:p>'
        for i, text in enumerate(paragraphs(doc))
    )
    section = f'{_XML_DECL}<hs:sec xmlns:hs="{_NS_HS}" xmlns:hp="{_NS_HP}">{paras}</hs:sec>'
    header = (
        f'{_XML_DECL}<hh:head xmlns:hh="{_NS_HH}" version="1.4" secCnt="1">'
        '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>'
        "<hh:refList/></hh:head>"
    )
    title = _esc(doc["title"])
    content = (
        f'{_XML_DECL}<opf:package xmlns:opf="http://www.idpf.org/2007/opf/" version="" unique-identifier="" id="">'
        f"<opf:metadata><opf:title>{title}</opf:title><opf:language>ko</opf:language></opf:metadata>"
        '<opf:manifest><opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
        '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="header" linear="yes"/><opf:itemref idref="section0" linear="yes"/></opf:spine>'
        "</opf:package>"
    )
    container = (
        f'{_XML_DECL}<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<ocf:rootfiles><ocf:rootfile full-path="Contents/content.hpf" media-type="application/hwpml-package+xml"/>'
        "</ocf:rootfiles></ocf:container>"
    )
    version = (
        f'{_XML_DECL}<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" '
        'tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="0" buildNumber="1" xmlVersion="1.4"/>'
    )
    return [
        ("mimetype", b"application/hwp+zip"),
        ("version.xml", version.encode("utf-8")),
        ("META-INF/container.xml", container.encode("utf-8")),
        ("Contents/content.hpf", content.encode("utf-8")),
        ("Contents/header.xml", header.encode("utf-8")),
        ("Contents/section0.xml", section.encode("utf-8")),
    ]


def render_hwpx(path: Path, doc: dict) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in _hwpx_parts(doc):
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.create_system = 0  # 생성 OS 바이트 고정(플랫폼 무관 동일 바이트)
            zi.external_attr = 0
            zi.compress_type = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
            zf.writestr(zi, data, compresslevel=9 if name != "mimetype" else None)
