#!/usr/bin/env python3
"""xlsx 수식 캐시값 재계산 — LibreOffice(soffice) 헤드리스 단독(#1690).

    python3 recalc.py in.xlsx [out.xlsx] [--json] [--timeout 180] [--soffice PATH]

엔진 7종(excelize·Formualizer·IronCalc 등)을 LibreOffice 정답과 대조한 결과 전부 에러 없이 틀린 값을 냈다.
그래서 계산은 LibreOffice 만 하고, 스크립트는 계산 **전후의 검사**만 맡는다.

계산 전
  1. 입력을 읽는다(zip·XML). 외부 링크를 참조하는 수식의 **링크 값 캐시가 없으면 거부**한다(exit 8) —
     LibreOffice 는 그 경우 0 을 성공으로 쓴다. 시트 캐시만 빈 경우(openpyxl 저장)는 계산한다.
  2. POSIX 에서 `socket(AF_UNIX)` 를 시험한다. 막힌 샌드박스에서는 LibreOffice 가 기동하지 못하므로 원인을 밝혀 실패한다(exit 7).
  3. `soffice --version` 이 24.8 미만이면 실패한다(exit 6) — 7.4.7 은 XLOOKUP 등 `_xlfn.` 함수를 몰라
     실무 파일 한 개에서 59,547셀을 에러 없이 틀렸다(엔진 비교 실측).
계산
  실행마다 격리 프로필(OOXML 재계산 모드 "항상")로 `--convert-to xlsx` 한다. timeout 을 넘기면 프로세스 그룹과
  이 실행의 프로필(경로·URI)로 뜬 프로세스를 정리하고 exit 4. 재시도하지 않는다.
계산 후
  수식 셀마다 타입에 맞는 캐시가 있는지(빈 숫자 `<v></v>` 는 없음으로 본다), 입력 수식 셀이 모두 수식으로 남았는지,
  외부 링크 파트가 줄지 않았는지 확인한다(exit 5). 수식 문자열이 LibreOffice 재직렬화로 바뀐 셀은 `formula_rewritten`
  으로 보고한다 — 막지는 않지만, 값이 바뀔 수 있는 모양(숫자·문자열 리터럴·함수·참조 변화)은 위험으로 표시한다.

종료 코드: 0 성공 · 2 사용법·입력 오류 · 3 soffice 없음·실행 불가 · 4 timeout · 5 변환·산출 검증 실패
          · 6 LibreOffice 버전 미달·판독 불가 · 7 AF_UNIX 소켓 차단 · 8 외부 링크 값 캐시 없음(계산 전 거부)
          · 9 지원하지 않는 통합문서 구조(Strict OOXML·데이터 테이블 — 계산 전 거부)
"""
from __future__ import annotations

import sys

if sys.version_info < (3, 10):
    sys.exit("xlsx-recalc 는 Python 3.10 이상이 필요하다")

import argparse
import json
import os
import posixpath
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.parse
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import formula_text  # noqa: E402
import xlsxscan  # noqa: E402

EXIT_USAGE, EXIT_NO_SOFFICE, EXIT_TIMEOUT, EXIT_FAILED = 2, 3, 4, 5
EXIT_LO_VERSION, EXIT_AF_UNIX, EXIT_EXTERNAL_LINK, EXIT_UNSUPPORTED = 6, 7, 8, 9
DEFAULT_TIMEOUT = 180
MIN_LO_VERSION = (24, 8)
LIST_LIMIT = 50

_RECALC_ALWAYS_XCU = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>0</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="ODFRecalcMode" oor:op="fuse"><value>0</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="FirstRun" oor:op="fuse"><value>false</value></prop></item>
</oor:items>
"""

_CANDIDATES = (
    "/usr/bin/soffice",
    "/usr/lib/libreoffice/program/soffice",
    "/opt/libreoffice/program/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
)


class RecalcError(Exception):
    def __init__(self, code: int, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


# ── 환경 검사 ──────────────────────────────────────────────────────────────

def find_soffice(explicit: str | None = None) -> str:
    """soffice 실행 파일을 찾는다. 못 찾으면 RecalcError(3)."""
    if explicit:
        found = shutil.which(explicit)
        if found:
            return found
        if Path(explicit).is_file():
            return explicit
        raise RecalcError(EXIT_NO_SOFFICE, f"지정한 soffice 가 없다: {explicit}")
    env = os.environ.get("SOFFICE")
    if env:
        return find_soffice(env)
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for cand in _CANDIDATES:
        if Path(cand).is_file():
            return cand
    raise RecalcError(
        EXIT_NO_SOFFICE,
        "LibreOffice(soffice) 를 찾지 못했다 — 설치하거나 --soffice/SOFFICE 로 경로를 지정하라",
    )


def probe_af_unix() -> None:
    """LibreOffice 는 기동 때 단일 인스턴스 IPC 를 socket(AF_UNIX) 로 만든다. 막혀 있으면 원인과 함께 실패한다.

    막힌 샌드박스에서 soffice 는 0.1초 안에 무관한 경고(`failed to launch javaldx`)만 남기고 죽는다(#1690 A/B §3.3).
    """
    if os.name != "posix" or not hasattr(socket, "AF_UNIX"):
        return
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    except OSError as e:
        raise RecalcError(
            EXIT_AF_UNIX,
            f"이 환경은 AF_UNIX 소켓 생성을 막는다({e}). LibreOffice 는 기동에 AF_UNIX IPC 가 필요해 실행할 수 없다 — "
            "샌드박스(seccomp 등) 설정을 확인하라",
        ) from None
    s.close()


def _version_exe(exe: str) -> str:
    # Windows 의 soffice.exe 는 GUI 서브시스템이라 --version 출력이 콘솔로 오지 않는다. 같은 폴더의 soffice.com 을 쓴다.
    p = Path(exe)
    if p.suffix.lower() == ".exe":
        com = p.with_suffix(".com")
        if com.is_file():
            return str(com)
    return exe


def parse_version(text: str) -> tuple[int, ...] | None:
    """`soffice --version` 첫 줄이 **LibreOffice 로 시작할 때만** 버전을 읽는다.

    `Collabora Office … (based on LibreOffice 25.2)`·`NotLibreOffice 99.1` 처럼 다른 제품 문자열에 섞인 번호로
    게이트를 통과시키지 않는다(Codex R2 #11).
    """
    first = next((l.strip() for l in text.splitlines() if l.strip()), "")
    m = re.match(r"LibreOffice(?:Dev)?\s+(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?(?!\d)", first)
    if not m:
        return None
    return tuple(int(g) for g in m.groups() if g is not None)


def _run_owned(cmd: list[str], timeout: float) -> tuple[int, str]:
    """자식 프로세스를 새 그룹으로 띄워 출력과 종료 코드를 받는다. timeout 이면 그룹째 정리한다(Codex R2 #13)."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **_session_kw())
    except OSError as e:
        raise RecalcError(EXIT_NO_SOFFICE, f"soffice 를 실행할 수 없다: {cmd[0]} ({e})") from None
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(proc.pid)
        try:
            proc.communicate(timeout=5)
        except (subprocess.TimeoutExpired, ValueError):
            pass
        raise
    finally:
        _kill_group(proc.pid)
    return proc.returncode, (out or b"").decode("utf-8", errors="replace")


VERSION_TIMEOUT = 60


def libreoffice_version(exe: str, profile_uri: str, timeout: float | None = None) -> tuple[tuple[int, ...], str]:
    """`--version` 은 계산 timeout 과 따로 잰다 — 작은 --timeout 이 버전 판독 실패로 둔갑하지 않게."""
    cmd = [_version_exe(exe), f"-env:UserInstallation={profile_uri}", "--version"]
    try:
        rc, raw = _run_owned(cmd, VERSION_TIMEOUT if timeout is None else timeout)
    except subprocess.TimeoutExpired:
        raise RecalcError(EXIT_LO_VERSION, "soffice --version 이 응답하지 않았다") from None
    raw = raw.strip()
    version = parse_version(raw) if rc == 0 else None
    if version is None:
        raise RecalcError(EXIT_LO_VERSION,
                          f"LibreOffice 버전을 읽지 못했다(exit {rc}): {raw[:200]!r} — 24.8 이상인지 확인할 수 없어 멈춘다")
    return version, raw.splitlines()[0]


def check_version(version: tuple[int, ...], raw: str) -> None:
    if version[:2] < MIN_LO_VERSION:
        raise RecalcError(
            EXIT_LO_VERSION,
            f"LibreOffice {'.'.join(map(str, version))} 는 지원하지 않는다(24.8 이상 필요). 24.8 미만은 XLOOKUP 같은 `_xlfn.` 함수를 "
            "몰라 에러 없이 틀린 값을 낸다 — 실측: 7.4.7 에서 IFERROR(XLOOKUP(..)) 가 모두 대체값으로 떨어져 59,547셀이 달랐다(#1690). "
            f"LibreOffice 를 올리거나 다른 환경에서 실행하라 ({raw})",
        )


# ── 프로세스 ───────────────────────────────────────────────────────────────

def _session_kw() -> dict:
    if os.name == "posix":
        return {"start_new_session": True}
    return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}


def _group_alive(pgid: int) -> bool:
    """그룹에 **좀비가 아닌** 구성원이 남았는가.

    `killpg(pgid, 0)` 은 거둬지지 않은 좀비에도 성공한다 — 부모(우리)가 아직 wait 하지 않은 리더나, PID 1 이 좀비를
    거두지 않는 컨테이너의 손자까지. 그걸 "살아 있음" 으로 보면 이미 끝난 그룹을 5초씩 두 번 기다려 timeout 이
    10초 늦게 반환된다(#1690 Cowork 프로브 실측: --timeout 0.3 → 10.5초). Linux 는 /proc 로 상태를 본다.
    """
    proc = Path("/proc")
    if proc.is_dir() and (proc / "self" / "stat").exists():
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            except (OSError, IndexError):
                continue
            if len(fields) > 2 and fields[2] == str(pgid) and fields[0] != "Z":
                return True
        return False
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _kill_group(pgid: int) -> None:
    """이 실행이 만든 프로세스 그룹 전체를 끝낸다. 부모가 이미 끝났어도 그룹의 남은 구성원을 정리한다(Codex #18).

    대기는 좀비가 아닌 구성원만 센다(_group_alive) — 거둬지지 않은 리더를 기다리지 않는다.
    """
    if os.name != "posix":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pgid)], capture_output=True)
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            return
        deadline = time.monotonic() + (3 if sig == signal.SIGTERM else 5)
        while time.monotonic() < deadline:
            if not _group_alive(pgid):
                return
            time.sleep(0.05)


def profile_markers(work: Path) -> list[str]:
    """프로세스 인자에서 이 실행을 알아볼 문자열 — 이 실행만의 작업 폴더(mkdtemp)에 **경로 구분자까지** 붙인다.

    soffice 에는 프로필을 URI(퍼센트 인코딩)로, 입력은 경로로 넘기므로 둘 다 찾는다. 끝의 `/` 가 없으면
    `/tmp/job/profile` 이 `/tmp/job/profile-other` 에도 걸려 남의 프로세스를 죽인다(Codex R2 #1).
    """
    return sorted({str(work) + os.sep, work.as_uri() + "/"})


def process_args() -> list[tuple[int, str]]:
    # /proc 는 인자 사이를 NUL 로, ps 는 공백으로 이어 붙인다. 마커 앞 경계 판정(_owns)에 둘 다 쓰인다.
    """(pid, 전체 인자 문자열) 목록. 인자가 잘리면 프로필 마커를 놓치므로 잘리지 않는 경로만 쓴다.

    Linux 는 /proc/<pid>/cmdline 을 읽는다 — procps `ps` 는 tty 가 없으면 args 를 화면 폭으로 자른다(#1690 Docker 실측:
    프로필 URI 가 잘려 잔존 프로세스 0개를 찾았다). 그 밖의 POSIX 는 `ps -ww`(폭 제한 해제)를 쓴다.
    """
    proc = Path("/proc")
    if proc.is_dir() and (proc / "self" / "cmdline").exists():
        out = []
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                raw = (entry / "cmdline").read_bytes()
            except OSError:
                continue
            if raw:
                # 끝의 NUL 을 남겨 "정확히 나뉜 인자" 임을 _owns 에 알린다(인자 하나뿐이어도).
                out.append((int(entry.name), raw.rstrip(b"\0").decode("utf-8", errors="replace") + "\0"))
        return out
    try:
        text = subprocess.run(["ps", "-ww", "-eo", "pid=,args="], capture_output=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    out = []
    for line in text.decode("utf-8", errors="replace").splitlines():
        pid_s, _, args = line.strip().partition(" ")
        if pid_s.isdigit():
            out.append((int(pid_s), args))
    return out


def _owns(args: str, markers: list[str]) -> bool:
    """마커가 **인자의 시작**(또는 `-env:UserInstallation=` 값의 시작)에 있을 때만 이 실행의 프로세스다.

    부분 문자열로 찾으면 `file:///archive/tmp/job/profile` 이 마커 `/tmp/job/` 에 걸린다(Codex R3 #1).
    /proc 판독(NUL 구분)은 인자를 정확히 나눠 **NUL 만** 경계로 본다 — 인자 안의 공백(`/backup /tmp/job/…`)을 경계로 보면
    남의 프로세스를 죽인다(Codex R4). ps 판독(공백 구분, /proc 가 없는 OS)은 인자 경계를 알 수 없어 공백을 경계로 쓴다.
    """
    if "\0" in args or args.endswith("\0"):
        tokens = args.split("\0")
    else:
        tokens = args.split()
    prefixes = [m for m in markers] + ["-env:UserInstallation=" + m for m in markers]
    return any(tok.startswith(prefixes_) for tok in tokens for prefixes_ in prefixes)


def _kill_by_profile(markers: list[str]) -> int:
    """이 실행의 작업 폴더(프로필·입력)를 인자로 가진 프로세스만 종료한다(POSIX). 종료한 수를 돌려준다."""
    if os.name != "posix":
        return 0
    killed = 0
    for pid, args in process_args():
        if pid in (os.getpid(), os.getppid()) or not _owns(args, markers):
            continue
        try:
            os.kill(pid, signal.SIGKILL)
            killed += 1
        except (ProcessLookupError, PermissionError):
            pass
    return killed


# ── 검사 ───────────────────────────────────────────────────────────────────

def link_location(target: str, base: Path) -> str:
    """외부 링크 대상이 가리키는 위치를 LibreOffice 와 같은 방식으로 정규화한다(비교용).

    LibreOffice 는 저장할 때 절대 경로를 작업 폴더 기준 상대 경로로 바꾸고(`/data/x.xlsx` → `../../../data/x.xlsx`),
    UNC 는 `file://server/…` 로 쓴다(#1690 실측). 표기가 달라도 같은 위치인지 가리기 위한 정규형이다.
    """
    t = target.strip()
    if re.match(r"(?i)(https?|ftp)://", t):
        return t
    # LibreOffice 는 모든 대상을 URI 참조로 다룬다 — 평문 `/data/a b` 와 `/data/a%20b` 를 같은 파일로 보고 `%20` 으로 쓰며,
    # `file:///…%2520…` 은 `%2520` 그대로 쓴다(#1690 실측). 그래서 file:// 여부와 무관하게 **한 번** 디코딩한다(Codex R3 신규 #1).
    if t.lower().startswith("file://"):
        t = t[7:]
        if not t.startswith("/"):
            t = "//" + t
    t = urllib.parse.unquote(t).replace("\\", "/")
    if t.startswith("//"):
        return "//" + posixpath.normpath(t[2:])
    if re.match(r"[A-Za-z]:/", t):
        return posixpath.normpath("/" + t)
    if t.startswith("/"):
        return posixpath.normpath(t)
    root = base.as_posix()
    if re.match(r"[A-Za-z]:/", root):
        root = "/" + root
    return posixpath.normpath(posixpath.join(root, t))


def restore_link_targets(produced: Path, inp: xlsxscan.ScanResult, out: xlsxscan.ScanResult, base: Path) -> list[dict]:
    """LibreOffice 가 표기만 바꾼 외부 링크 대상 경로를 입력 원문으로 되돌린다. 되돌린 목록을 돌려준다.

    링크 수·종류·시트 이름이 같고, 두 대상이 **같은 위치**를 가리킬 때만 되돌린다. 위치가 다르거나 LibreOffice 가 링크를
    합쳤으면(같은 파일을 가리키는 두 링크 → 하나, 실측) 손대지 않는다 — 산출 검증(compare)이 exit 5 로 막는다.
    """
    ins = [l for l in inp.external_links if l.kind == "book"]
    outs = [l for l in out.external_links if l.kind == "book"]
    if len(ins) != len(outs):
        return []
    changes = {}
    for a, b in zip(ins, outs):
        if a.target == b.target or b.part is None:
            continue
        if (a.kind, tuple(s.upper() for s in a.sheet_names)) != (b.kind, tuple(s.upper() for s in b.sheet_names)):
            return []
        if link_location(a.target, base) != link_location(b.target, base):
            return []
        rels = posixpath.join(posixpath.dirname(b.part), "_rels", posixpath.basename(b.part) + ".rels")
        changes[rels] = (b.target, a.target)
    if not changes:
        return []
    tmp = produced.with_name(produced.name + ".links")
    try:
        _rewrite_zip(produced, tmp, changes)
        os.replace(tmp, produced)
    except (OSError, zipfile.BadZipFile) as e:
        raise RecalcError(EXIT_FAILED, f"외부 링크 대상 경로를 되돌리는 중 파일 오류: {e}") from None
    return [{"from": old, "to": new} for old, new in changes.values()]


def _rewrite_zip(produced: Path, tmp: Path, changes: dict[str, tuple[str, str]]) -> None:
    with zipfile.ZipFile(produced) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info)
            if info.filename in changes:
                old, new = changes[info.filename]
                text = data.decode("utf-8")
                pat = re.compile(r'(Target=")' + re.escape(xml_escape(old, {'"': "&quot;"})) + r'(")')
                text, n = pat.subn(lambda m: m.group(1) + xml_escape(new, {'"': "&quot;"}) + m.group(2), text)
                if n != 1:
                    raise RecalcError(EXIT_FAILED, f"외부 링크 대상 경로를 되돌리지 못했다: {info.filename}")
                data = text.encode("utf-8")
            zout.writestr(info, data)


def _scan(path: Path, code: int, what: str) -> xlsxscan.ScanResult:
    try:
        return xlsxscan.scan(str(path))
    except xlsxscan.UnsupportedWorkbook as e:
        if code == EXIT_USAGE:  # 입력 구조 — 계산 전 거부
            raise RecalcError(EXIT_UNSUPPORTED, f"{what}: {e}") from None
        raise RecalcError(code, f"{what}을 검증할 수 없다: {e}") from None
    except xlsxscan.ScanError as e:
        raise RecalcError(code, f"{what}을 읽지 못했다: {e}") from None


def compare(inp: xlsxscan.ScanResult, out: xlsxscan.ScanResult) -> dict:
    """산출 검증 + 재직렬화 보고. 검증 실패는 RecalcError(5)."""
    out_cells = {c.key: c for c in out.formulas}
    lost = [c for c in inp.formulas if c.key not in out_cells]
    if lost:
        where = ", ".join(f"{c.sheet}!{c.cell}" for c in lost[:10])
        raise RecalcError(EXIT_FAILED, f"재계산 산출에서 수식이 사라진 셀 {len(lost)}개: {where}",
                          {"lost_formula_cells": len(lost)})
    missing = out.missing_cache
    if missing:
        where = ", ".join(f"{c.sheet}!{c.cell}({c.cache_problem})" for c in missing[:10])
        raise RecalcError(EXIT_FAILED, f"재계산 후에도 캐시가 없는 수식 셀 {len(missing)}개: {where}",
                          {"missing_cache_cells": len(missing)})
    for c in inp.formulas:
        if c.f_type == "array":
            o = out_cells[c.key]
            if o.f_type != "array" or xlsxscan._span(o.ref) != xlsxscan._span(c.ref):
                raise RecalcError(EXIT_FAILED, f"배열 수식 범위가 바뀌었다: {c.sheet}!{c.cell} {c.ref} → {o.ref or '(배열 아님)'}")
    # 입력에 없던 배열(예: SEQUENCE 가 산출에서 배열이 됨)도 결과 셀을 확인한다 — 산출 쪽 배열 전수(Codex R3 #8).
    try:
        for o in out.formulas:
            if o.f_type != "array":
                continue
            if not o.ref:  # 적용 범위를 모르면 결과 셀을 검증할 수 없다(Codex R4)
                raise RecalcError(EXIT_FAILED, f"배열 수식에 적용 범위(ref)가 없어 결과 셀을 검증할 수 없다: {o.sheet}!{o.cell}")
            for cell in xlsxscan.array_cells(o.ref):
                if cell == o.cell:
                    continue
                problem = out.array_results.get((o.sheet, cell), "array_result_cell_missing")
                if problem is not None:
                    raise RecalcError(EXIT_FAILED, f"배열 수식 결과 셀에 캐시가 없다: {o.sheet}!{cell} ({problem})")
    except xlsxscan.ScanError as e:
        raise RecalcError(EXIT_FAILED, str(e)) from None
    in_ids = [l.identity for l in inp.external_links if l.kind != "missing"]
    out_ids = [l.identity for l in out.external_links if l.kind != "missing"]
    if in_ids != out_ids:
        raise RecalcError(EXIT_FAILED, f"외부 링크가 보존되지 않았다(종류·대상 경로·시트 이름): {in_ids} → {out_ids}")
    rewritten = []
    for c in inp.formulas:
        o = out_cells[c.key]
        before, after = c.formula.strip(), o.formula.strip()
        if c.f_type == "array" or o.f_type == "array":
            before, after = before.lstrip("{").rstrip("}"), after.lstrip("{").rstrip("}")
        array_change = (c.f_type == "array") != (o.f_type == "array")
        if before.lstrip("=") == after.lstrip("=") and not array_change:
            continue
        risks = formula_text.rewrite_risks(before, after)
        if array_change:
            risks.append("array_formula_changed")  # 일반 수식이 배열로(또는 반대로) 저장됨 — 결과가 다른 셀로 번질 수 있다
        rewritten.append({"sheet": c.sheet, "cell": c.cell, "before": before, "after": after, "risks": risks})
    risky = [r for r in rewritten if r["risks"]]
    shown = (risky + [r for r in rewritten if not r["risks"]])[:LIST_LIMIT]
    return {
        "formula_rewritten_count": len(rewritten),
        "formula_rewritten_risky_count": len(risky),
        "formula_rewritten": shown,
    }


# ── 본체 ───────────────────────────────────────────────────────────────────

def default_output(src: Path) -> Path:
    return src.with_name(f"{src.stem}-recalc{src.suffix or '.xlsx'}")


def recalc(src: str, dst: str | None = None, *, timeout: float = DEFAULT_TIMEOUT, soffice: str | None = None) -> dict:
    """src 를 LibreOffice 로 재계산해 dst 에 쓴다. 실패는 RecalcError."""
    started = time.monotonic()
    src_p = Path(src).resolve()
    dst_p = Path(dst).resolve() if dst else default_output(src_p)
    if not src_p.is_file():
        raise RecalcError(EXIT_USAGE, f"입력 파일이 없다: {src}")
    if src_p == dst_p:
        raise RecalcError(EXIT_USAGE, "입력과 출력 경로가 같다 — 원본을 덮어쓰지 않는다")
    if not dst_p.parent.is_dir():
        raise RecalcError(EXIT_USAGE, f"출력 폴더가 없다: {dst_p.parent}")
    if timeout <= 0:
        raise RecalcError(EXIT_USAGE, "--timeout 은 0보다 커야 한다")

    inp = _scan(src_p, EXIT_USAGE, "입력 파일(xlsx)")
    ext_count, ext_problems = xlsxscan.external_link_problems(inp)
    if ext_problems:
        where = "; ".join(f"{p.sheet}!{p.cell} {p.reference} {p.reason}" for p in ext_problems[:5])
        by_filename = sum(1 for p in ext_problems if p.reason == "external_workbook_by_filename_without_link_part")
        why = []
        if len(ext_problems) > by_filename:
            why.append(f"링크 값 캐시가 없거나 필요한 셀을 확인할 수 없는 참조 {len(ext_problems) - by_filename}건"
                       f"(LibreOffice 는 이 경우 0 을 성공으로 쓴다)")
        if by_filename:  # openpyxl 저장형 — 값 캐시를 담을 링크 파트 자체가 없다(#1690 Cowork 실측)
            why.append(f"링크 정보 없이 파일 이름만 적힌 참조 {by_filename}건(계산에 쓸 값이 파일에 없다)")
        raise RecalcError(
            EXIT_EXTERNAL_LINK,
            f"외부 통합문서를 참조하는 수식이라 계산하지 않았다 — {'; '.join(why)}. "
            f"원본을 Excel 에서 열어 링크를 업데이트해 저장한 뒤 다시 실행하라: {where}",
            {"external_link_problems": [p.__dict__ for p in ext_problems[:LIST_LIMIT]],
             "external_link_problem_count": len(ext_problems)},
        )
    base = {
        "input": str(src_p),
        "output": str(dst_p),
        "formula_cells": len(inp.formulas),
        "input_missing_cache": len(inp.missing_cache),
        "external_link_refs": ext_count,
        "workbook": {"date1904": inp.date1904, "full_precision": inp.full_precision},
    }
    if not inp.formulas:
        try:
            shutil.copyfile(src_p, dst_p)
        except OSError as e:
            raise RecalcError(EXIT_FAILED, f"산출 파일을 쓰지 못했다: {dst_p} ({e})") from None
        return {"status": "ok", "engine": "none", **base, "error_cells": [], "error_cell_count": 0,
                "formula_rewritten_count": 0, "formula_rewritten_risky_count": 0, "formula_rewritten": [],
                "note": "수식이 없어 재계산하지 않고 그대로 복사했다",
                "elapsed_ms": int((time.monotonic() - started) * 1000)}

    probe_af_unix()
    exe = find_soffice(soffice)
    try:
        work = Path(tempfile.mkdtemp(prefix="xlsx-recalc-lo-"))
    except OSError as e:
        raise RecalcError(EXIT_FAILED, f"임시 작업 폴더를 만들지 못했다: {e}") from None
    profile = work / "profile"
    markers = profile_markers(work)
    stray = 0
    try:
        try:
            user = profile / "user"
            user.mkdir(parents=True)
            (user / "registrymodifications.xcu").write_text(_RECALC_ALWAYS_XCU, encoding="utf-8")
            # 입력과 산출을 **같은 폴더**에 두되 이름은 다르게 한다. 폴더가 다르면 LibreOffice 가 외부 링크의 상대 경로를
            # 작업 폴더 기준으로 바꿔 쓴다(other.xlsx → ../in/other.xlsx, #1690 실측). 같은 이름이면 열린 원본을 덮어쓰지 못해
            # 저장이 실패하는데도 exit 0 이다(실측) — 그래서 입력은 book.input, 산출은 새 파일 book.xlsx 다.
            io_dir = work / "io"
            io_dir.mkdir()
            staged = io_dir / "book.input"
            shutil.copyfile(src_p, staged)
        except OSError as e:
            raise RecalcError(EXIT_FAILED, f"작업 폴더 준비 실패: {e}") from None

        version, version_raw = libreoffice_version(exe, profile.as_uri())
        check_version(version, version_raw)

        cmd = [
            exe,
            f"-env:UserInstallation={profile.as_uri()}",
            "--headless", "--invisible", "--norestore", "--nologo", "--nodefault", "--nolockcheck",
            "--infilter=Calc MS Excel 2007 XML",
            "--convert-to", "xlsx:Calc MS Excel 2007 XML",
            "--outdir", str(io_dir),
            str(staged),
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **_session_kw())
        except OSError as e:
            raise RecalcError(EXIT_NO_SOFFICE, f"soffice 를 실행할 수 없다: {exe} ({e})") from None
        try:
            log_b, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc.pid)
            stray = _kill_by_profile(markers)
            try:
                proc.communicate(timeout=5)
            except (subprocess.TimeoutExpired, ValueError):
                pass
            raise RecalcError(
                EXIT_TIMEOUT,
                f"LibreOffice 재계산이 {timeout:g}초 안에 끝나지 않아 종료했다(재시도하지 않음)",
            ) from None
        finally:
            _kill_group(proc.pid)
        log = (log_b or b"").decode("utf-8", errors="replace")
        produced = io_dir / "book.xlsx"
        store_error = any(line.lstrip().startswith("Error:") for line in log.splitlines())
        if proc.returncode != 0 or not produced.is_file() or store_error:
            # LibreOffice 는 저장 실패(`SfxBaseModel::impl_store … failed`)에도 exit 0 을 낸다(#1690 실측) — 로그도 본다.
            raise RecalcError(EXIT_FAILED, f"LibreOffice 변환 실패(exit {proc.returncode}): {log.strip()[-400:]}")
        out = _scan(produced, EXIT_FAILED, "재계산 산출")
        restored = restore_link_targets(produced, inp, out, io_dir)
        if restored:
            out = _scan(produced, EXIT_FAILED, "재계산 산출")
        report = compare(inp, out)
        tmp_dst = dst_p.with_name(dst_p.name + ".tmp-recalc")
        try:
            shutil.copyfile(produced, tmp_dst)
            os.replace(tmp_dst, dst_p)
        except OSError as e:
            try:
                tmp_dst.unlink()
            except OSError:
                pass
            raise RecalcError(EXIT_FAILED, f"산출 파일을 쓰지 못했다: {dst_p} ({e})") from None
        errors = out.error_cells
        return {
            "status": "ok",
            "engine": "libreoffice",
            "libreoffice_version": ".".join(map(str, version)),
            **base,
            "error_cells": [{"sheet": c.sheet, "cell": c.cell, "value": c.value} for c in errors[:LIST_LIMIT]],
            "error_cell_count": len(errors),
            **report,
            "external_link_targets_restored": restored,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    finally:
        stray += _kill_by_profile(markers)
        if stray:
            print(f"[xlsx-recalc] 잔존 soffice {stray}개를 정리했다", file=sys.stderr)
        shutil.rmtree(work, ignore_errors=True)


def _reconfigure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _reconfigure_utf8()
    ap = argparse.ArgumentParser(description="xlsx 수식 캐시값 재계산(LibreOffice 헤드리스 · 격리 프로필 · timeout)")
    ap.add_argument("input")
    ap.add_argument("output", nargs="?", help="기본: <입력 이름>-recalc.xlsx")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"초(기본 {DEFAULT_TIMEOUT})")
    ap.add_argument("--soffice", help="soffice 경로(기본: PATH·SOFFICE·표준 위치)")
    args = ap.parse_args(argv)
    try:
        result = recalc(args.input, args.output, timeout=args.timeout, soffice=args.soffice)
    except RecalcError as e:
        if args.json:
            print(json.dumps({"status": "failed", "exit": e.code, "error": str(e), **e.details}, ensure_ascii=False))
        else:
            print(f"오류: {e}", file=sys.stderr)
        return e.code
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if result["engine"] == "none":
        print(f"ok: {result['note']} → {result['output']}")
        return 0
    print(f"ok: LibreOffice {result['libreoffice_version']} 로 수식 {result['formula_cells']}개 재계산 → "
          f"{result['output']} ({result['elapsed_ms']}ms)")
    if result["error_cell_count"]:
        print(f"  에러 값 셀 {result['error_cell_count']}개: "
              + ", ".join(f"{c['sheet']}!{c['cell']}={c['value']}" for c in result["error_cells"][:10]))
    for r in result.get("external_link_targets_restored", []):
        print(f"  외부 링크 대상 경로를 원문으로 되돌렸다: {r['from']} → {r['to']}")
    if result["formula_rewritten_count"]:
        print(f"  LibreOffice 가 수식 표기를 바꾼 셀 {result['formula_rewritten_count']}개"
              f"(값이 바뀔 수 있는 모양 {result['formula_rewritten_risky_count']}개)")
        for r in result["formula_rewritten"][:10]:
            mark = f" ⚠ {','.join(r['risks'])}" if r["risks"] else ""
            print(f"    {r['sheet']}!{r['cell']}: {r['before']} → {r['after']}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
