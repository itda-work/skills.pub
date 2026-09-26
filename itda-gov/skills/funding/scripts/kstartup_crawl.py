#!/usr/bin/env python3
# Portions derived from ir-search (https://github.com/djfksjd/ir-search, MIT)
# 개작 요지: (1) 진입점을 survey_crawl.py 로 옮기고 이 파일은 모듈화 —
# cmd_list 를 collect_list() 로 분해해 sys.exit 대신 (records, run, code) 를
# 반환하게 했다(`list all` 에서 5종을 한 jsonl·한 매니페스트로 합치기 위함).
# (2) 레코드에 source/id/apply_start/apply_end 별칭을 부여해 타 소스 스키마와
# 교차 비교 가능하게 했다. (3) KO_DATA_API_KEY·[funding] 태그. 크롤 파싱·
# 첨부·차단(exit 3) 계약은 원본 그대로 유지한다.
# 라이선스 전문·차용 파일 목록은 ../references/third-party.md 참조.
"""K-Startup announcement crawler — funding 스킬 동봉 (survey_crawl.py 의 모듈).

Accesses only public announcement pages (currently-recruiting list).
No login, no private areas. A polite delay is applied between requests.
진입점은 survey_crawl.py 다 — 이 파일은 직접 실행하지 않는다:

  python3 survey_crawl.py list kstartup -o survey.jsonl
  python3 survey_crawl.py detail kstartup 178481 -o details/ \
      --download-dir attachments/ --merge-into survey.jsonl

첨부 계약: K-Startup 다운로드 경로 /afile/... 은 robots.txt(2026-07-23 확인)의
"Disallow: /afile*/" 에 걸린다 — 첨부는 다운로드하지 않고 링크만 기록한다
(skipped_robots). 따라서 첨부가 있는 공고는 본문 v2 해시 +
attachments_complete:false + partial(2)이 정상 동작이다.

Dependency: curl_cffi>=0.15 recommended (passes TLS-fingerprint checks).
Falls back to the standard urllib with an explicit stderr notice.

종료코드·매니페스트 계약은 ../references/cli-contract.md 가 정본이다.
"""
import html as htmllib
import json
import os
import re
import sys
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from run_manifest import _reject_dup_keys, make_run  # noqa: E402
import attach_download  # noqa: E402 — 첨부 다운로드 공용 모듈 (hash v2/v3)
import kstartup_api  # noqa: E402 — 공식 API(data.go.kr) 우선 경로, 키 없으면 크롤 폴백

BASE ="https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"
DETAIL_URL = BASE + "?schM=view&pbancSn={sn}"
DELAY = 0.3  # seconds between requests (politeness)
MIN_EXPECTED = 50  # K-Startup normally lists 250+ open announcements
ALLOWED_DOMAINS = ("k-startup.go.kr",)
MAX_REDIRECTS = 5
REDIRECT_STATUSES = (301, 302, 303, 307, 308)
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
)


def host_allowed(url, domains=None):
    """Exact-match domain check on the URL's real hostname (https only)."""
    import urllib.parse
    if domains is None:
        domains = ALLOWED_DOMAINS
    try:
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    if parts.scheme != "https":
        return False
    return any(host == d or host.endswith("." + d) for d in domains)


def follow_redirects(do_request, url, allowed_domains=None):
    """Manually follow redirects, validating EVERY hop against the allowlist.

    Automatic redirect following is disabled in the transports: K-Startup
    302-ing to an external host must never make us request (let alone save)
    the external response. Each Location is resolved to an absolute URL and
    must pass host_allowed (https + allowlist) BEFORE any request goes out;
    a violating hop raises, failing that request. Max MAX_REDIRECTS hops.

    do_request(url) -> (status, text, location-header-or-None).
    """
    import urllib.parse

    current = url
    for _ in range(MAX_REDIRECTS + 1):
        status, text, location = do_request(current)
        if status in REDIRECT_STATUSES and location:
            nxt = urllib.parse.urljoin(current, location)
            if not host_allowed(nxt, allowed_domains):
                raise RuntimeError(f"redirect to non-source url blocked: {nxt[:80]}")
            current = nxt
            continue
        if status in (401, 403):
            # 목록·상세 어디서든 차단 신호는 exit 3(수동 전환)로 통일 — partial 강등 금지
            raise attach_download.ManualEscalation(f"HTTP {status} — 차단 신호")
        return status, text
    raise RuntimeError(f"redirect chain exceeded {MAX_REDIRECTS} hops")


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


def make_fetcher():
    """Prefer curl_cffi (Safari TLS fingerprint); fall back to urllib.

    Both transports have automatic redirects DISABLED; the returned fetch
    follows redirects manually via follow_redirects(), so every hop is
    checked against ALLOWED_DOMAINS (https-only, k-startup.go.kr).
    """
    try:
        from curl_cffi import requests as cr

        sess = cr.Session(impersonate="safari")

        def do_request(url):
            r = sess.get(url, timeout=30, allow_redirects=False)
            return r.status_code, r.text, r.headers.get("location")

        backend = "curl_cffi"
    except ImportError:
        import urllib.error
        import urllib.request

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None  # surface 3xx as HTTPError instead of following

        opener = urllib.request.build_opener(_NoRedirect())

        def do_request(url):
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with opener.open(req, timeout=30) as resp:
                    return resp.status, resp.read().decode("utf-8", "replace"), None
            except urllib.error.HTTPError as e:
                if e.code in REDIRECT_STATUSES:
                    return e.code, "", e.headers.get("Location")
                if e.code in (401, 403):
                    return e.code, "", None  # 차단 상태 반환 → ManualEscalation 통일
                raise

        backend = "urllib"

    def fetch(url):
        return follow_redirects(do_request, url, ALLOWED_DOMAINS)

    return fetch, backend


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


def collect_list(max_pages=40, min_expected=MIN_EXPECTED, smoke=False):
    """모집중 공고를 수집해 (records, run, code) 를 반환한다 — 파일은 쓰지 않는다.

    code 는 exit 계약과 같다: 0 전수 / 2 partial / 3 차단(수동 전환).
    run 은 run_manifest.make_run() 엔트리다. jsonl·매니페스트 기록과 프로세스
    종료코드는 호출자(survey_crawl.py)가 소유한다 — `list all` 에서 5종을 하나의
    jsonl·하나의 매니페스트로 합치기 위한 분해다.
    """
    # ---- API 우선 (data.go.kr 키가 있으면) --------------------------------
    # 키가 있으면 공식 오픈API로 모집중 공고를 받는다. 건강한 수집량이면 그대로
    # 사용(0/2), API가 실패하거나 커버리지가 부족하면 아래 크롤로 폴백한다.
    # 크롤이 전수 커버리지의 보증 경로이고, API는 최적화다.
    key = kstartup_api.load_key()
    if key:
        api_min = 0 if smoke else min_expected
        try:
            records, total, pages, proven = kstartup_api.list_announcements(
                key, min_expected=max(1, api_min),
                max_pages=min(max_pages, kstartup_api.MAX_PAGES),
            )
        except attach_download.ManualEscalation as e:
            # 401/403·200 위장 차단 신호 — 우회하지 않고 수동 전환(3). 크롤 폴백 금지.
            print(
                f"MANUAL [funding] K-Startup API: {e} — 우회하지 않고 수동 확인",
                file=sys.stderr,
            )
            return [], make_run(
                "kstartup", "manual", 3, pages_fetched=0, collected=0,
                stop_reason="blocked", errors=[str(e)]), 3
        except kstartup_api.ApiError as e:
            # 키가 잘못됐거나(등록/쿼터)·커버리지 미증명·전송오류 → 크롤로 폴백.
            # 조용히 넘어가지 않고 사유를 고지한다(키는 마스킹됨).
            print(
                f"[funding] K-Startup 공식 API 미사용 ({e}) — 공개 페이지 크롤로 폴백",
                file=sys.stderr,
            )
        else:
            seen = {}
            for r in records:
                seen[str(r["pbancSn"])] = annotate(r)
            fail = api_min > 0 and len(seen) < api_min
            # A non-proven (newest-first heuristic) stop is recent-window
            # coverage, NOT exhaustive — honestly report it as partial/exit 2
            # (matches the exit-code contract; the crawl is the exhaustive
            # authority, and diff mode must not conclude GONE from a partial run).
            window = not proven
            partial = fail or window
            errors = []
            if fail:
                errors.append(
                    f"only {len(seen)} items via API (< {api_min} expected)")
            if window:
                errors.append(
                    "api-window: recent-window coverage via newest-first heuristic "
                    "(not a proven exhaustive scan); the crawl is the exhaustive "
                    "authority for late reopened announcements")
            print(
                f"[funding] K-Startup via official API: {len(seen)} announcements "
                f"(dataset 15125364"
                f"{'' if proven else ', recent-window — partial(2), crawl is exhaustive'})",
                file=sys.stderr,
            )
            return list(seen.values()), make_run(
                "kstartup", "partial" if partial else "ok", 2 if partial else 0,
                pages_fetched=pages, collected=len(seen), reported_total=total,
                stop_reason="api" if proven else "api-window",
                errors=errors), (2 if partial else 0)

    fetch, backend = make_fetcher()
    attach_download.notify_backend(backend)
    seen = {}
    page = 1
    pages_done = 0
    duplicates = 0
    errors = []  # short strings for run_manifest.json
    partial = False  # network/HTTP failure mid-crawl
    no_new_streak = 0
    last_page_had_new = False
    stop_reason = None
    while page <= max_pages:
        try:
            status, html = fetch(f"{BASE}?page={page}&schStr=&pbancEndYn=N")
        except attach_download.ManualEscalation as e:
            # 목록 401/403 차단 — partial(2)이 아니라 수동 전환(3). 우회 안내(curl_cffi)
            # 대신 차단 신호임을 명확히 한다(Codex ir #4).
            print(f"MANUAL [funding] page {page}: {e} — 우회하지 않고 수동 확인",
                  file=sys.stderr)
            return list(seen.values()), make_run(
                "kstartup", "manual", 3, pages_fetched=pages_done,
                collected=len(seen), stop_reason="blocked", errors=[str(e)]), 3
        except Exception as e:  # noqa: BLE001 — fail closed, keep partial data
            code = getattr(e, "code", None)  # urllib raises HTTPError (has .code)
            if code is not None:
                status, html = code, ""
            else:
                print(f"[funding] page {page}: network error: {e}", file=sys.stderr)
                errors.append(f"page {page}: network error: {e}")
                partial = True
                stop_reason = "network-error"
                break
        if status != 200:
            print(f"[funding] page {page}: HTTP {status} — stopping", file=sys.stderr)
            if status in (403, 412):
                print(
                    "[funding] looks blocked; pip install 'curl_cffi>=0.15' and retry.",
                    file=sys.stderr,
                )
            errors.append(f"page {page}: HTTP {status}")
            partial = True
            stop_reason = f"http-{status}"
            break
        if attach_download.looks_blocked(html):
            # 200 위장 CAPTCHA/접근거부 목록 — parse-failure(partial)로 오인하지 않고
            # 수동 전환(exit 3). 우회하지 않는다(Codex ir #1 후속).
            print(f"MANUAL [funding] page {page}: 200 위장 차단 감지 — 수동 확인",
                  file=sys.stderr)
            return list(seen.values()), make_run(
                "kstartup", "manual", 3, pages_fetched=pages_done,
                collected=len(seen), stop_reason="blocked",
                errors=["200 위장 차단(CAPTCHA/접근거부)"]), 3
        # A 200 response was received → the page WAS fetched; count it now,
        # before parsing, so a parse-failure page still shows up in coverage.
        pages_done = page
        items = parse_list(html)
        if page == 1 and not items:
            print(
                "ERROR: page 1 parsed 0 items — site structure may have changed",
                file=sys.stderr,
            )
            return [], make_run(
                "kstartup", "partial", 2, pages_fetched=pages_done, collected=0,
                stop_reason="parse-failure",
                errors=["page 1 parsed 0 items — site structure may have changed"],
            ), 2
        new = [i for i in items if i["pbancSn"] not in seen]
        duplicates += len(items) - len(new)
        for i in items:
            seen[i["pbancSn"]] = annotate(i)
        last_page_had_new = bool(new)
        print(
            f"[funding] page {page}: {len(items)} parsed, {len(new)} new, total {len(seen)}",
            file=sys.stderr,
        )
        if not items:
            stop_reason = "reached-total"  # past the last page: empty list
            break
        if not new:
            # past the last page usually only carousel items remain → 0 new,
            # but a single no-new page can also be a transient duplicate page.
            no_new_streak += 1
            if no_new_streak >= 2:
                stop_reason = "no-new-2pages"
                break
        else:
            no_new_streak = 0
        page += 1
        time.sleep(DELAY)
    if stop_reason is None:
        stop_reason = "page-cap"
    print(f"[funding] stop reason: {stop_reason} (pages: {pages_done})", file=sys.stderr)

    fail = False
    if partial:
        print(
            f"WARNING: partial — {pages_done} pages collected "
            f"({len(seen)} items saved, coverage INCOMPLETE)",
            file=sys.stderr,
        )
        fail = True
    if stop_reason == "page-cap" and last_page_had_new and not smoke:
        print(
            "WARNING: page cap reached — collection may be INCOMPLETE "
            f"(--max-pages {max_pages}, last page still had new items)",
            file=sys.stderr,
        )
        errors.append(
            f"page cap reached at p{max_pages} — collection may be INCOMPLETE"
        )
        fail = True
    # --smoke: 첫 페이지만 확인하는 저부하 CI 스모크. coverage(page-cap·min_expected)
    # 검증만 완화한다. page-1 파싱 0건·네트워크/HTTP 실패는 그대로 실패(exit 2) —
    # 이것이 계약 회귀를 잡는 canary다. 전수 크롤 계약은 바뀌지 않는다.
    floor = 0 if smoke else min_expected
    if floor > 0 and len(seen) < floor:
        print(
            f"WARNING: only {len(seen)} items collected (< {floor} minimum "
            "expected — K-Startup normally lists 250+ open announcements; "
            "genuinely low season? re-run with --min-expected 0 to accept)",
            file=sys.stderr,
        )
        errors.append(
            f"only {len(seen)} items collected (< {floor} minimum expected)"
        )
        fail = True
    return list(seen.values()), make_run(
        "kstartup",
        "partial" if fail else "ok",
        2 if fail else 0,
        pages_fetched=pages_done,
        collected=len(seen),
        stop_reason=stop_reason,
        errors=errors,
        duplicates=duplicates,
    ), (2 if fail else 0)


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
KSTARTUP_ROBOTS_DISALLOWED = ("/afile", "/cubersc", "/cubedata", "/html", "/jsp",
                              "/testjsp", "/eng", "/oidc")

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


def merge_detail(jsonl_path, sn, content_hash, attachments, complete, hash_version):
    """목록 jsonl의 해당 레코드(pbancSn)에 상세 검증 결과를 병합한다 (원자적 교체)."""
    tmp = jsonl_path + ".tmp"
    found = False
    with open(jsonl_path, encoding="utf-8") as src, \
            open(tmp, "w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            # 중복 키 fail-closed — survey_diff·run_manifest 와 동일 정책.
            r = json.loads(line, object_pairs_hook=_reject_dup_keys)
            if str(r.get("pbancSn")) == str(sn):
                r["content_hash"] = content_hash
                if content_hash is not None:
                    r["hash_version"] = hash_version
                else:
                    r.pop("hash_version", None)  # 해시 없음 = 산식 버전도 무의미
                r["attachments"] = attachments
                r["attachments_complete"] = complete
                found = True
            dst.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, jsonl_path)
    return found


def collect_detail(ids, outdir, download_dir=None, merge_into=None):
    """상세 텍스트 저장. download_dir / merge_into 지정 시 첨부 계약 적용:

    첨부 링크를 수집하고 본문 hash v2를 계산한다. K-Startup 첨부 다운로드
    경로(/afile/...)는 robots 불허라 다운로드하지 않고 링크만 남긴다
    (skipped_robots) — 전부 성공("ok")일 수 없으므로 첨부가 있으면 항상
    본문 v2 유지 + attachments_complete:false + partial(2)이다.

    반환: 종료코드 0(전건 성공) / 2(일부 실패·첨부 불완전) / 3(차단 신호).
    """
    fetch, backend = make_fetcher()
    attach_download.notify_backend(backend)
    os.makedirs(outdir, exist_ok=True)
    results = []  # (sn, "OK path" | "FAIL reason" | "PARTIAL reason")
    for sn in ids:
        # 상세 URL을 그대로 받은 경우 공고번호만 뽑아 쓴다(jsonl url 복붙 허용)
        m_url = re.search(r"pbancSn=(\d+)", str(sn))
        if m_url:
            sn = m_url.group(1)
        if not sn.isdigit():
            results.append((sn, "FAIL invalid announcement id"))
            print(f"[funding] invalid announcement id: {sn}", file=sys.stderr)
            continue
        try:
            status, html = fetch(DETAIL_URL.format(sn=sn))
            if status in (401, 403):
                # 1차 페이지 차단 신호 — 우회 금지·수동 전환(exit 3), partial 강등 금지
                results.append((sn, f"FAIL MANUAL HTTP {status} — 차단 신호"))
                print(f"MANUAL [funding] {sn}: HTTP {status} 차단 — 수동 확인",
                      file=sys.stderr)
                continue
            if status != 200:
                results.append((sn, f"FAIL HTTP {status}"))
                print(f"[funding] {sn}: HTTP {status}", file=sys.stderr)
                continue
            if attach_download.looks_blocked(html):
                # 200 위장 CAPTCHA/접근거부 — 정상 본문 아님, 해시/병합 금지(exit 3)
                results.append((sn, "FAIL MANUAL 200 위장 차단(CAPTCHA/접근거부)"))
                print(f"MANUAL [funding] {sn}: 200 위장 차단 감지 — 수동 확인",
                      file=sys.stderr)
                continue
            path = os.path.join(outdir, f"{sn}.txt")
            if download_dir or merge_into:
                attachments = parse_attachments(html)
                text = extract_body(html)
                import hashlib
                content_hash = hashlib.sha256(text.encode()).hexdigest()
                hash_version = attach_download.HASH_VERSION_BODY
                complete = not attachments
                manual = None
                if download_dir and attachments:
                    try:
                        attach_hashes = attach_download.process_attachments(
                            attachments, download_dir, DELAY,
                            KSTARTUP_ATTACH_HOSTS,
                            KSTARTUP_ROBOTS_DISALLOWED,
                            subdir=sn)  # 공고별 폴더 — 동명 첨부 충돌 방지
                    except attach_download.ManualEscalation as e:
                        # 401/403 — 우회 금지. 병합 없이 끊으면 재시도 파일의
                        # 과거 v3/complete:true가 잔존한다 — v2/incomplete를
                        # 병합하고 partial로 계속한다.
                        manual = e
                        for f in attachments:
                            if "download_status" not in f:
                                f["download_status"] = "failed"
                                f["download_reason"] = f"manual: {e}"
                        complete = False
                    except Exception as e:  # noqa: BLE001
                        # subdir_symlink_blocked 등 비-Manual 예외도 바깥 except로 새면
                        # merge를 건너뛰어 과거 v3/complete:true가 잔존한다(Codex ir #2).
                        # v2/incomplete를 반드시 병합하고 partial(exit 2).
                        for f in attachments:
                            if "download_status" not in f:
                                f["download_status"] = "failed"
                                f["download_reason"] = f"error: {e}"
                        complete = False
                        print(f"WARNING [funding] {sn}: 첨부 처리 오류 — "
                              f"v2/incomplete 병합 후 partial: {e}", file=sys.stderr)
                    else:
                        complete = all(f.get("download_status") == "ok"
                                       for f in attachments)
                        if complete:
                            content_hash = attach_download.content_hash_of(
                                text, attach_hashes)
                            hash_version = attach_download.HASH_VERSION_ATTACH
                        # else: 본문 v2 유지 — None으로 지우면 반복 실패 사이의
                        # 본문 변경이 diff에서 숨는다.
                with open(path, "w", encoding="utf-8") as f:
                    f.write(DETAIL_URL.format(sn=sn) + "\n")
                    f.write("CONTENT_HASH: " + content_hash + "\n")
                    f.write(f"HASH_VERSION: {hash_version}\n")
                    f.write("ATTACHMENTS: "
                            + json.dumps(attachments, ensure_ascii=False) + "\n\n")
                    f.write(text)
                if merge_into and not merge_detail(
                        merge_into, sn, content_hash, attachments, complete,
                        hash_version):
                    results.append((sn, f"FAIL merge: {sn} not in {merge_into}"))
                    print(f"[funding] WARNING: {sn} 레코드를 {merge_into}에서 "
                          "못 찾음", file=sys.stderr)
                    time.sleep(DELAY)
                    continue
                if manual is not None:
                    results.append((sn, f"FAIL MANUAL {manual}"))
                    print(f"MANUAL [funding] {sn}: 첨부 401/403 — 우회하지 않고 "
                          f"수동 확인으로 전환 (v2/incomplete 병합 완료): {manual}",
                          file=sys.stderr)
                elif not complete:
                    skipped = [f for f in attachments
                               if f.get("download_status") != "ok"]
                    results.append((sn, f"PARTIAL attachments incomplete "
                                        f"({len(skipped)})"))
                    print(f"WARNING [funding] {sn}: 첨부 {len(skipped)}건 "
                          "미다운로드(robots 불허 등) — hash v2 유지, "
                          "attachments_complete=false (partial)", file=sys.stderr)
                else:
                    results.append((sn, f"OK {path}"))
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(strip_html(html))
                results.append((sn, f"OK {path}"))
            print(f"[funding] {sn}: saved → {path}", file=sys.stderr)
        except attach_download.ManualEscalation as e:
            results.append((sn, f"FAIL MANUAL {e}"))
            print(f"MANUAL [funding] {sn}: 첨부 401/403 — 우회하지 않고 수동 "
                  f"확인으로 전환: {e}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 — record failure, keep going
            results.append((sn, f"FAIL {e}"))
            print(f"[funding] {sn}: error {e}", file=sys.stderr)
        time.sleep(DELAY)
    failures = [r for r in results if r[1].startswith(("FAIL", "PARTIAL"))]
    manuals = [r for r in results if r[1].startswith("FAIL MANUAL")]
    print(
        f"[funding] detail summary: {len(results) - len(failures)} ok, "
        f"{len(failures)} failed/partial",
        file=sys.stderr,
    )
    for sn, res in results:
        print(f"[funding]   {sn}: {res}", file=sys.stderr)
    if manuals:
        return 3  # 차단 신호(401/403) — 우회하지 않고 수동 확인으로 전환
    if failures:
        return 2
    return 0
