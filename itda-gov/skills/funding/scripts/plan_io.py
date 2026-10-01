"""itda-hyve batch 계획 파일 — 쓰기·이름 짓기 (네트워크 없음).

funding 은 요청을 itda-hyve 에 맡긴다(itda-work/skills#45, 규칙 ``cowork-network-via-hyve``).
스크립트가 호출 목록을 batch ``plan_file`` 형식(``{calls, save_dir, timeout_sec}``)으로 쓰고,
모델은 그 파일 경로만 batch 에 넘긴다 — 호출 JSON 을 옮겨 적지 않는다.

계약:
  - 한 파일에 호출 40개까지(itda-hyve batch 는 40개를 넘으면 하나도 실행하지 않는다).
  - 한 파일에 **같은 호스트 20개까지**, 호스트를 번갈아 담는다. batch 는 동시 8개로 돌아
    한 호스트에 몰리면 옛 스크립트의 요청 간격(0.3~0.4초 순차)보다 훨씬 세게 두드린다(사용자 결정 D5).
  - 계획 파일은 회차 폴더(= ``save_dir``) 바로 아래에 둔다 — ``plan_file`` 의 상대 경로가 ``save_dir``
    기준으로 풀린다.
  - 저장 이름(``save_as``)은 회차 폴더 기준 상대 경로이고 한글이 없다.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, Optional

BATCH_LIMIT = 40        # itda-hyve batch 호출 상한
HOST_LIMIT = 20         # 계획 파일 하나에 같은 호스트 호출 상한(D5)
BATCH_TIMEOUT_SEC = 50  # Cowork 는 도구 호출 하나를 60초에서 끊는다
CALL_TIMEOUT_SEC = 30   # 쪽·상세 한 건
ATTACH_TIMEOUT_SEC = 45  # 첨부 한 건(수 MB)
PREVIEW = 3


def http_call(call_id: str, url: str, save_as: str, *, timeout_sec: int = CALL_TIMEOUT_SEC) -> dict[str, Any]:
    """batch 의 ``http_request`` 호출 한 칸. 리다이렉트는 따라가지 않는다(3xx 는 실패로 판정한다).

    User-Agent·Cookie 는 싣지 않는다 — itda-hyve 0.10.4 기본 UA(``Mozilla/5.0``)로 다섯 소스가
    응답한다(2026-09-30 실측). 쿼리는 ``params`` 가 아니라 ``url`` 에 사이트 순서 그대로 둔다
    (``params`` 는 이름순으로 다시 짠다 — ``request-profile-first``).
    """
    if not save_as or save_as.startswith(("/", ".")) or ".." in save_as.split("/"):
        raise ValueError(f"save_as 는 회차 폴더 기준 상대 경로다: {save_as!r}")
    if re.search(r"[^\x00-\x7f]", save_as):
        raise ValueError(f"save_as 에 한글을 넣지 않는다: {save_as!r}")
    return {
        "id": call_id,
        "tool": "http_request",
        "args": {"url": url, "follow_redirects": False, "timeout_sec": timeout_sec, "save_as": save_as},
    }


def host_of(call: dict[str, Any]) -> str:
    return (urllib.parse.urlsplit(call["args"]["url"]).hostname or "").lower()


def interleave(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """호스트별 순서를 지키며 번갈아 섞는다 — 한 파일에 한 호스트가 몰리지 않게."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for c in calls:
        groups.setdefault(host_of(c), []).append(c)
    out: list[dict[str, Any]] = []
    queues = list(groups.values())
    while any(queues):
        for q in queues:
            if q:
                out.append(q.pop(0))
    return out


def chunk(calls: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """40개·호스트당 20개 상한으로 나눈다. 넘치는 호스트 호출은 다음 파일로 미룬다."""
    pending = interleave(calls)
    files: list[list[dict[str, Any]]] = []
    while pending:
        cur: list[dict[str, Any]] = []
        per_host: dict[str, int] = {}
        rest: list[dict[str, Any]] = []
        for c in pending:
            h = host_of(c)
            if len(cur) < BATCH_LIMIT and per_host.get(h, 0) < HOST_LIMIT:
                cur.append(c)
                per_host[h] = per_host.get(h, 0) + 1
            else:
                rest.append(c)
        files.append(cur)
        pending = rest
    return files


def next_plan_name(run_dir: Path, stem: str) -> Path:
    """``<stem>-<n>.json`` 중 아직 없는 첫 번호(나뉜 파일 ``-<n>a`` 도 센다)."""
    used = set()
    for p in run_dir.glob(f"{stem}-*.json"):
        m = re.fullmatch(rf"{re.escape(stem)}-(\d+)[a-z]?\.json", p.name)
        if m:
            used.add(int(m.group(1)))
    n = 1
    while n in used:
        n += 1
    return run_dir / f"{stem}-{n}.json"


def write_plan(path: Path, run_dir: Path, calls: list[dict[str, Any]], save_dir: str) -> dict[str, Any]:
    """batch ``plan_file`` 을 쓴다. 나뉘면 ``<이름>a.json``·``<이름>b.json``.

    Returns: ``plan_files``(회차 폴더 기준 이름)·``batch_args``(batch 에 그대로 넘길 인자)·
    ``call_count``·``calls_preview``.
    """
    path = Path(path).expanduser()
    if path.suffix != ".json":
        raise ValueError(f"계획 파일은 .json 이다: {path}")
    if path.resolve().parent != Path(run_dir).resolve():
        raise ValueError(
            f"계획 파일은 회차 폴더 바로 아래에 쓴다(plan_file 은 save_dir 기준 상대 경로다) — 받은 값: {path}")
    if not calls:
        raise ValueError("계획할 호출이 없다")
    parts = chunk(calls)
    if len(parts) > 26:
        raise ValueError(f"호출이 {len(calls)}개다 — 소스를 나눠 받는다(계획 파일 26개 상한)")
    names, batch_args = [], []
    for i, part in enumerate(parts):
        target = path if len(parts) == 1 else path.with_name(f"{path.stem}{chr(ord('a') + i)}{path.suffix}")
        if target.exists():
            raise ValueError(f"계획 파일이 이미 있다: {target.name} — 다른 이름을 준다")
        payload = {"calls": part, "save_dir": save_dir, "timeout_sec": BATCH_TIMEOUT_SEC}
        target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        names.append(target.name)
        batch_args.append({"save_dir": save_dir, "plan_file": target.name})
    return {
        "plan_files": names,
        "batch_args": batch_args,
        "call_count": len(calls),
        "calls_preview": calls[:PREVIEW],
    }


RESYNC_ID = "resync-"   # 재동기화 회전의 호출 id 접두 — 계획 파일에 표식을 남기는 자리(itda-hyve 는 모르는 키를 거부한다)


class PlanLog:
    """회차 폴더의 계획 이력 — 저장 이름마다 몇 번 **시도**했는가, 파일이 어느 회전·계획 파일에서 왔는가.

    계획 파일은 이름이 아니라 모양(``{calls, save_dir}``)으로 알아본다(``--write``·``--next-plan`` 에 다른 이름을
    줘도 센다). 회전 번호는 ``<stem>-<n>[a-z].json`` 의 n 이다(나뉜 파일 a·b… 는 같은 회전). 다른 이름의 계획
    파일은 나뉜 파일(``mine2a``·``mine2b`` — 끝 글자만 다른 형제)끼리 한 회전, 나머지는 각자 한 회전이다.

    **시도**는 "그 계획이 **가장 늦게 담은** 저장 이름 중 파일(응답 또는 실패 자리)이 있는 것이 하나라도 있는 계획"
    만 센다(3차 리뷰 P1). 받지 않은 쪽은 회전마다 다시 계획되므로 계획이 겹치는데, 부르지 않은 앞 계획의 이름이 뒤
    계획으로 도착해도 앞 계획이 시도로 세어지지 않게 — 도착은 그 이름을 마지막으로 담은 계획에만 돌린다.
    """

    def __init__(self, files: list[tuple]):
        # (계획 파일 이름, 회전, save_as 목록, 시도됨[, 호출 id 목록]) — 회전·이름 순
        norm = [(f[0], f[1], list(f[2]), bool(f[3]), list(f[4]) if len(f) > 4 else [""] * len(f[2])) for f in files]
        self.files = sorted(norm, key=lambda f: (f[1], f[0]))

    @classmethod
    def read(cls, run_dir: Path) -> "PlanLog":
        run_dir = Path(run_dir)
        raw = []
        for p in sorted(run_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                if p.name.startswith("plan-"):
                    raise ValueError(f"계획 파일을 읽을 수 없다: {p.name} ({exc})") from exc
                continue  # 계획 파일이 아닌 JSON(사용자 메모 등)은 세지 않는다
            if not (isinstance(data, dict) and isinstance(data.get("calls"), list) and "save_dir" in data):
                continue
            calls = [c for c in data["calls"] if isinstance(((c or {}).get("args") or {}).get("save_as"), str)]
            raw.append((p.name, [c["args"]["save_as"] for c in calls], [str(c.get("id") or "") for c in calls]))
        # 회전: plan-<kind>-<n>[a-z] 는 n, 다른 이름은 끝 글자만 다른 형제끼리 한 회전
        stems = [n[:-5] for n, _, _ in raw]
        base = {}
        for st in stems:
            if not re.fullmatch(r"plan-(?:list|detail)-\d+[a-z]?", st) and re.search(r"[a-z]$", st):
                b = st[:-1]
                if sum(1 for o in stems if o != st and o[:-1] == b and re.search(r"[a-z]$", o)) >= 1:
                    base[st] = b
        extra, custom, files = 10 ** 6, {}, []
        for name, names, ids in raw:
            st = name[:-5]
            m = re.fullmatch(r"plan-(?:list|detail)-(\d+)[a-z]?", st)
            if m:
                rnd = int(m.group(1))
            else:
                key = base.get(st, st)
                if key not in custom:
                    custom[key] = extra
                    extra += 1
                rnd = custom[key]
            files.append([name, rnd, names, False, ids])
        files.sort(key=lambda f: (f[1], f[0]))
        last_plan = {}
        for f in files:
            for n in f[2]:
                last_plan[n] = f[0]
        for f in files:
            f[3] = any(last_plan[n] == f[0] and (run_dir / n).exists() for n in f[2])
        return cls([tuple(f) for f in files])

    def count(self, save_as: str) -> int:
        """그 저장 이름을 담은 **시도된** 계획 파일 수."""
        return sum(1 for _, _, names, att, _ in self.files if att and save_as in names)

    def origin(self, save_as: str) -> tuple[Optional[int], Optional[str]]:
        """있는 파일이 온 곳 — 그 이름을 담은 가장 늦은 시도된 계획(회전, 파일 이름). 모르면 (None, None).

        같은 이름을 여러 번 계획했다면 앞선 계획 뒤에는 파일이 없었으므로(그래서 다시 계획했다) 가장 늦은 계획에서 왔다."""
        for name, rnd, names, att, _ in reversed(self.files):
            if att and save_as in names:
                return rnd, name
        return None, None

    def rounds(self, prefix: str, *, attempted_only: bool = False) -> dict[int, list[str]]:
        """저장 이름이 ``prefix`` 로 시작하는 호출이 든 회전 → 그 회전의 해당 저장 이름들."""
        out: dict[int, list[str]] = {}
        for _, rnd, names, att, _ in self.files:
            if attempted_only and not att:
                continue
            hit = [n for n in names if n.startswith(prefix)]
            if hit:
                out.setdefault(rnd, []).extend(hit)
        return out

    def resync_rounds(self, prefix: str) -> int:
        """재동기화 표식(호출 id ``resync-``)이 든 **시도된** 회전 수(3차 리뷰 P6)."""
        hit = set()
        for _, rnd, names, att, ids in self.files:
            if att and any(n.startswith(prefix) and i.startswith(RESYNC_ID) for n, i in zip(names, ids)):
                hit.add(rnd)
        return len(hit)


def planned_counts(run_dir: Path) -> dict[str, int]:
    """저장 이름별 시도된 계획 수(``PlanLog.count`` 를 전부 편 것)."""
    log = PlanLog.read(run_dir)
    out: dict[str, int] = {}
    for _, _, names, att, _ in log.files:
        if att:
            for n in names:
                out[n] = out.get(n, 0) + 1
    return out
