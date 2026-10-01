#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hotel_search.py - 호텔 가격 비교 CLI (조회 전용, 네트워크 없음).

Xotelo API(트립어드바이저 메타서치)로 한 호텔의 여러 OTA(Booking·Agoda·Trip.com·공식사이트) 요금을 모아
비교한다. 요청은 itda-hyve 가 보낸다(itda-work/skills#45) — 이 스크립트는 부를 호출을 계획하고(``plan``),
itda-hyve 가 저장한 응답을 판독한다(``rates``·``heatmap``).

hotel_key 해소(이름→g<geo>-d<hotel>)는 Xotelo 무료 티어에 없으므로(search=유료·list=고장) 두 경로로
처리한다(SKILL.md): 에이전트 web_search 로 TripAdvisor 호텔 URL 확보 → --url, 또는 사용자가 URL/키 직접 제공.

서브커맨드:
  plan rates    요금 호출(+ 오늘 받은 적 없으면 환율 호출) 계획 → batch plan_file
  plan heatmap  가격 달력 호출 계획
  rates         OTA별 요금 비교표 (원화 환산 병기)
  heatmap       가격 달력(싼날/평균/비싼날)
  resolve       URL/텍스트 → hotel_key 추출(에이전트 해소 보조)

사용 예(R = 회차 폴더를 이 스크립트가 보는 경로, S = 같은 폴더의 호스트 절대 경로):
  python3 hotel_search.py resolve "https://www.tripadvisor.com/Hotel_Review-g294197-d5250436-...html"
  python3 hotel_search.py plan rates --hotel-key g294197-d5250436 --checkin 2026-11-12 --checkout 2026-11-14 \
      --run-dir R --save-dir S
  python3 hotel_search.py rates --hotel-key g294197-d5250436 --checkin 2026-11-12 --checkout 2026-11-14 \
      --run-dir R --name "써미트 호텔 서울"
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
from pathlib import Path

import fx as fx_mod
import links
import output
import xotelo
from errors import EXIT_GENERAL, EXIT_OK, ArgsError, HotelSearchError, NoResultError
from hyve_input import (
    HyveEmptyError, HyveFailure, HyveHTTPError, HyveInputError, HyveReadError, HyveTruncatedError, read_input,
)

BATCH_TIMEOUT_SEC = 50
# 받은 파일이 실패 자리·빈 본문·잘림·HTTP 오류면 plan 이 그 호출을 다시 계획한다 — 한 이름에 이만큼까지.
# 넘으면 끝없이 다시 받지 않고 멈춘다(요금·달력은 오류, 환율은 원화 환산만 빠진다).
MAX_REFETCH = 2
RETRY_STATE = "retries-hotel.json"
_TRANSIENT_4XX = (408, 429)  # 시간 초과·요청 과다 — 4xx 지만 다시 받으면 풀릴 수 있다
_META_NOTE = (
    "TripAdvisor 메타서치 요금 · OTA별 최저 예약가능 객실의 1박 대표값(객실 타입 구분 없음) · "
    "실제 예약가와 다를 수 있음 · OTA 노출 개수는 호텔·날짜별로 다름"
)
# 호스트 절대 경로 — 스크립트가 도는 OS 가 아니라 itda-hyve 호스트 기준(Windows 호스트면 C:\… 가 온다)
_HOST_ABS = re.compile(r"^(/|[A-Za-z]:[\\/]|\\\\[^\\]+\\)")


def host_abs_path(raw: str) -> str:
    """``--save-dir`` 검사 — itda-hyve 호스트의 절대 경로(POSIX ``/…``·``C:\\…``·``C:/…``·UNC)."""
    value = (raw or "").strip()
    if not _HOST_ABS.match(value):
        raise ArgsError(
            "--save-dir 는 회차 폴더의 호스트 절대 경로입니다(예: /Users/me/작업/hotel-search-runs/20261001-0930 · "
            "C:\\Users\\me\\작업\\…). Cowork 는 연결 폴더의 호스트 경로 뒤에 회차 폴더를 붙입니다."
        )
    stripped = value.rstrip("/\\")
    if re.fullmatch(r"[A-Za-z]:", stripped):  # 드라이브 뿌리는 구분자를 남긴다
        return value[:3]
    return stripped or "/"


def _validate_date(value: str, label: str) -> _dt.date:
    try:
        return _dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ArgsError(f"{label} 는 YYYY-MM-DD 형식이어야 합니다 (받음: {value!r})")


def _nights(checkin: str, checkout: str) -> int:
    ci = _validate_date(checkin, "--checkin")
    co = _validate_date(checkout, "--checkout")
    n = (co - ci).days
    if n <= 0:
        raise ArgsError(f"--checkout({checkout}) 는 --checkin({checkin}) 보다 이후여야 합니다")
    return n


def _positive(value: int, label: str) -> int:
    if value is None or value < 1:
        raise ArgsError(f"{label} 는 1 이상이어야 합니다 (받음: {value!r})")
    return value


def _resolve_key(args) -> str:
    """--hotel-key 또는 --url 에서 hotel_key 를 확정한다(정확히 하나 필요)."""
    key, url = getattr(args, "hotel_key", None), getattr(args, "url", None)
    if key and url:
        raise ArgsError("--hotel-key 와 --url 중 하나만 주세요")
    src = key or url
    if not src:
        raise ArgsError("--hotel-key 또는 --url 중 하나가 필요합니다")
    return xotelo.extract_hotel_key(src)


def _rates_query(args) -> dict:
    """plan rates·rates 공통 인자 해석 — 두 단계가 같은 저장 이름을 얻는다."""
    hotel_key = _resolve_key(args)
    nights = _nights(args.checkin, args.checkout)
    return {
        "hotel_key": hotel_key,
        "chk_in": args.checkin,
        "chk_out": args.checkout,
        "currency": xotelo.validate_currency(args.currency),
        "adults": _positive(args.adults, "--adults"),
        "rooms": _positive(args.rooms, "--rooms"),
        "nights": nights,
    }


def _emit(text: str, output_path: str | None) -> int:
    if output_path:
        try:
            Path(output_path).write_text(text, encoding="utf-8")
        except OSError as exc:
            raise HotelSearchError(f"결과를 저장할 수 없습니다: {output_path} ({exc})", kind="output")
        print(f"저장: {output_path}", file=sys.stderr)
    else:
        print(text)
    return EXIT_OK


def _print_json(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


# --- plan -------------------------------------------------------------------

def refetch_reason(path: Path) -> str | None:
    """받은 파일을 다시 받아야 하면 그 사유, 판독에 넘겨도 되면 None.

    다시 받는 것: itda-hyve 실패 자리 · 빈 본문 · 잘린 본문 · HTTP 5xx·408·429 또는 JSON 아닌 오류 본문 · JSON 아닌 본문
    (본문 그대로 저장된 파일의 잘림·점검 페이지). 그 밖의 4xx 와 함께 온 Xotelo JSON 오류 객체는 그 API 의 답(인자
    오류 등)이라 다시 받아도 같다 — 판독이 사유를 전한다. 408·429 는 시간이 지나면 풀리는 답이라 다시 받는다.
    """
    try:
        raw = read_input(path).data
    except HyveFailure as exc:
        return f"hyve:{exc.code}"
    except HyveEmptyError:
        return "empty"
    except HyveTruncatedError:
        return "truncated"
    except HyveHTTPError as exc:
        if isinstance(exc.status, int) and (exc.status >= 500 or exc.status in _TRANSIENT_4XX):
            return f"http:{exc.status}"
        try:
            json.loads(exc.body.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return f"http:{exc.status}"
        return None
    except HyveReadError:
        raise
    except HyveInputError as exc:
        return exc.kind
    try:
        json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "not_json"
    return None


class _Planner:
    """회차 폴더 하나의 호출 계획 — 없는 파일은 받고, 나쁜 파일은 덮어써 다시 받고, 성한 파일은 재사용한다."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.calls: list[dict] = []
        self.reused: list[str] = []
        self.retry: list[dict] = []
        self.gave_up: list[dict] = []
        self.warnings: list[str] = []
        self._dirty = False
        self._state_path = run_dir / RETRY_STATE
        self._state: dict = {}
        if self._state_path.exists():
            try:
                loaded = json.loads(self._state_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                loaded = exc
            if isinstance(loaded, dict):
                self._state = loaded
            else:
                # 조용히 풀지 않는다 — 상한을 처음부터 다시 세는 것을 출력에 밝힌다
                self.warnings.append(
                    f"{RETRY_STATE} 를 읽을 수 없어 다시 받은 횟수를 처음부터 셉니다"
                    f"({loaded if isinstance(loaded, Exception) else type(loaded).__name__})")
                self._dirty = True

    @staticmethod
    def _signature(path: Path) -> list[int]:
        st = path.stat()
        return [st.st_size, st.st_mtime_ns]

    def _entry(self, name: str) -> tuple[int, list | None]:
        raw = self._state.get(name, 0)
        if isinstance(raw, dict):
            try:
                return int(raw.get("count", 0)), raw.get("sig")
            except (TypeError, ValueError):
                return 0, None
        try:
            return int(raw), None
        except (TypeError, ValueError):
            return 0, None

    def add(self, call: dict) -> str:
        """``planned`` · ``retry`` · ``reused`` · ``gave_up`` 중 하나."""
        name = call["save_as"]
        path = self.run_dir / name
        if not path.exists():
            self.calls.append(call)
            return "planned"
        reason = refetch_reason(path)
        if reason is None:
            self.reused.append(name)
            return "reused"
        count, sig = self._entry(name)
        now_sig = self._signature(path)
        if count and sig == now_sig:
            # 지난 plan 이 다시 받기를 계획한 뒤로 파일이 그대로다 — batch 를 아직 안 보냈다. 같은 계획을 다시 내고 세지 않는다
            self.calls.append(dict(call, overwrite=True))
            self.retry.append({"save_as": name, "reason": reason, "attempt": count})
            return "retry"
        if count >= MAX_REFETCH:
            self.gave_up.append({"save_as": name, "reason": reason, "refetched": count})
            return "gave_up"
        self._state[name] = {"count": count + 1, "sig": now_sig}
        self._dirty = True
        # 회차 폴더는 이 스킬 전용이다 — 나쁜 파일을 같은 이름으로 덮어쓴다(판독은 저장 이름으로 찾는다)
        self.calls.append(dict(call, overwrite=True))
        self.retry.append({"save_as": name, "reason": reason, "attempt": count + 1})
        return "retry"

    def save_state(self) -> None:
        if not self._dirty:
            return
        try:
            self._state_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        except OSError as exc:
            raise HotelSearchError(f"회차 폴더에 재시도 기록을 쓸 수 없습니다: {exc}", kind="output")


def _exhausted_error(item: dict) -> HotelSearchError:
    return HotelSearchError(
        f"{item['save_as']} 를 {item['refetched']}번 다시 받았지만 여전히 쓸 수 없습니다({item['reason']}) — "
        "더 받지 않는다. 사용자에게 알리고, 나중에 새 회차 폴더로 plan 부터 다시 한다",
        kind="retry_exhausted",
    )


def _write_plan(run_dir: Path, save_dir: str, stem: str, planner: "_Planner") -> int:
    planner.save_state()
    calls = planner.calls
    out: dict = {"status": "planned", "run_dir": str(run_dir), "calls": len(calls), "reused": planner.reused}
    if planner.retry:
        out["retry"] = planner.retry
    if planner.gave_up:
        out["gave_up"] = planner.gave_up
    if planner.warnings:
        out["warnings"] = planner.warnings
    if not calls:
        out["status"] = "ready"
        out["next"] = "받을 것이 없습니다 — 바로 판독 명령을 실행하세요"
        _print_json(out)
        return EXIT_OK
    digest = hashlib.sha1(json.dumps(calls, sort_keys=True).encode("utf-8")).hexdigest()[:10]
    plan_name = f"plan-{stem}-{digest}.json"
    plan = {"calls": [{"id": c["save_as"].split("/")[-1].split(".")[0], "tool": "http_request", "args": c} for c in calls],
            "timeout_sec": BATCH_TIMEOUT_SEC}
    try:
        (run_dir / plan_name).write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    except OSError as exc:
        raise HotelSearchError(f"회차 폴더에 계획 파일을 쓸 수 없습니다: {exc}", kind="output")
    out["plan_file"] = str(run_dir / plan_name)
    out["batch_args"] = {"plan_file": plan_name, "save_dir": save_dir}
    # batch 에 plan_file 이 없는 옛 판이면 하나씩 부른다 — 한 칸이 곧 http_request 인자다
    out["single_calls"] = [dict(c, save_dir=save_dir) for c in calls]
    _print_json(out)
    return EXIT_OK


def _run_dir_for_plan(args) -> tuple[Path, str]:
    save_dir = host_abs_path(args.save_dir)
    run_dir = Path(args.run_dir).expanduser()
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HotelSearchError(f"회차 폴더를 만들 수 없습니다: {run_dir} ({exc})", kind="output")
    return run_dir, save_dir


def cmd_plan_rates(args) -> int:
    q = _rates_query(args)
    run_dir, save_dir = _run_dir_for_plan(args)
    planner = _Planner(run_dir)
    # 요금은 실시간 값이다 — 같은 회차 폴더에 같은 조회가 성하게 있으면 다시 받지 않고, rates 가 그 조회 시각을 밝힌다
    if planner.add(xotelo.rates_call(q["hotel_key"], q["chk_in"], q["chk_out"], q["currency"], q["adults"], q["rooms"])) == "gave_up":
        raise _exhausted_error(planner.gave_up[-1])
    if not args.no_krw:
        # 환율은 하루 한 번 갱신되고 캐시를 권한다(이용 조건) — 오늘 받은 성한 파일이 있으면 다시 받지 않는다.
        # 다시 받기를 다 써도 요금은 판독한다(원화 환산만 빠지고 rates 가 그 사유를 warnings 에 싣는다)
        planner.add(fx_mod.fx_call(q["currency"], fx_mod.today_kst()))
    return _write_plan(run_dir, save_dir, "rates", planner)


def cmd_plan_heatmap(args) -> int:
    hotel_key = _resolve_key(args)
    _validate_date(args.checkout, "--checkout")
    run_dir, save_dir = _run_dir_for_plan(args)
    planner = _Planner(run_dir)
    if planner.add(xotelo.heatmap_call(hotel_key, args.checkout)) == "gave_up":
        raise _exhausted_error(planner.gave_up[-1])
    return _write_plan(run_dir, save_dir, "heatmap", planner)


# --- 판독 -------------------------------------------------------------------

def cmd_resolve(args) -> int:
    """URL/텍스트에서 hotel_key 를 추출해 출력한다(에이전트 해소 보조)."""
    print(xotelo.extract_hotel_key(args.source))
    return EXIT_OK


def cmd_rates(args) -> int:
    q = _rates_query(args)
    run_dir = Path(args.run_dir).expanduser()
    rates_path = run_dir / xotelo.rates_name(q["hotel_key"], q["chk_in"], q["chk_out"], q["currency"], q["adults"], q["rooms"])
    result, fetched = xotelo.read_rates(rates_path, q["chk_in"], q["chk_out"], q["currency"])

    warnings: list[str] = []
    fx_rate = None
    fx_note = ""
    if not args.no_krw:
        fx_rate, fx_basis, fx_warn = fx_mod.pick_krw_rate(run_dir, q["currency"])
        warnings += fx_warn
        if fx_rate is None:
            # 조용한 폴백 금지 — 환산 실패를 출력에 명시(원화 컬럼만 생략)
            fx_note = f" · ⚠️ 원화 환산 생략 — {fx_basis}"
            warnings.append(f"원화 환산 생략 — {fx_basis}")
        else:
            fx_note = f" · 원화는 {fx_rate:,.0f}원/{q['currency']}({fx_basis}) 환산 참고값(예약가 아님) · {fx_mod.ATTRIBUTION}"

    offers, collected_currency, dropped = xotelo.parse_rates(result, nights=q["nights"], fx_rate=fx_rate)
    if dropped:
        warnings.append(f"요금 값을 읽을 수 없는 OTA 행 {dropped}개를 뺐습니다")
    if not offers:
        raise NoResultError(
            f"{q['chk_in']}~{q['chk_out']} 에 조회된 OTA 요금이 없습니다(매진·미커버 호텔·날짜 확인)"
        )

    # OTA별 예약 딥링크(호텔명 필요 — 없으면 링크 생략을 명시)
    link_note = ""
    if args.name:
        for o in offers:
            o["url"] = links.ota_deeplink(
                o.get("ota_code"), args.name, q["chk_in"], q["chk_out"],
                adults=q["adults"], rooms=q["rooms"],
            )
    else:
        link_note = " · 예약 링크는 --name(호텔명) 지정 시 제공"

    data = {
        "hotel_key": q["hotel_key"],
        "hotel_name": args.name,
        "checkin": q["chk_in"],
        "checkout": q["chk_out"],
        "nights": q["nights"],
        "adults": q["adults"],
        "rooms": q["rooms"],
        "currency": collected_currency or q["currency"],
        "fetched_at": fetched,
        "fx_rate": fx_rate,
        "offers": offers,
        "warnings": warnings,
        "_disclaimer": _META_NOTE + fx_note + link_note,
    }
    text = output.to_json(data) if args.format == "json" else output.rates_to_markdown(data)
    return _emit(text, args.output)


def cmd_heatmap(args) -> int:
    hotel_key = _resolve_key(args)
    _validate_date(args.checkout, "--checkout")
    run_dir = Path(args.run_dir).expanduser()
    result, fetched = xotelo.read_heatmap(run_dir / xotelo.heatmap_name(hotel_key, args.checkout), args.checkout)
    parsed = xotelo.parse_heatmap(result)
    data = {"hotel_key": hotel_key, "hotel_name": args.name, "fetched_at": fetched, **parsed}
    text = output.to_json(data) if args.format == "json" else output.heatmap_to_markdown(data)
    return _emit(text, args.output)


# --- 인자 정의 --------------------------------------------------------------

def _add_key_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--hotel-key", help="TripAdvisor hotel_key (예: g294197-d5250436)")
    p.add_argument("--url", help="TripAdvisor 호텔 페이지 URL (키를 자동 추출)")
    p.add_argument("--run-dir", required=True, help="회차 폴더(이 스크립트가 보는 경로)")


def _add_rates_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--checkin", required=True, help="체크인 YYYY-MM-DD")
    p.add_argument("--checkout", required=True, help="체크아웃 YYYY-MM-DD")
    p.add_argument("--currency", default="USD", help="Xotelo 수집 통화(기본 USD — KRW 미지원, 원화는 환산 표시)")
    p.add_argument("--adults", type=int, default=2, help="성인 수(기본 2)")
    p.add_argument("--rooms", type=int, default=1, help="객실 수(기본 1)")
    p.add_argument("--no-krw", action="store_true", help="원화 환산 생략(수집 통화만 표시)")


def _add_output_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--name", help="호텔 표시명(선택 — /rates 는 이름 미제공)")
    p.add_argument("--format", choices=["json", "markdown"], default="markdown", help="출력 형식(기본 markdown)")
    p.add_argument("--output", help="결과 저장 경로(기본 stdout)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hotel-search", description="호텔 가격 비교 (Xotelo, 조회 전용 — 요청은 itda-hyve)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("plan", help="itda-hyve 호출 계획")
    psub = pp.add_subparsers(dest="kind", required=True)
    ppr = psub.add_parser("rates", help="요금(+환율) 호출 계획")
    _add_key_args(ppr)
    _add_rates_args(ppr)
    ppr.add_argument("--save-dir", required=True, help="같은 회차 폴더의 호스트 절대 경로(itda-hyve save_dir)")
    ppr.set_defaults(func=cmd_plan_rates)
    pph = psub.add_parser("heatmap", help="가격 달력 호출 계획")
    _add_key_args(pph)
    pph.add_argument("--checkout", required=True, help="체크아웃 YYYY-MM-DD")
    pph.add_argument("--save-dir", required=True, help="같은 회차 폴더의 호스트 절대 경로(itda-hyve save_dir)")
    pph.set_defaults(func=cmd_plan_heatmap)

    pr = sub.add_parser("rates", help="OTA별 요금 비교(원화 환산 병기)")
    _add_key_args(pr)
    _add_rates_args(pr)
    _add_output_args(pr)
    pr.set_defaults(func=cmd_rates)

    ph = sub.add_parser("heatmap", help="가격 달력(싼날/평균/비싼날)")
    _add_key_args(ph)
    ph.add_argument("--checkout", required=True, help="체크아웃 YYYY-MM-DD")
    _add_output_args(ph)
    ph.set_defaults(func=cmd_heatmap)

    pv = sub.add_parser("resolve", help="URL/텍스트 → hotel_key 추출")
    pv.add_argument("source", help="TripAdvisor URL 또는 g<geo>-d<hotel> 문자열")
    pv.set_defaults(func=cmd_resolve)
    return p


def _reconfigure_stdio() -> None:
    """Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 UTF-8 로 바꾼다."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def main(argv=None) -> int:
    _reconfigure_stdio()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except HotelSearchError as e:
        print(f"오류: {e}", file=sys.stderr)
        if getattr(args, "format", None) == "json" or args.cmd == "plan":
            _print_json({"status": "error", "error": e.kind, "detail": str(e), **e.extra})
        return e.code
    except Exception as e:  # noqa: BLE001
        print(f"예기치 못한 오류: {e}", file=sys.stderr)
        return EXIT_GENERAL


if __name__ == "__main__":
    sys.exit(main())
