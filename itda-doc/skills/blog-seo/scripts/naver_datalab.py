"""
네이버 데이터랩 API 클라이언트

FR-005: 12개월 트렌드 분석, rising/falling/seasonal/stable 탐지
"""
from __future__ import annotations

import http.client
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from naver_searchad import MissingApiKeyError, RateLimitError

BASE_URL = "https://openapi.naver.com"
DATALAB_ENDPOINT = "/v1/datalab/search"
SIGNUP_URL = "https://developers.naver.com/apps/#/register"
MAX_RETRIES = 3

# 트렌드 분석 임계값
TREND_RISING_THRESHOLD = 0.15    # 15% 이상 성장 = 상승
TREND_FALLING_THRESHOLD = -0.15  # 15% 이상 감소 = 하락
SEASONAL_VARIANCE_THRESHOLD = 25.0  # 분산이 높으면 계절성

# 트렌드 보너스/패널티 점수
TREND_SCORES: dict[str, float] = {
    "rising": 20.0,
    "falling": -20.0,
    "seasonal": -10.0,
    "stable": 0.0,
    "unknown": 0.0,
}


class NaverDatalabClient:
    """네이버 데이터랩 API 클라이언트"""

    def __init__(self, client_id: str, client_secret: str) -> None:
        if not client_id:
            raise MissingApiKeyError(
                f"NAVER_CLIENT_ID가 설정되지 않았습니다. 발급 URL: {SIGNUP_URL}"
            )
        if not client_secret:
            raise MissingApiKeyError(
                f"NAVER_CLIENT_SECRET이 설정되지 않았습니다. 발급 URL: {SIGNUP_URL}"
            )
        self.client_id = client_id
        self.client_secret = client_secret

    @classmethod
    def from_env(cls) -> "NaverDatalabClient":
        """환경변수로 클라이언트 생성 (CLI > environ > .env, SPEC-ENV-ERROR-001)."""
        from _env_setup import get_naver_client_id, get_naver_client_secret
        client_id = get_naver_client_id()
        client_secret = get_naver_client_secret()
        return cls(client_id=client_id, client_secret=client_secret)

    def _get_date_range(self) -> tuple[str, str]:
        """최근 12개월 날짜 범위 반환"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    def get_trend(self, keyword: str) -> list[dict]:
        """키워드 월별 검색 트렌드 조회 (12개월)

        Args:
            keyword: 조회할 키워드

        Returns:
            [{"period": "YYYY-MM", "ratio": float}, ...] 형식의 월별 데이터
        """
        start_date, end_date = self._get_date_range()
        body = json.dumps({
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": "month",
            "keywordGroups": [
                {
                    "groupName": keyword,
                    "keywords": [keyword],
                }
            ],
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{BASE_URL}{DATALAB_ENDPOINT}",
            data=body,
            method="POST",
        )
        req.add_header("X-Naver-Client-Id", self.client_id)
        req.add_header("X-Naver-Client-Secret", self.client_secret)
        req.add_header("Content-Type", "application/json")

        for attempt in range(MAX_RETRIES):
            try:
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    results = data.get("results", [])
                    if results:
                        return results[0].get("data", [])
                    return []
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
                        continue
                    raise RateLimitError("데이터랩 API 요청 한도 초과")
                if e.code == 401:
                    body = e.read().decode("utf-8", errors="replace")
                    raise PermissionError(
                        f"데이터랩 API 인증 실패 (401). "
                        f"네이버 앱에 '데이터랩(검색어트렌드)' 권한이 없습니다. "
                        f"https://developers.naver.com 에서 앱 편집 후 권한을 추가하세요. "
                        f"서버 응답: {body}"
                    )
                raise
            except urllib.error.URLError as e:
                # keep-alive 연결이 서버 측에서 끊긴 경우 — 재시도
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except http.client.RemoteDisconnected:
                # Python 3.12: RemoteDisconnected는 URLError로 래핑되지 않아 별도 처리
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
        return []


def detect_trend_type(data: list[dict]) -> str:
    """트렌드 유형 탐지

    Args:
        data: [{"period": "YYYY-MM", "ratio": float}, ...] 형식

    Returns:
        "rising" | "falling" | "seasonal" | "stable" | "unknown"
    """
    if not data or len(data) < 3:
        return "unknown"

    ratios = [d.get("ratio", 0.0) for d in data]
    n = len(ratios)

    # 평균과 분산 계산
    mean = sum(ratios) / n
    variance = sum((r - mean) ** 2 for r in ratios) / n
    std_dev = variance ** 0.5

    # 계절성 탐지: 표준편차가 임계값 이상이고 패턴이 불규칙적
    if std_dev >= SEASONAL_VARIANCE_THRESHOLD:
        # 상승 또는 하락 추세가 뚜렷하면 seasonal이 아닐 수 있음
        first_half_mean = sum(ratios[:n // 2]) / (n // 2)
        second_half_mean = sum(ratios[n // 2:]) / (n - n // 2)
        half_change = (second_half_mean - first_half_mean) / (first_half_mean + 1e-9)

        if abs(half_change) < 0.3:  # 전반부/후반부 변화가 작으면 계절성
            return "seasonal"

    # 선형 추세 계산 (최소제곱법 대신 간단히 처음/끝 비교)
    first_quarter_mean = sum(ratios[:max(1, n // 4)]) / max(1, n // 4)
    last_quarter_mean = sum(ratios[-(n // 4 or 1):]) / max(1, n // 4)

    change_rate = (last_quarter_mean - first_quarter_mean) / (first_quarter_mean + 1e-9)

    if change_rate >= TREND_RISING_THRESHOLD:
        return "rising"
    elif change_rate <= TREND_FALLING_THRESHOLD:
        return "falling"
    else:
        return "stable"


def calculate_trend_score(trend_type: str) -> float:
    """트렌드 유형에 따른 보너스/패널티 점수"""
    return TREND_SCORES.get(trend_type, 0.0)
