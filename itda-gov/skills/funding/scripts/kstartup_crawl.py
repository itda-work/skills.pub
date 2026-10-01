#!/usr/bin/env python3
# Portions derived from ir-search (https://github.com/djfksjd/ir-search, MIT)
# 개작 요지: (1) 요청은 itda-hyve 가 보낸다 — 이 파일은 저장된 HTML 판독만 한다(itda-work/skills#45).
# (2) 레코드에 source/id/apply_start/apply_end 별칭을 부여해 타 소스와 교차 비교한다.
# (3) 목록 전량 대조는 listing.py, 상세·첨부 계획은 detailing.py 가 소유한다.
# 라이선스 전문·차용 파일 목록은 ../references/third-party.md 참조.
"""K-Startup 판독기 — 목록 쪽·상세 본문·첨부 링크 (네트워크 없음).

첨부 계약: K-Startup 다운로드 경로 /afile/... 은 robots.txt(2026-07-23·2026-09-30 확인)의
"Disallow: /afile*/" 에 걸린다 — 첨부는 받지 않고 링크만 기록한다(skipped_robots).
따라서 첨부가 있는 공고는 본문 v2 해시 + attachments_complete:false + partial(2)이 정상 동작이다.
"""
import html as htmllib
import re

BASE = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"
DETAIL_URL = BASE + "?schM=view&pbancSn={sn}"
ALLOWED_DOMAINS = ("=www.k-startup.go.kr", "=k-startup.go.kr")


def norm_date(s):
    """Normalize date-ish strings to YYYY-MM-DD; return input if not parseable."""
    s = re.sub(r"\s+", " ", htmllib.unescape(s or "")).strip()
    m = re.search(r"(\d{4})[.\-/\s]+(\d{1,2})[.\-/\s]+(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)  # 26.07.10
    if m:
        return f"20{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s


def parse_list(html):
    """Extract announcement records from a list page.

    Only the main list (id=bizPbancList) is parsed — the carousel at the top
    repeats featured announcements, so it is discarded. The real list holds
    15 items per page.
    """
    items = []
    parts = html.split('id="bizPbancList"', 1)
    if len(parts) < 2:
        return items
    body = parts[1]
    for blk in re.split(r'<li class="notice">|<li >|<li>', body)[1:]:
        m = re.search(r"go_view\((\d+)\)", blk)
        if not m:
            continue

        def g(pat):
            mm = re.search(pat, blk)
            return re.sub(r"\s+", " ", mm.group(1)).strip() if mm else ""

        lists = [
            re.sub(r"\s+", " ", x).strip()
            for x in re.findall(r'<span class="list"><i[^>]*></i>([^<]+)</span>', blk)
        ]

        def pick(prefix):
            for x in lists:
                if x.startswith(prefix):
                    return x.replace(prefix, "").strip()
            return ""

        items.append(
            {
                "pbancSn": m.group(1),
                "category": htmllib.unescape(
                    g(r'<span class="flag type\d+">\s*([^<]+)</span>')
                ),
                "dday": g(r'<span class="flag day">\s*([^<]+)</span>'),
                "title": htmllib.unescape(g(r'<p class="tit">\s*([^<]+)')),
                "program": htmllib.unescape(lists[0]) if lists else "",
                "org": htmllib.unescape(lists[1]) if len(lists) > 1 else "",
                "start": norm_date(pick("시작일자")),
                "deadline": norm_date(pick("마감일자")),
                "agency_type": g(r'<span class="flag_agency">\s*([^<]+)</span>'),
                "url": DETAIL_URL.format(sn=m.group(1)),
            }
        )
    return items


def annotate(rec):
    """K-Startup 레코드에 교차 소스 비교용 별칭을 붙인다(원본 키는 보존).

    survey_diff 는 레코드를 (source, id) 로 키잉하고 apply_start/apply_end 를
    비교 필드로 쓴다. pbancSn/start/deadline 만 갖는 K-Startup 레코드에 별칭을
    부여해 `list all` 의 단일 jsonl 안에서 타 소스와 같은 규약으로 다뤄지게 한다.
    """
    rec.setdefault("source", "kstartup")
    rec.setdefault("id", str(rec.get("pbancSn", "")))
    rec.setdefault("apply_start", rec.get("start", ""))
    rec.setdefault("apply_end", rec.get("deadline", ""))
    return rec


def strip_html(text):
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", text)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = htmllib.unescape(text)
    return re.sub(r"\n\s*\n+", "\n", text)


# ---- 첨부 계약 (2026-07-23 상세 페이지 2건 실호출로 확인) ----------------------
#
# 첨부는 board_file 블록의 <li class="clear"> 안에
#   <a class="file_bg" title="[첨부파일] NAME">NAME</a>
#   <a href="/afile/fileDownload/<KEY>" class="btn_down">다운로드</a>
# 쌍으로 나온다. 다운로드 경로 /afile/... 은 robots.txt(2026-07-23 확인)의
# "Disallow: /afile*/" 에 걸린다 — 따라서 K-Startup 첨부는 **다운로드하지 않고
# 링크만 기록**한다(download_status "skipped_robots", bizinfo /uploads/와 동일
# 패턴). 그 결과 첨부가 있는 공고는 hash v3에 도달할 수 없고, 본문 v2 해시 +
# attachments_complete:false + exit 2(partial)가 정상 동작이다.
#
# robots.txt `User-agent: *` 블록 **전사**(2026-09-30 판독, 원문 그대로의 접두·와일드카드 규칙). 3.0.0 은 이
# 상수를 첨부뿐 아니라 **상세 대상 URL** 의 robots 게이트로도 쓰므로 부분집합이면 안 된다(M8). `Allow: /` 는
# 모든 Disallow 보다 짧아 효과가 없다. 목록 경로 `/web/contents/bizpbanc-ongoing.do` 는 루트 규칙
# `/bizpbanc-ongoing.do` 와 접두가 달라 걸리지 않는다 — 글자 그대로의 접두 규칙을 따른다(사용자 결정 2026-09-30,
# references/sources.md).
KSTARTUP_ROBOTS_DISALLOWED = (
    "/cubersc*/", "/cubedata*/", "/afile*/", "/html*/", "/jsp*/", "/testjsp*/", "/eng*/",
    "/webFSBIPBANC.do", "/webCMRCZN.do", "/webRND.do", "/webFC_SP_NR.do", "/webMNT_CNS.do",
    "/webENT_NET.do", "/webBUSI_INTR_VIEW.do", "/webMNPW.do", "/webGLOBAL.do",
    "/bizpbanc-ongoing.do", "/bizpbanc-deadline.do", "/webNOTICE_MATR.do", "/webKSTARTUP_ISSE_TRD.do",
    "/webCARD_NEWS.do", "/startupnews.do", "/webFND_GUIDE.do", "/webFND_SCS_CASE.do",
    "/webFND_STATS_RSCH_DATA.do", "/webACTSUPT_LOCAL_FAQ.do", "/webACTSUPT_GLBL_FAQ.do",
    "/webACTSUPT_EDU_VIDEO.do", "/webRFRR.do", "/webFAQ.do", "/webNMMN.do", "/webFBMN.do",
    "/oidc/",
)

# 첨부 다운로드 허용 호스트 — 정확한 호스트만('=' 접두). 페이지 크롤링의
# 서브도메인 와일드카드(ALLOWED_DOMAINS)와 달리 미확정 서브도메인을 배제한다.
KSTARTUP_ATTACH_HOSTS = ("=www.k-startup.go.kr", "=k-startup.go.kr")

# 본문 시작/끝 마커 — content_wrap ~ footer (실측 2026-07-23)
KSTARTUP_START_MARKERS = (r'<div[^>]+class="[^"]*content_wrap[^"]*"',)
KSTARTUP_END_MARKERS = (r'<div[^>]+class="[^"]*footer_area', r'<footer\b',
                        r'<div[^>]+id="footer"')


def extract_body(h):
    """시작 마커 ~ 첫 끝 마커(없으면 문서 끝) 구간의 텍스트. 마커 미발견 시 전체 폴백."""
    sm = None
    for p in KSTARTUP_START_MARKERS:
        sm = re.search(p, h)
        if sm:
            break
    seg = h[sm.start():] if sm else h
    ends = [m.start() for p in KSTARTUP_END_MARKERS for m in [re.search(p, seg)] if m]
    if ends:
        seg = seg[:min(ends)]
    return strip_html(seg)


def parse_attachments(h):
    """상세 페이지의 첨부 (filename, url) 목록. <li class="clear"> 세그먼트마다
    file_bg 파일명과 /afile/fileDownload/ 링크를 짝짓는다 (실측 2026-07-23)."""
    out = []
    seen_urls = set()
    for blk in re.split(r'<li class="clear">', h)[1:]:
        name = re.search(r'class="file_bg"[^>]*>\s*([^<]+?)\s*</a>', blk)
        href = re.search(r'href="(/afile/fileDownload/[^"]+)"', blk)
        if not href:
            continue
        url = "https://www.k-startup.go.kr" + htmllib.unescape(href.group(1))
        if url in seen_urls:
            continue
        seen_urls.add(url)
        out.append({
            "url": url,
            "filename": htmllib.unescape(name.group(1)) if name else
            href.group(1).rsplit("/", 1)[-1],
        })
    return out
