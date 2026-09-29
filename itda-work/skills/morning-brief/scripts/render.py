#!/usr/bin/env python3
"""itda-work morning-brief: render.py — candidates.json + content.json → 단일 HTML.

LLM 은 HTML 을 쓰지 않는다. 브리핑의 목록(오늘 일정·일정별 관련 메일·일정과 무관한 미회신)은
candidates.json 에서 코드가 그리고, content.json 에서는 **미회신 메일의 요약 문장**(과 선택적 버튼)만
가져온다(itda-work/skills#38). 이스케이프·링크 화이트리스트·버튼 href 인코딩·요일·시간 표기도 여기서
결정론으로 만든다.

`--style` 로 보고서 모양을 고른다(itda-work/skills#42) — timeline(기본)·memo·desk·print. 네 스타일은 같은 조각을
다른 자리에 놓을 뿐 내용(일정·관련 메일·미회신·대량 발송·날씨·출처)과 `data-mb-*` 표지가 같다. `verify.py` 는 스타일과
무관하게 같은 검사를 한다.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

SCHEMA_VERSION = 2
SAMPLE_BANNER = "샘플 브리핑 — 실제 계정 데이터가 아니에요"
SAMPLE_ACCOUNT_LABEL = "샘플 · 에이전트 생성 시나리오"
SAMPLE_HINT = "샘플 브리핑을 요청하면 형식을 미리 볼 수 있어요."
BUTTON_ORIGIN = "https://claude.ai"
BUTTON_PATH = "/new"
MAX_SUMMARY_CHARS = 200
MAX_LABEL_WORDS = 5
MAX_SEED_CHARS = 600

WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")
READY_STATES = ("ready", "sample")

# 메일 회신 판정 표기 — gather.judge_threads 의 값.
VERDICT_LABEL = {
    "unreplied": "미회신",
    "replied_then_new": "답장 뒤 새 메일",
    "replied": "회신함",
    "unknown": "회신 여부 모름",
    "bulk": "단체 발송",      # 관련 메일에 주소로 붙은 대량 메일(itda-work/skills#39)
}

# 보고서 스타일(itda-work/skills#42). 내용(목록·요약·출처)은 같고 배치와 표면만 다르다.
#   timeline — 세로 시간축(기본). 일정 길이에 비례한 블록, 1시간 이상 빈 시간, 관련 메일은 일정 옆(좁으면 아래).
#   memo     — 결재 메모처럼 위에서 아래로 정독. 명조 제목, 관련 메일은 일정 아래 들여쓰기.
#   desk     — 운영 표. 지표 띠·표·회신 상태 칩, 고정폭 숫자. 좁은 화면에서는 표 행이 블록으로 접힌다.
#   print    — A4 한 장 두 단. 검은 머리띠·굵은 시간, 왼쪽 일정·오른쪽 메일. 인쇄 CSS(@page A4).
STYLES = ("timeline", "memo", "desk", "print")
DEFAULT_STYLE = "timeline"

# 웹 폰트는 싣지 않는다(외부 자산 0) — 시스템 글꼴만.
SANS = ('-apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", '
        '"Noto Sans CJK KR", "Noto Sans KR", system-ui, sans-serif')
SERIF = ('"Apple Myungjo", AppleMyungjo, Batang, "Noto Serif CJK KR", "Noto Serif KR", serif')
MONO = 'ui-monospace, "SF Mono", Menlo, Consolas, "D2Coding", monospace'

# 색 토큰 — 스타일마다 라이트·다크 한 벌. 인쇄는 늘 라이트다.
# bg 바탕 · panel 면 · wash 옅은 면 · ink 본문 · soft 보조 · faint 흐린 글 · line 구분선 · accent 강조 · accent-ink 강조 위 글자
# alert(-bg) 미회신 · ok(-bg) 회신함 · block 일정 블록 · rail 시간축 · band(-ink) 머리띠
TOKENS: dict[str, dict[str, dict[str, str]]] = {
    "timeline": {
        "light": {"bg": "#FFFFFF", "panel": "#FFFFFF", "wash": "#F2F7F6", "ink": "#132A2A", "soft": "#3F5757",
                  "faint": "#6F8785", "line": "#DCE7E6", "accent": "#0F766E", "accent-ink": "#FFFFFF",
                  "alert": "#B54708", "alert-bg": "#FFF6EE", "ok": "#2F7A55", "ok-bg": "#E9F6EF",
                  "block": "#E7F4F2", "rail": "#CFE7E4", "band": "#132A2A", "band-ink": "#FFFFFF"},
        "dark": {"bg": "#0E1717", "panel": "#132121", "wash": "#152624", "ink": "#E2EEEC", "soft": "#A9C2BF",
                 "faint": "#7F9A97", "line": "#253B39", "accent": "#5EC4B6", "accent-ink": "#08201D",
                 "alert": "#F4A261", "alert-bg": "#2A1D12", "ok": "#7FD1A4", "ok-bg": "#12291D",
                 "block": "#16302D", "rail": "#24413E", "band": "#E2EEEC", "band-ink": "#0E1717"},
    },
    "memo": {
        "light": {"bg": "#FCFCFA", "panel": "#FFFFFF", "wash": "#F1F3F6", "ink": "#1B2230", "soft": "#3A4250",
                  "faint": "#6A7280", "line": "#E3E5E8", "accent": "#1F3A5F", "accent-ink": "#FFFFFF",
                  "alert": "#9A3412", "alert-bg": "#FBEFE8", "ok": "#4B6B3A", "ok-bg": "#EEF4EA",
                  "block": "#F1F3F6", "rail": "#C9D2DE", "band": "#1F3A5F", "band-ink": "#FFFFFF"},
        "dark": {"bg": "#14171C", "panel": "#1A1E25", "wash": "#20252E", "ink": "#E4E7EC", "soft": "#B7BEC9",
                 "faint": "#8B93A0", "line": "#2B3039", "accent": "#A9C1E3", "accent-ink": "#14171C",
                 "alert": "#F2A07B", "alert-bg": "#2C1D16", "ok": "#9CC48A", "ok-bg": "#1B2618",
                 "block": "#20252E", "rail": "#3A4452", "band": "#A9C1E3", "band-ink": "#14171C"},
    },
    "desk": {
        "light": {"bg": "#F4F6F8", "panel": "#FFFFFF", "wash": "#F2F4F7", "ink": "#1C2330", "soft": "#475467",
                  "faint": "#667085", "line": "#DDE2E8", "accent": "#2F4B7C", "accent-ink": "#FFFFFF",
                  "alert": "#B42318", "alert-bg": "#FEE4E2", "ok": "#085D3A", "ok-bg": "#DCFAE6",
                  "block": "#FAFBFC", "rail": "#EAECF0", "band": "#1C2330", "band-ink": "#FFFFFF"},
        "dark": {"bg": "#0F1217", "panel": "#171B22", "wash": "#1E232C", "ink": "#E6E9EF", "soft": "#B4BCC8",
                 "faint": "#8A94A3", "line": "#2A303A", "accent": "#9DB5E0", "accent-ink": "#0F1217",
                 "alert": "#FDA29B", "alert-bg": "#3A1714", "ok": "#75E0A7", "ok-bg": "#0F2E1F",
                 "block": "#1B2029", "rail": "#232933", "band": "#E6E9EF", "band-ink": "#0F1217"},
    },
    "print": {
        "light": {"bg": "#FFFFFF", "panel": "#FAFAFB", "wash": "#F1F1F3", "ink": "#0E0E10", "soft": "#4A4A52",
                  "faint": "#6B6B75", "line": "#E4E4E7", "accent": "#1D4ED8", "accent-ink": "#FFFFFF",
                  "alert": "#C2410C", "alert-bg": "#FFF1E8", "ok": "#6B6B75", "ok-bg": "#F1F1F3",
                  "block": "#FAFAFB", "rail": "#0E0E10", "band": "#0E0E10", "band-ink": "#FFFFFF"},
        "dark": {"bg": "#111114", "panel": "#18181C", "wash": "#222228", "ink": "#EDEDF0", "soft": "#C4C4CC",
                 "faint": "#9A9AA3", "line": "#2C2C33", "accent": "#8FB0FF", "accent-ink": "#111114",
                 "alert": "#FB923C", "alert-bg": "#2B1A0E", "ok": "#9A9AA3", "ok-bg": "#222228",
                 "block": "#18181C", "rail": "#EDEDF0", "band": "#000000", "band-ink": "#FFFFFF"},
    },
}

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


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def format_date_line(iso_date: str) -> str:
    """`9월 3일 목요일` — 요일은 코드가 낸다."""
    try:
        d = date.fromisoformat(iso_date)
    except (TypeError, ValueError) as exc:
        raise ContentError("bad_date", str(iso_date)) from exc
    return f"{d.month}월 {d.day}일 {WEEKDAYS[d.weekday()]}요일"


def format_month_day(d: date) -> str:
    return f"{d.month}월 {d.day}일"


def format_time(dt: datetime) -> str:
    """`오전 9:30` / `오후 1시`."""
    ampm = "오전" if dt.hour < 12 else "오후"
    hour12 = dt.hour % 12 or 12
    if dt.minute == 0:
        return f"{ampm} {hour12}시"
    return f"{ampm} {hour12}:{dt.minute:02d}"


def _parse_dt(raw) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_date(raw) -> date | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def format_range(start: str, end: str | None) -> str:
    s = _parse_dt(start)
    if s is None:
        return ""
    e = _parse_dt(end) if end else None
    if e is None or e <= s:
        return f"{format_time(s)}"
    return f"{format_time(s)} – {format_time(e)}"


def format_when(start, end, all_day: bool) -> str:
    """출처 원본의 시각 한 줄 — `9월 3일 오전 9:30 – 오전 10시` / `9월 3일 종일`.
    읽을 수 없는 값은 그대로 둔다(지어내지 않는다)."""
    if all_day:
        sd = _parse_date(start)
        if sd is None:
            return str(start or "")
        ed = _parse_date(end)
        # 종일 일정의 끝은 배타다 — 마지막 날을 하루 당겨 포함 범위로 쓴다.
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
    """메일 수신 시각 — `9월 2일 오후 7:12`. 자유 표기(샘플 "어제 17:40")는 그대로."""
    dt = _parse_dt(raw)
    if dt is None:
        return str(raw or "")
    return f"{format_month_day(dt.date())} {format_time(dt)}"


def event_when(ev: dict) -> str:
    """오늘 일정 목록의 시간 칸. 종일은 `종일`, 며칠짜리는 기간을 붙인다."""
    if ev.get("all_day"):
        sd, ed = _parse_date(ev.get("start")), _parse_date(ev.get("end"))
        if sd and ed and ed - sd > timedelta(days=1):
            return format_when(ev.get("start"), ev.get("end"), True)
        return "종일"
    s, e = _parse_dt(ev.get("start")), _parse_dt(ev.get("end"))
    if s and e and e.date() != s.date():
        return format_when(ev.get("start"), ev.get("end"), False)
    return format_range(ev.get("start") or "", ev.get("end"))


def sender_name(raw: str) -> str:
    """`김지현 <jihyun@…>` → `김지현`. 이름이 없으면 주소 그대로."""
    text = (raw or "").split(",")[0].strip()
    if "<" in text:
        name = text[:text.find("<")].strip().strip('"').strip()
        if name:
            return name
        return text[text.find("<") + 1:text.rfind(">")].strip()
    return text


def brief_date(candidates: dict) -> str:
    gen = _parse_dt(candidates.get("generated_at"))
    if gen is None:
        raise ContentError("bad_generated_at", str(candidates.get("generated_at")))
    return gen.date().isoformat()


def role_state(candidates: dict, role: str) -> str:
    return str(((candidates.get("roles") or {}).get(role) or {}).get("state") or "")


def page_state(candidates: dict) -> str:
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
# 출처 번호 — 앵커 하나에 번호 하나
# --------------------------------------------------------------------------

def source_entries(candidates: dict) -> list[dict]:
    """출처 절의 항목 순서: 오늘 일정 → 각 일정의 관련 메일 → 일정과 무관한 미회신.
    같은 앵커(여러 일정에 걸린 같은 메일)는 처음 한 번만 센다. `verify.source_entries` 와 같은 규칙이다."""
    out: list[dict] = []
    seen: set[str] = set()

    def add(group: str, item) -> None:
        if not isinstance(item, dict):
            return
        anchor = item.get("anchor")
        if not isinstance(anchor, dict) or not anchor:
            return
        key = canon(anchor)
        if key in seen:
            return
        seen.add(key)
        out.append({"group": group, "item": item, "key": key})

    events = (candidates.get("calendar") or {}).get("today") or []
    for ev in events:
        add("calendar", ev)
    for ev in events:
        for mail in (ev.get("related") or []) if isinstance(ev, dict) else []:
            add("email", mail)
    for mail in (candidates.get("email") or {}).get("unreplied") or []:
        add("email", mail)
    return out


def source_numbers(candidates: dict) -> dict[str, int]:
    return {e["key"]: i for i, e in enumerate(source_entries(candidates), start=1)}


# --------------------------------------------------------------------------
# content 검증
# --------------------------------------------------------------------------

def _words(text: str) -> int:
    return len([w for w in str(text).split() if w])


def validate_content(content: object, candidates: dict) -> dict[str, dict]:
    """content.json → 앵커 키별 요약. 미회신 후보마다 요약이 **정확히 하나**여야 한다."""
    if not isinstance(content, dict):
        raise ContentError("content_not_object")
    if content.get("schema_version") != SCHEMA_VERSION:
        raise ContentError("schema_version", str(content.get("schema_version")))
    rows = content.get("summaries")
    if not isinstance(rows, list):
        raise ContentError("missing_summaries")
    wanted = {canon(m.get("anchor")): m for m in
              (candidates.get("email") or {}).get("unreplied") or []
              if isinstance(m, dict) and isinstance(m.get("anchor"), dict)}
    out: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("anchor"), dict):
            raise ContentError("missing_anchor", str(row)[:80])
        key = canon(row["anchor"])
        if key not in wanted:
            raise ContentError("summary_unknown_anchor", str(row["anchor"].get("uid")))
        if key in out:
            raise ContentError("summary_duplicate", str(row["anchor"].get("uid")))
        text = row.get("summary")
        if not isinstance(text, str) or not text.strip():
            raise ContentError("missing_summary", str(row["anchor"].get("uid")))
        if len(text) > MAX_SUMMARY_CHARS:
            raise ContentError("summary_too_long", text[:40])
        button = row.get("button")
        if button is not None:
            if not isinstance(button, dict):
                raise ContentError("bad_button", str(row["anchor"].get("uid")))
            label, seed = button.get("label"), button.get("seed")
            if not isinstance(label, str) or not label.strip():
                raise ContentError("missing_button_label", str(row["anchor"].get("uid")))
            if _words(label) > MAX_LABEL_WORDS:
                raise ContentError("button_label_too_long", label)
            if not isinstance(seed, str) or not seed.strip():
                raise ContentError("missing_button_seed", str(row["anchor"].get("uid")))
            if len(seed) > MAX_SEED_CHARS:
                raise ContentError("button_seed_too_long", str(row["anchor"].get("uid")))
        out[key] = row
    missing = [str(m["anchor"].get("uid")) for k, m in wanted.items() if k not in out]
    if missing:
        raise ContentError("summary_missing", ", ".join(missing))
    return out


# --------------------------------------------------------------------------
# HTML 조립
# --------------------------------------------------------------------------

def button_href(seed: str) -> str:
    query = urlencode({"q": seed, "surface": "cowork", "composer": "mini"})
    return f"{BUTTON_ORIGIN}{BUTTON_PATH}?{query}"


class Refs:
    """출처 번호표와, 페이지가 실제로 링크한 번호(「이 항목의 근거」 표시용)."""

    def __init__(self, numbers: dict[str, int] | None) -> None:
        self.numbers = numbers
        self.used: set[int] = set()


def _ref(src: Refs | None, anchor) -> str:
    if src is None or src.numbers is None:
        return ""
    no = src.numbers.get(canon(anchor))
    if no is None:
        return ""
    src.used.add(no)
    return (f'<a class="mb-src-ref" data-mb-src-ref="1" '
            f'href="#mb-src-{no}">출처 {no}</a>')


def _badge(verdict: str) -> str:
    label = VERDICT_LABEL.get(verdict, verdict or "회신 여부 모름")
    return f'<span class="mb-badge mb-badge-{esc(verdict)}">{esc(label)}</span>'


def _attendee_text(ev: dict) -> str:
    n = ev.get("attendee_count")
    if n is None:
        return "참석 인원 미상"
    if not n:
        return ""
    return f"참석 {n}명 이상" if ev.get("attendees_truncated") else f"참석 {n}명"


def _is_cancelled(ev: dict) -> bool:
    return str(ev.get("status") or "").upper() == "CANCELLED"


def _event_title(ev: dict, src: Refs | None) -> str:
    tag = ' <span class="mb-tag">취소</span>' if _is_cancelled(ev) else ""
    return (f'<p class="mb-event-title">{esc(ev.get("summary"))}{tag}'
            f'{_ref(src, ev.get("anchor"))}</p>')


def _event_meta(ev: dict, *extra: str) -> str:
    """일정 한 줄 부가 정보 — `extra`(시간·길이) 뒤에 장소·참석 인원. 빈 값은 뺀다."""
    parts = [x for x in (*extra, ev.get("location") or "", _attendee_text(ev)) if x]
    return f'<p class="mb-meta">{esc(" · ".join(parts))}</p>' if parts else ""


def _events(candidates: dict) -> list[dict]:
    return [e for e in (candidates.get("calendar") or {}).get("today") or [] if isinstance(e, dict)]


def _related_total(candidates: dict) -> int:
    return sum(len(ev.get("related") or []) for ev in _events(candidates))


def _related_block(candidates: dict, ev: dict, src: Refs | None) -> str:
    """한 일정의 관련 메일 목록 — 두 역할이 준비됐을 때만. 스타일마다 놓는 자리(아래·옆)만 다르다."""
    if page_state(candidates) != "all-ready":
        return ""
    rows = "".join(
        f'<li class="mb-mail" data-mb-related="1"><p class="mb-mail-subject">'
        f'{esc(m.get("subject"))}{_ref(src, m.get("anchor"))}</p>'
        f'{_mail_meta(m, str(m.get("match_detail") or ""), _acct_badge(candidates, m.get("anchor")))}</li>'
        for m in ev.get("related") or [] if isinstance(m, dict))
    more = int(ev.get("related_more") or 0)
    more_html = (f'<p class="mb-more" data-mb-more="1">관련 메일 {more}통은 더 있어요.</p>' if more else "")
    if not rows and not more_html:
        return ""
    return (f'<ul class="mb-mails">{rows}</ul>' if rows else "") + more_html


def _related_empty_line(candidates: dict) -> str:
    """두 역할이 준비됐고 일정이 있는데 어느 일정에도 관련 메일이 없으면 한 줄로 말한다."""
    if page_state(candidates) != "all-ready":
        return ""
    events = _events(candidates)
    if not events or _related_total(candidates) or any(ev.get("related_more") for ev in events):
        return ""
    return '<p class="mb-quiet" data-mb-empty="related">오늘 일정과 이어지는 메일이 없어요.</p>'


def _schedule_unavailable(candidates: dict) -> str:
    """일정을 못 그리는 경우의 한 줄 — 미연결·오류·빈 날. 그릴 수 있으면 빈 문자열."""
    state = role_state(candidates, "calendar")
    if state not in READY_STATES:
        line = "일정을 가져오지 못했어요." if state == "error" else "캘린더가 연결돼 있지 않아요."
        return f'<p class="mb-quiet" data-mb-empty="schedule">{esc(line)}</p>'
    if not _events(candidates):
        return '<p class="mb-quiet" data-mb-empty="schedule">오늘은 잡힌 일정이 없어요.</p>'
    return ""


def _schedule_count(candidates: dict) -> str:
    if role_state(candidates, "calendar") not in READY_STATES:
        return ""
    text = f"{len(_events(candidates))}건"
    if page_state(candidates) == "all-ready":
        text += f" · 관련 메일 {_related_total(candidates)}통"
    return f'<span class="mb-count">{esc(text)}</span>'


def _schedule_section(candidates: dict, inner: str, cls: str = "") -> str:
    head = f'<h2 class="mb-heading">오늘 일정{_schedule_count(candidates)}</h2>'
    body = _schedule_unavailable(candidates) or (inner + _related_empty_line(candidates))
    return f'<section class="mb-part{cls}" data-mb-part="schedule">{head}{body}</section>'


def _when_parts(ev: dict) -> tuple[str, str]:
    """목록형 스타일의 시간 칸 — (굵은 줄, 작은 줄). 같은 날 시간 일정은 `오전 11시` / `오후 1시까지`."""
    if ev.get("all_day"):
        return event_when(ev), ""
    s, e = _parse_dt(ev.get("start")), _parse_dt(ev.get("end"))
    if s is None:
        return str(ev.get("start") or ""), ""
    if e is not None and e.date() != s.date():
        return event_when(ev), ""
    if e is None or e <= s:
        return format_time(s), ""
    return format_time(s), f"{format_time(e)}까지"


def schedule_list(candidates: dict, src: Refs | None) -> str:
    """메모·인쇄 스타일 — 시간 칸 옆에 일정, 그 아래 관련 메일."""
    rows = []
    for ev in _events(candidates):
        main, sub = _when_parts(ev)
        sub_html = f'<small>{esc(sub)}</small>' if sub else ""
        cls = "mb-event mb-cancelled" if _is_cancelled(ev) else "mb-event"
        rows.append(f'<li class="{cls}" data-mb-event="1"><p class="mb-when">{esc(main)}{sub_html}</p>'
                    f'<div class="mb-event-body">{_event_title(ev, src)}{_event_meta(ev)}'
                    f'{_related_block(candidates, ev, src)}</div></li>')
    return _schedule_section(candidates, f'<ol class="mb-events">{"".join(rows)}</ol>')


def _hhmm(dt: datetime) -> str:
    return f"{dt.hour:02d}:{dt.minute:02d}"


def duration_text(minutes: int) -> str:
    """`30분` / `2시간` / `1시간 30분`."""
    if minutes < 60:
        return f"{minutes}분"
    h, m = divmod(minutes, 60)
    return f"{h}시간 {m}분" if m else f"{h}시간"


def _span_minutes(ev: dict) -> int | None:
    if ev.get("all_day"):
        return None
    s, e = _parse_dt(ev.get("start")), _parse_dt(ev.get("end"))
    if s is None or e is None or e <= s:
        return None
    return int((e - s).total_seconds() // 60)


# 시간축 블록 높이 — 1분에 0.9px, 짧아도 52px, 길어도 270px(5시간)에서 멈춘다.
TL_PX_PER_MIN = 0.9
TL_MIN_PX = 52
TL_MAX_PX = 270
TL_GAP_MIN = 60   # 이만큼 비면 「빈 시간」 줄


def block_height(minutes: int | None) -> int:
    if minutes is None:
        return TL_MIN_PX
    return max(TL_MIN_PX, min(TL_MAX_PX, round(minutes * TL_PX_PER_MIN)))


def schedule_timeline(candidates: dict, src: Refs | None) -> str:
    """타임라인 스타일 — 세로 시간축. 순서는 candidates 그대로(gather 가 종일 먼저·시작 시각순으로 정렬한다).

    시간 일정 사이가 1시간 이상 비면 「빈 시간」 줄을 넣는다. 취소된 일정은 시간을 차지하지 않는다 — 그 앞뒤 빈 시간을
    나눠 말할 뿐 빈 시간을 줄이지 않는다."""
    rows: list[str] = []
    busy_until: datetime | None = None   # 빈 시간을 재기 시작할 시각
    for ev in _events(candidates):
        s = None if ev.get("all_day") else _parse_dt(ev.get("start"))
        cancelled = _is_cancelled(ev)
        cls = "mb-tl-row mb-event" + (" mb-cancelled" if cancelled else "") + ("" if s else " mb-tl-allday")
        if s is not None and busy_until is not None:
            gap = int((s - busy_until).total_seconds() // 60)
            if gap >= TL_GAP_MIN:
                rows.append(f'<li class="mb-tl-row mb-tl-gap"><span class="mb-tl-t">{_hhmm(busy_until)}</span>'
                            f'<span class="mb-tl-rail" aria-hidden="true"></span>'
                            f'<p class="mb-tl-free">빈 시간 {esc(duration_text(gap))}</p></li>')
        minutes = _span_minutes(ev)
        label = _hhmm(s) if s is not None else "종일"
        extra = [w for w in (event_when(ev),) if w and w != label] + ([duration_text(minutes)] if minutes else [])
        mails = _related_block(candidates, ev, src)
        rows.append(f'<li class="{cls}" data-mb-event="1"><span class="mb-tl-t">{esc(label)}</span>'
                    f'<span class="mb-tl-rail" aria-hidden="true"></span>'
                    f'<div class="mb-tl-blk" style="min-height:{block_height(minutes) if s else TL_MIN_PX}px">'
                    f'{_event_title(ev, src)}{_event_meta(ev, *extra)}</div>'
                    f'<div class="mb-tl-mails">{mails}</div></li>')
        if s is not None:
            e = _parse_dt(ev.get("end"))
            end = s if cancelled or e is None or e <= s else e
            busy_until = end if busy_until is None or end > busy_until else busy_until
    return _schedule_section(candidates, f'<ol class="mb-tl">{"".join(rows)}</ol>')


def schedule_table(candidates: dict, src: Refs | None) -> str:
    """데스크 스타일 — 일정 행 아래에 관련 메일 하위 행. 좁은 화면에서는 CSS 가 행을 블록으로 접는다."""
    rows: list[str] = []
    for ev in _events(candidates):
        minutes = _span_minutes(ev)
        cls = "mb-event mb-cancelled" if _is_cancelled(ev) else "mb-event"
        rows.append(f'<tr class="{cls}" data-mb-event="1"><td class="mb-when">{esc(event_when(ev))}</td>'
                    f'<td>{_event_title(ev, src)}</td><td>{_event_meta(ev)}</td>'
                    f'<td class="mb-dur">{esc(duration_text(minutes) if minutes else "")}</td></tr>')
        if page_state(candidates) != "all-ready":
            continue
        for m in ev.get("related") or []:
            if not isinstance(m, dict):
                continue
            detail = str(m.get("match_detail") or "")
            rows.append(f'<tr class="mb-mail mb-sub" data-mb-related="1"><td class="mb-sub-mark" aria-hidden="true">↳</td>'
                        f'<td><p class="mb-mail-subject">{esc(m.get("subject"))}{_ref(src, m.get("anchor"))}</p>'
                        + (f'<p class="mb-meta">{esc(detail)}</p>' if detail else "")
                        + f'</td><td>{_mail_meta(m, acct=_acct_badge(candidates, m.get("anchor")))}</td>'
                        f'<td></td></tr>')
        more = int(ev.get("related_more") or 0)
        if more:
            rows.append(f'<tr class="mb-sub"><td></td><td colspan="3"><p class="mb-more" data-mb-more="1">'
                        f'관련 메일 {more}통은 더 있어요.</p></td></tr>')
    table = ('<div class="mb-tw"><table class="mb-table"><thead><tr><th scope="col">시간</th>'
             '<th scope="col">일정 · 관련 메일</th><th scope="col">장소 · 보낸 사람</th><th scope="col">길이</th>'
             f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    return _schedule_section(candidates, table, " mb-panel")


def _mail_meta(mail: dict, extra: str = "", acct: str = "") -> str:
    parts = [acct, esc(sender_name(str(mail.get("from") or ""))),
             esc(format_moment(mail.get("date"))), _badge(str(mail.get("verdict") or ""))]
    if extra:
        parts.append(esc(extra))
    return f'<p class="mb-meta">{" · ".join(p for p in parts if p)}</p>'


BULK_LABEL = (("newsletter", "뉴스레터"), ("notice", "자동 알림"), ("billing", "결제·청구"), ("ad", "광고"))


def bulk_count(email: dict) -> int:
    bulk = email.get("bulk") if isinstance(email, dict) else None
    try:
        return int((bulk or {}).get("count") or 0)
    except (TypeError, ValueError, AttributeError):
        return 0


def bulk_pointer(email: dict) -> str:
    """미회신 절 끝의 한 줄 — 대량 발송 메일을 목록·요약에서 빼고 아래 절에 모았다는 사실. 0통이면 없다."""
    n = bulk_count(email)
    if not n:
        return ""
    return (f'<p class="mb-more" data-mb-bulk-pointer="1">대량 발송 메일 {n}통은 목록과 요약에서 빼고 '
            '아래에 따로 모았어요.</p>')


def multi_account(candidates: dict) -> bool:
    """메일 계정이 둘 이상인가 — 그때만 계정 배지·「대량 발송 메일」 계정 소절을 단다(itda-work/skills#41).

    계정이 하나면 어느 계정인지 묻는 사람이 없다 — 배지와 소절 머리는 소음이다. 샘플은 계정이 하나다.
    `verify.multi_account` 와 같은 규칙이다."""
    if is_sample(candidates):
        return False
    return len(_role_accounts(candidates, "email")) > 1


def _acct_badge(candidates: dict, anchor) -> str:
    """메일이 온 계정(accounts_list 의 이름) — 앵커의 `account` 그대로. 계정이 하나면 빈 문자열."""
    if not multi_account(candidates):
        return ""
    name = str((anchor or {}).get("account") or "") if isinstance(anchor, dict) else ""
    return f'<span class="mb-acct" data-mb-acct="{esc(name)}">{esc(name or "계정 미상")}</span>'


def _bulk_kinds(groups, h: str) -> str:
    """종류 → 발신자 → 제목. `h` 는 종류 머리의 태그(계정 소절 안이면 한 단계 아래)."""
    labels = dict(BULK_LABEL)
    blocks: list[str] = []
    for group in groups or []:
        if not isinstance(group, dict):
            continue
        rows: list[str] = []
        for snd in group.get("senders") or []:
            if not isinstance(snd, dict):
                continue
            subjects = "".join(
                f'<li class="mb-bulk-subject" data-mb-bulk-subject="1">{esc(x.get("subject"))}'
                f'<span class="mb-bulk-date"> · {esc(format_moment(x.get("date")))}</span></li>'
                for x in snd.get("subjects") or [] if isinstance(x, dict))
            more = int(snd.get("more") or 0)
            more_html = (f'<li class="mb-bulk-subject mb-bulk-more">외 {more}통</li>' if more else "")
            rows.append(f'<li class="mb-mail" data-mb-bulk-sender="{int(snd.get("count") or 0)}">'
                        f'<p class="mb-mail-subject">{esc(snd.get("sender"))}'
                        f'<span class="mb-bulk-n"> · {int(snd.get("count") or 0)}통</span></p>'
                        f'<ul class="mb-bulk-subjects">{subjects}{more_html}</ul></li>')
        rest = int(group.get("senders_more") or 0)
        rest_html = (f'<p class="mb-more">그 밖 {rest}곳 {int(group.get("senders_more_count") or 0)}통</p>'
                     if rest else "")
        kind = str(group.get("kind") or "")
        blocks.append(f'<div class="mb-group" data-mb-bulk-kind="{esc(kind)}">'
                      f'<{h} class="mb-group-h">{esc(labels.get(kind, kind))} {int(group.get("count") or 0)}통</{h}>'
                      f'<ul class="mb-mails">{"".join(rows)}</ul>{rest_html}</div>')
    return "".join(blocks)


def render_bulk(candidates: dict, show_login: bool = True) -> str:
    """「대량 발송 메일」 절 — 계정 → 종류 → 발신자 → 제목 목록. 모델 요약 없이 candidates 그대로(#40·#41).

    메일 계정이 둘 이상이면 계정마다 소절(이름·주소·통수)을 두고 그 안에 종류를 묶는다. 하나면 소절 머리 없이
    종류가 바로 온다. 주소는 `show_login` 일 때만 — `--no-sources`(공유용 노출 축소)에서는 이름만 남긴다. 발신자 줄은 이름과 통수, 그 아래 최신 제목 몇 개와 "외 N통". 싣지 못한 발신자는 "그 밖 N곳 M통".
    """
    if role_state(candidates, "email") not in READY_STATES:
        return ""
    email = candidates.get("email") or {}
    n = bulk_count(email)
    if not n:
        return ""
    accounts = [a for a in (email.get("bulk") or {}).get("accounts") or [] if isinstance(a, dict)]
    if multi_account(candidates):
        body = "".join(
            f'<div class="mb-bulk-account" data-mb-bulk-account="{int(a.get("count") or 0)}">'
            f'<h3 class="mb-bulk-acct-h">{esc(a.get("account"))}'
            + (f'<span class="mb-bulk-login"> {esc(a.get("login"))}</span>'
               if show_login and a.get("login") else "")
            + f'<span class="mb-bulk-n"> · {int(a.get("count") or 0)}통</span></h3>'
            f'{_bulk_kinds(a.get("groups"), "h4")}</div>'
            for a in accounts)
    else:
        body = "".join(_bulk_kinds(a.get("groups"), "h3") for a in accounts)
    return (f'<section class="mb-part mb-bulk-part" data-mb-part="bulk" data-mb-bulk="{n}">'
            f'<h2 class="mb-heading">대량 발송 메일 {n}통</h2>'
            '<p class="mb-more">뉴스레터·자동 알림·결제·광고처럼 답장을 기다리지 않는 메일이에요. 제목만 모았어요.</p>'
            f'<div class="mb-bulk-body">{body}</div></section>')


def _unreplied_count(candidates: dict) -> str:
    if role_state(candidates, "email") not in READY_STATES:
        return ""
    email = candidates.get("email") or {}
    return f'<span class="mb-count">{len(email.get("unreplied") or [])}통</span>'


def _button_html(candidates: dict, row: dict) -> str:
    button = row.get("button")
    if not (candidates.get("controls") or {}).get("buttons") or not isinstance(button, dict):
        return ""
    return (f'<a class="mb-button" data-mb-button="1" '
            f'href="{esc(button_href(button["seed"]))}">{esc(button["label"])}</a>')


def render_unreplied(candidates: dict, summaries: dict[str, dict],
                     src: Refs | None, table: bool = False) -> str:
    """「일정과 무관한 미회신 메일」 — 제목·보낸 사람·요약(content). `table` 이면 데스크 스타일의 표."""
    state = role_state(candidates, "email")
    head = f'<h2 class="mb-heading">일정과 무관한 미회신 메일{_unreplied_count(candidates)}</h2>'
    cls = "mb-part mb-panel" if table else "mb-part"
    if state not in READY_STATES:
        line = ("메일을 가져오지 못했어요." if state == "error"
                else "메일이 연결돼 있지 않아요.")
        return (f'<section class="{cls}" data-mb-part="unreplied">{head}'
                f'<p class="mb-quiet" data-mb-empty="unreplied">{esc(line)}</p></section>')
    email = candidates.get("email") or {}
    mails = email.get("unreplied") or []
    more = int(email.get("unreplied_more") or 0)
    more_html = (f'<p class="mb-more" data-mb-more="1">목록에 싣지 못한 미회신 메일이 {more}통 더 있어요.</p>'
                 if more else "")
    more_html += bulk_pointer(email)
    if not mails:
        return (f'<section class="{cls}" data-mb-part="unreplied">{head}'
                '<p class="mb-quiet" data-mb-empty="unreplied">답을 기다리는 메일이 없어요.</p>'
                f'{more_html}</section>')
    rows = []
    for i, mail in enumerate(mails, start=1):
        row = summaries.get(canon(mail.get("anchor"))) or {}
        title = f'<p class="mb-item-title">{esc(mail.get("subject"))}{_ref(src, mail.get("anchor"))}</p>'
        meta = _mail_meta(mail, acct=_acct_badge(candidates, mail.get("anchor")))
        summary = f'<p class="mb-summary" data-mb-summary="1">{esc(row.get("summary"))}</p>'
        if table:
            rows.append(f'<tr class="mb-item" data-mb-item="1"><td class="mb-num mb-mono">{i:02d}</td>'
                        f'<td>{title}</td><td>{meta}</td><td>{summary}{_button_html(candidates, row)}</td></tr>')
        else:
            rows.append(f'<li class="mb-item" data-mb-item="1"><span class="mb-num">{i:02d}</span>'
                        f'<div class="mb-item-body">{title}{meta}{summary}'
                        f'{_button_html(candidates, row)}</div></li>')
    if table:
        body = ('<div class="mb-tw"><table class="mb-table mb-table-items"><thead><tr><th scope="col">#</th>'
                '<th scope="col">제목</th><th scope="col">보낸 사람 · 받은 때</th><th scope="col">요약</th>'
                f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    else:
        body = f'<ol class="mb-items">{"".join(rows)}</ol>'
    return f'<section class="{cls}" data-mb-part="unreplied">{head}{body}{more_html}</section>'


def section_texts(candidates: dict) -> list[tuple[str, list[str]]]:
    """날씨·환율 — 수집한 평문을 그대로(이름, 줄들). content 에서 받지 않는다(지어낸 절이 끼지 않게)."""
    out: list[tuple[str, list[str]]] = []
    for name, sec in (candidates.get("sections") or {}).items():
        text = sec.get("text") if isinstance(sec, dict) else None
        if not isinstance(text, str) or not text.strip():
            continue
        out.append((str(name), [line for line in text.splitlines() if line.strip()]))
    return out


def render_sections(candidates: dict, cls: str = "mb-section") -> str:
    """절마다 `data-mb-section` 한 번. 놓는 자리(머리 옆·메모 머리·표 위)는 스타일이 정한다."""
    return "".join(
        f'<div class="{cls}" data-mb-section="1"><h2 class="mb-heading">{esc(name)}</h2>'
        + "".join(f'<p>{esc(line)}</p>' for line in lines) + '</div>'
        for name, lines in section_texts(candidates))


ROLE_LABEL = {"calendar": "캘린더", "email": "메일"}

# 결손(degraded)은 코드마다 이유가 다르다 — 뭉뚱그리면 무엇이 빈 것인지 알 수 없다.
# gather.py 의 DEGRADED_EMAIL_CODES·DEGRADED_CALENDAR_CODES 와 같은 목록이다.
DEGRADED_LINE = {
    "sent_folder_not_found": "보낸편지함을 찾지 못해 메일 회신 여부를 가리지 못했어요.",
    "sent_read_failed": "보낸편지함을 읽지 못해 메일 회신 여부를 가리지 못했어요.",
    "inbox_truncated": "받은편지함 메일이 많아 최근 것만 봤어요 — 메일 항목이 빠져 있을 수 있어요.",
    "thread_headers_missing": "itda-hyve 가 옛 판이라 메일 회신 여부를 가리지 못했어요 — "
                              "0.9.3 이상으로 업데이트해 주세요.",
    "calendar_partial": "캘린더 일부를 읽지 못해 일정이 빠져 있을 수 있어요.",
    "calendar_truncated": "일정이 많아 일부만 가져왔어요 — 일정이 빠져 있을 수 있어요.",
    "recurrence_unsupported": "반복 일정 일부의 회차를 계산하지 못해 일정이 빠져 있을 수 있어요.",
    "attendees_missing": "itda-hyve 가 옛 판이라 일정 참석자를 몰라 관련 메일을 제목으로만 이었어요 — "
                         "0.9.3 이상으로 업데이트해 주세요.",
}
# 오류(error) 중 사용자가 할 일이 정해진 것 — 「계정 확인 실패」 한 줄로 뭉뚱그리지 않는다.
# 옛 itda-hyve(hyve_outdated)는 여기 없다 — 페이지에 한 줄로 말하는 대신 그리지 않는다(아래 HYVE_OUTDATED, #43).
ERROR_LINE: dict[str, str] = {}
# gather.py 의 HYVE_OUTDATED 와 같은 코드. gather 가 옛 판이면 candidates 를 쓰지 않지만, 옛 gather(0.11.0 이하)가
# 쓴 candidates 가 남아 있을 수 있다 — 그것으로 빈 브리핑을 그리지 않는다(itda-work/skills#43).
HYVE_OUTDATED = "hyve_outdated"
DEGRADED_FALLBACK = {
    "calendar": "캘린더 일부를 읽지 못해 이 영역이 비어 있을 수 있어요.",
    "email": "메일 일부를 읽지 못해 이 영역이 비어 있을 수 있어요.",
}
DEGRADED_FALLBACK_ANY = "일부를 읽지 못해 이 영역이 비어 있을 수 있어요."

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
        line = ERROR_LINE.get(str(warn.get("code") or ""))
        if line:
            if line not in lines:
                lines.append(line)
            continue
        label = ROLE_LABEL.get(str(warn.get("role") or ""), "일부")
        if label not in roles:
            roles.append(label)
    if roles:
        lines.insert(0, f'{"·".join(roles)} 계정 확인이 실패해 그 부분은 비어 있어요.')
    for warn in warns:
        if warn.get("severity") != "degraded":
            continue
        line = DEGRADED_LINE.get(
            str(warn.get("code") or ""),
            DEGRADED_FALLBACK.get(str(warn.get("role") or ""), DEGRADED_FALLBACK_ANY))
        if line not in lines:
            lines.append(line)
    return "".join(f'<p class="mb-warning" data-mb-warning="1">{esc(line)}</p>'
                   for line in lines)


# --------------------------------------------------------------------------
# 출처 절 — candidates.json 만으로 코드가 만든다
# --------------------------------------------------------------------------

ROLE_STATE_LABEL = {"ready": "준비됨", "not_configured": "미설정",
                    "error": "확인 실패", "sample": "샘플"}
SEVERITY_LABEL = {"error": "오류", "degraded": "결손", "warning": "경고"}


def _account_label(acc: dict) -> str:
    """`itda-hyve / naver · me@example.com` — 어느 계정에서 가져왔는지 남긴다."""
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
    if str((anchor or {}).get("provider") or "") == "sample":
        return SAMPLE_ACCOUNT_LABEL
    provider = str((anchor or {}).get("provider") or "")
    account = str((anchor or {}).get("account") or "")
    for acc in _role_accounts(candidates, group):
        if str(acc.get("provider") or "") != provider:
            continue
        if account and account not in (str(acc.get("account") or ""),
                                       str(acc.get("login") or "")):
            continue
        return _account_label(acc)
    return f"{provider} / {account}" if account else (provider or "계정 미상")


def _bulk_split(email: dict) -> str:
    """출처 요약의 계정별 대량 메일 수 — `naver 14 · google 3`. 계정이 둘 이상일 때만."""
    accounts = [a for a in ((email.get("bulk") or {}).get("accounts") or []) if isinstance(a, dict)]
    if len(accounts) < 2:
        return ""
    return " — " + " · ".join(f'{a.get("account")} {int(a.get("count") or 0)}' for a in accounts)


def _summary_lines(candidates: dict) -> list[str]:
    lines: list[str] = []
    events = (candidates.get("calendar") or {}).get("today") or []
    email = candidates.get("email") or {}
    sample = is_sample(candidates)
    for role, label in (("calendar", "캘린더"), ("email", "메일")):
        if sample:
            lines.append(f"{label} — {SAMPLE_ACCOUNT_LABEL}")
            continue
        state = role_state(candidates, role) or "?"
        accounts = _role_accounts(candidates, role)
        text = f"{label} — {ROLE_STATE_LABEL.get(state, state)}"
        if accounts:
            text += " · " + " · ".join(_account_label(a) for a in accounts)
        lines.append(text)
    n_related = sum(len(ev.get("related") or []) for ev in events if isinstance(ev, dict))
    lines.append(f"오늘 일정 {len(events)}건 · 일정별 관련 메일 {n_related}통 · "
                 f"일정과 무관한 미회신 {len(email.get('unreplied') or [])}통 · "
                 f"대량 발송 메일 {bulk_count(email)}통(미회신·요약에서 뺌{_bulk_split(email)})")
    sections = candidates.get("sections") or {}
    lines.append("Sections — " + (" · ".join(f"{k} 있음" for k in sections)
                                  if sections else "없음"))
    warns = [w for w in candidates.get("warnings") or [] if isinstance(w, dict)]
    if not warns:
        lines.append("경고 없음")
    for warn in warns:
        sev = SEVERITY_LABEL.get(str(warn.get("severity") or ""),
                                 str(warn.get("severity") or "?"))
        where = " / ".join(x for x in (str(warn.get("provider") or ""),
                                       str(warn.get("account") or "")) if x)
        lines.append(f"{sev} — {warn.get('role') or ''} {warn.get('code') or ''}"
                     + (f" ({where})" if where else ""))
    return lines


def _source_entry(candidates: dict, entry: dict, number: int, used: bool) -> str:
    item = entry["item"]
    group = entry["group"]
    account = _source_account_label(candidates, group, item.get("anchor") or {})
    rows = [f'<p class="mb-src-head">{number:02d} · {"일정" if group == "calendar" else "메일"} · '
            f'{esc(account)}</p>']
    if group == "email":
        rows.append(f'<p>보낸 사람: {esc(item.get("from"))}</p>')
        rows.append(f'<p>제목: {esc(item.get("subject"))}</p>')
        rows.append(f'<p>날짜: {esc(format_moment(item.get("date")))}</p>')
        rows.append(f'<p>판정: {esc(item.get("verdict"))} · {esc(item.get("reason_code"))}</p>')
        if item.get("match"):
            rows.append(f'<p>일정과 이은 근거: {esc(item.get("match_detail"))}</p>')
        body = item.get("body")
        if isinstance(body, str) and body.strip():
            rows.append(f'<p>본문 발췌: {esc(body)}</p>')
    else:
        anchor = item.get("anchor") or {}
        rows.append(f'<p>캘린더: {esc(anchor.get("calendar"))}</p>')
        rows.append(f'<p>제목: {esc(item.get("summary"))}</p>')
        rows.append(f'<p>시간: {esc(format_when(item.get("start"), item.get("end"), bool(item.get("all_day"))))}</p>')
        rows.append(f'<p>주최자: {esc(item.get("organizer") or "미상")}</p>')
        rows.append(f'<p>상태: {esc(item.get("status") or "")}</p>')
    tag = ('<p class="mb-src-tag" data-mb-used="1">이 항목의 근거</p>' if used
           else '<p class="mb-src-tag" data-mb-unused="1">표시 안 함</p>')
    return f'<li class="mb-src" id="mb-src-{number}">' + "".join(rows) + tag + '</li>'


def render_sources(candidates: dict, used_numbers: set[int]) -> str:
    """페이지 끝의 접이식 「출처」. 무엇을 어느 계정에서 읽었는지와 원본 발췌."""
    entries = source_entries(candidates)
    summary = "".join(f'<li>{esc(line)}</li>' for line in _summary_lines(candidates))
    body = "".join(_source_entry(candidates, e, i, i in used_numbers)
                   for i, e in enumerate(entries, start=1))
    if not body:
        body = '<li class="mb-src">모은 원본이 없습니다.</li>'
    return ('<details class="mb-sources" data-mb-sources="1"><summary>출처</summary>'
            '<div class="mb-sources-body">'
            '<h3 class="mb-src-h">수집 요약</h3>'
            f'<ul class="mb-src-summary">{summary}</ul>'
            '<h3 class="mb-src-h">원본</h3>'
            f'<ol class="mb-src-list">{body}</ol>'
            '</div></details>')


# --------------------------------------------------------------------------
# 스타일 — 색 토큰 + 공통 CSS + 스타일별 배치 CSS
# --------------------------------------------------------------------------

def _vars(tokens: dict[str, str]) -> str:
    return "".join(f"--{k}:{v};" for k, v in tokens.items())


def token_css(style: str) -> str:
    """라이트 기본, 다크는 OS 설정(`data-theme` 로 고정 가능), 인쇄는 늘 라이트."""
    light, dark = _vars(TOKENS[style]["light"]), _vars(TOKENS[style]["dark"])
    return (f":root{{{light}color-scheme:light}}\n"
            f"@media (prefers-color-scheme: dark){{:root:not([data-theme=\"light\"]){{{dark}color-scheme:dark}}}}\n"
            f":root[data-theme=\"dark\"]{{{dark}color-scheme:dark}}\n"
            # 인쇄 — 다크 설정이어도 종이에는 라이트. id 선택자로 위 규칙보다 우선한다.
            f"@media print{{:root:not(#mb-print){{{light}color-scheme:light}}}}\n")


# 한국어가 흐르는 모든 표면 — 어절 단위로 줄을 바꾸고, 긴 주소·제목은 어디서든 끊어 가로 스크롤을 막는다.
KEEP_ALL = (".mb-headline, .mb-event-title, .mb-item-title, .mb-mail-subject, .mb-summary, .mb-meta, "
            ".mb-group-h, .mb-heading, .mb-quiet, .mb-more, .mb-warning, .mb-section p, .mb-src, "
            ".mb-bulk-subject, .mb-bulk-acct-h, .mb-sample, .mb-hint, .mb-none p, .mb-tl-free, .mb-when")

BASE_CSS = f"""* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: {SANS};
  font-size: 15px; line-height: 1.65; }}
p, h1, h2, h3, h4 {{ margin: 0; }}
ol, ul {{ list-style: none; margin: 0; padding: 0; }}
{KEEP_ALL} {{ word-break: keep-all; overflow-wrap: anywhere; }}
.mb-page {{ max-width: 960px; margin: 0 auto; padding: 32px 16px 64px; }}
.mb-part, .mb-bulk-part {{ margin-top: 40px; }}
.mb-heading {{ font-size: 15px; font-weight: 700; margin: 0 0 12px; display: flex; flex-wrap: wrap;
  gap: 4px 10px; align-items: baseline; }}
.mb-count {{ font-size: 12.5px; font-weight: 400; color: var(--faint); }}
.mb-dateline {{ font-size: 13px; color: var(--soft); }}
.mb-headline {{ font-size: 26px; line-height: 1.3; font-weight: 700; }}
.mb-event-title, .mb-item-title, .mb-mail-subject {{ font-weight: 600; }}
.mb-mail-subject {{ font-size: 13.5px; }}
.mb-meta {{ margin-top: 2px; font-size: 12.5px; color: var(--soft); }}
.mb-cancelled .mb-event-title {{ text-decoration: line-through; color: var(--faint); }}
.mb-tag {{ font-size: 12px; font-weight: 500; color: var(--alert); display: inline-block;
  margin-left: 6px; text-decoration: none; }}
.mb-src-ref {{ margin-left: 6px; font-size: 11.5px; font-weight: 400; color: var(--faint);
  text-decoration: none; border-bottom: 1px solid var(--line); white-space: nowrap; }}
.mb-src-ref:hover, .mb-src-ref:focus-visible {{ color: var(--accent); border-color: var(--accent); }}
.mb-badge {{ display: inline-block; padding: 0 7px; border-radius: 999px; font-size: 11.5px; line-height: 18px;
  border: 1px solid var(--line); color: var(--soft); white-space: nowrap; }}
.mb-badge-unreplied, .mb-badge-replied_then_new {{ border-color: transparent; background: var(--alert-bg);
  color: var(--alert); font-weight: 600; }}
.mb-badge-replied {{ border-color: transparent; background: var(--ok-bg); color: var(--ok); }}
.mb-acct {{ display: inline-block; padding: 0 6px; border-radius: 4px; font-size: 11.5px; line-height: 18px;
  background: var(--wash); color: var(--soft); white-space: nowrap; }}
.mb-summary {{ margin-top: 6px; }}
.mb-button {{ display: inline-block; margin-top: 10px; padding: 8px 14px; border-radius: 6px;
  background: var(--accent); color: var(--accent-ink); font-size: 13px; font-weight: 600; text-decoration: none; }}
.mb-button:hover, .mb-button:focus-visible {{ filter: brightness(1.1); }}
.mb-quiet {{ color: var(--soft); margin: 4px 0 0; }}
.mb-more {{ margin: 8px 0 0; font-size: 12.5px; color: var(--faint); }}
.mb-warning {{ margin: 12px 0 0; padding: 8px 12px; border-left: 3px solid var(--alert);
  background: var(--alert-bg); font-size: 13.5px; }}
.mb-num {{ color: var(--faint); font-size: 12.5px; font-variant-numeric: tabular-nums; }}
.mb-mono {{ font-family: {MONO}; font-variant-numeric: tabular-nums; }}
.mb-section p {{ font-size: 13.5px; }}
.mb-bulk-body {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr));
  gap: 16px 24px; align-items: start; }}
.mb-bulk-account {{ min-width: 0; }}
.mb-bulk-acct-h {{ font-size: 14px; font-weight: 700; padding-bottom: 6px; margin-bottom: 8px;
  border-bottom: 1px solid var(--line); }}
.mb-group {{ margin-bottom: 14px; min-width: 0; }}
.mb-group-h {{ font-size: 13px; font-weight: 700; margin-bottom: 4px; }}
.mb-group .mb-mail {{ padding: 4px 0; }}
.mb-group .mb-mail-subject {{ font-size: 13px; }}
.mb-bulk-subjects {{ font-size: 12.5px; color: var(--soft); padding-left: 10px; }}
.mb-bulk-subject {{ margin-top: 2px; }}
.mb-bulk-date, .mb-bulk-n, .mb-bulk-more, .mb-bulk-login {{ color: var(--faint); font-weight: 400; }}
.mb-bulk-login {{ font-size: 12.5px; }}
.mb-sample {{ background: var(--ink); color: var(--bg); padding: 10px 16px; font-size: 13px;
  text-align: center; }}
.mb-none {{ max-width: 640px; margin: 0 auto; padding: 56px 16px; }}
.mb-none p {{ margin: 0 0 12px; }}
.mb-none [data-mb-headline] {{ font-size: 22px; font-weight: 700; }}
.mb-hint {{ margin-top: 16px; color: var(--soft); font-size: 14px; }}
.mb-sources {{ margin-top: 48px; border-top: 1px solid var(--line); padding-top: 14px; font-size: 13px;
  color: var(--soft); }}
.mb-sources summary {{ cursor: pointer; font-weight: 700; color: var(--ink); }}
.mb-src-h {{ font-size: 12.5px; font-weight: 700; color: var(--ink); margin: 18px 0 8px; }}
.mb-src-summary {{ padding-left: 18px; list-style: disc; }}
.mb-src {{ padding: 10px 0; border-top: 1px solid var(--line); }}
.mb-src p {{ margin: 0 0 2px; }}
.mb-src-head {{ color: var(--ink); font-weight: 600; }}
.mb-src-tag {{ margin-top: 6px; color: var(--faint); }}
@media print {{
  .mb-button {{ display: none; }}
  .mb-event, .mb-item, .mb-mail, .mb-group, .mb-src {{ break-inside: avoid; }}
  .mb-sample {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
}}
"""

# 시안 C — Agenda Timeline
TIMELINE_CSS = """.mb-tl-hd { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 16px;
  align-items: flex-end; padding-bottom: 20px; border-bottom: 1px solid var(--line); }
.mb-tl-hd .mb-dateline { color: var(--accent); font-weight: 600; }
.mb-tl-aside { display: grid; gap: 6px; max-width: 420px; }
.mb-tl-aside .mb-section { text-align: right; }
.mb-tl-aside .mb-heading { display: none; }
.mb-tl-aside .mb-section p { color: var(--soft); }
.mb-tl { display: grid; }
.mb-tl-row { display: grid; grid-template-columns: 52px 14px minmax(0, 1fr) minmax(0, 1.1fr); gap: 0 14px; }
.mb-tl-t { font-variant-numeric: tabular-nums; font-size: 13px; color: var(--accent); font-weight: 600;
  text-align: right; padding-top: 11px; white-space: nowrap; }
.mb-tl-rail { position: relative; }
.mb-tl-rail::before { content: ""; position: absolute; left: 6px; top: 0; bottom: 0; width: 2px;
  background: var(--rail); }
.mb-event .mb-tl-rail::after { content: ""; position: absolute; left: 1px; top: 14px; width: 12px; height: 12px;
  border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 3px var(--bg); }
.mb-cancelled .mb-tl-rail::after { background: var(--bg); border: 2px solid var(--faint); }
.mb-tl-allday .mb-tl-rail::after { border-radius: 3px; }
.mb-tl-blk { background: var(--block); border-radius: 8px; padding: 10px 12px; margin: 4px 0; min-width: 0; }
.mb-tl-allday .mb-tl-blk { background: var(--wash); border: 1px dashed var(--rail); }
.mb-cancelled .mb-tl-blk { background: transparent; border: 1px dashed var(--line); }
.mb-tl-mails { padding: 4px 0; min-width: 0; }
.mb-tl-mails .mb-mails { display: grid; gap: 6px; }
.mb-tl-mails .mb-mail { border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; background: var(--panel); }
.mb-tl-mails .mb-more { margin-top: 6px; }
.mb-tl-gap .mb-tl-t { color: var(--faint); font-weight: 400; }
.mb-tl-free { grid-column: 3 / -1; font-size: 12.5px; color: var(--faint); padding: 10px 0;
  border-bottom: 1px dashed var(--line); margin-bottom: 6px; }
.mb-tl-page .mb-items { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr)); gap: 10px; }
.mb-tl-page .mb-item { border-left: 3px solid var(--alert); background: var(--alert-bg);
  padding: 12px 14px; border-radius: 0 8px 8px 0; min-width: 0; }
.mb-tl-page .mb-num { display: none; }
@media (max-width: 720px) {
  .mb-tl-row { grid-template-columns: 44px 14px minmax(0, 1fr); gap: 0 10px; }
  .mb-tl-t { grid-column: 1; grid-row: 1; }
  .mb-tl-rail { grid-column: 2; grid-row: 1 / span 2; }
  .mb-tl-blk, .mb-tl-free { grid-column: 3; grid-row: 1; }
  .mb-tl-mails { grid-column: 3; grid-row: 2; padding-top: 0; }
  .mb-tl-mails:empty { display: none; }
  .mb-tl-aside { max-width: none; }
  .mb-tl-aside .mb-section { text-align: left; }
}
"""

# 시안 A — Executive Memo
MEMO_CSS = f""".mb-memo {{ max-width: 820px; padding-top: 44px; }}
.mb-memo-head {{ display: grid; gap: 4px; font-size: 13.5px; border-bottom: 2px solid var(--accent);
  padding-bottom: 14px; margin-bottom: 24px; }}
.mb-memo-row {{ display: grid; grid-template-columns: 5.5em minmax(0, 1fr); gap: 0 16px; }}
.mb-memo-row > :not(:first-child) {{ grid-column: 2; }}
.mb-memo-k, .mb-memo-row .mb-heading {{ font-size: 12.5px; font-weight: 400; color: var(--faint);
  letter-spacing: .06em; margin: 0; display: block; }}
.mb-memo .mb-count {{ font-family: {SANS}; }}
.mb-memo .mb-headline {{ font-family: {SERIF}; font-size: 26px; color: var(--accent); font-weight: 700; }}
.mb-memo .mb-part > .mb-heading {{ font-family: {SERIF}; font-size: 18px; color: var(--accent);
  border-bottom: 1px solid var(--line); padding-bottom: 8px; margin-bottom: 0; }}
.mb-memo .mb-event {{ display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 16px; padding: 14px 0;
  border-bottom: 1px solid var(--line); }}
.mb-memo .mb-when {{ color: var(--accent); font-weight: 600; font-variant-numeric: tabular-nums; font-size: 14px; }}
.mb-memo .mb-when small {{ display: block; color: var(--faint); font-weight: 400; font-size: 12.5px; }}
.mb-memo .mb-event-title {{ font-size: 15.5px; }}
.mb-memo .mb-mails {{ margin-top: 8px; padding-left: 14px; border-left: 1px solid var(--rail); display: grid; gap: 8px; }}
.mb-memo .mb-item {{ display: grid; grid-template-columns: 2.2em minmax(0, 1fr); gap: 8px; padding: 14px 0;
  border-bottom: 1px solid var(--line); }}
.mb-memo .mb-num {{ padding-top: 2px; }}
.mb-memo .mb-summary {{ color: var(--soft); }}
@media (max-width: 560px) {{
  .mb-memo .mb-event {{ grid-template-columns: 1fr; gap: 4px; }}
  .mb-memo .mb-when small {{ display: inline; margin-left: 6px; }}
  .mb-memo-row {{ grid-template-columns: 4.5em minmax(0, 1fr); }}
}}
"""

# 시안 B — Data Desk
DESK_CSS = f""".mb-desk {{ max-width: 1120px; font-size: 14px; padding-top: 20px; }}
.mb-desk-top {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 16px; align-items: baseline;
  margin-bottom: 14px; }}
.mb-desk .mb-headline {{ font-size: 18px; }}
.mb-kpi {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(150px, 100%), 1fr)); gap: 1px;
  background: var(--line); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; margin: 14px 0 0; }}
.mb-kpi > div {{ background: var(--panel); padding: 10px 12px; min-width: 0; }}
.mb-kpi small {{ display: block; color: var(--faint); font-size: 11.5px; }}
.mb-kpi strong {{ font-family: {MONO}; font-size: 22px; font-weight: 500; font-variant-numeric: tabular-nums; }}
.mb-kpi strong.mb-alert {{ color: var(--alert); }}
.mb-kpi em {{ display: block; font-style: normal; font-size: 11.5px; color: var(--faint); overflow-wrap: anywhere; }}
.mb-desk .mb-part, .mb-desk .mb-sections {{ margin-top: 16px; }}
.mb-panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 0; overflow: hidden; }}
.mb-panel > .mb-heading {{ margin: 0; padding: 8px 12px; font-size: 12.5px; letter-spacing: .04em; color: var(--soft);
  border-bottom: 1px solid var(--line); justify-content: space-between; }}
.mb-panel > .mb-quiet, .mb-panel > .mb-more, .mb-panel > .mb-bulk-body {{ padding: 8px 12px; margin: 0; }}
.mb-panel > .mb-more + .mb-more {{ padding-top: 0; }}
.mb-sections {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr)); gap: 12px; }}
.mb-sections .mb-section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 8px 12px; }}
.mb-sections .mb-heading {{ font-size: 11.5px; color: var(--faint); font-weight: 500; margin-bottom: 2px; }}
.mb-table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; }}
.mb-table th, .mb-table td {{ padding: 7px 12px; border-bottom: 1px solid var(--rail); text-align: left; vertical-align: top; }}
.mb-table th {{ font-size: 11.5px; color: var(--faint); font-weight: 500; background: var(--block); white-space: nowrap; }}
.mb-table tr:last-child td {{ border-bottom: 0; }}
.mb-table .mb-when {{ white-space: nowrap; font-size: 12.5px; color: var(--ink); font-variant-numeric: tabular-nums; }}
.mb-table .mb-dur {{ white-space: nowrap; color: var(--faint); font-size: 12.5px; }}
.mb-sub td {{ background: var(--block); font-size: 12.5px; }}
.mb-sub-mark {{ color: var(--faint); text-align: right; }}
.mb-table .mb-meta {{ margin: 0; }}
.mb-table-items .mb-num {{ width: 2.5em; }}
.mb-table .mb-summary {{ margin: 0; }}
.mb-desk .mb-bulk-part .mb-bulk-body {{ padding: 12px; }}
@media (max-width: 720px) {{
  .mb-table, .mb-table tbody, .mb-table tr, .mb-table td {{ display: block; width: auto; }}
  .mb-table thead {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }}
  .mb-table tr {{ padding: 8px 12px; border-bottom: 1px solid var(--rail); }}
  .mb-table td {{ padding: 0; border: 0; }}
  .mb-table td:empty {{ display: none; }}
  .mb-sub {{ padding-left: 28px !important; background: var(--block); }}
  .mb-sub-mark {{ display: none !important; }}
  .mb-table .mb-when, .mb-table .mb-dur {{ display: inline-block; margin-right: 8px; }}
  .mb-table-items .mb-num {{ display: none; }}
}}
"""

# 시안 E — One-Page Print
PRINT_CSS = """.mb-print { max-width: 1000px; margin: 0 auto; }
.mb-band { background: var(--band); color: var(--band-ink); padding: 22px 28px; display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, auto); gap: 12px 24px; align-items: end; }
.mb-band .mb-dateline { color: inherit; opacity: .75; font-size: 12px; font-weight: 700; letter-spacing: .12em; }
.mb-band .mb-headline { font-size: 30px; font-weight: 800; letter-spacing: -.01em; line-height: 1.15; }
.mb-band-aside { display: grid; gap: 4px; max-width: 360px; text-align: right; font-size: 12.5px; }
.mb-band-aside .mb-heading { display: none; }
.mb-band-aside .mb-section p { font-size: 12.5px; }
.mb-print-warn { padding: 0 28px; }
.mb-cols { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); }
.mb-col { padding: 22px 28px; min-width: 0; }
.mb-col + .mb-col { border-left: 1px solid var(--line); background: var(--panel); }
.mb-print .mb-part { margin-top: 0; }
.mb-print .mb-part + .mb-part { margin-top: 28px; }
.mb-print .mb-heading { font-size: 11.5px; letter-spacing: .12em; font-weight: 800; color: var(--accent); }
.mb-print .mb-event { display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 12px; padding: 10px 0;
  border-top: 2px solid var(--rail); }
.mb-print .mb-when { font-size: 16px; font-weight: 800; font-variant-numeric: tabular-nums; line-height: 1.2; }
.mb-print .mb-when small { display: block; font-size: 11px; font-weight: 400; color: var(--faint); }
.mb-print .mb-event-title { font-weight: 800; }
.mb-print .mb-mails { margin-top: 6px; display: grid; gap: 4px; }
.mb-print .mb-mail { font-size: 12.5px; }
.mb-print .mb-item { padding: 8px 0; border-top: 1px solid var(--line); }
.mb-print .mb-num { display: none; }
.mb-print .mb-bulk-part .mb-bulk-body { grid-template-columns: 1fr; }
.mb-print-foot { padding: 0 28px 28px; }
@media (max-width: 720px) {
  .mb-band { grid-template-columns: 1fr; padding: 20px 16px; }
  .mb-band-aside { text-align: left; max-width: none; }
  .mb-cols { grid-template-columns: 1fr; }
  .mb-col { padding: 18px 16px; }
  .mb-col + .mb-col { border-left: 0; border-top: 1px solid var(--line); }
  .mb-print-warn, .mb-print-foot { padding-left: 16px; padding-right: 16px; }
  .mb-print .mb-event { grid-template-columns: 84px minmax(0, 1fr); }
  .mb-print .mb-when { font-size: 14px; }
}
@page { size: A4; margin: 12mm; }
@media print {
  body { font-size: 10.5pt; }
  .mb-print { max-width: none; }
  .mb-band { grid-template-columns: minmax(0, 1fr) minmax(0, auto); padding: 14px 18px;
    -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .mb-band-aside { text-align: right; }
  .mb-cols { grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); }
  .mb-col { padding: 14px 18px; }
  .mb-col + .mb-col { border-left: 1px solid var(--line); border-top: 0; }
  .mb-print-warn, .mb-print-foot { padding-left: 18px; padding-right: 18px; }
  .mb-print .mb-event { grid-template-columns: 76px minmax(0, 1fr); }
}
"""

STYLE_CSS = {"timeline": TIMELINE_CSS, "memo": MEMO_CSS, "desk": DESK_CSS, "print": PRINT_CSS}


def style_block(style: str = DEFAULT_STYLE) -> str:
    return f"<style>\n{token_css(style)}{BASE_CSS}{STYLE_CSS[style]}</style>"


# --------------------------------------------------------------------------
# 스타일별 배치 — 같은 조각(일정·관련 메일·미회신·대량·절·출처)을 다른 자리에 놓는다
# --------------------------------------------------------------------------

def _account_names(candidates: dict, role: str) -> str:
    """메모 머리의 계정 줄 — 이름만(주소는 싣지 않는다: `--no-sources` 에서도 본문에 `@` 0)."""
    if is_sample(candidates):
        return SAMPLE_ACCOUNT_LABEL
    state = role_state(candidates, role)
    if state not in READY_STATES:
        return ROLE_STATE_LABEL.get(state, state or "미설정")
    names = [str(a.get("account") or "default") for a in _role_accounts(candidates, role)]
    return ", ".join(names) or ROLE_STATE_LABEL.get(state, state)


def memo_headline(candidates: dict) -> str:
    """메모의 한 줄 요지 — 준비된 역할의 수만(코드가 센다)."""
    parts: list[str] = []
    if role_state(candidates, "calendar") in READY_STATES:
        parts.append(f"일정 {len(_events(candidates))}건")
    if role_state(candidates, "email") in READY_STATES:
        email = candidates.get("email") or {}
        n = len(email.get("unreplied") or []) + int(email.get("unreplied_more") or 0)
        parts.append(f"답을 기다리는 메일 {n}통")
    return f"오늘은 {', '.join(parts)}이에요."


def _kpi(label: str, value: str, sub: str = "", alert: bool = False) -> str:
    cls = ' class="mb-alert"' if alert else ""
    sub_html = f"<em>{esc(sub)}</em>" if sub else ""
    return f"<div><small>{esc(label)}</small><strong{cls}>{esc(value)}</strong>{sub_html}</div>"


def desk_kpis(candidates: dict) -> str:
    """데스크 지표 띠 — 전부 candidates 에서 센 수. 준비 안 된 역할은 `—`."""
    cal = role_state(candidates, "calendar") in READY_STATES
    mail = role_state(candidates, "email") in READY_STATES
    events = _events(candidates)
    email = candidates.get("email") or {}
    timed = [(s, _parse_dt(ev.get("end"))) for ev in events if not ev.get("all_day") and not _is_cancelled(ev)
             for s in [_parse_dt(ev.get("start"))] if s is not None]
    span = ""
    if timed:
        first = min(s for s, _ in timed)
        last = max((e if e is not None and e > s else s) for s, e in timed)
        span = f"{_hhmm(first)}–{_hhmm(last)}"
    unreplied = len(email.get("unreplied") or [])
    more = int(email.get("unreplied_more") or 0)
    tiles = [
        _kpi("오늘 일정", str(len(events)) if cal else "—", span),
        _kpi("일정별 관련 메일", str(_related_total(candidates)) if cal and mail else "—"),
        _kpi("일정과 무관한 미회신", str(unreplied) if mail else "—", f"그 밖 {more}통" if more else "",
             alert=mail and unreplied > 0),
        _kpi("대량 발송", str(bulk_count(email)) if mail else "—", _bulk_split(email).lstrip(" —")),
    ]
    return f'<div class="mb-kpi">{"".join(tiles)}</div>'


def _bulk(ctx: "Ctx") -> str:
    return render_bulk(ctx.candidates, show_login=ctx.include_sources)


def _sources(ctx: "Ctx") -> str:
    return render_sources(ctx.candidates, ctx.src.used) if ctx.include_sources else ""


class Ctx:
    def __init__(self, candidates: dict, summaries: dict[str, dict], src: Refs,
                 include_sources: bool, dateline: str, warnings: str) -> None:
        self.candidates = candidates
        self.summaries = summaries
        self.src = src
        self.include_sources = include_sources
        self.dateline = dateline
        self.warnings = warnings


def _dateline(ctx: Ctx) -> str:
    return f'<p class="mb-dateline" data-mb-dateline="1">{esc(ctx.dateline)}</p>'


HEADLINE = '<h1 class="mb-headline" data-mb-headline="1">아침 브리핑</h1>'


def layout_timeline(ctx: Ctx) -> str:
    c = ctx.candidates
    schedule = schedule_timeline(c, ctx.src)
    unreplied = render_unreplied(c, ctx.summaries, ctx.src)
    bulk = _bulk(ctx)
    return (f'<div class="mb-page mb-tl-page"><header class="mb-tl-hd"><div>{_dateline(ctx)}{HEADLINE}</div>'
            f'<div class="mb-tl-aside">{render_sections(c)}</div></header>{ctx.warnings}'
            f'{schedule}{unreplied}{bulk}{_sources(ctx)}</div>')


def layout_memo(ctx: Ctx) -> str:
    c = ctx.candidates
    head = (f'<div class="mb-memo-head">'
            f'<div class="mb-memo-row"><span class="mb-memo-k">날짜</span>'
            f'<p class="mb-dateline" data-mb-dateline="1">{esc(ctx.dateline)}</p></div>'
            f'<div class="mb-memo-row"><span class="mb-memo-k">캘린더</span><p>{esc(_account_names(c, "calendar"))}</p></div>'
            f'<div class="mb-memo-row"><span class="mb-memo-k">메일</span><p>{esc(_account_names(c, "email"))}</p></div>'
            f'{render_sections(c, "mb-section mb-memo-row")}</div>')
    headline = f'<h1 class="mb-headline" data-mb-headline="1">{esc(memo_headline(c))}</h1>'
    schedule = schedule_list(c, ctx.src)
    unreplied = render_unreplied(c, ctx.summaries, ctx.src)
    return (f'<div class="mb-page mb-memo">{head}{headline}{ctx.warnings}'
            f'{schedule}{unreplied}{_bulk(ctx)}{_sources(ctx)}</div>')


def layout_desk(ctx: Ctx) -> str:
    c = ctx.candidates
    sections = render_sections(c)
    sections_html = f'<div class="mb-sections">{sections}</div>' if sections else ""
    schedule = schedule_table(c, ctx.src)
    unreplied = render_unreplied(c, ctx.summaries, ctx.src, table=True)
    bulk = _bulk(ctx).replace('class="mb-part mb-bulk-part"', 'class="mb-part mb-bulk-part mb-panel"', 1)
    return (f'<div class="mb-page mb-desk"><header class="mb-desk-top">{HEADLINE}{_dateline(ctx)}</header>'
            f'{ctx.warnings}{desk_kpis(c)}{sections_html}{schedule}{unreplied}{bulk}{_sources(ctx)}</div>')


def layout_print(ctx: Ctx) -> str:
    c = ctx.candidates
    schedule = schedule_list(c, ctx.src)
    unreplied = render_unreplied(c, ctx.summaries, ctx.src)
    bulk = _bulk(ctx)
    warn = f'<div class="mb-print-warn">{ctx.warnings}</div>' if ctx.warnings else ""
    foot = f'<div class="mb-print-foot">{_sources(ctx)}</div>' if ctx.include_sources else ""
    return (f'<div class="mb-print"><header class="mb-band"><div>{_dateline(ctx)}{HEADLINE}</div>'
            f'<div class="mb-band-aside">{render_sections(c)}</div></header>{warn}'
            f'<div class="mb-cols"><div class="mb-col">{schedule}</div>'
            f'<div class="mb-col">{unreplied}{bulk}</div></div>{foot}</div>')


LAYOUTS = {"timeline": layout_timeline, "memo": layout_memo, "desk": layout_desk, "print": layout_print}


def render_html(content: dict, candidates: dict, include_sources: bool = True,
                style: str = DEFAULT_STYLE) -> str:
    if style not in STYLES:
        raise ContentError("unknown_style", str(style))
    if any(isinstance(w, dict) and w.get("code") == HYVE_OUTDATED for w in candidates.get("warnings") or []):
        raise ContentError(HYVE_OUTDATED, "itda-hyve 가 옛 판이다 — 업데이트 뒤 수집부터 다시 한다(gather.py 가 안내를 낸다)")
    summaries = validate_content(content, candidates)
    state = page_state(candidates)
    sample = is_sample(candidates)
    src = Refs(source_numbers(candidates) if include_sources else None)
    dateline = format_date_line(brief_date(candidates))
    warning_html = render_warnings(candidates)

    if state == "none":
        sources_html = render_sources(candidates, src.used) if include_sources else ""
        # 계정이 없다고 스킬이 스스로 샘플로 바꾸지 않는다 — 길만 알려 준다.
        hint = ("" if sample else
                f'<p class="mb-hint" data-mb-sample-hint="1">{esc(SAMPLE_HINT)}</p>')
        body = (f'<div class="mb-none" data-mb-none="1"><p class="mb-dateline" data-mb-dateline="1">'
                f'{esc(dateline)}</p><p data-mb-headline="1">아침 브리핑을 만들 계정이 없어요.</p>'
                f'<p>연결된 캘린더와 메일이 없어 오늘은 여기까지예요.</p>{hint}{warning_html}'
                f'{sources_html}</div>')
        return _document(dateline, state, style, body, sample=sample)

    ctx = Ctx(candidates, summaries, src, include_sources, dateline, warning_html)
    return _document(dateline, state, style, LAYOUTS[style](ctx), sample=sample)


def _document(dateline: str, state: str, style: str, body: str, *, sample: bool = False) -> str:
    # 샘플 띠는 페이지 **최상단 상시**다 — 접거나 스크롤로 사라지지 않는다.
    banner = (f'<div class="mb-sample" data-mb-sample="1">{esc(SAMPLE_BANNER)}</div>'
              if sample else "")
    title = ("샘플 " if sample else "") + f"{dateline} 아침 브리핑"
    return ("<!DOCTYPE html>\n"
            '<html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)}</title>{style_block(style)}</head>'
            f'<body data-mb-state="{esc(state)}" data-mb-style="{esc(style)}">{banner}{body}</body></html>\n')


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
    ap.add_argument("--style", choices=STYLES, default=DEFAULT_STYLE,
                    help="보고서 스타일 — timeline(기본)·memo(보고서)·desk(표)·print(인쇄용)")
    ap.add_argument("--no-sources", action="store_true",
                    help="페이지 끝 「출처」 절을 뺀다(파일 공유 시 노출 축소)")
    args = ap.parse_args(argv)

    try:
        content = json.loads(Path(args.content).read_text(encoding="utf-8"))
        candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _fail("input_unreadable", str(exc)[:300])
    if candidates.get("schema_version") != SCHEMA_VERSION:
        return _fail("candidates_schema_version", str(candidates.get("schema_version")))

    try:
        page = render_html(content, candidates, include_sources=not args.no_sources, style=args.style)
    except ContentError as exc:
        return _fail(exc.code, exc.detail)

    try:
        Path(args.out).write_text(page, encoding="utf-8")
    except OSError as exc:
        # 대체 경로로 조용히 넘어가지 않는다 (no-silent-fallback).
        return _fail("write_failed", f"{args.out}: {exc}", rc=3)

    print(json.dumps({"status": "ok", "path": args.out, "state": page_state(candidates),
                      "style": args.style, "sources": not args.no_sources,
                      "bytes": len(page.encode("utf-8"))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
