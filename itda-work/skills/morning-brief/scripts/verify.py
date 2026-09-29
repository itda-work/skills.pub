#!/usr/bin/env python3
"""itda-work morning-brief: verify.py — 정적 검증이 이 스킬의 판정 정본.

Cowork 샌드박스에는 playwright·chromium 이 없다(Phase 0 확정). 시각 축은
INCONCLUSIVE 로 보고하고, 아래 ①~⑨ 를 코드가 집행한다(itda-work/skills#38 구성).

  ① 상태(역할 준비) × 세 목록 — 오늘 일정 수·일정별 관련 메일 수·미회신 수가 candidates 와 같고,
     빈 목록·미연결은 한 줄로 말한다. 대량 발송 메일은 계정 소절·종류·발신자·제목 수와 합, 메일 계정이
     둘 이상이면 계정 배지(#41)
  ② 요약 — content 의 요약이 「일정과 무관한 미회신」 후보와 **1:1**(앵커 정확 일치, 빠짐·남음·중복 0),
     요약 문장이 페이지에 그대로 있다. 날씨·환율 절은 수집한 것만
  ③ seed 에 원본 필드(보낸 사람·제목·본문·주소·일정 제목)의 정규화 12자+ 부분문자열 0
  ④ 버튼 href 재파싱 — origin·path·query 키 정확 일치
  ⑤ 외부 자산 0
  ⑥ controls.buttons=false 인데 버튼이 있으면 RED
  ⑦ error·degraded 경고가 있으면 그 사실을 말하는 한 줄이 페이지에 있어야 함
  ⑧ 「출처」 절 — 원본 수 == 후보 앵커 수, 목록 행마다 실재하는 출처 링크
  ⑨ 샘플 모드 — sample 이면 상시 띠 + 전 앵커 provider 가 sample,
     아니면 띠 0 + sample 앵커 0 (상호 배타)

스타일(timeline·memo·desk·print, itda-work/skills#42)은 배치만 다르다 — 위 검사는 스타일과 무관하게 같다.
페이지가 아는 스타일 하나를 선언했는지(`--style` 을 주면 그 스타일인지)만 따로 본다.
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SCHEMA_VERSION = 2
BUTTON_ORIGIN = "https://claude.ai"
BUTTON_PATH = "/new"
BUTTON_QUERY_KEYS = {"q", "surface", "composer"}
SEED_NGRAM = 12
SAMPLE_TOKEN = "sample"
READY_STATES = ("ready", SAMPLE_TOKEN)
STATES = ("all-ready", "calendar-only", "email-only", "none")
STYLES = ("timeline", "memo", "desk", "print")

for _stream in (sys.stdout, sys.stderr):
    if _stream.encoding and _stream.encoding.lower() not in ("utf-8", "utf8"):
        try:
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover
            pass


# --------------------------------------------------------------------------
# 도우미
# --------------------------------------------------------------------------

def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def normalize_text(value: str) -> str:
    """NFC · casefold · 공백 축약."""
    text = unicodedata.normalize("NFC", value).casefold()
    return re.sub(r"\s+", " ", text).strip()


def events_of(candidates: dict) -> list[dict]:
    return [e for e in (candidates.get("calendar") or {}).get("today") or []
            if isinstance(e, dict)]


def unreplied_of(candidates: dict) -> list[dict]:
    return [m for m in (candidates.get("email") or {}).get("unreplied") or []
            if isinstance(m, dict)]


def iter_items(candidates: dict):
    """(group, item) — 일정, 일정의 관련 메일, 무관 미회신을 모두 훑는다."""
    for ev in events_of(candidates):
        yield "calendar", ev
        for mail in ev.get("related") or []:
            if isinstance(mail, dict):
                yield "email", mail
    for mail in unreplied_of(candidates):
        yield "email", mail


def source_entries(candidates: dict) -> list[dict]:
    """출처 번호의 정본 순서 — `render.source_entries` 와 같은 규칙(테스트가 대조)."""
    out: list[dict] = []
    seen: set[str] = set()
    ordered = [("calendar", e) for e in events_of(candidates)]
    ordered += [("email", m) for e in events_of(candidates)
                for m in e.get("related") or [] if isinstance(m, dict)]
    ordered += [("email", m) for m in unreplied_of(candidates)]
    for group, item in ordered:
        anchor = item.get("anchor")
        if not isinstance(anchor, dict) or not anchor:
            continue
        key = canon(anchor)
        if key in seen:
            continue
        seen.add(key)
        out.append({"group": group, "item": item, "key": key})
    return out


def strings_of(obj, skip_keys: tuple[str, ...] = ()) -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in skip_keys:
                continue
            out.extend(strings_of(value, skip_keys))
    elif isinstance(obj, list):
        for value in obj:
            out.extend(strings_of(value, skip_keys))
    elif isinstance(obj, str):
        out.append(obj)
    return out


def role_state(candidates: dict, role: str) -> str:
    return str(((candidates.get("roles") or {}).get(role) or {}).get("state") or "")


def multi_account(candidates: dict) -> bool:
    """메일 계정이 둘 이상인가 — `render.multi_account` 와 같은 규칙(샘플은 하나)."""
    if (candidates.get("controls") or {}).get("sample"):
        return False
    accounts = ((candidates.get("roles") or {}).get("email") or {}).get("accounts") or []
    return len([a for a in accounts if isinstance(a, dict)]) > 1


def expected_state(candidates: dict) -> str:
    cal = role_state(candidates, "calendar") in READY_STATES
    mail = role_state(candidates, "email") in READY_STATES
    if cal and mail:
        return "all-ready"
    if cal:
        return "calendar-only"
    if mail:
        return "email-only"
    return "none"


# --------------------------------------------------------------------------
# 검사
# --------------------------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, check: str, ok: bool, detail: str = "") -> None:
        self.checks.append({"check": check, "ok": bool(ok), "detail": detail})

    @property
    def failures(self) -> list[dict]:
        return [c for c in self.checks if not c["ok"]]


def check_structure(rep: Report, candidates: dict, page: str) -> None:
    want = expected_state(candidates)
    m = re.search(r'data-mb-state="([^"]*)"', page)
    got = m.group(1) if m else ""
    rep.add("①-state-matches-roles", got == want, f"html={got} roles={want}")

    events = events_of(candidates)
    n_events = page.count('data-mb-event="1"')
    n_related = page.count('data-mb-related="1"')
    n_items = page.count('data-mb-item="1"')
    want_related = sum(len(e.get("related") or []) for e in events)
    unreplied = unreplied_of(candidates)

    if want == "none":
        rep.add("①-none-two-sentences", 'data-mb-none="1"' in page, "data-mb-none 부재")
        rep.add("①-none-no-rows", n_events + n_related + n_items == 0,
                f"events={n_events} related={n_related} items={n_items}")
        return
    rep.add("①-dateline", 'data-mb-dateline="1"' in page, "")
    rep.add("①-schedule-part", 'data-mb-part="schedule"' in page, "오늘 일정 절 부재")
    rep.add("①-unreplied-part", 'data-mb-part="unreplied"' in page, "미회신 절 부재")

    cal_ready = role_state(candidates, "calendar") in READY_STATES
    mail_ready = role_state(candidates, "email") in READY_STATES
    rep.add("①-events-rendered", n_events == (len(events) if cal_ready else 0),
            f"html={n_events} candidates={len(events)}")
    if not cal_ready or not events:
        rep.add("①-schedule-empty-line", 'data-mb-empty="schedule"' in page,
                "빈 일정·미연결 한 줄 부재")
    related_expected = want_related if (want == "all-ready") else 0
    rep.add("①-related-rendered", n_related == related_expected,
            f"html={n_related} candidates={related_expected}")
    if want == "all-ready" and events and not want_related:
        rep.add("①-related-empty-line", 'data-mb-empty="related"' in page,
                "관련 메일 없음 한 줄 부재")
    rep.add("①-unreplied-rendered", n_items == (len(unreplied) if mail_ready else 0),
            f"html={n_items} candidates={len(unreplied)}")
    if not mail_ready or not unreplied:
        rep.add("①-unreplied-empty-line", 'data-mb-empty="unreplied"' in page,
                "빈 미회신·미연결 한 줄 부재")
    # 대량 발송 메일 절(itda-work/skills#40) — 메일이 준비됐고 센 수가 있으면 그 수 그대로 정확히 한 번, 아니면 없다.
    bulk = (candidates.get("email") or {}).get("bulk") or {}
    n_bulk = int(bulk.get("count") or 0)
    bulk_lines = re.findall(r'data-mb-bulk="(\d+)"', page)
    want_bulk = [str(n_bulk)] if (mail_ready and n_bulk) else []
    rep.add("①-bulk-line", bulk_lines == want_bulk, f"html={bulk_lines} candidates={want_bulk}")
    # 계정 소절(#41) — 계정 값의 합이 전체이고, 계정마다 종류 합·종류 묶음 합이 그 계정 수다. 메일 계정이 둘 이상이면
    # 계정마다 소절이 정확히 하나(그 수 그대로), 하나면 소절 머리가 없다.
    accounts = [a for a in bulk.get("accounts") or [] if isinstance(a, dict)] if want_bulk else []
    acct_counts = [int(a.get("count") or 0) for a in accounts]
    rep.add("①-bulk-accounts-sum", not want_bulk or sum(acct_counts) == n_bulk,
            f"계정 합={sum(acct_counts)} 전체={n_bulk}")
    for a in accounts:
        kinds_sum = sum(int(v or 0) for v in (a.get("kinds") or {}).values())
        groups_sum = sum(int(g.get("count") or 0) for g in a.get("groups") or [] if isinstance(g, dict))
        rep.add("①-bulk-account-consistent", int(a.get("count") or 0) == kinds_sum == groups_sum,
                f"{a.get('account')}: count={a.get('count')} kinds={kinds_sum} groups={groups_sum}")
    html_accounts = [int(x) for x in re.findall(r'data-mb-bulk-account="(\d+)"', page)]
    want_accounts = acct_counts if multi_account(candidates) else []
    rep.add("①-bulk-account-sections", html_accounts == want_accounts,
            f"html={html_accounts} candidates={want_accounts}")
    if want_bulk and not multi_account(candidates):
        rep.add("①-bulk-single-account", len(accounts) <= 1, f"계정 {len(accounts)}곳인데 메일 계정은 하나")
    # 발신자 줄·제목 수가 candidates 와 같고, 싣지 못한 것까지 더하면 전체 수다(묶다가 흘린 메일이 없다).
    groups = [g for a in accounts for g in a.get("groups") or [] if isinstance(g, dict)]
    senders = [x for g in groups for x in g.get("senders") or [] if isinstance(x, dict)]
    html_senders = [int(x) for x in re.findall(r'data-mb-bulk-sender="(\d+)"', page)]
    rep.add("①-bulk-senders", html_senders == [int(x.get("count") or 0) for x in senders],
            f"html={html_senders} candidates={[x.get('count') for x in senders]}")
    n_subjects = sum(len(x.get("subjects") or []) for x in senders)
    html_subjects = page.count('data-mb-bulk-subject="1"')
    rep.add("①-bulk-subjects", html_subjects == n_subjects,
            f"html={html_subjects} candidates={n_subjects}")
    accounted = sum(int(x.get("count") or 0) for x in senders) \
        + sum(int(g.get("senders_more_count") or 0) for g in groups)
    rep.add("①-bulk-accounted", not want_bulk or accounted == n_bulk or not senders,
            f"발신자 합={accounted} 전체={n_bulk}")
    # 계정 배지(#41) — 메일 계정이 둘 이상이면 관련 메일·미회신 줄마다 앵커의 계정 이름 그대로, 하나면 0.
    want_acct: list[str] = []
    if multi_account(candidates):
        if want == "all-ready":
            want_acct += [str((m.get("anchor") or {}).get("account") or "") for e in events
                          for m in e.get("related") or [] if isinstance(m, dict)]
        if mail_ready:
            want_acct += [str((m.get("anchor") or {}).get("account") or "") for m in unreplied]
    html_acct = [html_mod.unescape(x) for x in re.findall(r'data-mb-acct="([^"]*)"', page)]
    rep.add("①-account-badges", html_acct == want_acct, f"html={html_acct} candidates={want_acct}")
    n_more = page.count('data-mb-more="1"')
    want_more = (sum(1 for e in events if e.get("related_more")) if want == "all-ready" else 0) \
        + (1 if mail_ready and (candidates.get("email") or {}).get("unreplied_more") else 0)
    rep.add("①-more-lines", n_more == want_more, f"html={n_more} candidates={want_more}")


def check_style(rep: Report, page: str, expect_style: str | None) -> None:
    got = re.findall(r'data-mb-style="([^"]*)"', page)
    rep.add("style-declared", len(got) == 1 and got[0] in STYLES, f"html={got}")
    if expect_style is not None:
        rep.add("style-matches", got == [expect_style], f"html={got} 기대={expect_style}")


def check_summaries(rep: Report, content: dict, candidates: dict, page: str) -> None:
    rows = content.get("summaries")
    if not isinstance(rows, list):
        rep.add("②-summaries-present", False, "summaries 배열 부재")
        return
    wanted = {canon(m.get("anchor")): m for m in unreplied_of(candidates)
              if isinstance(m.get("anchor"), dict)}
    seen: dict[str, int] = {}
    for row in rows:
        anchor = row.get("anchor") if isinstance(row, dict) else None
        if not isinstance(anchor, dict) or not anchor:
            rep.add("②-summary-anchor-present", False, str(row)[:60])
            continue
        key = canon(anchor)
        seen[key] = seen.get(key, 0) + 1
        rep.add("②-summary-anchor-known", key in wanted,
                f"uid={anchor.get('uid')}: 「일정과 무관한 미회신」 후보가 아니다")
        text = row.get("summary")
        if isinstance(text, str) and text.strip():
            rep.add("②-summary-in-html", html_mod.escape(text, quote=True) in page,
                    f"uid={anchor.get('uid')}")
        else:
            rep.add("②-summary-text", False, f"uid={anchor.get('uid')}: 빈 요약")
    for key, mail in wanted.items():
        rep.add("②-summary-exactly-one", seen.get(key, 0) == 1,
                f"uid={mail['anchor'].get('uid')}: {seen.get(key, 0)}건")
    n_summary = page.count('data-mb-summary="1"')
    want_summary = len(wanted) if role_state(candidates, "email") in READY_STATES else 0
    rep.add("②-summary-rendered", n_summary == want_summary,
            f"html={n_summary} candidates={want_summary}")


def check_sections(rep: Report, candidates: dict, page: str) -> None:
    """날씨·환율 절은 candidates 에 수집된 것만 — render 가 그것만 그린다."""
    collected = [k for k, v in (candidates.get("sections") or {}).items()
                 if isinstance(v, dict) and str(v.get("text") or "").strip()]
    n = page.count('data-mb-section="1"')
    want = len(collected) if expected_state(candidates) != "none" else 0
    rep.add("②-sections-from-candidates", n == want, f"html={n} candidates={want}")


def check_seeds(rep: Report, content: dict, candidates: dict) -> None:
    originals: list[str] = []
    for _group, item in iter_items(candidates):
        originals.extend(strings_of(item))
    normalized = [normalize_text(s) for s in originals]
    normalized = [s for s in normalized if len(s) >= SEED_NGRAM]
    for row in content.get("summaries") or []:
        button = row.get("button") if isinstance(row, dict) else None
        if not isinstance(button, dict):
            continue
        seed = str(button.get("seed") or "")
        uid = str((row.get("anchor") or {}).get("uid"))
        rep.add("③-seed-length", len(seed) <= 600, f"uid={uid}: {len(seed)}자")
        norm_seed = normalize_text(seed)
        hit = ""
        for field in normalized:
            for i in range(0, len(field) - SEED_NGRAM + 1):
                window = field[i:i + SEED_NGRAM]
                if window in norm_seed:
                    hit = window
                    break
            if hit:
                break
        rep.add("③-seed-no-thirdparty-fragment", not hit,
                f"uid={uid}: “{hit}”" if hit else "")


def check_buttons(rep: Report, content: dict, candidates: dict, page: str) -> None:
    allowed = bool((candidates.get("controls") or {}).get("buttons"))
    hrefs = re.findall(r'data-mb-button="1"\s+href="([^"]*)"', page)
    content_buttons = sum(1 for row in content.get("summaries") or []
                          if isinstance(row, dict) and isinstance(row.get("button"), dict))
    if not allowed:
        rep.add("⑥-no-buttons-without-phrase", not hrefs and content_buttons == 0,
                f"html={len(hrefs)} content={content_buttons}")
        return
    rep.add("⑥-buttons-rendered", len(hrefs) == content_buttons,
            f"html={len(hrefs)} content={content_buttons}")
    for raw in hrefs:
        parsed = urlparse(html_mod.unescape(raw))
        origin = f"{parsed.scheme}://{parsed.netloc}"
        rep.add("④-button-origin", origin == BUTTON_ORIGIN, origin)
        rep.add("④-button-path", parsed.path == BUTTON_PATH, parsed.path)
        keys = set(parse_qs(parsed.query, keep_blank_values=True).keys())
        rep.add("④-button-query-keys", keys == BUTTON_QUERY_KEYS, str(sorted(keys)))


BANNED_TAGS = ("script", "link", "iframe", "img", "embed", "object",
               "source", "video", "audio", "base")


def check_assets(rep: Report, page: str) -> None:
    """자산 검사는 **태그 영역**에서만 한다 — 이스케이프된 본문에 `<img src=` 같은
    글자가 텍스트로 들어 있는 것은 정상이다."""
    tags = re.findall(r"<[^>]*>", page)
    for tag in tags:
        lowered = tag.lower()
        name = re.match(r"<\s*/?\s*([a-z0-9]+)", lowered)
        if name and name.group(1) in BANNED_TAGS:
            rep.add("⑤-no-external-asset", False, tag[:80])
        if re.search(r"\ssrc\s*=", lowered):
            rep.add("⑤-no-external-asset", False, tag[:80])
    rep.add("⑤-no-external-asset", True, f"tags={len(tags)}")
    style = "".join(re.findall(r"<style[^>]*>(.*?)</style>", page, re.S))
    for token in ("@import", "@font-face", "url("):
        rep.add("⑤-no-external-css", token not in style.lower(), token)
    for tag in tags:
        for href in re.findall(r'href="([^"]*)"', tag):
            url = html_mod.unescape(href)
            ok = url.startswith("https://") or url.startswith("#")
            rep.add("⑤-href-https", ok, url[:80])


SURFACED_SEVERITIES = ("error", "degraded")


def check_warnings(rep: Report, candidates: dict, page: str) -> None:
    warns = [w for w in candidates.get("warnings") or []
             if isinstance(w, dict) and w.get("severity") in SURFACED_SEVERITIES]
    if not warns:
        rep.add("⑦-no-error-warnings", True, "")
        return
    rep.add("⑦-error-surfaced", 'data-mb-warning="1"' in page,
            f"표면화 대상 {len(warns)}건")


def check_sources(rep: Report, candidates: dict, page: str, expect_sources: bool) -> None:
    present = 'data-mb-sources="1"' in page
    if not expect_sources:
        rep.add("⑧-sources-absent", not present, "출처 절이 남아 있다")
        rep.add("⑧-no-dangling-ref", 'data-mb-src-ref="1"' not in page, "대상 없는 출처 링크")
        return
    rep.add("⑧-sources-present", present, "data-mb-sources 부재")
    ids = re.findall(r'id="mb-src-(\d+)"', page)
    expected = len(source_entries(candidates))
    rep.add("⑧-source-count", len(ids) == expected, f"html={len(ids)} candidates={expected}")
    rows = (page.count('data-mb-event="1"') + page.count('data-mb-related="1"')
            + page.count('data-mb-item="1"'))
    refs = re.findall(r'data-mb-src-ref="1"\s+href="#mb-src-(\d+)"', page)
    rep.add("⑧-every-row-has-ref", len(refs) == rows, f"refs={len(refs)} rows={rows}")
    missing = sorted(set(refs) - set(ids))
    rep.add("⑧-ref-targets-exist", not missing, f"미상 대상 {missing}")
    used = page.count('data-mb-used="1"')
    rep.add("⑧-used-marks-match", used == len(set(refs)), f"used={used} refs={len(set(refs))}")


def check_sample(rep: Report, candidates: dict, page: str) -> None:
    """⑨ 샘플과 실데이터는 섞이지 않는다 — 양방향 모두 막는다."""
    sample = bool((candidates.get("controls") or {}).get("sample"))
    banner = 'data-mb-sample="1"' in page
    anchors = [item.get("anchor") for _g, item in iter_items(candidates)
               if isinstance(item.get("anchor"), dict)]
    sample_anchors = [a for a in anchors if str(a.get("provider") or "") == SAMPLE_TOKEN]
    if sample:
        rep.add("⑨-sample-banner", banner, "상시 띠 부재")
        rep.add("⑨-sample-anchors-all", len(sample_anchors) == len(anchors),
                f"sample={len(sample_anchors)} 전체={len(anchors)}")
        states = {r: role_state(candidates, r) for r in ("calendar", "email")}
        rep.add("⑨-sample-role-state", all(v == SAMPLE_TOKEN for v in states.values()),
                str(states))
    else:
        rep.add("⑨-no-sample-banner", not banner, "실데이터에 샘플 띠")
        rep.add("⑨-no-sample-anchors", not sample_anchors,
                f"실데이터에 sample 앵커 {len(sample_anchors)}건")


def check_sample_seeds(rep: Report, content: dict, candidates: dict) -> None:
    """샘플 버튼의 seed 는 새 세션에 **샘플임을 먼저** 말해야 한다."""
    if not (candidates.get("controls") or {}).get("sample"):
        return
    for row in content.get("summaries") or []:
        button = row.get("button") if isinstance(row, dict) else None
        if not isinstance(button, dict):
            continue
        seed = str(button.get("seed") or "")
        rep.add("⑨-sample-seed-prefix", seed.startswith("샘플 시나리오의"),
                f"uid={(row.get('anchor') or {}).get('uid')}: {seed[:20]}…")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def run(candidates: dict, content: dict, page: str, expect_sources: bool = True,
        expect_style: str | None = None) -> Report:
    rep = Report()
    rep.add("schema-candidates", candidates.get("schema_version") == SCHEMA_VERSION,
            str(candidates.get("schema_version")))
    rep.add("schema-content", content.get("schema_version") == SCHEMA_VERSION,
            str(content.get("schema_version")))
    check_style(rep, page, expect_style)
    check_structure(rep, candidates, page)
    check_summaries(rep, content, candidates, page)
    check_sections(rep, candidates, page)
    check_seeds(rep, content, candidates)
    check_buttons(rep, content, candidates, page)
    check_assets(rep, page)
    check_warnings(rep, candidates, page)
    check_sources(rep, candidates, page, expect_sources)
    check_sample(rep, candidates, page)
    check_sample_seeds(rep, content, candidates)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="아침 브리핑 정적 검증")
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--content", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--no-sources", action="store_true",
                    help="`render.py --no-sources` 로 만든 페이지 — ⑧ 을 그에 맞춰 본다")
    ap.add_argument("--style", choices=STYLES,
                    help="`render.py --style` 로 만든 페이지 — 그 스타일인지도 본다")
    args = ap.parse_args(argv)
    try:
        candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
        content = json.loads(Path(args.content).read_text(encoding="utf-8"))
        page = Path(args.html).read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": "input_unreadable",
                          "detail": str(exc)[:300]}, ensure_ascii=False))
        return 2
    rep = run(candidates, content, page, expect_sources=not args.no_sources, expect_style=args.style)
    failures = rep.failures
    print(json.dumps({
        "status": "fail" if failures else "pass",
        "visual": "INCONCLUSIVE",
        "visual_reason": "Cowork 샌드박스에 브라우저가 없어 시각 축은 판정하지 않는다",
        "checked": len(rep.checks),
        "failures": failures,
    }, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
