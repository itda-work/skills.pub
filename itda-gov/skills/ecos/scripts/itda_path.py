"""itda-skills 데이터 경로 해석 유틸리티.

모든 환경(macOS · Linux · Windows 로컬, Cowork 샌드박스)에서
동일한 후보 경로 열거(candidate-path enumeration) 알고리즘으로
적절한 데이터 디렉토리를 결정한다.

환경 분기 로직을 완전히 제거하고
단일 _candidate_roots() 함수로 통합했다 (SPEC-DATAPATH-002).

후보 열거 순서 (_candidate_roots() 가 이 순서로 후보를 나열한다 — 이 순서
자체는 우선순위가 아니다. 실제 우선순위는 아래 "소비 규칙"이 정한다):
  1. ITDA_DATA_ROOT 환경변수 (명시 오버라이드)
  2. /proc/mounts에서 추출한 rw 마운트 포인트 (Linux 한정)
  3. $HOME/mnt/ 하위 비시스템 디렉토리 (Cowork 호스트 마운트)
  4. CLAUDE_PROJECT_DIR 및 그 상위 (Cowork $HOME 비의존 후보)
  5. 현재 세션 /sessions/<slug>/mnt/* (Cowork 절대 마운트, 현재 세션 한정)
  6. $HOME (semi-persistent)
  7. Path.cwd() (macOS/Windows 로컬)

소비 규칙 (열거 순서를 방향이 다른 두 규칙으로 소비한다):
  - **쓰기 (pick_cache_location / resolve_data_dir)**: 열거 **선순위**부터
    첫 쓰기 가능 후보가 승리한다. 앞 후보(마운트·호스트 영속 경로)일수록
    캐시 거주지로 우선한다.
  - **읽기 (find_env_files 병합)**: 열거 **후순위**(더 로컬한 후보)의 환경변수
    파일이 승리한다(later-wins, AC-006.10a). 같은 루트 안에서는 파일명 별칭
    우선순위(.env > .env.txt > env.txt > 환경변수.txt, #1210)가 적용된다. 단
    ITDA_DATA_ROOT 루트의 파일은 **명시 오버라이드**라 예외적으로 병합 최강
    (리스트 맨 뒤)으로 블록 재배치된다(#1205). settings.json·os.environ·CLI 인자는
    여전히 모든 환경변수 파일 위(env_loader 참조).

환경변수 파일명 별칭 (#1210): 각 후보 루트에서 `.env` · `.env.txt` · `env.txt` ·
  `환경변수.txt` 를 탐색한다(비개발자가 점 파일을 만들기 어려운 문제 대응).
  한글 파일명은 NFC·NFD 두 형태 모두 매칭한다(macOS↔Linux 정규화 함정).

읽기(find_env_files)와 쓰기(pick_cache_location)의 후보 집합이 다르다:
  - 쓰기(기본): outputs/uploads 제외 — 사용자 결과 폴더에 캐시를 쓰지 않는다.
  - 읽기(include_output_dirs=True): outputs/uploads 포함 — Cowork는 영속 .env가
    outputs에만 살 수 있으므로(실측 확정), .env 탐색은 이 둘을 후보에 넣는다.
  #5는 전체 세션을 glob하지 않고 cwd·$HOME에서 유도한 현재 세션만 본다
  (타 세션 .env 혼입·수백 세션 순회 방지).

데이터 경로 패턴:
  <root>/.itda-skills/<skill_name>/[subdir]

사용법:
  from itda_path import resolve_data_dir, resolve_cache_dir

  data = resolve_data_dir("law-korean")           # <root>/.itda-skills/law-korean/
  cache = resolve_cache_dir("law-korean")          # <root>/.itda-skills/law-korean/cache/
  profiles = resolve_data_dir("web-reader", "profiles")

테스트/CI에서 루트 경로 고정:
  ITDA_DATA_ROOT=/path/to/dir python3 -m pytest ...
"""
from __future__ import annotations

import os
import sys
import unicodedata
from pathlib import Path

_ITDA_DIR = ".itda-skills"

# 환경변수 파일명 별칭 (#1210) — 비개발자가 점(.) 파일을 만들기 어려워 .txt 형태를
# 허용한다. 같은 루트 내 우선순위: .env > .env.txt > env.txt > 환경변수.txt (정본
# 우선). 병합이 later-wins 라 find_env_files 는 루트 내에서 약→강(이 튜플의 역순)
# 으로 append 한다. 이 상수는 env_doctor 등과 공유되는 단일 정의다.
_ENV_FILENAMES = (".env", ".env.txt", "env.txt", "환경변수.txt")

# 한글 파일명은 NFC/NFD 두 정규화 형태 모두 탐색한다 (#1210) — macOS 호스트가 만든
# NFD 파일명이 Cowork Linux 마운트의 NFC 문자열 조회에 안 잡히는 함정 대응.
_NFC_NFD_FILENAMES = ("환경변수.txt",)

# $HOME/mnt/ 에서 제외할 시스템 디렉토리 이름
_MNT_EXCLUDE_NAMES = {"outputs", "uploads"}

# /proc/mounts 에서 제외할 마운트 포인트 prefix
_SYSTEM_PREFIXES = (
    "/proc", "/sys", "/dev", "/run", "/tmp", "/var", "/snap", "/boot",
)
# 정확히 일치 제외
_EXACT_EXCLUDE = {"/", "/sessions"}


def _resolved_key(p: Path) -> str | None:
    """경로를 resolve() 한 정규화 문자열 키를 반환(비교·중복 제거용).

    심볼릭 링크 깨짐(OSError)·심링크 루프(RuntimeError) 등으로 resolve 가
    실패하면 None 을 반환한다 — 자격증명 해석 전체가 중단되지 않도록 흡수한다.
    """
    try:
        return str(p.resolve())
    except (OSError, RuntimeError):
        return None


def _dedup_key(p: Path) -> str | None:
    """중복 제거용 **버킷** 키 — resolve 키를 NFC 로 정규화한다 (#1210).

    macOS 는 파일명 정규화 무관 조회라 NFC·NFD 두 질의가 같은 파일을 잡지만
    resolve() 는 질의 바이트를 보존해 두 경로 문자열이 달라진다(실측 확정).
    NFC 정규화로 두 형태를 같은 버킷에 모은다. 단 **접기 여부는 버킷 키만으로
    판정하지 않는다** — Linux 에선 NFC·NFD 가 서로 다른 두 파일일 수 있어(같은
    버킷이라도) 내용이 통째로 소거되면 안 된다. 실제 접기는 _same_file 로
    동일 파일임을 확인한 경우에만 한다(find_env_files 참조).
    """
    key = _resolved_key(p)
    return None if key is None else unicodedata.normalize("NFC", key)


def _same_file(a: Path, b: Path) -> bool:
    """두 경로가 같은 실제 파일인지 판정한다 (inode/device 비교, #1210).

    os.path.samefile 실패(파일 부재·권한·플랫폼 예외) 시 보수적으로 **별개**로
    본다 — 서로 다른 파일을 잘못 접어 내용을 소거하는 것보다 중복을 남기는 편이
    안전하다.
    """
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _env_file_variants(root: Path, filename: str) -> list[Path]:
    """루트에서 주어진 별칭 파일명의 존재하는 경로를 반환한다 (#1210).

    한글 파일명(_NFC_NFD_FILENAMES)은 NFC·NFD 두 정규화 형태 모두 exists() 확인
    (macOS NFD 파일 ↔ Linux NFC 조회 함정 대응). 동일 파일이 두 형태로 잡히면
    find_env_files 의 _dedup_key(NFC) 중복 제거가 하나로 접는다.
    """
    if filename in _NFC_NFD_FILENAMES:
        names: list[str] = []
        for form in ("NFC", "NFD"):
            norm = unicodedata.normalize(form, filename)
            if norm not in names:
                names.append(norm)
    else:
        names = [filename]

    out: list[Path] = []
    for name in names:
        cand = root / name
        try:
            if cand.exists():
                out.append(cand)
        except OSError:
            continue
    return out


def _list_rw_mounts() -> list[Path]:
    """/proc/mounts 에서 rw 마운트 포인트 목록을 추출한다.

    Linux가 아니거나 /proc/mounts가 없으면 빈 리스트를 반환한다.
    경로 깊이 내림차순으로 정렬하여 더 구체적인 경로가 우선된다.

    Returns:
        rw 마운트 포인트 Path 리스트 (깊이 내림차순).
    """
    if sys.platform != "linux":
        return []

    proc_mounts = Path("/proc/mounts")
    if not proc_mounts.exists():
        return []

    results: list[Path] = []
    try:
        with open(proc_mounts, encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 4:
                    continue
                # 두 번째 컬럼이 마운트 포인트
                mount_point_raw = parts[1]
                # 네 번째 컬럼의 옵션에 "rw"가 포함돼야 함
                options = parts[3].split(",")
                if "rw" not in options:
                    continue

                # \040 → 공백 디코드
                mount_point_str = mount_point_raw.replace("\\040", " ")
                mount_path = Path(mount_point_str)

                # 정확히 일치 제외
                if str(mount_path) in _EXACT_EXCLUDE:
                    continue

                # 시스템 prefix 제외
                path_str = str(mount_path)
                if any(
                    path_str == prefix or path_str.startswith(prefix + "/")
                    for prefix in _SYSTEM_PREFIXES
                ):
                    continue

                results.append(mount_path)
    except OSError:
        return []

    # 경로 깊이 내림차순 정렬 (깊은 경로 우선)
    results.sort(key=lambda p: len(p.parts), reverse=True)
    return results


def _mnt_child_ok(name: str, include_output_dirs: bool) -> bool:
    """mnt/ 하위 디렉토리 이름이 후보로 적합한지 판정한다.

    `.`-prefix 시스템 디렉토리는 항상 제외한다.
    outputs/uploads는 쓰기 후보에서는 제외(사용자 결과 폴더 오염 방지),
    읽기 후보(include_output_dirs=True)에서는 포함한다(Cowork .env 거주지).
    """
    if name.startswith("."):
        return False
    if not include_output_dirs and name in _MNT_EXCLUDE_NAMES:
        return False
    return True


def _current_session_roots() -> list[Path]:
    """현재 세션의 /sessions/<slug> 루트를 cwd·$HOME에서 유도한다.

    전체 세션을 glob(`/sessions/*/mnt/*`)하면 수백 개 타 세션이 후보에 섞여
    엉뚱한 .env가 혼입되고 매 호출 수백 디렉토리를 순회하게 된다.
    대신 현재 런타임 경로(cwd, $HOME)가 실제로 `/sessions/<slug>/...` 아래
    있을 때만 그 `<slug>` 세션 루트를 추출한다. 해당 세그먼트가 없으면
    아무것도 반환하지 않는다(로컬 모드 등은 /proc/mounts·cwd가 이미 커버).

    심볼릭 링크 해석(resolve)은 의도적으로 하지 않는다 — 로컬 에이전트 모드는
    `/sessions/<slug>`가 사용자 Library 경로로의 심링크라 resolve하면 세그먼트가
    사라진다. 마운트 네임스페이스 경로 그대로 사용한다.
    """
    sources: list[Path] = []
    try:
        sources.append(Path.cwd())
    except OSError:
        pass
    try:
        sources.append(Path.home())
    except RuntimeError:
        pass

    roots: list[Path] = []
    seen: set[str] = set()
    for src in sources:
        parts = src.parts
        # parts 예: ('/', 'sessions', '<slug>', 'mnt', 'outputs', ...)
        if len(parts) >= 3 and parts[0] == os.sep and parts[1] == "sessions":
            sroot = Path(os.sep) / "sessions" / parts[2]
            key = str(sroot)
            if key not in seen:
                seen.add(key)
                roots.append(sroot)
    return roots


def _candidate_roots(include_output_dirs: bool = False) -> list[Path]:
    """데이터 루트 후보 경로 목록을 열거 순서대로 반환한다.

    후보 열거 순서 (우선순위가 아니다 — 소비 방향은 소비자가 정한다. 모듈
    docstring "소비 규칙" 참조: 쓰기=선순위 승리 / 읽기 병합=후순위 승리):
        1. ITDA_DATA_ROOT 환경변수
        2. /proc/mounts rw 마운트 포인트 (Linux 한정)
        3. $HOME/mnt/ 하위 비시스템 디렉토리
        4. CLAUDE_PROJECT_DIR 및 그 상위
        5. 현재 세션 /sessions/<slug>/mnt/* (현재 세션 한정)
        6. $HOME
        7. Path.cwd()

    Args:
        include_output_dirs: True면 mnt/ 하위에서 outputs/uploads도 후보에
            포함한다(.env 읽기 전용). 기본 False는 쓰기 경로용으로
            outputs/uploads를 제외해 사용자 결과 폴더 오염을 막는다.

    Returns:
        중복 제거된 Path 리스트 (resolve() 기준).
    """
    candidates: list[Path] = []

    # 1. ITDA_DATA_ROOT 환경변수 최우선
    env_root = os.environ.get("ITDA_DATA_ROOT")
    if env_root:
        candidates.append(Path(env_root))

    # 2. /proc/mounts rw 마운트 포인트 (Linux 한정)
    candidates.extend(_list_rw_mounts())

    # 3. $HOME/mnt/ 하위 비시스템 디렉토리
    try:
        home = Path.home()
    except RuntimeError:
        home = None

    if home is not None:
        mnt_dir = home / "mnt"
        if mnt_dir.is_dir():
            subdirs = sorted(
                (d for d in mnt_dir.iterdir()
                 if d.is_dir()
                 and _mnt_child_ok(d.name, include_output_dirs)),
                key=lambda d: d.name,
            )
            candidates.extend(subdirs)

    # 4. CLAUDE_PROJECT_DIR 및 그 상위 ($HOME 비의존, Cowork 환경)
    _cpd = os.environ.get("CLAUDE_PROJECT_DIR")
    if _cpd:
        try:
            _cpd_path = Path(_cpd)
            if _cpd_path.is_dir():
                candidates.append(_cpd_path)
            # 상위 디렉토리도 후보 (워크스페이스 루트에 .env가 있는 경우)
            _cpd_parent = _cpd_path.parent
            if _cpd_parent.is_dir() and _cpd_parent != _cpd_path:
                candidates.append(_cpd_parent)
        except (OSError, ValueError):
            pass

    # 5. 현재 세션 /sessions/<slug>/mnt/* (Cowork 절대 마운트, 현재 세션 한정)
    #    전체 세션 glob 금지 — 타 세션 .env 혼입·수백 세션 순회 방지.
    for _sroot in _current_session_roots():
        _mnt_dir = _sroot / "mnt"
        try:
            if _mnt_dir.is_dir():
                _children = sorted(
                    (d for d in _mnt_dir.iterdir()
                     if d.is_dir()
                     and _mnt_child_ok(d.name, include_output_dirs)),
                    key=lambda d: d.name,
                )
                candidates.extend(_children)
        except OSError:
            pass

    # 6. $HOME
    if home is not None:
        candidates.append(home)

    # 7. Path.cwd()
    candidates.append(Path.cwd())

    # resolve() 기준 중복 제거 (순서 보존)
    seen: set[str] = set()
    unique: list[Path] = []
    for cand in candidates:
        try:
            resolved = cand.resolve()
        except (OSError, RuntimeError):
            # 심볼릭 링크 깨짐(OSError)·심링크 루프(RuntimeError) 시 해당 후보만 스킵
            continue
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            unique.append(resolved)

    return unique


def find_cached(rel: str) -> Path | None:
    """후보 경로에서 기존 캐시 디렉토리를 찾는다.

    <root>/.itda-skills/<rel> 경로를 각 후보에 대해 검사하여
    존재하고 비어있지 않은 첫 번째 경로를 반환한다.

    Args:
        rel: 캐시 상대 경로 (예: "browser/playwright").

    Returns:
        비어있지 않은 캐시 Path, 없으면 None.
    """
    for root in _candidate_roots():
        candidate = root / _ITDA_DIR / rel
        if candidate.is_dir() and any(candidate.iterdir()):
            return candidate
    return None


def pick_cache_location(rel: str) -> Path:
    """캐시 디렉토리 위치를 결정하고 필요 시 생성한다.

    알고리즘:
        1. 기존 비어있지 않은 캐시가 있으면 즉시 반환 (find_cached)
        2. 없으면 최우선 쓰기 가능 후보에 새 디렉토리 생성

    Args:
        rel: 캐시 상대 경로 (예: "browser/playwright").

    Returns:
        캐시 디렉토리 Path (생성됨 또는 기존).

    Raises:
        RuntimeError: 쓰기 가능한 후보가 없을 때.
    """
    # 기존 캐시 우선
    cached = find_cached(rel)
    if cached is not None:
        return cached

    # 최우선 쓰기 가능 후보에 신규 생성
    for root in _candidate_roots():
        target = root / _ITDA_DIR / rel
        try:
            target.mkdir(parents=True, exist_ok=True)
            return target
        except OSError:
            continue

    raise RuntimeError("No writable cache location")


def find_env_files() -> list[Path]:
    """모든 후보 경로에서 환경변수 파일을 탐색한다 (병합 순서 = 약 → 강).

    각 후보 루트에서 별칭 4종(`.env` · `.env.txt` · `env.txt` · `환경변수.txt`,
    #1210)을 탐색해 존재하는 파일만 반환한다. 이 리스트는 **읽기 병합용 순서**다
    — 소비자(env_loader.merged_env·resolve_api_key)는 **뒤에 오는 파일일수록 우선**
    적재한다(후순위=더 로컬 후보 승리, AC-006.10a).

    두 축의 우선순위:
      - **루트 간(상위 축)**: 후보 열거 순서. 더 로컬한(뒤) 루트가 앞 루트를
        이긴다 — 루트 locality 가 파일명보다 우선한다.
      - **같은 루트 내(하위 축)**: `.env` > `.env.txt` > `env.txt` > `환경변수.txt`
        (정본 우선). later-wins 라 루트 내에서는 약→강(`환경변수.txt` … `.env`)
        순으로 append 해 `.env` 가 그 루트의 최강이 되게 한다.

    한글 파일명(`환경변수.txt`)은 NFC·NFD 두 형태 모두 탐색한다(macOS↔Linux 정규화
    함정, #1210). 두 형태가 **같은 파일**이면(macOS 실측) _same_file 로 확인해 하나로
    접고, **다른 파일**이면(Linux 가능) 둘 다 유지한다 — 이 경우 append 순서상
    뒤(NFD)가 병합 승자다. 무조건 접으면 NFD 파일 내용이 소거되는 Codex R1 지적 대응.

    캐시 쓰기와 달리 읽기는 outputs/uploads도 후보에 포함한다
    (include_output_dirs=True). Cowork는 영속 파일이 마운트된 작업 폴더
    (outputs)에만 살 수 있기 때문이다(실측 확정).

    **ITDA_DATA_ROOT 예외 (명시 오버라이드, #1205)**: ITDA_DATA_ROOT 루트에서
    발견된 별칭 파일 **전부를 블록으로**(내부 약→강 순서 유지) 반환 리스트의
    **맨 뒤(=병합 최강)** 로 재배치한다. ITDA_DATA_ROOT 는 후보 열거상 첫 번째
    (병합 최약)라, 명시적으로 지정한 데이터 루트가 오히려 로컬 파일에 가려지는
    결함을 교정한다. 일반 후보 간 later-wins 는 그대로 유지된다.
    (settings.json·os.environ·CLI 인자는 여전히 모든 파일 위 — env_loader 참조.)

    Returns:
        존재하는 환경변수 파일 Path 리스트 (병합 순서 — 뒤일수록 우선).
    """
    env_root = os.environ.get("ITDA_DATA_ROOT")
    override_root_key = _dedup_key(Path(env_root)) if env_root else None

    general: list[Path] = []
    override_block: list[Path] = []
    for root in _candidate_roots(include_output_dirs=True):
        # 같은 루트 내: 약→강(환경변수.txt … .env) 순으로 append → .env 가 최강.
        root_files: list[Path] = []
        for filename in reversed(_ENV_FILENAMES):
            root_files.extend(_env_file_variants(root, filename))

        if override_root_key is not None and _dedup_key(root) == override_root_key:
            # ITDA_DATA_ROOT 루트의 별칭 전부를 블록으로(내부 순서 유지) 끝에 재배치.
            override_block.extend(root_files)
        else:
            general.extend(root_files)

    # 병합 순서 = 일반 후보(약→강) + ITDA_DATA_ROOT 블록(최강).
    # 중복 제거: NFC 버킷으로 후보를 모으되, 실제 접기는 _same_file 로 **동일
    # 파일**임을 확인한 경우에만(NFC·NFD 가 Linux 에선 별개 파일일 수 있어 무조건
    # 접으면 NFD 파일 내용이 통째로 소거된다). 별개 파일이면 둘 다 유지하고,
    # append 순서상 뒤(NFD)가 병합 승자가 된다(SPEC-DATAPATH-002 §1.1).
    kept_by_bucket: dict[str, list[Path]] = {}
    unique: list[Path] = []
    for path in general + override_block:
        key = _dedup_key(path)
        if key is None:
            continue
        prior = kept_by_bucket.get(key)
        if prior is not None and any(_same_file(path, kept) for kept in prior):
            continue  # 동일 파일 — 접는다
        unique.append(path)
        kept_by_bucket.setdefault(key, []).append(path)
    return unique


def resolve_data_dir(skill_name: str, subdir: str = "") -> Path:
    """스킬의 데이터 디렉토리 경로를 결정하고 자동 생성한다.

    Args:
        skill_name: 스킬 이름 (예: "law-korean").
        subdir: 하위 디렉토리 (예: "cache"). 빈 문자열이면 스킬 루트.

    Returns:
        생성된 디렉토리의 절대 경로.
    """
    # pick_cache_location을 사용하되 rel에 skill_name을 포함시킴
    rel_parts = skill_name
    if subdir:
        rel_parts = f"{skill_name}/{subdir}"

    # ITDA_DATA_ROOT가 설정된 경우 해당 경로를 직접 사용
    env_root = os.environ.get("ITDA_DATA_ROOT")
    if env_root:
        base = Path(env_root).resolve()
        path = base / skill_name
        if subdir:
            path = path / subdir
        path.mkdir(parents=True, exist_ok=True)
        return path

    # 후보 경로 중 최우선 쓰기 가능 경로 사용
    return pick_cache_location(rel_parts)


def resolve_cache_dir(skill_name: str) -> Path:
    """스킬의 캐시 디렉토리를 반환한다.

    캐시는 재생성 가능한 데이터이므로 세션 종료 시 소멸해도 무방하다.
    호스트 마운트가 있으면 마운트 경로를 우선 사용하여 세션 간 공유한다.

    Args:
        skill_name: 스킬 이름 (예: "law-korean").

    Returns:
        생성된 캐시 디렉토리의 절대 경로.
    """
    return resolve_data_dir(skill_name, "cache")


def resolve_browsers_dir() -> Path:
    """Playwright 브라우저 바이너리 캐시 디렉토리를 반환한다.

    세션 간 바이너리를 공유하여 재설치를 방지한다.
    pick_cache_location("browser/playwright")을 내부적으로 사용한다.

    Returns:
        생성된 브라우저 캐시 디렉토리의 절대 경로.
    """
    return pick_cache_location("browser/playwright")


def ensure_playwright_env() -> None:
    """Playwright 바이너리 영속성을 보장한다.

    PLAYWRIGHT_BROWSERS_PATH 환경변수가 이미 설정되어 있으면 덮어쓰지 않는다
    (외부 설정 존중). 미설정 시 pick_cache_location("browser/playwright")
    결과로 설정한다.

    Side effect:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"]를 설정할 수 있다.
    """
    if "PLAYWRIGHT_BROWSERS_PATH" in os.environ:
        return
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(
        pick_cache_location("browser/playwright")
    )
