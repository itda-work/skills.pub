"""hyve_store.py — itda-hyve 가 저장한 응답 파일로 파이프라인을 돌리고, 빠진 호출을 다음 계획으로 쓴다 (네트워크 없음).

흐름(회차 폴더 ``--run-dir`` 하나에 한 번):
    plan     → 회차 상태(eatery-state.json)를 만들고 collect 와 같은 일을 한다(첫 회차는 데이터랩 호출만 나온다)
    collect  → 저장된 파일로 모드 A/B 파이프라인을 돌린다. 파이프라인이 원한 요청 중 파일이 없거나 실패한 것이
               있으면 ``incomplete`` + 다음 호출(POST 는 ``single_calls``, GET 은 batch ``plan_file``)을 낸다.
               다 있으면 ``ok`` + 결과.

요청 하나의 저장 이름은 요청 모양의 지문이다(``raw/dl-<지문>.json``·``raw/ls-<지문>.json``) — 응답 본문에 조회 조건이
없어도 이름으로 짝을 맞춘다. 실패한 파일을 덮어쓰지 않고 ``-r2``·``-r3`` 이름으로 다시 받는다(최대 3번).
데이터랩 조회 기간은 plan 때 정해 상태에 둔다 — 회차 안에서 요청 본문이 바뀌지 않게.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import posixpath
import re
from pathlib import Path
from typing import Any, Callable, Optional

import adapters
from hyve_input import HyveFailure, HyveHTTPError, HyveInputError, read_input

STATE_NAME = "eatery-state.json"
BATCH_LIMIT = 40            # itda-hyve batch 는 40개를 넘으면 하나도 실행하지 않는다
BATCH_TIMEOUT_SEC = 50
MAX_TRIES = 3               # 같은 요청을 받으려는 시도 상한(실패 자리·HTTP 오류·잘림·형식 오류)
MAX_ABSENT = 3              # 계획에 실었는데 파일이 없던 회차 상한(호출을 안 했다)
DATALAB_WEEKS = 78          # ≥56주(YoY) 보장하는 조회 범위(약 18개월)
STOP_HYVE_CODES = {"secret_missing", "secret_host_denied", "secret_scope_denied"}
_WIN_ABS = re.compile(r"^[A-Za-z]:[\\/]")


class StoreError(Exception):
    """판정 불가 — ``kind`` 가 출력 JSON 의 ``error`` 값이다."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def host_abs_path(path: str) -> bool:
    """itda-hyve 가 도는 **호스트**의 절대 경로인가(Cowork VM 이 리눅스여도 호스트는 Windows 일 수 있다)."""
    return bool(path) and (path.startswith("/") or bool(_WIN_ABS.match(path)) or path.startswith("\\\\"))


def date_window(today: Optional[datetime.date] = None, weeks: int = DATALAB_WEEKS) -> tuple[str, str]:
    end = today or datetime.date.today()
    return (end - datetime.timedelta(weeks=weeks)).isoformat(), end.isoformat()


def fingerprint(args: dict[str, Any]) -> str:
    """요청 모양(url·method·params·body)의 지문 10자. 헤더는 자리표시라 넣지 않는다."""
    core = {k: args.get(k) for k in ("url", "method", "params", "body")}
    return hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:10]


def attempt_name(base: str, attempt: int) -> str:
    """저장 이름(``raw/dl-….json``)의 ``attempt`` 번째 이름. 저장 이름은 itda-hyve ``save_as`` 이자 ``calls`` 의 키라
    **POSIX 문자열로만** 다룬다 — ``Path`` 를 거치면 Windows 에서 ``raw\\…`` 가 돼 키가 갈린다(W17 리뷰 M1)."""
    if attempt <= 1:
        return base
    stem, ext = posixpath.splitext(base)
    return f"{stem}-r{attempt}{ext}"


def load_state(run_dir: Path) -> dict[str, Any]:
    p = run_dir / STATE_NAME
    if not p.is_file():
        raise StoreError("input", f"{STATE_NAME} 가 없다 — 이 폴더에서 plan 부터 한다: {run_dir}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreError("input", f"{STATE_NAME} 를 읽지 못했다: {exc}") from exc


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    (run_dir / STATE_NAME).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


class Store:
    """파이프라인에 넣는 파일 기반 어댑터. 요청마다 받은 파일을 판독하고, 없거나 실패한 요청을 모은다."""

    def __init__(self, run_dir: Path, state: dict[str, Any]):
        self.run_dir = run_dir
        self.state = state
        self.calls: dict[str, dict[str, Any]] = state.setdefault("calls", {})
        self.pending: dict[str, dict[str, Any]] = {}   # 이번에 받아야 할 요청: name → http_request 인자
        self.exhausted: list[str] = []                  # 상한을 넘겨 못 받은 요청의 사유
        self.stop: Optional[tuple[str, str]] = None     # (kind, message) — 사용자가 고칠 것(키·앱 설정)
        self.received = 0
        self._stopped_here = False

    # -- 요청 하나 --------------------------------------------------------
    def _fetch(self, kind: str, label: str, args: dict[str, Any], parse: Callable[[Any], tuple[bool, Any, str]],
               empty: Any) -> tuple[bool, Any, str]:
        base = f"raw/{kind}-{fingerprint(args)}.json"
        rec = self.calls.setdefault(base, {"label": label, "tries": 1, "absent": 0})
        name = attempt_name(base, rec["tries"])
        path = self.run_dir / name
        if not path.exists():
            if self.stop is not None:
                return False, empty, self.stop[1]
            if rec["absent"] >= MAX_ABSENT:
                self.exhausted.append(f"{label}: {MAX_ABSENT}번 계획했는데 받은 파일이 없다({name})")
                return False, empty, "받은 파일 없음"
            self.pending[name] = args
            return False, empty, "아직 받지 않음"
        reason = self._judge(path, parse)
        if reason is None:
            return True, self._parsed, ""
        if self._stopped_here:
            # 사용자가 키·앱 설정을 고친 뒤 **같은 회차 폴더**에서 collect 하면 다시 받게 다음 이름으로 넘긴다
            # — 실패 자리를 다시 읽어 같은 멈춤을 내지 않는다(W17 리뷰 m3). 멈춘 파일 전부를 이 회차에 넘기고, 상한은 그대로 센다.
            if rec["tries"] < MAX_TRIES:
                rec["tries"] += 1
                rec["absent"] = 0
            return False, empty, self.stop[1]
        if self.stop is not None:
            return False, empty, self.stop[1]
        if rec["tries"] >= MAX_TRIES:
            self.exhausted.append(f"{label}: {MAX_TRIES}번 받아도 실패 — {reason}")
            return False, empty, reason
        rec["tries"] += 1
        rec["absent"] = 0
        self.pending[attempt_name(base, rec["tries"])] = args
        return False, empty, f"다시 받는다({reason})"

    def _set_stop(self, kind: str, message: str) -> None:
        self._stopped_here = True
        if self.stop is None:
            self.stop = (kind, message)

    def _judge(self, path: Path, parse: Callable[[Any], tuple[bool, Any, str]]) -> Optional[str]:
        """None 이면 성공(self._parsed 에 결과). 아니면 실패 사유 — 멈출 실패면 self.stop 도 정한다."""
        self._parsed = None
        self._stopped_here = False
        try:
            body = read_input(path)
            obj = json.loads(body.data.decode("utf-8-sig"))
        except HyveFailure as exc:
            if exc.code in STOP_HYVE_CODES:
                self._set_stop("hyve", f"itda-hyve {exc.code}: {exc.hyve_message or exc} — 시크릿 탭에 NAVER_CLIENT_ID·"
                                     "NAVER_CLIENT_SECRET 을 등록하고(허용 호스트 openapi.naver.com) 같은 --run-dir 로 "
                                     "collect 를 다시 부른다(다시 받을 호출이 나온다)")
            return f"hyve: {exc}"
        except HyveHTTPError as exc:
            err = None
            try:
                err = adapters.naver_error(json.loads(exc.body.decode("utf-8-sig")))
            except (ValueError, UnicodeDecodeError):
                pass
            if err is not None and err.auth:
                self._set_stop("naver", f"{err} — 고친 뒤 같은 --run-dir 로 collect 를 다시 부른다")
            return f"http {exc.status}: {err or exc}"
        except HyveInputError as exc:
            return f"{exc.kind}: {exc}"
        except (ValueError, UnicodeDecodeError) as exc:
            return f"JSON 아님(잘림 의심): {exc}"
        try:
            ok, data, reason = parse(obj)
        except adapters.NaverAPIError as exc:
            if exc.auth:
                self._set_stop("naver", f"{exc} — 고친 뒤 같은 --run-dir 로 collect 를 다시 부른다")
            return str(exc)
        if not ok:
            return reason
        self.received += 1
        self._parsed = data
        return None

    # -- 파이프라인에 넣는 함수 --------------------------------------------
    def datalab_fn(self, keywords, start=None, end=None, unit="week"):
        kws = list(keywords)
        args = adapters.datalab_args(kws, start, end, unit)
        return self._fetch("dl", f"데이터랩({'/'.join(kws)})", args,
                           lambda obj: adapters.parse_datalab(obj, kws, start=start, end=end, unit=unit), None)

    def local_search_fn(self, q):
        return self._fetch("ls", f"지역검색({q})", adapters.local_args(q), adapters.parse_local, [])

    # -- 다음 계획 ------------------------------------------------------
    def write_next(self) -> dict[str, Any]:
        """빠진 요청을 이번 회차 계획으로 쓴다 — GET 은 plan 파일(batch), POST 는 single_calls."""
        save_dir = self.state["save_dir"]
        rnd = int(self.state.get("round", 0)) + 1
        prev = self.state.get("last_pending") or []
        if prev and not any((self.run_dir / n).exists() for n in prev):
            warn = "지난 계획의 파일이 하나도 없다 — 아래 호출을 먼저 부른다(Cowork 는 --run-dir 이 save_dir 와 같은 폴더인지 확인)"
        else:
            warn = ""
        gets, singles = [], []
        for name, args in sorted(self.pending.items()):
            base = re.sub(r"-r\d+(\.json)$", r"\1", name)
            rec = self.calls[base]
            if name in prev:
                rec["absent"] += 1
            call = dict(args, save_as=name)
            if args.get("method", "GET") == "GET":
                gets.append({"id": posixpath.splitext(posixpath.basename(name))[0], "tool": "http_request", "args": call})
            else:
                singles.append(dict(call, save_dir=save_dir))
        plan_files, batch_args = [], []
        parts = [gets[i:i + BATCH_LIMIT] for i in range(0, len(gets), BATCH_LIMIT)]
        for i, part in enumerate(parts):
            pname = f"plan-{rnd}.json" if len(parts) == 1 else f"plan-{rnd}{chr(ord('a') + i)}.json"
            payload = {"calls": part, "save_dir": save_dir, "timeout_sec": BATCH_TIMEOUT_SEC}
            (self.run_dir / pname).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            plan_files.append(pname)
            batch_args.append({"save_dir": save_dir, "plan_file": pname})
        self.state["round"] = rnd
        self.state["last_pending"] = sorted(self.pending)
        out: dict[str, Any] = {"round": rnd, "call_count": len(gets) + len(singles),
                               "batch_args": batch_args, "plan_files": plan_files, "single_calls": singles}
        if warn:
            out["warning"] = warn
        return out
