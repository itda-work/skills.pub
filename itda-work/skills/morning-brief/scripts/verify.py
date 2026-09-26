#!/usr/bin/env python3
"""itda-work morning-brief: verify.py — 정적 검증이 이 스킬의 판정 정본.

Cowork 샌드박스에는 playwright·chromium 이 없다(Phase 0 확정). 시각 축은
INCONCLUSIVE 로 보고하고, 아래 ①~⑦ 을 코드가 집행한다.

  ① state(역할 준비) × items(항목 수) 두 축의 필수 요소
  ② content 각 항목의 anchor 가 candidates 의 **정확히 한 후보**와 일치하고
     quote 가 그 후보 문자열과 **바이트 동일**(연속 부분문자열)이며,
     그 후보가 그 목록(needs/resolved)에 올 수 있는 버킷에서 왔는가
  ③ seed 에 원본 필드(from·subject·본문·주소·제목)의 정규화 12자+ 부분문자열 0
  ④ 버튼 href 재파싱 — origin·path·query 키 정확 일치
  ⑤ 외부 자산 0
  ⑥ controls.buttons=false 인데 버튼이 있으면 RED
  ⑦ error 역할 경고가 있으면 그 사실을 말하는 한 줄이 페이지에 있어야 함
  ⑧ 「출처」 절 — 원본 수 == 후보 수(접기 후), 목록 항목마다 실재하는 출처 링크
  ⑨ 샘플 모드 — sample 이면 상시 띠 + 전 앵커 provider 가 sample,
     아니면 띠 0 + sample 앵커 0 (상호 배타)
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

SCHEMA_VERSION = 1
BUTTON_ORIGIN = "https://claude.ai"
BUTTON_PATH = "/new"
BUTTON_QUERY_KEYS = {"q", "surface", "composer"}
SEED_NGRAM = 12
SAMPLE_TOKEN = "sample"

CANDIDATE_GROUPS = (
    ("calendar", ("today", "tomorrow", "prep", "cancelled")),
    ("email", ("unreplied", "replied_then_new")),
)

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


def iter_candidates(candidates: dict):
    """(group, bucket, candidate) 를 훑는다. 동일 후보 중복은 호출자가 접는다."""
    for group, buckets in CANDIDATE_GROUPS:
        section = candidates.get(group) or {}
        for bucket in buckets:
            for item in section.get(bucket) or []:
                if isinstance(item, dict):
                    yield group, bucket, item


def folded_candidates(candidates: dict) -> list[dict]:
    """후보를 훑되 **완전 동일한 후보**는 하나로 접는다(prep/cancelled 는
    today/tomorrow 의 같은 이벤트를 다시 담는다). 접힌 항목은 자기가 나타난
    버킷을 **전부** 들고 있어야 한다 — 목록↔버킷 대조(②)가 그것을 본다.

    반환 순서는 `render.folded_candidates` 와 같아야 하며, 그 순서가 곧
    출처 번호(`mb-src-N`)다. 두 구현의 일치는 테스트가 대조한다."""
    out: list[dict] = []
    by_body: dict[str, dict] = {}
    seen: dict[str, set[str]] = {}
    for group, bucket, item in iter_candidates(candidates):
        anchor = item.get("anchor")
        if not isinstance(anchor, dict) or not anchor:
            continue
        key = canon(anchor)
        body = canon(item)
        if body in seen.setdefault(key, set()):
            by_body[body]["buckets"].append((group, bucket))
            continue
        seen[key].add(body)
        entry = {"key": key, "group": group, "buckets": [(group, bucket)],
                 "item": item}
        by_body[body] = entry
        out.append(entry)
    return out


def build_anchor_index(candidates: dict) -> dict[str, list[dict]]:
    """anchor 키 → 서로 다른 후보 entry 목록(버킷 보존)."""
    index: dict[str, list[dict]] = {}
    for entry in folded_candidates(candidates):
        index.setdefault(entry["key"], []).append(entry)
    return index


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


# 샘플 역할은 실데이터가 아니지만 **레이아웃은 완전판**이다 — 형식을 미리 보는 것이
# 목적이므로 all-ready 로 해석한다.
READY_STATES = ("ready", SAMPLE_TOKEN)


def expected_state(candidates: dict) -> str:
    roles = candidates.get("roles") or {}
    cal = (roles.get("calendar") or {}).get("state") in READY_STATES
    mail = (roles.get("email") or {}).get("state") in READY_STATES
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


def check_structure(rep: Report, content: dict, candidates: dict,
                    page: str) -> None:
    state = content.get("state")
    rep.add("①-state-declared", state in
            ("all-ready", "calendar-only", "email-only", "none"), str(state))
    want = expected_state(candidates)
    rep.add("①-state-matches-roles", state == want,
            f"content={state} roles={want}")
    rep.add("①-state-in-html", f'data-mb-state="{state}"' in page, str(state))

    has_terrain = 'data-mb-terrain="1"' in page
    n_acts = page.count('data-mb-act="1"')
    n_items = page.count('data-mb-item="1"')
    has_none = 'data-mb-none="1"' in page
    has_empty_line = 'data-mb-empty-lists="1"' in page

    if state == "none":
        rep.add("①-none-two-sentences", has_none, "data-mb-none 부재")
        rep.add("①-none-no-terrain", not has_terrain, "지형은 그리지 않는다")
        rep.add("①-none-no-items", n_items == 0, f"items={n_items}")
    else:
        rep.add("①-dateline", 'data-mb-dateline="1"' in page, "")
        rep.add("①-headline", 'data-mb-headline="1"' in page, "")

    if state in ("all-ready", "calendar-only"):
        rep.add("①-terrain-single-stroke", has_terrain and page.count("<path ") >= 1,
                "지형 한 획 부재")
        # 상류 계약은 "세 act" 다 — 일정이 오전에만 있어도 오후·저녁 칸은 비었다는
        # 관찰로 채운다. content 쪽도 함께 재서 4개를 넣고 하나가 잘리는(render 가
        # [:3] 로 자른다) 무음 누락까지 막는다.
        n_content_acts = len(content.get("acts") or [])
        rep.add("①-acts-exactly-three", n_acts == 3 and n_content_acts == 3,
                f"html={n_acts} content={n_content_acts}")
    if state == "calendar-only":
        rep.add("①-calendar-only-one-line", has_empty_line, "목록 자리 한 줄 부재")
        rep.add("①-calendar-only-no-items", n_items == 0, f"items={n_items}")
    if state == "email-only":
        rep.add("①-email-only-no-terrain", not has_terrain, "지형 생략 계약")
        rep.add("①-email-only-no-acts", n_acts == 0, f"acts={n_acts}")

    needs = content.get("needs_attention") or []
    resolved = content.get("resolved") or []
    total = len(needs) + len(resolved)
    rep.add("①-items-rendered", n_items == total,
            f"html={n_items} content={total}")
    if state in ("all-ready", "email-only") and total == 0:
        rep.add("①-empty-lists-line", has_empty_line, "빈 목록 한 줄 부재")
    if needs:
        rep.add("①-needs-list", 'data-mb-list="needs"' in page, "")
    if resolved:
        rep.add("①-resolved-list", 'data-mb-list="resolved"' in page, "")


# 목록마다 올 수 있는 후보 버킷. 이미 답한 스레드가 "지금 필요한 일" 에 서거나
# 미회신이 "정리된 일" 에 서면 앵커가 실재해도 페이지가 거짓말을 한다.
BUCKETS_FOR_LIST = {
    "needs_attention": {("email", "unreplied"), ("calendar", "prep")},
    "resolved": {("email", "replied_then_new"), ("calendar", "cancelled")},
}


def check_anchors(rep: Report, content: dict, candidates: dict,
                  page: str) -> None:
    index = build_anchor_index(candidates)
    for key in ("needs_attention", "resolved"):
        allowed = BUCKETS_FOR_LIST[key]
        for item in content.get(key) or []:
            title = str(item.get("title") or "?")
            anchor = item.get("anchor")
            if not isinstance(anchor, dict) or not anchor:
                rep.add("②-anchor-present", False, title)
                continue
            matches = index.get(canon(anchor), [])
            rep.add("②-anchor-exactly-one", len(matches) == 1,
                    f"{title}: {len(matches)}건")
            if len(matches) == 1:
                buckets = set(matches[0]["buckets"])
                hit = buckets & allowed
                rep.add("②-anchor-bucket", bool(hit),
                        f"{title}: {sorted(f'{g}.{b}' for g, b in buckets)} "
                        f"∉ {sorted(f'{g}.{b}' for g, b in allowed)}")
            quote = item.get("quote")
            if not isinstance(quote, str) or not quote:
                continue
            if len(matches) != 1:
                rep.add("②-quote-byte-identical", False, f"{title}: 후보 미상")
                continue
            fields = strings_of(matches[0]["item"], skip_keys=("anchor",))
            rep.add("②-quote-byte-identical",
                    any(quote in field for field in fields), title)
            rep.add("②-quote-in-html",
                    html_mod.escape(quote, quote=True) in page, title)


def check_sections(rep: Report, content: dict, candidates: dict) -> None:
    """content 의 섹션은 **수집된 것만** — 앵커·인용과 같은 '지어내지 않는다' 축.

    render 는 content 의 섹션을 그대로 그리므로, 수집되지 않은 절을 content 가
    적으면 없는 날씨·환율이 사실처럼 실린다. 날씨가 기본이 된 뒤로는 회차마다
    수집 집합이 달라져 이 어긋남이 더 쉽게 난다."""
    collected = set(candidates.get("sections") or {})
    for sec in content.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        heading = str(sec.get("heading") or "")
        if not heading:
            continue
        rep.add("②-section-from-candidates", heading in collected,
                f"{heading}: 수집분 {sorted(collected)}")


def check_seeds(rep: Report, content: dict, candidates: dict) -> None:
    originals: list[str] = []
    for _group, _bucket, item in iter_candidates(candidates):
        originals.extend(strings_of(item))
    normalized = [normalize_text(s) for s in originals]
    normalized = [s for s in normalized if len(s) >= SEED_NGRAM]

    for item in content.get("needs_attention") or []:
        button = item.get("button")
        if not isinstance(button, dict):
            continue
        seed = str(button.get("seed") or "")
        title = str(item.get("title") or "?")
        rep.add("③-seed-length", len(seed) <= 600, f"{title}: {len(seed)}자")
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
                f"{title}: “{hit}”" if hit else "")


def check_buttons(rep: Report, content: dict, candidates: dict,
                  page: str) -> None:
    allowed = bool((candidates.get("controls") or {}).get("buttons"))
    hrefs = re.findall(r'data-mb-button="1"\s+href="([^"]*)"', page)
    content_buttons = sum(1 for item in content.get("needs_attention") or []
                          if isinstance(item.get("button"), dict))

    if not allowed:
        rep.add("⑥-no-buttons-without-phrase", not hrefs and content_buttons == 0,
                f"html={len(hrefs)} content={content_buttons}")
        return
    rep.add("⑥-buttons-rendered", len(hrefs) == content_buttons,
            f"html={len(hrefs)} content={content_buttons}")

    for raw in hrefs:
        href = html_mod.unescape(raw)
        parsed = urlparse(href)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        rep.add("④-button-origin", origin == BUTTON_ORIGIN, origin)
        rep.add("④-button-path", parsed.path == BUTTON_PATH, parsed.path)
        keys = set(parse_qs(parsed.query, keep_blank_values=True).keys())
        rep.add("④-button-query-keys", keys == BUTTON_QUERY_KEYS, str(sorted(keys)))


BANNED_TAGS = ("script", "link", "iframe", "img", "embed", "object",
               "source", "video", "audio", "base")


def check_assets(rep: Report, page: str) -> None:
    """자산 검사는 **태그 영역**에서만 한다 — 이스케이프된 본문에 `<img src=` 같은
    글자가 텍스트로 들어 있는 것은 정상이고, 그것을 위반으로 세면 악성 픽스처가
    거짓 RED 를 만든다."""
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
            # 같은 문서 안의 출처 앵커(`#mb-src-N`)는 외부 자산이 아니다.
            # 허용은 딱 두 형태뿐 — `javascript:`·`http:` 는 그대로 RED.
            ok = url.startswith("https://") or url.startswith("#")
            rep.add("⑤-href-https", ok, url[:80])


SURFACED_SEVERITIES = ("error", "degraded")


def check_warnings(rep: Report, candidates: dict, page: str) -> None:
    """오류(error)와 결손(degraded) 둘 다 페이지가 말해야 한다.

    `degraded` 는 역할이 ready 인데 판정을 못 해 후보가 빈 경우다
    (예: `sent_folder_not_found`). 그것을 조용한 빈 목록으로 두면 "오늘 아침은
    당신을 기다리는 일이 없어요" 가 거짓말이 된다."""
    warns = [w for w in candidates.get("warnings") or []
             if isinstance(w, dict) and w.get("severity") in SURFACED_SEVERITIES]
    if not warns:
        rep.add("⑦-no-error-warnings", True, "")
        return
    rep.add("⑦-error-surfaced", 'data-mb-warning="1"' in page,
            f"표면화 대상 {len(warns)}건")


def check_sources(rep: Report, content: dict, candidates: dict, page: str,
                  expect_sources: bool) -> None:
    """⑧ 출처 절 — 원본 수가 후보 수와 같고, 목록 항목마다 실재하는 링크."""
    present = 'data-mb-sources="1"' in page
    if not expect_sources:
        # `--no-sources` 로 렌더했다고 말했는데 절이 있으면 둘이 어긋난 것이다.
        rep.add("⑧-sources-absent", not present, "출처 절이 남아 있다")
        rep.add("⑧-no-dangling-ref", 'data-mb-src-ref="1"' not in page,
                "대상 없는 출처 링크")
        return

    rep.add("⑧-sources-present", present, "data-mb-sources 부재")

    ids = re.findall(r'id="mb-src-(\d+)"', page)
    expected = len(folded_candidates(candidates))
    rep.add("⑧-source-count", len(ids) == expected,
            f"html={len(ids)} candidates={expected}")

    items = list(content.get("needs_attention") or []) \
        + list(content.get("resolved") or [])
    refs = re.findall(r'data-mb-src-ref="1"\s+href="#mb-src-(\d+)"', page)
    rep.add("⑧-every-item-has-ref", len(refs) == len(items),
            f"refs={len(refs)} items={len(items)}")

    id_set = set(ids)
    missing = sorted(set(refs) - id_set)
    rep.add("⑧-ref-targets-exist", not missing, f"미상 대상 {missing}")

    used = page.count('data-mb-used="1"')
    # 서로 다른 항목이 같은 후보를 가리키면(② 가 따로 보는 축) 표시는 한 번이다.
    rep.add("⑧-used-marks-match", used == len(set(refs)),
            f"used={used} refs={len(set(refs))}")


def check_sample(rep: Report, candidates: dict, page: str) -> None:
    """⑨ 샘플과 실데이터는 섞이지 않는다.

    샘플이 실데이터로 읽히면 없는 일정에 사람이 움직이고, 실데이터에 sample
    앵커가 섞이면 진짜 항목이 픽션으로 보인다 — 양방향 모두 막는다."""
    sample = bool((candidates.get("controls") or {}).get("sample"))
    banner = 'data-mb-sample="1"' in page

    anchors = [a for a in (
        item.get("anchor") for _g, _b, item in iter_candidates(candidates))
        if isinstance(a, dict)]
    sample_anchors = [a for a in anchors
                      if str(a.get("provider") or "") == SAMPLE_TOKEN]

    if sample:
        rep.add("⑨-sample-banner", banner, "상시 띠 부재")
        rep.add("⑨-sample-anchors-all", len(sample_anchors) == len(anchors),
                f"sample={len(sample_anchors)} 전체={len(anchors)}")
        roles = candidates.get("roles") or {}
        states = {r: str((roles.get(r) or {}).get("state") or "")
                  for r in ("calendar", "email")}
        rep.add("⑨-sample-role-state",
                all(v == SAMPLE_TOKEN for v in states.values()), str(states))
    else:
        rep.add("⑨-no-sample-banner", not banner, "실데이터에 샘플 띠")
        rep.add("⑨-no-sample-anchors", not sample_anchors,
                f"실데이터에 sample 앵커 {len(sample_anchors)}건")


def check_sample_seeds(rep: Report, content: dict, candidates: dict) -> None:
    """샘플 버튼의 seed 는 새 세션에 **샘플임을 먼저** 말해야 한다 — 그 세션은
    candidates 를 못 보고 seed 문장만 읽는다."""
    if not (candidates.get("controls") or {}).get("sample"):
        return
    for item in content.get("needs_attention") or []:
        button = item.get("button")
        if not isinstance(button, dict):
            continue
        seed = str(button.get("seed") or "")
        rep.add("⑨-sample-seed-prefix", seed.startswith("샘플 시나리오의"),
                f'{item.get("title")}: {seed[:20]}…')


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def run(candidates: dict, content: dict, page: str,
        expect_sources: bool = True) -> Report:
    rep = Report()
    rep.add("schema-candidates", candidates.get("schema_version") == SCHEMA_VERSION,
            str(candidates.get("schema_version")))
    rep.add("schema-content", content.get("schema_version") == SCHEMA_VERSION,
            str(content.get("schema_version")))
    check_structure(rep, content, candidates, page)
    check_anchors(rep, content, candidates, page)
    check_sections(rep, content, candidates)
    check_seeds(rep, content, candidates)
    check_buttons(rep, content, candidates, page)
    check_assets(rep, page)
    check_warnings(rep, candidates, page)
    check_sources(rep, content, candidates, page, expect_sources)
    check_sample(rep, candidates, page)
    check_sample_seeds(rep, content, candidates)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="아침 브리핑 정적 검증")
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--content", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--no-sources", action="store_true",
                    help="`render.py --no-sources` 로 만든 페이지 — ⑧ 을 건너뛴다")
    args = ap.parse_args(argv)

    try:
        candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
        content = json.loads(Path(args.content).read_text(encoding="utf-8"))
        page = Path(args.html).read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": "input_unreadable",
                          "detail": str(exc)[:300]}, ensure_ascii=False))
        return 2

    rep = run(candidates, content, page, expect_sources=not args.no_sources)
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
