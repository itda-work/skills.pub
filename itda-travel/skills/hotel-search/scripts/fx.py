#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fx.py - 환율(수집 통화 → KRW) 요청 계획과 응답 판독 — 네트워크 없음.

Xotelo 는 KRW 미지원이라 USD 등으로 수집한 뒤 원화로 환산 표시한다(#1013 결정). 환율은 open.er-api.com
(ExchangeRate-API 의 키 없는 공개 엔드포인트)을 itda-hyve 로 받는다.

## 이용 조건 (https://www.exchangerate-api.com/docs/free — 2026-10-01 판독)
- 키 없는 Open API 는 **출처 표기가 필수**다("Rates By Exchange Rate API" 링크) → 출력에 :data:`ATTRIBUTION` 을 싣는다.
- 하루 한 번 갱신되고, 받은 값을 캐시해도 된다(요청 한도가 있어 한 시간에 한 번 넘게 부르지 말라고 권한다)
  → 저장 이름에 받은 날(KST)을 넣어 **같은 회차 폴더에서 하루 한 번만** 받는다.
- 재배포는 안 된다 — 환율 표를 파일로 내보내지 않고 환산 결과에만 쓴다.

조용한 폴백 금지(no-silent-fallback): 환율을 못 읽으면 0/추정으로 덮지 않고 ``(None, 사유)`` 를 돌려준다.
호출부(hotel_search)는 원화 환산을 생략하고 그 사유를 출력에 **명시**한다.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from hyve_input import HyveInputError, read_input

FX_URL = "https://open.er-api.com/v6/latest/{base}"
ATTRIBUTION = "환율: Rates By Exchange Rate API (https://www.exchangerate-api.com)"
TIMEOUT_SEC = 45
SAVE_PREFIX = "hotel/"
STALE_HOURS = 48  # 하루 한 번 갱신 — 이보다 묵었으면 경고
KST = _dt.timezone(_dt.timedelta(hours=9))


def now_kst() -> _dt.datetime:
    """지금(KST). 테스트는 이 함수를 바꿔 끼운다."""
    return _dt.datetime.now(KST)


def today_kst() -> _dt.date:
    """받은 날의 기준 — 환율 저장 이름의 날짜."""
    return now_kst().date()


def fx_name(base: str, day: _dt.date) -> str:
    return f"{SAVE_PREFIX}fx-{base.upper()}-{day:%Y%m%d}.json"


_NAME_RE = re.compile(r"^fx-(?P<base>[A-Z]{3})-(?P<d>\d{8})\.json$")


def fx_call(base: str, day: _dt.date) -> dict:
    """itda-hyve ``http_request`` 인자."""
    return {"url": FX_URL.format(base=base.upper()), "timeout_sec": TIMEOUT_SEC, "save_as": fx_name(base, day)}


def fx_files(run_dir: Path, base: str) -> list[Path]:
    """회차 폴더에서 그 통화의 환율 파일 — 최근 날짜부터."""
    folder = run_dir / SAVE_PREFIX.rstrip("/")
    if not folder.is_dir():
        return []
    found = []
    for p in folder.iterdir():
        m = _NAME_RE.match(p.name)
        if m and m.group("base") == base.upper():
            found.append((m.group("d"), p))
    return [p for _, p in sorted(found, reverse=True)]


def latest_fx_file(run_dir: Path, base: str) -> Path | None:
    """회차 폴더에서 그 통화의 가장 최근 날짜 환율 파일. 없으면 None."""
    files = fx_files(run_dir, base)
    return files[0] if files else None


def pick_krw_rate(run_dir: Path, base: str, *, now: _dt.datetime | None = None) -> tuple[float | None, str, list[str]]:
    """가장 최근 환율 파일을 읽고, 쓸 수 없으면 같은 회차 폴더의 더 이른 성한 파일로 내려간다 — 내려갔으면 경고한다.

    이른 파일도 ``read_krw_rate`` 의 48시간 경고를 그대로 받는다. 전부 쓸 수 없으면 가장 최근 파일의 사유를 돌려준다.
    """
    files = fx_files(run_dir, base)
    first = read_krw_rate(files[0] if files else None, base, now=now)
    if first[0] is not None or len(files) < 2:
        return first
    for older in files[1:]:
        rate, basis, warns = read_krw_rate(older, base, now=now)
        if rate is not None:
            return rate, basis, [f"가장 최근 환율 파일을 쓸 수 없어 {older.name} 를 썼습니다 — {first[1]}"] + warns
    return first


def read_krw_rate(path: Path | None, base: str, *, now: _dt.datetime | None = None) -> tuple[float | None, str, list[str]]:
    """환율 파일 → (base 1단위당 KRW | None, 사유 또는 기준 시각, 경고 목록).

    base 가 KRW 면 1.0. 파일이 없거나·실패 자리·형식 오류·다른 통화 기준이면 None + 사유.
    """
    base = (base or "USD").upper()
    if base == "KRW":
        return 1.0, "", []
    if path is None:
        return None, "환율 파일이 없습니다(받지 않았거나 batch 에서 실패)", []
    try:
        data = json.loads(read_input(path).data.decode("utf-8-sig"))
    except HyveInputError as exc:
        return None, f"환율 파일을 쓸 수 없습니다({exc.kind}): {exc}", []
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, f"환율 응답이 JSON 이 아닙니다({path.name})", []
    if not isinstance(data, dict) or data.get("result") != "success":
        return None, f"환율 응답이 성공이 아닙니다({path.name}: result={data.get('result') if isinstance(data, dict) else '?'})", []
    if (data.get("base_code") or "").upper() != base:
        return None, f"환율 응답의 기준 통화({data.get('base_code')})가 {base} 가 아닙니다({path.name})", []
    try:
        rate = float((data.get("rates") or {}).get("KRW"))
    except (TypeError, ValueError):
        return None, f"환율 응답에 KRW 가 없습니다({path.name})", []
    if rate <= 0:
        return None, f"환율 응답의 KRW 값이 0 이하입니다({path.name})", []

    warnings: list[str] = []
    updated = data.get("time_last_update_unix")
    try:
        upd = _dt.datetime.fromtimestamp(int(updated), KST)
    except (TypeError, ValueError, OverflowError, OSError):
        return rate, "기준 시각 미상", ["환율 기준 시각(time_last_update_unix)을 읽지 못했습니다"]
    now = now or now_kst()
    if now - upd > _dt.timedelta(hours=STALE_HOURS):
        warnings.append(f"환율 기준 시각이 {upd:%Y-%m-%d %H:%M} KST 로 {STALE_HOURS}시간 넘게 지났습니다 — 참고값으로만 보세요")
    return rate, f"{upd:%Y-%m-%d} 기준", warnings
