#!/usr/bin/env python3
"""itda-work morning-brief: render.py — content.json + candidates.json → 단일 HTML.

LLM 은 HTML 을 쓰지 않는다. 이스케이프·링크 화이트리스트·버튼 href 인코딩·요일·
시간 표기·지형 SVG 는 전부 여기서 결정론으로 만든다.

`--candidates` 는 필수다: 지형 한 획은 오늘 일정 분포에서 계산하고, error 역할의
경고 한 줄도 candidates.warnings 가 정본이기 때문이다(추론 금지).
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse

SCHEMA_VERSION = 1
STATES = ("all-ready", "calendar-only", "email-only", "none")
SAMPLE_BANNER = "샘플 브리핑 — 실제 계정 데이터가 아니에요"
SAMPLE_ACCOUNT_LABEL = "샘플 · 에이전트 생성 시나리오"
SAMPLE_HINT = "샘플 브리핑을 요청하면 형식을 미리 볼 수 있어요."
BUTTON_ORIGIN = "https://claude.ai"
BUTTON_PATH = "/new"
MAX_TITLE_WORDS = 10
MAX_SENTENCE_CHARS = 200
MAX_LABEL_WORDS = 5
MAX_SEED_CHARS = 600

WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")

# 먹·한지 톤. accent 는 단청 주홍 1색.
PALETTE = {
    "bg": "#FBF8F1",
    "wash": "#F4F0E6",
    "ink": "#22201C",
    "ink_soft": "#6B6459",
    "ink_grey": "#B3AB9C",
    "hairline": "#E3DDD0",
    "accent": "#B3492D",
    "accent_hover": "#93381F",
}

SERIF = ('"Apple Myungjo", Batang, "Noto Serif CJK KR", "Noto Serif KR", serif')
SANS = ('"Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans CJK KR", '
        '"Noto Sans KR", sans-serif')

TERRAIN_W, TERRAIN_H = 840, 170
TERRAIN_X0, TERRAIN_X1 = 20.0, 820.0
DAY_START_MIN, DAY_END_MIN = 7 * 60, 22 * 60
BASE_Y, STEP_Y, MIN_Y = 148.0, 26.0, 34.0
SAMPLE_MIN = 15

for _stream in (sys.stdout, sys.stderr):
    if _stream.encoding and _stream.encoding.lower() not in ("utf-8", "utf8"):
        try:
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover
            pass


class ContentError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


# --------------------------------------------------------------------------
# 표기 계산
# --------------------------------------------------------------------------

def is_sample(candidates: dict) -> bool:
    """샘플 여부의 단일 판정 — gather 가 고정한 `controls.sample` 만 본다."""
    return bool((candidates.get("controls") or {}).get("sample"))


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def format_date_line(iso_date: str) -> str:
    """`9월 3일 목요일` — 요일은 코드가 낸다."""
    try:
        d = date.fromisoformat(iso_date)
    except (TypeError, ValueError) as exc:
        raise ContentError("bad_date", str(iso_date)) from exc
    return f"{d.month}월 {d.day}일 {WEEKDAYS[d.weekday()]}요일"


def format_month_day(d: date) -> str:
    """`9월 3일` — 날짜줄(`format_date_line`)에서 요일만 뺀 표기."""
    return f"{d.month}월 {d.day}일"


def format_time(dt: datetime) -> str:
    """`오전 9:30` / `오후 1시`."""
    ampm = "오전" if dt.hour < 12 else "오후"
    hour12 = dt.hour % 12 or 12
    if dt.minute == 0:
        return f"{ampm} {hour12}시"
    return f"{ampm} {hour12}:{dt.minute:02d}"


def format_range(start: str, end: str | None) -> str:
    s = _parse_dt(start)
    if s is None:
        return ""
    e = _parse_dt(end) if end else None
    if e is None:
        return f"{format_time(s)}부터"
    return f"{format_time(s)} – {format_time(e)}"


def _parse_dt(raw) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def format_when(start, end, all_day: bool) -> str:
    """출처 원본의 시각 한 줄 — ISO 원문 대신 사람이 읽는 표기.

    `9월 3일 오전 9:30 – 오전 10시` / 날짜를 넘기면 끝쪽에도 날짜를 붙인다 /
    종일은 `9월 3일 종일`. 읽을 수 없는 값은 그대로 둔다(지어내지 않는다)."""
    if all_day:
        sd = _parse_date(start)
        if sd is None:
            return str(start or "")
        ed = _parse_date(end)
        # 종일 일정의 DTEND 는 배타다(event_model.build_vevent: start + 1일).
        # 마지막 날을 하루 당겨 사람이 읽는 포함 범위로 쓴다.
        last = ed - timedelta(days=1) if ed and ed > sd else sd
        if last <= sd:
            return f"{format_month_day(sd)} 종일"
        return f"{format_month_day(sd)} – {format_month_day(last)} 종일"

    s = _parse_dt(start)
    if s is None:
        return str(start or "")
    e = _parse_dt(end)
    head = f"{format_month_day(s.date())} {format_time(s)}"
    if e is None:
        return f"{head}부터"
    if e.date() == s.date():
        return f"{head} – {format_time(e)}"
    return f"{head} – {format_month_day(e.date())} {format_time(e)}"


def format_moment(raw) -> str:
    """메일 수신 시각 — `9월 2일 오후 7:12`."""
    dt = _parse_dt(raw)
    if dt is None:
        return str(raw or "")
    return f"{format_month_day(dt.date())} {format_time(dt)}"


def _parse_date(raw) -> date | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


# --------------------------------------------------------------------------
# 지형 한 획
# --------------------------------------------------------------------------

def _minutes(dt: datetime) -> float:
    return dt.hour * 60 + dt.minute


def _spans(events: list[dict]) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    for ev in events:
        if ev.get("all_day"):
            continue
        if str(ev.get("status") or "").upper() == "CANCELLED":
            continue  # 취소된 자리는 하루의 지형이 아니다
        s = _parse_dt(ev.get("start"))
        if s is None:
            continue
        e = _parse_dt(ev.get("end")) or (s + timedelta(minutes=30))
        out.append((_minutes(s), max(_minutes(e), _minutes(s) + 15),
                    str(ev.get("summary") or "")))
    return sorted(out)


def _x_of(minute: float) -> float:
    span = DAY_END_MIN - DAY_START_MIN
    ratio = (minute - DAY_START_MIN) / span
    ratio = min(1.0, max(0.0, ratio))
    return TERRAIN_X0 + ratio * (TERRAIN_X1 - TERRAIN_X0)


def _load_at(spans, minute: float) -> int:
    return sum(1 for s, e, _ in spans if s <= minute < e)


def _y_of(load: int) -> float:
    return max(MIN_Y, BASE_Y - load * STEP_Y)


def terrain_svg(events: list[dict]) -> str:
    """끊기지 않은 한 획 + 회의 점. 조용한 날은 잔잔한 수면으로 눕는다."""
    spans = _spans(events)
    pts: list[tuple[float, float]] = []
    minute = float(DAY_START_MIN)
    while minute <= DAY_END_MIN:
        pts.append((round(_x_of(minute), 1), round(_y_of(_load_at(spans, minute)), 1)))
        minute += SAMPLE_MIN
    path = "M " + " L ".join(f"{x},{y}" for x, y in pts)

    dots: list[str] = []
    for idx, (s, e, _summary) in enumerate(spans):
        mid = (s + e) / 2.0
        x = round(_x_of(mid), 1)
        y = round(_y_of(max(1, _load_at(spans, mid))), 1)
        minutes = max(15.0, e - s)
        r = round(min(13.0, 6.0 + minutes / 30.0), 1)
        overlap = any(j != idx and other_s < e and s < other_e
                      for j, (other_s, other_e, _o) in enumerate(spans))
        if overlap:
            dots.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{PALETTE["bg"]}" '
                        f'stroke="{PALETTE["ink"]}" stroke-width="2"/>')
        else:
            dots.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{PALETTE["ink"]}"/>')

    return (f'<svg data-mb-terrain="1" viewBox="0 0 {TERRAIN_W} {TERRAIN_H}" '
            f'width="100%" height="{TERRAIN_H}" role="img" '
            f'aria-label="오늘 일정의 흐름"><path d="{path}" fill="none" '
            f'stroke="{PALETTE["ink"]}" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round"/>' + "".join(dots) + "</svg>")


# --------------------------------------------------------------------------
# 후보 접기 — 출처 번호의 정본
# --------------------------------------------------------------------------

CANDIDATE_GROUPS = (
    ("calendar", ("today", "tomorrow", "prep", "cancelled")),
    ("email", ("unreplied", "replied_then_new")),
)
GROUP_LABEL = {"calendar": "일정", "email": "메일"}


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def folded_candidates(candidates: dict) -> list[dict]:
    """후보를 훑되 **완전 동일한 후보**(prep/cancelled 가 today/tomorrow 를 다시
    담는 경우)는 하나로 접는다. 반환 순서가 곧 `mb-src-N` 의 N 이며,
    `verify.build_anchor_index` 의 접기 규칙과 같아야 한다(테스트가 대조).

    앵커 없는 후보는 verify 와 동일하게 세지 않는다 — 앵커가 목록과 출처를
    잇는 유일한 키이기 때문이다."""
    out: list[dict] = []
    by_key: dict[str, dict] = {}
    seen: dict[str, set[str]] = {}
    for group, buckets in CANDIDATE_GROUPS:
        section = candidates.get(group) or {}
        for bucket in buckets:
            for item in section.get(bucket) or []:
                if not isinstance(item, dict):
                    continue
                anchor = item.get("anchor")
                if not isinstance(anchor, dict) or not anchor:
                    continue
                key = _canon(anchor)
                body = _canon(item)
                if body in seen.setdefault(key, set()):
                    by_key[body]["buckets"].append((group, bucket))
                    continue
                seen[key].add(body)
                entry = {"group": group, "buckets": [(group, bucket)],
                         "item": item, "key": key}
                by_key[body] = entry
                out.append(entry)
    return out


def source_numbers(candidates: dict) -> dict[str, int]:
    """anchor 키 → 출처 번호(1부터). 같은 앵커가 여럿이면 첫 번째를 쓴다
    (그 상태는 verify ② 가 따로 RED 로 잡는다)."""
    numbers: dict[str, int] = {}
    for idx, entry in enumerate(folded_candidates(candidates), start=1):
        numbers.setdefault(entry["key"], idx)
    return numbers


# --------------------------------------------------------------------------
# content 검증
# --------------------------------------------------------------------------

def _words(text: str) -> int:
    return len([w for w in str(text).split() if w])


def validate_content(content: object) -> dict:
    if not isinstance(content, dict):
        raise ContentError("content_not_object")
    if content.get("schema_version") != SCHEMA_VERSION:
        raise ContentError("schema_version", str(content.get("schema_version")))
    state = content.get("state")
    if state not in STATES:
        raise ContentError("bad_state", str(state))
    if not isinstance(content.get("date"), str):
        raise ContentError("missing_date")
    format_date_line(content["date"])
    if not isinstance(content.get("headline"), str) or not content["headline"].strip():
        raise ContentError("missing_headline")

    for act in content.get("acts") or []:
        if not isinstance(act, dict) or not isinstance(act.get("sentence"), str):
            raise ContentError("bad_act")
        if len(act["sentence"]) > MAX_SENTENCE_CHARS:
            raise ContentError("act_sentence_too_long", act["sentence"][:40])

    for key in ("needs_attention", "resolved"):
        for item in content.get(key) or []:
            if not isinstance(item, dict):
                raise ContentError("bad_item", key)
            title = item.get("title")
            if not isinstance(title, str) or not title.strip():
                raise ContentError("missing_title", key)
            if _words(title) > MAX_TITLE_WORDS:
                raise ContentError("title_too_long", title)
            sentence = item.get("sentence")
            if not isinstance(sentence, str) or not sentence.strip():
                raise ContentError("missing_sentence", title)
            if len(sentence) > MAX_SENTENCE_CHARS:
                raise ContentError("sentence_too_long", title)
            if not isinstance(item.get("anchor"), dict) or not item["anchor"]:
                raise ContentError("missing_anchor", title)
            button = item.get("button")
            if button is not None:
                if key == "resolved":
                    raise ContentError("button_on_resolved", title)
                if not isinstance(button, dict):
                    raise ContentError("bad_button", title)
                label = button.get("label")
                seed = button.get("seed")
                if not isinstance(label, str) or not label.strip():
                    raise ContentError("missing_button_label", title)
                if _words(label) > MAX_LABEL_WORDS:
                    raise ContentError("button_label_too_long", label)
                if not isinstance(seed, str) or not seed.strip():
                    raise ContentError("missing_button_seed", title)
                if len(seed) > MAX_SEED_CHARS:
                    raise ContentError("button_seed_too_long", title)
    return content


# --------------------------------------------------------------------------
# HTML 조립
# --------------------------------------------------------------------------

def button_href(seed: str) -> str:
    query = urlencode({"q": seed, "surface": "cowork", "composer": "mini"})
    return f"{BUTTON_ORIGIN}{BUTTON_PATH}?{query}"


def _safe_url(raw) -> str | None:
    if not isinstance(raw, str) or not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return raw


def render_item(item: dict, index: int, buttons_allowed: bool,
                src_no: int | None = None) -> str:
    title = esc(item["title"])
    url = _safe_url(item.get("url"))
    title_html = (f'<a class="mb-title-link" href="{esc(url)}">{title}</a>'
                  if url else title)

    sentence = esc(item["sentence"])
    phrase = item.get("source_phrase")
    if isinstance(phrase, str) and phrase and phrase in item["sentence"]:
        marked = f'<span class="mb-source">{esc(phrase)}</span>'
        sentence = esc(item["sentence"]).replace(esc(phrase), marked, 1)

    quote_html = ""
    quote = item.get("quote")
    if isinstance(quote, str) and quote:
        quote_html = f' <span class="mb-quote">“{esc(quote)}”</span>'  # 문장과 인용 사이 공백

    button_html = ""
    button = item.get("button")
    if buttons_allowed and isinstance(button, dict):
        href = button_href(button["seed"])
        button_html = (f'<a class="mb-button" data-mb-button="1" '
                       f'href="{esc(href)}">{esc(button["label"])}</a>')

    ref_html = ""
    if src_no is not None:
        ref_html = (f'<a class="mb-src-ref" data-mb-src-ref="1" '
                    f'href="#mb-src-{src_no}">출처 {src_no}</a>')

    return (f'<li class="mb-item" data-mb-item="1">'
            f'<span class="mb-num">{index:02d}</span>'
            f'<div class="mb-item-body"><p class="mb-item-title">{title_html}</p>'
            f'<p class="mb-item-sentence">{sentence}{quote_html}{ref_html}</p>'
            f'{button_html}</div></li>')


def render_list(heading: str, items: list[dict], kind: str,
                buttons_allowed: bool,
                src_numbers: dict[str, int] | None = None) -> str:
    if not items:
        return ""
    rows = "".join(
        render_item(item, i + 1, buttons_allowed,
                    None if src_numbers is None
                    else src_numbers.get(_canon(item.get("anchor"))))
        for i, item in enumerate(items))
    return (f'<section class="mb-list" data-mb-list="{esc(kind)}">'
            f'<h2 class="mb-heading">{esc(heading)}</h2>'
            f'<ol class="mb-items">{rows}</ol></section>')


def render_sections(sections: list) -> str:
    out: list[str] = []
    for sec in sections or []:
        if not isinstance(sec, dict):
            continue
        heading = sec.get("heading")
        if not isinstance(heading, str) or not heading.strip():
            continue
        items = sec.get("items")
        prose = sec.get("prose")
        if isinstance(items, list) and items:
            body = "".join(f'<li>{esc(x)}</li>' for x in items if str(x).strip())
            body = f'<ul class="mb-section-items">{body}</ul>'
        elif isinstance(prose, str) and prose.strip():
            body = "".join(f'<p>{esc(line)}</p>'
                           for line in prose.splitlines() if line.strip())
        else:
            continue  # 빈 섹션은 제목까지 통째로 뺀다
        out.append(f'<section class="mb-section" data-mb-section="1">'
                   f'<h2 class="mb-heading">{esc(heading)}</h2>{body}</section>')
    return "".join(out)


ROLE_LABEL = {"calendar": "캘린더", "email": "메일"}

# 결손(degraded)은 코드마다 이유가 다르다 — 뭉뚱그리면 무엇이 빈 것인지 알 수 없다.
DEGRADED_LINE = {
    "sent_folder_not_found": "보낸편지함을 찾지 못해 메일 회신 여부를 가리지 못했어요.",
    "sent_read_failed": "보낸편지함을 읽지 못해 메일 회신 여부를 가리지 못했어요.",
    "inbox_read_failed": "받은편지함 일부를 읽지 못해 메일 항목이 빠져 있을 수 있어요.",
}
DEGRADED_FALLBACK = "메일 일부를 읽지 못해 이 영역이 비어 있을 수 있어요."

# 형제 스킬 의존성 부재는 "계정 확인 실패" 가 아니다 — 처방이 다르므로 따로 말한다.
DEPS_MISSING_CODE = "sibling_deps_missing"
# 설치 스크립트를 가진 스킬만 그 경로를 말한다 — email 은 stdlib 라 없다(실측).
DEPS_INSTALLER = {"calendar": "calendar 의 install_skill_deps.py 를 먼저 실행하세요"}
DEPS_INSTALLER_FALLBACK = "그 스킬의 설치 안내를 먼저 따라 주세요"

SURFACED_SEVERITIES = ("error", "degraded")


def render_warnings(candidates: dict) -> str:
    """오류·결손을 빈 상태로 위장하지 않는다 — 한 줄로 말한다."""
    warns = [w for w in candidates.get("warnings") or []
             if isinstance(w, dict) and w.get("severity") in SURFACED_SEVERITIES]
    if not warns:
        return ""

    lines: list[str] = []
    roles: list[str] = []
    for warn in warns:
        if warn.get("severity") != "error":
            continue
        role = str(warn.get("role") or "")
        label = ROLE_LABEL.get(role, "일부")
        if str(warn.get("code") or "") == DEPS_MISSING_CODE:
            how = DEPS_INSTALLER.get(role, DEPS_INSTALLER_FALLBACK)
            line = f"{label} 스킬 의존성이 설치되지 않았어요 — {how}."
            if line not in lines:
                lines.append(line)
            continue
        if label not in roles:
            roles.append(label)
    if roles:
        lines.append(f'{"·".join(roles)} 계정 확인이 실패해 이 영역은 비어 있어요.')

    for warn in warns:
        if warn.get("severity") != "degraded":
            continue
        line = DEGRADED_LINE.get(str(warn.get("code") or ""), DEGRADED_FALLBACK)
        if line not in lines:
            lines.append(line)

    return "".join(f'<p class="mb-warning" data-mb-warning="1">{esc(line)}</p>'
                   for line in lines)


# --------------------------------------------------------------------------
# 출처 절 — candidates.json 만으로 코드가 만든다 (content 무접촉)
# --------------------------------------------------------------------------

ROLE_STATE_LABEL = {"ready": "준비됨", "not_configured": "미설정",
                    "error": "확인 실패", "sample": "샘플"}
SEVERITY_LABEL = {"error": "오류", "degraded": "결손", "warning": "경고"}


def _account_label(acc: dict) -> str:
    """`naver / work · me@example.com` — 어느 계정에서 가져왔는지 남긴다."""
    if str(acc.get("provider") or "") == "sample":
        return SAMPLE_ACCOUNT_LABEL
    provider = str(acc.get("provider") or "?")
    account = str(acc.get("account") or "default")
    login = str(acc.get("login") or "")
    base = f"{provider} / {account}"
    return f"{base} · {login}" if login else base


def _role_accounts(candidates: dict, role: str) -> list[dict]:
    role_info = (candidates.get("roles") or {}).get(role) or {}
    return [a for a in (role_info.get("accounts") or []) if isinstance(a, dict)]


def _source_account_label(candidates: dict, group: str, anchor: dict) -> str:
    """후보 앵커의 provider(+account)를 역할 계정 목록과 맞춰 주소까지 붙인다."""
    if str((anchor or {}).get("provider") or "") == "sample":
        return SAMPLE_ACCOUNT_LABEL
    role = "calendar" if group == "calendar" else "email"
    provider = str((anchor or {}).get("provider") or "")
    account = str((anchor or {}).get("account") or "")
    best = ""
    for acc in _role_accounts(candidates, role):
        if str(acc.get("provider") or "") != provider:
            continue
        # thread_status 의 anchor.account 는 **계정 주소**이고 check_env 의
        # account_id 는 별칭이다 — 둘 중 하나만 맞아도 같은 계정이다(실측).
        if account and account not in (str(acc.get("account") or ""),
                                       str(acc.get("login") or "")):
            continue
        best = _account_label(acc)
        break
    if best:
        return best
    return f"{provider} / {account}" if account else (provider or "계정 미상")


def _summary_lines(candidates: dict) -> list[str]:
    lines: list[str] = []
    cal = candidates.get("calendar") or {}
    mail = candidates.get("email") or {}
    roles = candidates.get("roles") or {}

    sample = is_sample(candidates)
    for role, label in (("calendar", "캘린더"), ("email", "메일")):
        if sample:
            # 상태 라벨('샘플')과 계정 라벨('샘플 · …')이 둘 다 붙으면 '샘플'이
            # 두 번 나온다 — 샘플일 때는 계정 라벨 하나로 끝낸다.
            lines.append(f"{label} — {SAMPLE_ACCOUNT_LABEL}")
            continue
        state = str((roles.get(role) or {}).get("state") or "?")
        accounts = _role_accounts(candidates, role)
        text = f"{label} — {ROLE_STATE_LABEL.get(state, state)}"
        if accounts:
            text += " · " + " · ".join(_account_label(a) for a in accounts)
        lines.append(text)

    lines.append(f"오늘 일정 {len(cal.get('today') or [])}건 · "
                 f"내일 일정 {len(cal.get('tomorrow') or [])}건 "
                 f"(내가 여는 자리 {len(cal.get('prep') or [])}건 · "
                 f"취소 {len(cal.get('cancelled') or [])}건)")
    lines.append(f"메일 후보 {len(mail.get('unreplied') or []) + len(mail.get('replied_then_new') or [])}건 "
                 f"(미회신 {len(mail.get('unreplied') or [])} · "
                 f"재회신 {len(mail.get('replied_then_new') or [])})")

    sections = candidates.get("sections") or {}
    lines.append("Sections — " + (" · ".join(f"{k} 있음" for k in sections)
                                  if sections else "없음"))

    warns = [w for w in candidates.get("warnings") or [] if isinstance(w, dict)]
    if not warns:
        lines.append("경고 없음")
    else:
        for warn in warns:
            sev = SEVERITY_LABEL.get(str(warn.get("severity") or ""),
                                     str(warn.get("severity") or "?"))
            who = str(warn.get("role") or "")
            acc = str(warn.get("account") or "")
            prov = str(warn.get("provider") or "")
            where = " / ".join(x for x in (prov, acc) if x)
            lines.append(f"{sev} — {who} {str(warn.get('code') or '')}"
                         + (f" ({where})" if where else ""))
    return lines


def _source_entry(candidates: dict, entry: dict, number: int,
                  used: bool) -> str:
    item = entry["item"]
    group = entry["group"]
    account = _source_account_label(candidates, group, item.get("anchor") or {})
    rows = [f'<p class="mb-src-head">{number:02d} · {esc(GROUP_LABEL[group])} · '
            f'{esc(account)}</p>']

    if group == "email":
        rows.append(f'<p>보낸 사람: {esc(item.get("from"))}</p>')
        rows.append(f'<p>제목: {esc(item.get("subject"))}</p>')
        rows.append(f'<p>날짜: {esc(format_moment(item.get("date")))}</p>')
        rows.append(f'<p>판정: {esc(item.get("verdict"))} · '
                    f'{esc(item.get("reason_code"))}</p>')
        body = item.get("body")
        if isinstance(body, str) and body.strip():
            rows.append(f'<p>본문 발췌: {esc(body)}</p>')
    else:
        anchor = item.get("anchor") or {}
        rows.append(f'<p>캘린더: {esc(anchor.get("calendar"))}</p>')
        rows.append(f'<p>제목: {esc(item.get("summary"))}</p>')
        rows.append(f'<p>시간: '
                    f'{esc(format_when(item.get("start"), item.get("end"), bool(item.get("all_day"))))}'
                    f'</p>')
        rows.append(f'<p>주최자: {esc(item.get("organizer") or "미상")}</p>')
        rows.append(f'<p>상태: {esc(item.get("status") or "")}</p>')

    if used:
        rows.append('<p class="mb-src-tag" data-mb-used="1">이 항목의 근거</p>')
    else:
        rows.append('<p class="mb-src-tag" data-mb-unused="1">표시 안 함</p>')

    return (f'<li class="mb-src" id="mb-src-{number}">' + "".join(rows)
            + '</li>')


def render_sources(candidates: dict, used_numbers: set[int]) -> str:
    """페이지 끝의 접이식 「출처」. content 는 읽지 않는다 — 무엇이 목록에
    쓰였는지만 번호로 받는다."""
    entries = folded_candidates(candidates)
    summary = "".join(f'<li>{esc(line)}</li>' for line in _summary_lines(candidates))
    body = "".join(_source_entry(candidates, entry, idx, idx in used_numbers)
                   for idx, entry in enumerate(entries, start=1))
    if not body:
        body = '<li class="mb-src">모은 원본이 없습니다.</li>'
    return ('<details class="mb-sources" data-mb-sources="1"><summary>출처</summary>'
            '<div class="mb-sources-body">'
            '<h3 class="mb-src-h">수집 요약</h3>'
            f'<ul class="mb-src-summary">{summary}</ul>'
            '<h3 class="mb-src-h">원본</h3>'
            f'<ol class="mb-src-list">{body}</ol>'
            '</div></details>')


def style_block() -> str:
    p = PALETTE
    return f"""<style>
:root {{ color-scheme: light; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: {p['bg']}; color: {p['ink_soft']};
  font-family: {SANS}; font-size: 15px; line-height: 1.7; }}
.mb-band {{ width: 100%; padding: 56px 24px; }}
.mb-band-top {{ background: {p['wash']}; border-bottom: 1px solid {p['hairline']}; }}
.mb-band-bottom {{ background: {p['bg']}; }}
.mb-inner {{ max-width: 860px; margin: 0 auto; }}
.mb-dateline {{ font-size: 13px; letter-spacing: .04em; color: {p['ink_soft']};
  margin: 0 0 10px; }}
.mb-headline {{ font-family: {SERIF}; font-size: 38px; line-height: 1.35;
  color: {p['ink']}; margin: 0 0 32px; font-weight: 600;
  word-break: keep-all; overflow-wrap: anywhere; }}
.mb-acts {{ display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 28px; }}
.mb-act {{ padding: 0 20px; border-left: 1px solid {p['hairline']}; }}
.mb-act:first-child {{ padding-left: 0; border-left: none; }}
.mb-act-time {{ font-weight: 600; color: {p['ink']}; font-size: 13px;
  margin: 0 0 6px; }}
.mb-act-sentence {{ margin: 0; font-size: 14px;
  word-break: keep-all; overflow-wrap: anywhere; }}
.mb-list, .mb-section {{ margin-bottom: 44px; }}
.mb-heading {{ font-size: 13px; letter-spacing: .08em; color: {p['ink']};
  font-weight: 600; margin: 0 0 18px; }}
.mb-items {{ list-style: none; margin: 0; padding: 0; }}
.mb-item {{ display: flex; gap: 16px; padding: 16px 0;
  border-top: 1px solid {p['hairline']}; }}
.mb-num {{ color: {p['ink_grey']}; font-size: 13px; padding-top: 2px; }}
.mb-item-body {{ flex: 1; min-width: 0; }}
.mb-item-title {{ margin: 0 0 4px; color: {p['ink']}; font-weight: 600;
  word-break: keep-all; overflow-wrap: anywhere; }}
.mb-item-title a, .mb-title-link {{ color: {p['ink']}; text-decoration: none;
  border-bottom: 1px solid {p['hairline']}; }}
.mb-item-sentence {{ margin: 0; word-break: keep-all; overflow-wrap: anywhere; }}
.mb-source {{ border-bottom: 1px solid {p['ink_grey']}; }}
.mb-quote {{ color: {p['ink_soft']}; }}
.mb-button {{ display: inline-block; margin-top: 12px; padding: 9px 16px;
  border: 1px solid {p['accent']}; border-radius: 8px; background: {p['accent']};
  color: {p['bg']}; font-size: 13px; font-weight: 500; text-decoration: none; }}
.mb-button:hover {{ background: {p['accent_hover']}; border-color: {p['accent_hover']}; }}
.mb-quiet, .mb-warning {{ margin: 0 0 16px; }}
.mb-warning {{ color: {p['ink_soft']}; }}
.mb-none p {{ font-family: {SERIF}; font-size: 22px; color: {p['ink']};
  line-height: 1.6; margin: 0 0 12px;
  word-break: keep-all; overflow-wrap: anywhere; }}
.mb-section-items {{ margin: 0; padding-left: 18px; }}
.mb-sample {{ background: {p['ink']}; color: {p['bg']}; padding: 10px 24px;
  font-size: 13px; letter-spacing: .02em; text-align: center;
  word-break: keep-all; overflow-wrap: anywhere; }}
.mb-hint {{ margin: 16px 0 0; color: {p['ink_soft']}; font-size: 14px;
  word-break: keep-all; overflow-wrap: anywhere; }}
.mb-sources {{ margin-top: 8px; border-top: 1px solid {p['hairline']};
  padding-top: 16px; font-size: 13px; color: {p['ink_soft']}; }}
.mb-sources summary {{ cursor: pointer; letter-spacing: .08em;
  color: {p['ink']}; font-weight: 600; }}
.mb-src-h {{ font-size: 12px; letter-spacing: .08em; color: {p['ink']};
  font-weight: 600; margin: 20px 0 8px; }}
.mb-src-summary {{ margin: 0; padding-left: 18px; }}
.mb-src-list {{ margin: 0; padding: 0; list-style: none; }}
.mb-src {{ padding: 12px 0; border-top: 1px solid {p['hairline']};
  word-break: keep-all; overflow-wrap: anywhere; }}
.mb-src p {{ margin: 0 0 2px; }}
.mb-src-head {{ color: {p['ink']}; font-weight: 600; }}
.mb-src-tag {{ margin-top: 6px; color: {p['ink_grey']}; }}
.mb-src-ref {{ margin-left: 8px; font-size: 12px; color: {p['ink_grey']};
  text-decoration: none; border-bottom: 1px solid {p['hairline']}; }}
@media (max-width: 640px) {{
  .mb-band {{ padding: 36px 18px; }}
  .mb-headline {{ font-size: 28px; }}
  .mb-acts {{ grid-template-columns: 1fr; }}
  .mb-act {{ padding: 14px 0; border-left: none; border-top: 1px solid {p['hairline']}; }}
  .mb-act:first-child {{ border-top: none; padding-top: 0; }}
}}
</style>"""


def render_html(content: dict, candidates: dict,
                include_sources: bool = True) -> str:
    state = content["state"]
    buttons_allowed = bool((candidates.get("controls") or {}).get("buttons"))
    sample = is_sample(candidates)
    # 출처를 빼면 항목의 `출처 N` 링크도 함께 뺀다 — 대상 없는 링크를 남기지 않는다.
    src_numbers = source_numbers(candidates) if include_sources else None
    used_numbers: set[int] = set()
    if src_numbers is not None:
        for key in ("needs_attention", "resolved"):
            for item in content.get(key) or []:
                if not isinstance(item, dict):
                    continue
                num = src_numbers.get(_canon(item.get("anchor")))
                if num is not None:
                    used_numbers.add(num)

    dateline = format_date_line(content["date"])
    headline = esc(content["headline"])
    warning_html = render_warnings(candidates)

    if state == "none":
        notes = [n for n in (content.get("notes") or []) if str(n).strip()]
        second = esc(notes[0]) if notes else "연결된 캘린더와 메일이 없어 오늘은 여기까지예요."
        sources_html = (render_sources(candidates, used_numbers)
                        if include_sources else "")
        # 계정이 없다고 스킬이 스스로 샘플로 바꾸지 않는다 — 길만 알려 준다.
        hint = ("" if sample else
                f'<p class="mb-hint" data-mb-sample-hint="1">{esc(SAMPLE_HINT)}</p>')
        body = (f'<div class="mb-band mb-band-top"><div class="mb-inner mb-none" '
                f'data-mb-none="1"><p class="mb-dateline" data-mb-dateline="1">'
                f'{esc(dateline)}</p><p data-mb-headline="1">{headline}</p>'
                f'<p>{second}</p>{hint}{warning_html}{sources_html}</div></div>')
        return _document(dateline, state, body, sample=sample)

    top_parts = [f'<p class="mb-dateline" data-mb-dateline="1">{esc(dateline)}</p>',
                 f'<h1 class="mb-headline" data-mb-headline="1">{headline}</h1>']
    if state in ("all-ready", "calendar-only"):
        today = ((candidates.get("calendar") or {}).get("today")) or []
        top_parts.append(terrain_svg(today))
        acts = (content.get("acts") or [])[:3]
        if acts:
            cells = []
            for act in acts:
                start = act.get("start")
                label = (format_range(start, act.get("end")) if start
                         else str(act.get("time_range") or ""))
                cells.append(f'<div class="mb-act" data-mb-act="1">'
                             f'<p class="mb-act-time">{esc(label)}</p>'
                             f'<p class="mb-act-sentence">{esc(act["sentence"])}</p>'
                             f'</div>')
            top_parts.append(f'<div class="mb-acts">{"".join(cells)}</div>')

    needs = content.get("needs_attention") or []
    resolved = content.get("resolved") or []
    bottom_parts: list[str] = []
    if warning_html:
        bottom_parts.append(warning_html)
    if state == "calendar-only":
        bottom_parts.append('<p class="mb-quiet" data-mb-empty-lists="1">'
                            '메일은 아직 연결돼 있지 않아 오늘은 일정만 보여드려요.</p>')
    else:
        if not needs and not resolved:
            bottom_parts.append('<p class="mb-quiet" data-mb-empty-lists="1">'
                                '오늘 아침은 당신을 기다리는 일이 없어요.</p>')
        else:
            bottom_parts.append(render_list("지금 당신이 필요한 일", needs,
                                            "needs", buttons_allowed,
                                            src_numbers))
            bottom_parts.append(render_list("정리된 일", resolved, "resolved",
                                            False, src_numbers))
    bottom_parts.append(render_sections(content.get("sections") or []))
    if include_sources:
        bottom_parts.append(render_sources(candidates, used_numbers))

    body = (f'<div class="mb-band mb-band-top"><div class="mb-inner">'
            f'{"".join(top_parts)}</div></div>'
            f'<div class="mb-band mb-band-bottom"><div class="mb-inner">'
            f'{"".join(bottom_parts)}</div></div>')
    return _document(dateline, state, body, sample=sample)


def _document(dateline: str, state: str, body: str, *,
              sample: bool = False) -> str:
    # 샘플 띠는 페이지 **최상단 상시**다 — 접거나 스크롤로 사라지지 않는다.
    banner = (f'<div class="mb-sample" data-mb-sample="1">{esc(SAMPLE_BANNER)}</div>'
              if sample else "")
    title = ("샘플 " if sample else "") + f"{dateline} 아침 브리핑"
    return ("<!DOCTYPE html>\n"
            '<html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)}</title>{style_block()}</head>'
            f'<body data-mb-state="{esc(state)}">{banner}{body}</body></html>\n')


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _fail(code: str, detail: str = "", rc: int = 2) -> int:
    print(json.dumps({"status": "error", "error": code, "detail": detail},
                     ensure_ascii=False), file=sys.stderr)
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="아침 브리핑 HTML 렌더")
    ap.add_argument("--content", required=True)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-sources", action="store_true",
                    help="페이지 끝 「출처」 절을 뺀다(파일 공유 시 노출 축소)")
    args = ap.parse_args(argv)

    try:
        content = json.loads(Path(args.content).read_text(encoding="utf-8"))
        candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _fail("input_unreadable", str(exc)[:300])

    try:
        validate_content(content)
        page = render_html(content, candidates,
                           include_sources=not args.no_sources)
    except ContentError as exc:
        return _fail(exc.code, exc.detail)

    try:
        Path(args.out).write_text(page, encoding="utf-8")
    except OSError as exc:
        # 대체 경로로 조용히 넘어가지 않는다 (no-silent-fallback).
        return _fail("write_failed", f"{args.out}: {exc}", rc=3)

    print(json.dumps({"status": "ok", "path": args.out, "state": content["state"],
                      "sources": not args.no_sources,
                      "bytes": len(page.encode("utf-8"))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
