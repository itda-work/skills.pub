"""blog-seo 환경변수 resolver — 두 그룹(검색광고 / Open API) 통합.

shared/env_loader.resolve_api_key() 를 위임 호출하여 다음 우선순위로 키를 해석한다:
    CLI 인자 > 환경변수 > .env 파일 (find_env_files 다중 경로 탐색)

기존 코드와의 호환을 위해 env_loader의 MissingAPIKeyError를 잡아
naver_searchad.MissingApiKeyError 로 재발생시킨다 (대소문자 P/k 차이).
"""
from __future__ import annotations

import env_loader

# ---------------------------------------------------------------------------
# Group 1: 네이버 검색광고 API (NAVER_SEARCHAD_*)
# ---------------------------------------------------------------------------

_SEARCHAD_GUIDE = (
    "네이버 검색광고 API 인증 키가 설정되지 않았습니다.\n\n"
    "네이버 검색광고 API 발급 방법:\n"
    "  1. https://searchad.naver.com 회원가입 (사업자 인증 필요)\n"
    "  2. 좌측 메뉴 → 도구 → API 관리\n"
    "  3. ACCESS KEY · SECRET KEY · CUSTOMER ID 발급/확인\n\n"
    "설정 방법: 작업 폴더 루트(예: outputs/)에 .env 파일을 만들고 3개 키 모두 추가하세요.\n"
    "    NAVER_SEARCHAD_ACCESS_KEY=...\n"
    "    NAVER_SEARCHAD_SECRET_KEY=...\n"
    "    NAVER_SEARCHAD_CUSTOMER_ID=...\n"
)

# ---------------------------------------------------------------------------
# Group 2: 네이버 Open API (NAVER_CLIENT_*)
# ---------------------------------------------------------------------------

_OPEN_API_GUIDE = (
    "네이버 Open API 인증 키가 설정되지 않았습니다.\n\n"
    "네이버 Open API 발급 방법:\n"
    "  1. https://developers.naver.com 로그인\n"
    "  2. Application → 애플리케이션 등록\n"
    "  3. 사용 API에 '검색' 또는 '데이터랩' 체크 → Client ID/Secret 발급\n\n"
    "설정 방법: 작업 폴더 루트(예: outputs/)에 .env 파일을 만들고 2개 키를 추가하세요.\n"
    "    NAVER_CLIENT_ID=...\n"
    "    NAVER_CLIENT_SECRET=...\n"
)


def _resolve(var_name: str, guide: str, cli_arg: str | None = None) -> str:
    """env_loader.resolve_api_key 위임 + 예외 클래스 변환.

    naver_searchad.MissingApiKeyError 로 재발생시켜 기존 except 절과 호환.
    """
    # circular import 방지: naver_searchad import 는 함수 안에서
    from naver_searchad import MissingApiKeyError

    try:
        return env_loader.resolve_api_key(var_name, cli_arg, guide)
    except env_loader.MissingAPIKeyError as exc:
        raise MissingApiKeyError(str(exc)) from exc


# ---------------------------------------------------------------------------
# 검색광고 그룹 resolver
# ---------------------------------------------------------------------------

def get_searchad_access_key(cli_arg: str | None = None) -> str:
    return _resolve("NAVER_SEARCHAD_ACCESS_KEY", _SEARCHAD_GUIDE, cli_arg)


def get_searchad_secret_key(cli_arg: str | None = None) -> str:
    return _resolve("NAVER_SEARCHAD_SECRET_KEY", _SEARCHAD_GUIDE, cli_arg)


def get_searchad_customer_id(cli_arg: str | None = None) -> str:
    return _resolve("NAVER_SEARCHAD_CUSTOMER_ID", _SEARCHAD_GUIDE, cli_arg)


# ---------------------------------------------------------------------------
# Open API 그룹 resolver
# ---------------------------------------------------------------------------

def get_naver_client_id(cli_arg: str | None = None) -> str:
    return _resolve("NAVER_CLIENT_ID", _OPEN_API_GUIDE, cli_arg)


def get_naver_client_secret(cli_arg: str | None = None) -> str:
    return _resolve("NAVER_CLIENT_SECRET", _OPEN_API_GUIDE, cli_arg)


__all__ = [
    "get_searchad_access_key",
    "get_searchad_secret_key",
    "get_searchad_customer_id",
    "get_naver_client_id",
    "get_naver_client_secret",
]
