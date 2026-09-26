"""API 키 및 OC 인증 정보 resolver — 한국 공공데이터 API 공통 모듈.

조회 우선순위 (높음 → 낮음):
    CLI 인자 > os.environ > ~/.claude/settings.json env > .env 파일들

.env 파일들 사이의 우선순위는 itda_path.find_env_files() 가 정한 병합 순서를
따른다 — **뒤에 오는(더 로컬한) .env 가 우선**하며(later-wins),
**ITDA_DATA_ROOT/.env 는 명시 오버라이드라 .env 중 최강**이다(#1205).

단일 경로 탐색 헬퍼를 제거하고 itda_path.find_env_files()를 사용하여
모든 후보 경로의 .env를 병합한다 (SPEC-DATAPATH-002).
Cowork 환경 등 subprocess inject가 누락되는 경우를 위해
~/.claude/settings.json의 env 키를 추가 탐색한다 (SPEC-DART-FEEDBACK-001 REQ-002).

지원 스킬:
    - API 계열 (DART, KOSIS, ECOS, 부동산, 복지급여, 나라장터):
        MissingAPIKeyError, resolve_api_key, normalize_service_key
    - 법령정보 (law-korean):
        MissingOCError, resolve_oc

단계적 제거 (#1707):
    네트워크와 자격증명은 itda-hyve 단일 경로로 옮겨 간다. 스킬은 키 값을 읽지 않고
    itda-hyve 의 ``http_request`` 에 ``{{secret:NAME}}`` 자리표시자를 적으며, 사용자는
    키를 itda-hyve GUI 의 시크릿 탭에 등록한다(규약: 스킬의 ``references/netbridge.md``, 정본 저장소 ``shared/netbridge.md``).
    ``resolve_api_key()``·``resolve_oc()`` 는 기존 스크립트(약 46개 파일)가 아직 부르므로
    남아 있지만 **단계적으로 제거된다 — 새 스킬은 이 모듈로 키를 읽지 않는다.**
    키 부재 안내는 itda-hyve 등록만 알린다(``.env`` 설정 안내는 더 이상 권장 경로가 아니어서 뺐다).
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
from collections.abc import Iterable
from pathlib import Path

from itda_path import find_env_files


def _default_claude_settings_path() -> Path | None:
    """Claude Code settings.json 경로를 반환. HOME 미확정 환경이면 None.

    SPEC-DART-FEEDBACK-001 REQ-002: Cowork 환경에서 subprocess env inject가
    누락되는 경우를 위한 보조 탐색 경로.

    #1330: Claude Code 공식 계약 — ``CLAUDE_CONFIG_DIR`` 설정 시 모든
    ``~/.claude`` 경로가 그 디렉토리로 대체된다. 하드코딩하면 설정 분리
    사용자에게 활성 settings 가 아닌 구 위치의 stale 키를 읽는 결함이 된다.
    """
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if config_dir:
        return Path(config_dir).expanduser() / "settings.json"
    try:
        return Path.home() / ".claude" / "settings.json"
    except RuntimeError:
        return None


def claude_settings_label() -> str:
    """진단·provenance 표시용 settings.json 출처 라벨 (#1330).

    기본 위치면 관례 표기 ``~/.claude/settings.json`` 을, CLAUDE_CONFIG_DIR
    로 재지정된 환경이면 실제 해석 경로를 반환한다 — 진단 출력이 실경로와
    어긋나지 않게 한다. 값이 아닌 경로 라벨만 다룬다(보안 계약 무관).
    """
    if os.environ.get("CLAUDE_CONFIG_DIR", "").strip():
        path = _default_claude_settings_path()
        if path is not None:
            return str(path)
    return "~/.claude/settings.json"

# ---------------------------------------------------------------------------
# law-korean 전용 상수
# ---------------------------------------------------------------------------

_OC_VAR = "LAW_API_OC"
_OC_REGISTER_URL = "https://open.law.go.kr/LSO/openApi/openApiInfo.do"

_OC_GUIDE_MSG = (
    "OC 발급 방법:\n"
    f"  1. 법제처 Open API 신청 페이지 접속: {_OC_REGISTER_URL}\n"
    "  2. 회원가입 후 Open API 사용 신청\n"
    "  3. 발급받은 OC를 itda-hyve GUI 시크릿 탭에 LAW_API_OC 이름으로 등록\n"
)


# ---------------------------------------------------------------------------
# 예외 클래스
# ---------------------------------------------------------------------------

class MissingAPIKeyError(Exception):
    """API 키가 설정되지 않은 경우."""


class MissingOCError(MissingAPIKeyError):
    """LAW_API_OC is not set in any supported location.

    MissingAPIKeyError의 서브클래스로, 기존 law-korean 코드에서
    ``except MissingOCError`` 와 ``except MissingAPIKeyError`` 모두 정상 작동.
    """


# ---------------------------------------------------------------------------
# 공통 유틸리티
# ---------------------------------------------------------------------------

def _parse_value(raw: str) -> str:
    """``=`` 오른쪽 원문을 값으로 정규화한다 (python-dotenv 동형 — #1639).

    - 따옴표 값: 여는 따옴표와 **짝이 맞는 닫는 따옴표** 사이가 값. 닫는 따옴표 뒤의
      공백·``# 주석`` 은 버린다. 따옴표 안의 ``#`` 은 값이다.
      ``KEY='tvly-…'  # 메모`` 가 ``'tvly-…'  # 메모`` 통째로 읽혀 인증 실패를 내던 결함.
    - 비따옴표 값: **공백 뒤 ``#``** 부터 주석. 공백 없는 ``#``(``abc#1``·URL fragment)은 값.
    - 닫는 따옴표가 없거나 닫힌 뒤에 주석 아닌 문자가 오면(``"a"b``) 종전처럼 원문을
      그대로 둔다 — 조용히 잘라내지 않는다.
    """
    value = raw.strip()
    if len(value) >= 2 and value[0] in ("'", '"'):
        quote = value[0]
        end = value.find(quote, 1)
        if end != -1:
            trailing = value[end + 1 :].lstrip()
            if trailing == "" or trailing.startswith("#"):
                return value[1:end]
        return value
    return _INLINE_COMMENT_RE.sub("", value).rstrip()


_INLINE_COMMENT_RE = re.compile(r"\s+#.*$")


def load_env(env_path: str | Path | None = None) -> dict[str, str]:
    """.env 파일을 파싱하여 키-값 딕셔너리로 반환.

    파싱 규칙:
        - KEY=VALUE, KEY="VALUE", KEY='VALUE' 형식 지원
        - ``#`` 으로 시작하는 줄은 주석으로 처리
        - 값 뒤 인라인 주석 제거 — 따옴표 값은 닫는 따옴표 뒤 ``# …``,
          비따옴표 값은 공백 뒤 ``# …`` (``_parse_value`` — #1639)
        - 빈 줄 무시
        - ``=`` 주변 공백 제거
        - 값의 앞뒤 따옴표 제거

    주의: 이 함수는 os.environ을 수정하지 않습니다.

    Args:
        env_path: .env 파일 경로. None이면 빈 딕셔너리 반환.

    Returns:
        파싱된 키-값 딕셔너리. 파일이 없거나 오류 시 {} 반환.
    """
    if env_path is None:
        return {}

    env_path = Path(env_path)
    if not env_path.exists():
        return {}

    result: dict[str, str] = {}
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n").rstrip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                # export 접두사 관용 (#1210, python-dotenv 동형): "export KEY=V" →
                # "KEY". 단 "export=1" 처럼 export 자체가 키면(뒤에 공백/탭 없음) 유지.
                if key.startswith("export"):
                    rest = key[len("export"):]
                    if rest[:1] in (" ", "\t"):
                        key = rest.lstrip(" \t")
                value = _parse_value(value)
                if key:
                    result[key] = value
    except (OSError, UnicodeDecodeError):
        # 비UTF8(cp949 등) .env 는 graceful 하게 {} 반환 — UnicodeDecodeError 를
        # 흡수하지 않으면 doctor CLI 가 traceback 으로 문제 바이트·위치를 노출한다.
        return {}

    return result


def _load_claude_settings_env(settings_path: str | Path | None = None) -> dict[str, str]:
    """~/.claude/settings.json의 env 키를 파싱하여 딕셔너리로 반환.

    SPEC-DART-FEEDBACK-001 REQ-002: `claude config set env.X "value"` 명령으로
    설정된 환경변수가 Cowork 등 격리된 subprocess에 자동 inject되지 않는 경우를
    보조하기 위해 settings.json을 직접 읽는다.

    파싱 규칙:
        - 파일 부재 시 {} 반환 (graceful)
        - JSON 파싱 실패 시 {} 반환 (graceful)
        - env 키가 dict가 아니면 {} 반환
        - 값이 문자열이 아닌 항목은 스킵

    주의: 이 함수는 os.environ을 수정하지 않는다.

    Args:
        settings_path: settings.json 경로. None이면 ~/.claude/settings.json 사용.

    Returns:
        env 키-값 딕셔너리. 어떤 사유로든 읽을 수 없으면 {}.
    """
    if settings_path is None:
        path = _default_claude_settings_path()
    else:
        path = Path(settings_path)

    if path is None or not path.exists():
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        # 비UTF8 settings.json 의 UnicodeDecodeError(json.load 내부 디코드 중
        # 발생, JSONDecodeError 아님)까지 흡수 — graceful {} 계약 유지.
        return {}

    env_section = data.get("env") if isinstance(data, dict) else None
    if not isinstance(env_section, dict):
        return {}

    return {k: v for k, v in env_section.items() if isinstance(k, str) and isinstance(v, str)}


def merged_env(env_path: str | Path | None = None) -> dict[str, str]:
    """환경변수와 .env 파일들, ~/.claude/settings.json env를 병합하여 반환.

    병합 우선순위 (높음 → 낮음):
        1. os.environ (항상 최우선)
        2. ~/.claude/settings.json의 env 키
        3. .env 파일들 — find_env_files() 의 병합 순서를 따른다:
           - 후순위(더 로컬한) .env 가 선순위를 덮어씀 (later-wins)
           - ITDA_DATA_ROOT/.env 는 명시 오버라이드라 .env 중 최강 (#1205)

    env_path가 명시되면 그 파일만 사용한다 (기존 호환성 유지).
    None이면 find_env_files()로 다중 경로를 탐색하여 모두 병합한다.

    Args:
        env_path: .env 파일 경로. None이면 find_env_files()로 자동 탐색.

    Returns:
        병합된 환경변수 딕셔너리.
    """
    # 빈 딕셔너리부터 시작하여 나중에 적재된 것이 이전 것을 덮어씀
    dotenv_merged: dict[str, str] = {}

    if env_path is not None:
        # 명시적 경로: 해당 파일만 사용
        dotenv_merged = load_env(Path(env_path))
    else:
        # 자동 탐색: 발견 순서대로 적재 (나중 발견이 먼저 발견을 덮어씀)
        for env_file in find_env_files():
            dotenv_merged.update(load_env(env_file))

    # settings.json env 적재 — .env files보다 우선
    dotenv_merged.update(_load_claude_settings_env())

    # os.environ을 마지막 적재 — 항상 최우선 승리
    result = dict(dotenv_merged)
    result.update(os.environ)
    return result


# ---------------------------------------------------------------------------
# API 계열 (DART / KOSIS / ECOS / 부동산 / 복지급여 / 나라장터)
# ---------------------------------------------------------------------------

# 호출자가 준 안내문(guide_msg)에서 떼어 내는 옛 설정 경로 줄 — .env·환경변수·settings.json·
# CLAUDE.md 로 키를 넣으라는 안내와 ``KEY=값`` 예시 줄. 발급처 URL·점검 절차 같은 나머지 줄은 남긴다.
# 판정이 아니라 안내문 정리다(줄이 남아도 동작은 같다) — 46개 호출자의 문구를 한꺼번에 고치지 않기 위한
# 과도기 장치이며, 호출자가 itda-hyve 경로로 옮겨 가면 함께 사라진다.
_LEGACY_SETUP_LINE = re.compile(
    r"\.env|환경변수|settings\.json|CLAUDE\.md|Claude 지침|\bexport\s|^\s*[A-Z][A-Z0-9_]*\s*=",
)


def _strip_legacy_setup_lines(guide_msg: str) -> str:
    """guide_msg 에서 옛 설정 경로(.env 등) 안내 줄을 뺀다. 남는 것이 없으면 빈 문자열."""
    kept = [ln for ln in guide_msg.splitlines() if not _LEGACY_SETUP_LINE.search(ln)]
    # 연속 빈 줄 1개로 접기 + 앞뒤 공백 제거
    out: list[str] = []
    for ln in kept:
        if not ln.strip() and out and not out[-1].strip():
            continue
        out.append(ln.rstrip())
    return "\n".join(out).strip("\n")


def _hyve_hint(var_name: str) -> str:
    """키 부재 안내의 본문 — itda-hyve 시크릿 탭 등록 (#1707).

    값은 itda-hyve 볼트에만 있고 그것을 **읽어 오는 경로는 없다**(설계). 스킬은 itda-hyve 의
    ``http_request`` 에 ``{{secret:NAME}}`` 자리표시자를 적어 부르므로, 여기서도 값을 가져오려
    하지 않고 등록 위치만 알린다.
    """
    return (
        f"itda-hyve GUI 의 시크릿 탭에서 {var_name} 를 등록하세요. "
        "스킬은 키 값을 읽지 않고 itda-hyve 의 http_request 에 "
        f"{{{{secret:{var_name}}}}} 자리표시자로 부릅니다(규약: 스킬의 references/netbridge.md). "
        "키 값을 대화에 붙여 넣지 마세요."
    )


def _missing_key_message(var_name: str, guide_msg: str) -> str:
    """MissingAPIKeyError 메시지: 부재 한 줄 + itda-hyve 등록 안내 + (남으면) 발급 안내."""
    parts = [f"{var_name} 가 설정되지 않았습니다.", _hyve_hint(var_name)]
    extra = _strip_legacy_setup_lines(guide_msg) if guide_msg else ""
    # 호출자 안내의 첫 줄이 "X가 설정되지 않았습니다" 류면 부재 문장과 중복이므로 뺀다.
    lines = extra.splitlines()
    while lines and ("설정되지 않았" in lines[0] or not lines[0].strip()):
        lines.pop(0)
    extra = "\n".join(lines).strip("\n")
    if extra:
        parts.append(f"[발급 안내]\n{extra}")
    return "\n\n".join(parts)


def normalize_service_key(key: str) -> str:
    """공공데이터포털 인증키의 URL 인코딩 상태를 감지하여 정규화.

    공공데이터포털에서 발급받은 serviceKey는 두 가지 상태로 존재할 수 있음:
    1. URL 디코딩 상태: abc+def/ghi= (원본)
    2. URL 인코딩 상태: abc%2Bdef%2Fghi%3D (포털에서 복사 시)

    % 문자가 포함되어 있으면 이미 인코딩된 것으로 판단하여 디코딩.
    URL 구성 시 별도로 인코딩하므로 이중 인코딩을 방지.

    Args:
        key: 정규화할 인증키 문자열.

    Returns:
        URL 디코딩된 인증키 (% 없으면 그대로 반환).
    """
    if not key:
        return key
    if "%" in key:
        return urllib.parse.unquote(key)
    return key


# 프로세스당 (키, 출처) 1회만 provenance 를 표시하기 위한 모듈 레벨 억제 집합 (#1212).
_PROVENANCE_SEEN: set[tuple[str, str]] = set()


def _emit_provenance(var_name: str, source: str) -> None:
    """자격증명 해석 성공 시 출처를 stderr 에 1줄 표시한다 (#1212, 마스터 결정 A안).

    형식: ``[자격증명] {VAR} ← {출처}``. 출처는 해석 경로 그대로
    (CLI 인자 / os.environ / ~/.claude/settings.json / 실제 파일 경로).

    규칙:
      - **값·값 길이는 절대 비노출** — 키 이름과 출처만.
      - 키·경로는 _sanitize_control 로 제어문자(개행·ESC) 정제.
      - **프로세스당 (키, 출처) 1회**(_PROVENANCE_SEEN) — 반복 호출 소음 억제.
      - **stderr 전용** — stdout(JSON 산출) 을 오염시키지 않는다.
      - 예외 시 provenance 만 생략(기능 무영향) — env_doctor 미가용 등.
    """
    try:
        import env_doctor  # _sanitize_control 재사용 (지역 import — publish 주입 대상)

        seen_key = (var_name, source)
        if seen_key in _PROVENANCE_SEEN:
            return
        _PROVENANCE_SEEN.add(seen_key)
        safe_var = env_doctor._sanitize_control(var_name)
        safe_source = env_doctor._sanitize_control(source)
        print(f"[자격증명] {safe_var} ← {safe_source}", file=sys.stderr)
    except Exception:
        return


# @MX:ANCHOR: [AUTO] API key resolution entry point used by all skill scripts.
# @MX:REASON: fan_in >= 5; lookup priority order (cli > environ > settings.json > env-files) is a contract.
def resolve_api_key(
    var_name: str,
    cli_arg: str | None = None,
    guide_msg: str = "",
    normalize: bool = False,
) -> str:
    """API 키를 해석.

    조회 우선순위:
        1. CLI 인자
        2. os.environ
        3. ~/.claude/settings.json의 env 키 (SPEC-DART-FEEDBACK-001 REQ-002)
        4. .env 파일 (find_env_files() — 뒤에 오는 파일이 우선, 즉 마지막
           발견이 승리. ITDA_DATA_ROOT/.env 는 명시 오버라이드라 최강, #1205)

    Args:
        var_name: 환경변수 이름.
        cli_arg: CLI에서 전달된 키 값.
        guide_msg: 키 미설정 시 안내 메시지.
        normalize: True이면 반환 전 normalize_service_key() 적용
                   (KO_DATA_API_KEY 계열에 사용).

    Returns:
        API 키 문자열.

    Raises:
        MissingAPIKeyError: 어디서도 키를 찾지 못한 경우.

    Side effect (#1212):
        해석 성공 시 stderr 에 ``[자격증명] {VAR} ← {출처}`` 1줄을 표시한다
        (프로세스당 (키,출처) 1회, 값 비노출, stdout 불침범). _emit_provenance 참조.
    """
    if cli_arg:
        resolved = cli_arg
        _emit_provenance(var_name, "CLI 인자")
    elif env_val := os.environ.get(var_name):
        resolved = env_val
        _emit_provenance(var_name, "os.environ")
    elif settings_val := _load_claude_settings_env().get(var_name):
        # Claude settings.json env 키 (Cowork 환경에서 subprocess inject 누락 보조)
        resolved = settings_val
        _emit_provenance(var_name, claude_settings_label())
    else:
        # find_env_files()로 다중 경로 탐색 — 이긴 파일 경로를 추적해 provenance 로 표시
        dotenv_val = None
        dotenv_source: Path | None = None
        for env_file in find_env_files():
            val = load_env(env_file).get(var_name)
            if val:
                dotenv_val = val
                dotenv_source = env_file
                # 마지막 발견이 이기므로 계속 탐색
        if dotenv_val:
            resolved = dotenv_val
            _emit_provenance(var_name, str(dotenv_source))
        else:
            raise MissingAPIKeyError(_missing_key_message(var_name, guide_msg))

    if normalize:
        return normalize_service_key(resolved)
    return resolved


def report_credential_sources(var_names: Iterable[str]) -> None:
    """주어진 키들의 출처를 stderr 에 표시한다 (#1212, merged_env 소비자용 헬퍼).

    resolve_api_key 를 거치지 않고 merged_env 등으로 값을 쓰는 소비자가, 어떤 키가
    어디서 왔는지 동일 형식(``[자격증명] {VAR} ← {출처}``)으로 표시하고 싶을 때
    호출한다. env_doctor 의 승자 판정 로직을 재사용해 각 키의 승자 출처를 구한다.

    ⚠️ env_doctor.collect_diagnosis() 는 파일·settings 에 **등장한 키**만 수집하므로
    (전체 environ 덤프 방지 설계), os.environ 에만 존재하는 키는 그 결과에 안 잡힌다.
    resolve_api_key 는 os.environ 을 최강으로 해석하므로, 출처 형식 일관성을 위해
    **명시 전달된 var_names 에 한해 os.environ 존재를 직접 확인**해 os.environ 출처를
    표시한다(전체 environ 열거가 아니라 지목된 키만 — 덤프 금지 불변, #1212 후속).

    _emit_provenance 를 그대로 쓰므로 규칙(값 비노출·제어문자 정제·(키,출처) 1회·
    stderr 전용)이 동일하게 적용된다. 예외 시 전체 생략(기능 무영향).
    """
    try:
        import env_doctor

        keys = env_doctor.collect_diagnosis().get("keys", {})
        for var in var_names:
            # os.environ 이 최강 — 지목된 키에 한해 직접 확인(전체 environ 덤프 아님).
            if var in os.environ:
                _emit_provenance(var, "os.environ")
                continue
            info = keys.get(var)
            if not info:
                continue
            source = info.get("winner_source")
            if source:
                _emit_provenance(var, source)
    except Exception:
        return


# ---------------------------------------------------------------------------
# law-korean 전용 resolver
# ---------------------------------------------------------------------------

# @MX:ANCHOR: [AUTO] OC resolution entry point used by all law-korean CLI scripts.
# @MX:REASON: fan_in >= 3 (get_law, search_law, law_api); lookup priority is a contract.
def resolve_oc(cli_arg: str | None = None) -> str:
    """법제처 API용 OC (사용자 ID) 를 결정.

    조회 우선순위 (resolve_api_key 위임 — 그 계약과 동일):
        1. cli_arg (--oc flag)
        2. os.environ 의 LAW_API_OC
        3. ~/.claude/settings.json env 의 LAW_API_OC (SPEC-DART-FEEDBACK-001 REQ-002)
        4. .env 파일의 LAW_API_OC (find_env_files() — 뒤에 오는 파일이 우선,
           ITDA_DATA_ROOT/.env 는 명시 오버라이드로 최강, #1205)

    내부적으로 resolve_api_key()를 호출하되, MissingAPIKeyError를
    MissingOCError로 변환하여 기존 law-korean 코드 호환성을 유지.

    Args:
        cli_arg: --oc CLI 옵션 값, 또는 None.

    Returns:
        API 요청에 사용할 OC 문자열.

    Raises:
        MissingOCError: OC를 어느 위치에서도 찾지 못한 경우.
    """
    try:
        return resolve_api_key(_OC_VAR, cli_arg, _OC_GUIDE_MSG)
    except MissingAPIKeyError as exc:
        raise MissingOCError(str(exc)) from exc
