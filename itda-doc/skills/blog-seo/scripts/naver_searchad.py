"""
네이버 검색광고 API 클라이언트

FR-001: 키워드 확장 - 관련 키워드 + 월간 PC/모바일 검색량 + 경쟁지수
NFR-001: API 키 환경변수 (NAVER_SEARCHAD_ACCESS_KEY, NAVER_SEARCHAD_SECRET_KEY, NAVER_SEARCHAD_CUSTOMER_ID)
NFR-002: 에러 처리 (429 지수 백오프, 누락 키 친절한 오류)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.searchad.naver.com"
SIGNUP_URL = "https://searchad.naver.com/"
MAX_RETRIES = 3
MAX_SEED_KEYWORDS = 5


class MissingApiKeyError(Exception):
    """API 키 누락 오류"""
    pass


class RateLimitError(Exception):
    """API 요청 한도 초과 오류"""
    pass


class ValidationError(Exception):
    """입력 유효성 검사 오류"""
    pass


def generate_signature(timestamp: str, method: str, uri: str, secret_key: str) -> str:
    """HMAC-SHA256 서명 생성"""
    message = f"{timestamp}.{method}.{uri}"
    signature = base64.b64encode(
        hmac.new(
            secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).digest()
    ).decode("utf-8")
    return signature


def build_auth_headers(
    api_key: str,
    customer_id: str,
    secret_key: str,
    method: str,
    uri: str,
) -> dict[str, str]:
    """인증 헤더 생성 — GET 요청에는 Content-Type 포함하지 않음"""
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(timestamp, method, uri, secret_key)
    headers: dict[str, str] = {
        "X-Timestamp": timestamp,
        "X-API-KEY": api_key,
        "X-Customer": customer_id,
        "X-Signature": signature,
    }
    if method.upper() != "GET":
        headers["Content-Type"] = "application/json"
    return headers


def _parse_volume(value: str | int) -> int:
    """검색량 파싱 - '< 10' 을 5로 대체"""
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if "< 10" in s or "<10" in s:
        return 5
    try:
        return int(s.replace(",", ""))
    except (ValueError, AttributeError):
        return 5


class NaverSearchAdClient:
    """네이버 검색광고 API 클라이언트"""

    def __init__(self, api_key: str, customer_id: str, secret_key: str) -> None:
        if not api_key:
            raise MissingApiKeyError(
                f"NAVER_SEARCHAD_ACCESS_KEY가 설정되지 않았습니다. "
                f"발급 URL: {SIGNUP_URL}"
            )
        if not customer_id:
            raise MissingApiKeyError(
                f"NAVER_SEARCHAD_CUSTOMER_ID가 설정되지 않았습니다. "
                f"발급 URL: {SIGNUP_URL}"
            )
        if not secret_key:
            raise MissingApiKeyError(
                f"NAVER_SEARCHAD_SECRET_KEY가 설정되지 않았습니다. "
                f"발급 URL: {SIGNUP_URL}"
            )
        self.api_key = api_key
        self.customer_id = customer_id
        self.secret_key = secret_key

    @classmethod
    def from_env(cls) -> "NaverSearchAdClient":
        """환경변수로 클라이언트 생성 (CLI > environ > .env, SPEC-ENV-ERROR-001)."""
        from _env_setup import (
            get_searchad_access_key,
            get_searchad_customer_id,
            get_searchad_secret_key,
        )
        api_key = get_searchad_access_key()
        secret_key = get_searchad_secret_key()
        customer_id = get_searchad_customer_id()
        return cls(api_key=api_key, customer_id=customer_id, secret_key=secret_key)

    def _request(self, method: str, uri: str, params: dict | None = None) -> dict:
        """API 요청 (지수 백오프 재시도)"""
        if params:
            query_string = urllib.parse.urlencode(params, doseq=True, quote_via=urllib.parse.quote)
            full_uri = f"{uri}?{query_string}"
        else:
            full_uri = uri

        headers = build_auth_headers(
            api_key=self.api_key,
            customer_id=self.customer_id,
            secret_key=self.secret_key,
            method=method,
            uri=uri,
        )

        url = f"{BASE_URL}{full_uri}"
        req = urllib.request.Request(url, headers=headers, method=method)

        for attempt in range(MAX_RETRIES):
            try:
                with urllib.request.urlopen(req) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    if attempt < MAX_RETRIES - 1:
                        wait_time = 2 ** attempt  # 1, 2, 4초
                        time.sleep(wait_time)
                        continue
                    raise RateLimitError(
                        f"네이버 검색광고 API 요청 한도 초과. {MAX_RETRIES}회 재시도 후 실패."
                    )
                raise
        raise RateLimitError("최대 재시도 횟수 초과")

    def get_keyword_suggestions(self, seed_keywords: list[str]) -> list[dict]:
        """관련 키워드 제안 조회

        Args:
            seed_keywords: 시드 키워드 목록 (최대 5개)

        Returns:
            관련 키워드 목록 (relKeyword, monthly_pc, monthly_mobile, comp_idx)
        """
        if len(seed_keywords) > MAX_SEED_KEYWORDS:
            raise ValidationError(
                f"시드 키워드는 최대 {MAX_SEED_KEYWORDS}개까지만 입력 가능합니다. "
                f"현재 {len(seed_keywords)}개."
            )

        # Naver Search Ad API는 hintKeywords 내 공백을 허용하지 않음.
        # 공백 있는 키워드는 단어 단위로 분리하여 쉼표 구분 목록으로 전달.
        tokens: list[str] = []
        for kw in seed_keywords:
            tokens.extend(kw.split())
        params = {
            "showDetail": "1",
            "hintKeywords": ",".join(tokens),
        }

        data = self._request("GET", "/keywordstool", params)
        keywords = data.get("keywordList", [])

        result = []
        for kw in keywords:
            result.append({
                "relKeyword": kw.get("relKeyword", ""),
                "monthly_pc": _parse_volume(kw.get("monthlyPcQcCnt", 0)),
                "monthly_mobile": _parse_volume(kw.get("monthlyMobileQcCnt", 0)),
                "comp_idx": kw.get("compIdx", ""),
            })
        return result
