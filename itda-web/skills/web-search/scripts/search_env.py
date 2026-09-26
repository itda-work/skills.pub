"""web-search 키 해석 + 마스킹 + 가용 엔진 진단.

``shared/env_loader.resolve_api_key()`` 를 위임 호출한다(우선순위:
``os.environ``(Claude 주입 포함) > ``~/.claude/settings.json`` > ``.env``).
키 평문은 어디에도 로깅하지 않는다(SPEC-WEB-SEARCH-001 §3.4 · REQ-006).
"""
from __future__ import annotations

import env_loader

from search_http import MissingKeyError

# 엔진 → 필요한 환경변수와 발급 안내.
#   required: 모두 있어야 엔진 사용 가능.
#   fallback: required 키가 없을 때 대신 읽을 변수(기존 스킬 키 재사용).
ENGINE_SPECS: dict[str, dict] = {
    "perplexity": {
        "required": ["PERPLEXITY_API_KEY"],
        "fallback": {},
        "label": "Perplexity",
        "guide": "PERPLEXITY_API_KEY 미설정 — https://www.perplexity.ai/settings/api 에서 발급하세요.",
    },
    "tavily": {
        "required": ["TAVILY_API_KEY"],
        "fallback": {},
        "label": "Tavily",
        "guide": "TAVILY_API_KEY 미설정 — https://app.tavily.com 가입 후 무료 키를 발급하세요.",
    },
    "serper": {
        "required": ["SERPER_API_KEY"],
        "fallback": {},
        "label": "Serper",
        "guide": "SERPER_API_KEY 미설정 — https://serper.dev 가입 후 키를 발급하세요(Google 결과).",
    },
    "exa": {
        "required": ["EXA_API_KEY"],
        "fallback": {},
        "label": "Exa",
        "guide": "EXA_API_KEY 미설정 — https://dashboard.exa.ai 에서 발급하세요(시맨틱 검색).",
    },
    "naver": {
        "required": ["NAVER_SEARCH_CLIENT_ID", "NAVER_SEARCH_CLIENT_SECRET"],
        "fallback": {
            "NAVER_SEARCH_CLIENT_ID": "NAVER_CLIENT_ID",
            "NAVER_SEARCH_CLIENT_SECRET": "NAVER_CLIENT_SECRET",
        },
        "label": "Naver",
        "guide": (
            "NAVER_SEARCH_CLIENT_ID / NAVER_SEARCH_CLIENT_SECRET 미설정 — "
            "https://developers.naver.com 애플리케이션 등록 후 발급하세요"
            "(기존 NAVER_CLIENT_ID/SECRET 도 자동 사용)."
        ),
    },
}

ENGINE_NAMES: list[str] = list(ENGINE_SPECS)


def _resolve_optional(var_name: str, fallback: str | None = None) -> str | None:
    """키를 해석하되 없으면(또는 폴백도 없으면) None 을 반환한다(예외 X)."""
    try:
        return env_loader.resolve_api_key(var_name)
    except env_loader.MissingAPIKeyError:
        pass
    if fallback:
        try:
            return env_loader.resolve_api_key(fallback)
        except env_loader.MissingAPIKeyError:
            return None
    return None


def _resolve_required(var_name: str, fallback: str | None, guide: str) -> str:
    value = _resolve_optional(var_name, fallback)
    if not value:
        raise MissingKeyError(guide or f"{var_name}가 설정되지 않았습니다.")
    return value


def engine_available(engine: str) -> bool:
    """엔진의 모든 필수 키(또는 폴백)가 존재하는가 — 네트워크 호출 없음."""
    spec = ENGINE_SPECS[engine]
    fallback = spec.get("fallback", {})
    return all(
        _resolve_optional(var, fallback.get(var)) is not None
        for var in spec["required"]
    )


def available_engines() -> dict[str, bool]:
    """엔진별 키 보유 여부 매핑(``--check-env`` 용)."""
    return {engine: engine_available(engine) for engine in ENGINE_NAMES}


def guide_for(engine: str) -> str:
    return ENGINE_SPECS[engine]["guide"]


def all_guides() -> str:
    """전체 엔진 키 발급 안내(auto 0키 시 출력)."""
    return "\n".join(f"  - {spec['guide']}" for spec in ENGINE_SPECS.values())


def get_perplexity_key() -> str:
    spec = ENGINE_SPECS["perplexity"]
    return _resolve_required("PERPLEXITY_API_KEY", None, spec["guide"])


def get_tavily_key() -> str:
    spec = ENGINE_SPECS["tavily"]
    return _resolve_required("TAVILY_API_KEY", None, spec["guide"])


def get_serper_key() -> str:
    spec = ENGINE_SPECS["serper"]
    return _resolve_required("SERPER_API_KEY", None, spec["guide"])


def get_exa_key() -> str:
    spec = ENGINE_SPECS["exa"]
    return _resolve_required("EXA_API_KEY", None, spec["guide"])


def get_naver_keys() -> tuple[str, str]:
    spec = ENGINE_SPECS["naver"]
    fallback = spec["fallback"]
    client_id = _resolve_required(
        "NAVER_SEARCH_CLIENT_ID", fallback["NAVER_SEARCH_CLIENT_ID"], spec["guide"]
    )
    client_secret = _resolve_required(
        "NAVER_SEARCH_CLIENT_SECRET", fallback["NAVER_SEARCH_CLIENT_SECRET"], spec["guide"]
    )
    return client_id, client_secret


def mask(value: str | None) -> str:
    """키를 ``앞4자****`` 형태로 마스킹한다(로그·진단용, 평문 노출 금지)."""
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return value[:4] + "****"
