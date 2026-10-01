"""첨부 계약 공용 모듈 — robots·호스트 검사, 본문 해시, 받은 파일 검사 (네트워크 없음).

첨부는 itda-hyve 가 받는다(itda-work/skills#45, 규칙 ``cowork-network-via-hyve``). 이 모듈은
**요청 전**(계획 단계)에 URL 을 거르고, **받은 뒤** 저장 파일이 진짜 문서인지 검사한다.

요청 전 계약:
  - https + 정확한 호스트(`ATTACH_HOSTS` — '=' 접두는 서브도메인 배제)만 계획에 넣는다.
  - robots.txt 불허 경로는 요청하지 않고 링크만 남긴다(download_status "skipped_robots").
    퍼센트 인코딩 위장·와일드카드·끝 앵커까지 판정한다(`robots_allowed`).
  - 호출은 ``follow_redirects:false`` 로 보낸다 — 3xx 는 따라가지 않고 실패로 판정하므로
    허용 호스트 밖·robots 불허 경로로 요청이 나갈 수 없다.

받은 뒤 계약(`verify_attachment`):
  - 크기 > 0, 50MiB(itda-hyve 저장 상한) 미만, 첫 바이트가 ``<`` 가 아님(HTML 오류·차단 페이지),
    확장자와 매직 바이트가 맞음, 형식별 끝 검사(PDF ``%%EOF``·ZIP 중앙 디렉터리 끝·OLE 머리가 가리키는
    FAT 가 쓰는 마지막 섹터까지 파일 안에 있음). 모르는 확장자는 ``unverified_format``(v3 을 찍지 않는다).
    저장 파일에는 상태 코드·헤더가 없어서(``save_as`` 는 본문만 쓴다) 판정 근거는 이 바이트뿐이다.

hash 계약:
  HASH_VERSION_BODY(2)   = 본문 텍스트만의 sha256
  HASH_VERSION_ATTACH(3) = 본문 + 정렬된 첨부 sha256 (content_hash_of — sole-search 와 같은 산식)
  첨부가 **전부** 검사를 통과했을 때만 v3 을 찍는다. 하나라도 실패·robots 생략·계약 미확정·형식 미확인이면
  본문 v2 해시를 유지하고 attachments_complete:false + partial(exit 2) 로 표현한다.
"""
import hashlib
import os
import re
import struct
import urllib.parse

MAX_ATTACH_BYTES = 50 * 1024 * 1024  # itda-hyve save_as 절대 상한 50MiB — 이 크기면 잘렸다고 본다
HASH_VERSION_BODY = 2
HASH_VERSION_ATTACH = 3


def host_allowed(url, allowed_hosts):
    """https + 정확한 호스트/서브도메인 경계 검사 — endswith/부분 문자열 매칭은
    evilbizinfo.go.kr, userinfo(@)·쿼리스트링 위장에 뚫린다.

    허용 항목이 '='로 시작하면 **정확한 호스트 일치만** 허용한다(서브도메인
    매칭 배제). 예: '=www.kocca.kr'은 www.kocca.kr만 통과 — pms.kocca.kr 등
    계약 미확정 서브도메인으로의 리다이렉트가 요청되지 않는다."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parts.scheme != "https":
        return False
    host = (parts.hostname or "").lower().rstrip(".")
    for a in allowed_hosts:
        if a.startswith("="):
            if host == a[1:]:
                return True
        elif host == a or host.endswith("." + a):
            return True
    return False


def content_hash_of(body_text, attachment_hashes):
    """hash v3 산식 — sole-search sbiz_crawl.content_hash_of와 동일해야 한다."""
    payload = body_text + "\n" + "\n".join(sorted(attachment_hashes))
    return hashlib.sha256(payload.encode()).hexdigest()


# HTTP 200으로 위장한 소프트 차단(CAPTCHA·접근거부) 마커 — 상세 페이지 HTML을
# 정상 공고로 해시/병합하면 잘못된 UNCHANGED가 된다(Codex ir #1). sources·kstartup 공용.
_BLOCK_MARKERS = (
    "captcha", "recaptcha", "verify you are human", "are you a robot",
    "access denied", "forbidden", "접근이 제한", "접근이 차단", "비정상적인 접근",
    "자동입력 방지", "로봇이 아닙", "일시적으로 차단",
)


def looks_blocked(html):
    """앞부분에 차단/캡차 마커가 있으면 True — 200 위장 소프트 차단 감지."""
    low = (html or "")[:4000].lower()
    return any(m in low for m in _BLOCK_MARKERS)


def looks_like_html_error(first_bytes, filename):
    """마크업/HTML 확장자 첨부가 아닌데 본문이 `<`(태그)로 시작하면 True.
    PDF(%PDF-)·OLE(D0CF)·ZIP/HWPX(PK)·이미지 등 실제 문서 바이너리는 어느 것도
    '<'로 시작하지 않으므로, `<`로 시작하면 HTML/XML 오류·차단 페이지다. 이렇게
    하면 `<!doctype>`뿐 아니라 `<body>`·`<!--`·`<html`·BOM 선행까지 모두 잡힌다
    (Codex ir #1 후속). Content-Type 은 서버가 자주 오기재하고 저장 파일에는 없으므로 근거로 쓰지 않는다."""
    name = (filename or "").lower()
    if name.endswith((".html", ".htm", ".xhtml", ".xml", ".svg", ".xsl")):
        return False  # 마크업 첨부 자체는 정상
    head = first_bytes[:512]
    if head[:3] == b"\xef\xbb\xbf":  # UTF-8 BOM 선행 제거
        head = head[3:]
    return head.lstrip()[:1] == b"<"


_MAX_UNQUOTE = 5  # 반복 percent-디코딩 상한 (이중 인코딩 %2575… 커버)


def _robots_path_match(path, pattern):
    """robots 패턴 1건 매칭 — 접두 매칭 + 구글 확장 문법('*' 와일드카드,
    '$' 끝 앵커) 지원. KOCCA의 'Disallow:/*/FileDown.do' 같은 패턴용."""
    if "*" not in pattern and not pattern.endswith("$"):
        return path.startswith(pattern)
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in pattern)
    return re.match(regex + ("$" if anchored else ""), path) is not None


def robots_allowed(url, disallowed_prefixes):
    """robots.txt 불허 접두 경로 검사 — 매칭되면 다운로드 금지(링크만 수집).

    fail-closed: percent-인코딩 위장(/%75ploads/, 이중 인코딩 /%2575ploads/)을
    반복 unquote(최대 5회, 고정점 도달 시 중단)로 정규화하고, **원본과 모든
    디코딩 단계 + normpath 정규화 형태 중 하나라도** 불허 접두에 걸리면
    거부한다. 디코딩 불가/파싱 불가도 거부.

    매칭 대상은 path에 쿼리를 결합한 문자열(path?query)이다 — SMTECH의
    'Disallow: /...List.do?RECH_ANCM_ID=S20131' 같은 쿼리 포함 규칙도
    매칭된다. 인코딩 위장 후보 생성도 동일 결합 문자열 기준."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    target = parts.path + (("?" + parts.query) if parts.query else "")
    candidates = []
    cur = target
    for _ in range(_MAX_UNQUOTE + 1):
        # 잘못된 percent 인코딩(%ZZ, 뒤 2자리 non-hex, % 단독)은 unquote가 예외 없이
        # 원문 유지 → robots 우회 소지. **매 디코드 단계**에서 검사한다 — %25ZZ가
        # 1회 디코드되면 %ZZ가 되므로 루프 밖 1회 검사로는 못 잡는다(Codex ir #7 후속).
        if re.search(r"%(?![0-9A-Fa-f]{2})", cur):
            return False
        candidates.append(cur)
        try:
            # errors="strict": 기본값 "replace"는 %FF·%ZZ·절단 %E0%A4를 대체문자로
            # 삼켜 '디코딩 불가 → 거부' 경로를 죽인다(Codex ir #7). strict면 잘못된
            # 바이트가 예외 → fail-closed. 정상 UTF-8 인코딩 경로는 영향 없음.
            nxt = urllib.parse.unquote(cur, errors="strict")
        except (ValueError, UnicodeDecodeError):
            return False  # 디코딩 불가 — fail-closed
        if nxt == cur:
            break
        cur = nxt
    else:
        return False  # 상한 내 고정점 미도달(과도한 다중 인코딩) — fail-closed
    for c in list(candidates):
        # /a/../uploads 류 경로 정규화 형태도 함께 검사 (normpath는 path
        # 부분에만 적용 — 쿼리는 그대로 재결합).
        # POSIX normpath는 선행 '//'를 보존한다 — /%2Fuploads가 디코딩 후
        # //uploads로 남아 startswith(/uploads)를 피하므로, 선행 슬래시를
        # 단일화한 후보도 추가한다
        p_, sep, q_ = c.partition("?")
        n = os.path.normpath(p_) + sep + q_
        candidates.extend([n, re.sub(r"^/+", "/", c), re.sub(r"^/+", "/", n)])
    return not any(_robots_path_match(c, p)
                   for c in candidates for p in disallowed_prefixes)


# ---- 받은 첨부 파일 검사 ------------------------------------------------------

_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP = b"PK\x03\x04"
MAGIC = {
    "pdf": (b"%PDF-",),
    "hwp": (_OLE,), "doc": (_OLE,), "xls": (_OLE,), "ppt": (_OLE,),
    "hwpx": (_ZIP,), "docx": (_ZIP,), "xlsx": (_ZIP,), "pptx": (_ZIP,), "zip": (_ZIP,), "odt": (_ZIP,),
    "jpg": (b"\xff\xd8\xff",), "jpeg": (b"\xff\xd8\xff",), "png": (b"\x89PNG\r\n\x1a\n",),
    "gif": (b"GIF87a", b"GIF89a"),
}


def ext_of(filename):
    """파일 이름의 확장자(소문자, 점 없이). 확장자 글자만 허용한다 — 저장 이름에 그대로 쓰인다."""
    m = re.search(r"\.([A-Za-z0-9]{1,5})\s*$", filename or "")
    return m.group(1).lower() if m else "bin"


_FREESECT = 0xFFFFFFFF
_MAXREGSECT = 0xFFFFFFFA


def _ole_truncated(data):
    """OLE(CFB) 잘림 검사. 잘렸으면 사유, 멀쩡하면 "".

    512 배수 검사만으로는 버퍼 경계(512 배수)에서 끊긴 파일을 못 잡는다(m2). 머리의 섹터 크기·FAT 섹터
    위치(DIFAT)를 읽고, FAT 가 쓰고 있다고 적은 **마지막 섹터**까지 파일 안에 있어야 멀쩡하다고 본다.
    """
    size = len(data)
    if size < 512:
        return f"머리(512바이트)보다 짧다({size})"
    shift = struct.unpack_from("<H", data, 0x1E)[0]
    if shift not in (9, 12):
        return f"섹터 크기 표지가 이상하다(shift {shift})"
    ss = 1 << shift
    if size % ss:
        return f"크기 {size} 가 섹터 크기 {ss} 의 배수가 아니다"
    n_sectors = size // ss - 1  # 머리가 섹터 하나를 차지한다(v3 512, v4 4096)
    n_fat = struct.unpack_from("<I", data, 0x2C)[0]
    difat = [x for x in struct.unpack_from("<109I", data, 0x4C) if x != _FREESECT]
    nxt, n_difat = struct.unpack_from("<II", data, 0x44)
    per = ss // 4
    seen = 0
    while nxt < _MAXREGSECT and seen <= n_difat:  # FAT 섹터가 109개를 넘는 큰 파일
        if nxt >= n_sectors:
            return f"DIFAT 섹터 {nxt} 가 파일 밖이다"
        off = (nxt + 1) * ss
        chunk = struct.unpack_from(f"<{per}I", data, off)
        difat.extend(x for x in chunk[:-1] if x != _FREESECT)
        nxt, seen = chunk[-1], seen + 1
    if n_fat == 0 or len(difat) < n_fat:
        return f"FAT 섹터 목록이 모자란다({len(difat)}/{n_fat})"
    last_used = -1
    for k, fs in enumerate(difat[:n_fat]):
        if fs >= n_sectors:
            return f"FAT 섹터 {fs} 가 파일 밖이다(섹터 {n_sectors}개)"
        entries = struct.unpack_from(f"<{per}I", data, (fs + 1) * ss)
        base = k * per
        for i, v in enumerate(entries):
            if v != _FREESECT:
                last_used = max(last_used, base + i)
    if last_used >= n_sectors:
        return f"FAT 는 섹터 {last_used} 까지 쓰는데 파일에는 {n_sectors}개뿐이다"
    return ""


def verify_attachment(data, ext):
    """받은 첨부 바이트를 검사한다. 반환: (ok, reason, sha256, size).

    ok 는 True(검사 통과) · False(실패) · None(형식을 모름 — ``unverified_format``). True 일 때만 sha256 이 있다.

    - 빈 파일·50MiB 이상(itda-hyve 상한 — 잘렸다고 본다)·HTML 로 시작하는 파일은 실패.
    - 알려진 확장자는 매직 바이트가 맞아야 하고, 끝 검사를 통과해야 한다(잘린 파일).
    - 모르는 확장자(``bin``·``txt`` 등)는 잘림·오류 본문을 가를 근거가 없다 — 통과로 두지 않는다(m2).
    """
    size = len(data)
    head, tail = data[:512], data[-1024:]
    if size == 0:
        return False, "빈 파일", None, 0
    if size >= MAX_ATTACH_BYTES:
        return False, "too_large — itda-hyve 저장 상한(50MiB)에 닿아 잘렸을 수 있다", None, size
    if looks_like_html_error(head, f"x.{ext}"):
        return False, "soft_block_html — 첨부가 아닌 HTML 오류·차단 페이지", None, size
    magics = MAGIC.get(ext)
    if not magics:
        return None, f"unverified_format — .{ext} 는 형식 검사 규칙이 없어 잘림·오류 본문을 가를 수 없다", None, size
    if not any(head.startswith(m) for m in magics):
        return False, f"형식 불일치 — .{ext} 인데 파일 머리가 {head[:8].hex()}", None, size
    if ext == "pdf" and b"%%EOF" not in tail:
        return False, "잘린 PDF — 끝 표지(%%EOF)가 없다", None, size
    if magics[0] == _ZIP and b"PK\x05\x06" not in tail:
        return False, "잘린 ZIP 계열 — 중앙 디렉터리 끝이 없다", None, size
    if magics[0] == _OLE:
        why = _ole_truncated(data)
        if why:
            return False, f"잘린 OLE(HWP 등) — {why}", None, size
    if ext in ("jpg", "jpeg") and b"\xff\xd9" not in tail:
        return False, "잘린 JPEG — 끝 표지(FFD9)가 없다", None, size
    if ext == "png" and b"IEND" not in tail:
        return False, "잘린 PNG — IEND 가 없다", None, size
    if ext == "gif" and not data.rstrip(b"\0").endswith(b";"):
        return False, "잘린 GIF — 끝 표지(3B)가 없다", None, size
    return True, "", hashlib.sha256(data).hexdigest(), size
