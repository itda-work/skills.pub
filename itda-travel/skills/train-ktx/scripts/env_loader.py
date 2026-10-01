"""API 키 및 OC 인증 정보 resolver — 스킬 스크립트 공통 모듈.

조회 우선순위 (높음 → 낮음):
    CLI 인자 > os.environ

**자격증명 파일은 읽지 않는다 (itda-work/skills#45, 사용자 결정 2026-09-30).**
``.env``·``.env.txt`` 등 어떤 env 파일도, ``~/.claude/settings.json`` 도 스크립트가 직접 열지 않는다.
키는 두 경로로만 들어온다:

1. **프로세스 환경변수**(``os.environ``) — Claude Code CLI 에서는 셸 환경변수(``export KEY=값``) 또는
   ``claude config set env.KEY "값"``(Claude Code 가 Bash 도구의 환경에 넣어 준다).
2. **itda-hyve 시크릿** — 사용자가 itda-hyve GUI 시크릿 탭에 등록한 키를 hyve MCP 도구(``http_request`` 등)가
   ``{{secret:NAME}}`` 자리표시자 자리에 넣어 요청한다. 스크립트는 그 값을 보지 못한다
   (규약: 스킬의 ``references/netbridge.md``, 정본 저장소 ``shared/netbridge.md``).

이 모듈이 다루는 것은 1번뿐이다. 2번은 스킬 절차(SKILL.md)가 스크립트 밖에서 쓴다.

지원 스킬:
    - API 계열 (DART, KOSIS, ECOS, 부동산, 복지급여, 나라장터 등):
        MissingAPIKeyError, resolve_api_key, normalize_service_key
    - 법령정보 (law-korean):
        MissingOCError, resolve_oc
"""
from __future__ import annotations

import os
import re
import sys
import urllib.parse
from collections.abc import Iterable


# ---------------------------------------------------------------------------
# law-korean 전용 상수
# ---------------------------------------------------------------------------

_OC_VAR = "LAW_API_OC"
_OC_REGISTER_URL = "https://open.law.go.kr/LSO/openApi/openApiInfo.do"

_OC_GUIDE_MSG = (
    "OC 발급 방법:\n"
    f"  1. 법제처 Open API 신청 페이지 접속: {_OC_REGISTER_URL}\n"
    "  2. 회원가입 후 Open API 사용 신청\n"
    "  3. 발급받은 OC를 LAW_API_OC 이름으로 등록(아래 두 경로 중 하나)\n"
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
# API 계열 (DART / KOSIS / ECOS / 부동산 / 복지급여 / 나라장터)
# ---------------------------------------------------------------------------

# 호출자가 준 안내문(guide_msg)에서 떼어 내는 설정 방법 줄 — .env·환경변수·settings.json·CLAUDE.md 로
# 키를 넣으라는 안내와 ``KEY=값`` 예시 줄. 설정 방법은 _missing_key_message 가 한 벌로 말하므로
# 호출자 안내에서는 발급처 URL·점검 절차 같은 나머지 줄만 남긴다(판정이 아니라 안내문 정리다).
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


def _setup_hint(var_name: str) -> str:
    """키 부재 안내의 본문 — 키를 넣는 두 경로 (#45).

    env 파일은 읽지 않으므로 파일을 만들라고 안내하지 않는다. itda-hyve 시크릿은 이 스크립트가
    읽는 경로가 아니다 — itda-hyve 절차가 있는 스킬에서만 쓰인다는 점을 그대로 밝힌다(itda-hyve 절차가
    없는 스킬 사용자가 시크릿만 등록하고 헛걸음하지 않게). 값을 가져오려 하지 않는다.
    """
    return (
        "이 스크립트는 프로세스 환경변수만 읽습니다(.env 같은 파일은 읽지 않습니다).\n"
        f"- Claude Code: 셸 환경변수로 {var_name} 를 넣거나 "
        f'`claude config set env.{var_name} "<키>"` 로 등록한 뒤 세션을 다시 시작하세요.\n'
        f"- itda-hyve GUI 의 시크릿 탭에 등록한 {var_name} 는 이 스크립트가 읽지 못합니다. "
        "스킬 문서(SKILL.md)에 itda-hyve 의 http_request 절차가 있는 경우에만 그 절차에서 "
        f"{{{{secret:{var_name}}}}} 자리표시자로 쓰입니다(규약: 스킬의 references/netbridge.md).\n"
        "키 값을 대화에 붙여 넣지 마세요."
    )


def _missing_key_message(var_name: str, guide_msg: str) -> str:
    """MissingAPIKeyError 메시지: 부재 한 줄 + 키를 넣는 두 경로 + (남으면) 발급 안내."""
    parts = [f"{var_name} 가 설정되지 않았습니다.", _setup_hint(var_name)]
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
    (CLI 인자 / os.environ).

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
# @MX:REASON: fan_in >= 5; lookup priority order (cli > environ, no env files — #45) is a contract.
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

    env 파일(``.env``·``.env.txt`` 등)과 ``~/.claude/settings.json`` 은 읽지 않는다(#45).

    Args:
        var_name: 환경변수 이름.
        cli_arg: CLI에서 전달된 키 값.
        guide_msg: 키 미설정 시 안내 메시지(발급처 등 — 설정 방법 줄은 떼어 낸다).
        normalize: True이면 반환 전 normalize_service_key() 적용
                   (KO_DATA_API_KEY 계열에 사용).

    Returns:
        API 키 문자열.

    Raises:
        MissingAPIKeyError: CLI 인자에도 os.environ 에도 키가 없는 경우.

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
    else:
        raise MissingAPIKeyError(_missing_key_message(var_name, guide_msg))

    if normalize:
        return normalize_service_key(resolved)
    return resolved


def report_credential_sources(var_names: Iterable[str]) -> None:
    """주어진 키들의 출처를 stderr 에 표시한다 (#1212).

    resolve_api_key 를 거치지 않고 os.environ 을 직접 쓰는 소비자가 같은 형식
    (``[자격증명] {VAR} ← {출처}``)으로 표시하고 싶을 때 부른다. 출처는 os.environ 하나뿐이다(#45) —
    지목된 키에 한해 존재만 확인한다(전체 environ 덤프 금지). 예외 시 전체 생략(기능 무영향).
    """
    try:
        for var in var_names:
            if os.environ.get(var):
                _emit_provenance(var, "os.environ")
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
