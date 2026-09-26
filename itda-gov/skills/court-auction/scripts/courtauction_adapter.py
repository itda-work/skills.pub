"""법원경매정보(courtauction.go.kr) WebSquare XHR 어댑터.

공식 OPEN API가 없어 사이트 내부 WebSquare JSON XHR endpoint를 직접 호출한다.
인증 키는 필요 없고(`shared/data_go_client` 비의존), 매 호출 전 해당 PGJ 화면을
GET해 세션 쿠키(JSESSIONID/WMONID)를 확보(warmup)한 뒤 POST한다.

사이트는 IP 단위 자동화 차단이 공격적(≈16회/30초 → 1시간 차단)이라 보수적으로
동작한다 — 호출 간 2초 throttle, 세션 budget 10회, `data.ipcheck === false` 즉시
중단(자동 재시도 없음). 이는 매크로가 아니라 차단 회피용 매너이며 read-only다.

모든 호출은 ``(ok, payload, reason)`` 계약을 따른다(place-finder ``kakao_adapter``
패턴) — 예외를 전파하지 않고 한국어 실패 사유를 reason으로 돌려준다(fail-loud).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://www.courtauction.go.kr"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 엔드포인트 → POST 경로
ENDPOINT_PATHS = {
    "notices": "/pgj/pgj143/selectRletDspslPbanc.on",
    "noticeDetail": "/pgj/pgj143/selectRletDspslPbancDtl.on",
    "caseDetail": "/pgj/pgj15A/selectAuctnCsSrchRslt.on",
    "propertySearch": "/pgj/pgjsearch/searchControllerMain.on",
    "courts": "/pgj/pgjComm/selectCortOfcCdLst.on",
}

# 엔드포인트별 warmup/Referer PGJ 화면 (notices/noticeDetail/courts=143M01, caseDetail=159M00, propertySearch=151F00)
_PGJ_SCREEN = {
    "notices": "/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ143M01.xml&pgjId=143M01",
    "noticeDetail": "/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ143M01.xml&pgjId=143M01",
    "caseDetail": "/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ159M00.xml&pgjId=159M00",
    "propertySearch": "/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml&pgjId=151F00",
    "courts": "/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ143M01.xml&pgjId=143M01",
}

# 물건 자유검색(WebSquare submission)만 추가 헤더
_SUBMISSION_ID = {"propertySearch": "mf_wfm_mainFrame_sbm_selectGdsDtlSrch"}

_BLOCKED_REASON = (
    "법원경매 사이트가 자동화 접근을 차단했습니다(ipcheck=false). 같은 IP로는 약 1시간 뒤에 "
    "다시 시도하거나, 사람이 브라우저로 접속해 차단 해제 화면을 거쳐야 합니다. 자동 재시도하지 않습니다."
)


class CourtAuctionClient:
    """법원경매 WebSquare 세션 클라이언트.

    하나의 인스턴스가 쿠키·호출 budget·throttle 상태를 들고 다닌다. 같은 클라이언트로
    연속 호출하면 warmup 쿠키를 재사용한다. 테스트는 ``now``/``sleep`` 주입 + urllib
    monkeypatch로 네트워크 없이 검증한다.
    """

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        user_agent: str = _USER_AGENT,
        timeout: int = 15,
        min_delay: float = 2.0,
        max_calls: int = 10,
        warmup_retries: int = 1,
        retry_backoff: float = 0.5,
        now=None,
        sleep=None,
    ):
        self.base_url = str(base_url).rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout
        self.min_delay = float(min_delay)
        self.max_calls = int(max_calls)
        # #492: warmup GET 의 일시적 네트워크/타임아웃(US 러너→KR 사이트 지연)에 대한 재시도.
        # budget 비차감(warmup 은 _ensure_budget 전), transient(URLError/TimeoutError)만 재시도.
        self.warmup_retries = max(0, int(warmup_retries))
        self.retry_backoff = float(retry_backoff)
        self._now = now or time.monotonic
        self._sleep = sleep or time.sleep
        self._cookie_jar: dict[str, str] = {}
        self._warmed: str | None = None
        self._calls = 0
        self._last_call_at = 0.0

    @property
    def calls_remaining(self) -> int:
        return max(0, self.max_calls - self._calls)

    def reset_session(self) -> None:
        self._cookie_jar = {}
        self._warmed = None
        self._calls = 0
        self._last_call_at = 0.0

    # --- 쿠키 ---

    def _ingest_cookies(self, resp) -> None:
        headers = getattr(resp, "headers", None)
        if headers is None or not hasattr(headers, "get_all"):
            return
        for line in headers.get_all("Set-Cookie") or []:
            first = str(line).split(";")[0]
            name, sep, value = first.partition("=")
            name = name.strip()
            if sep and name:
                self._cookie_jar[name] = value.strip()

    def _cookie_header(self) -> str:
        return "; ".join(f"{key}={value}" for key, value in self._cookie_jar.items())

    def _build_headers(self, endpoint_key: str, *, is_post: bool) -> dict:
        screen = _PGJ_SCREEN.get(endpoint_key, _PGJ_SCREEN["notices"])
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}{screen}",
            "X-Requested-With": "XMLHttpRequest",
        }
        if is_post:
            headers["Content-Type"] = "application/json; charset=UTF-8"
        if endpoint_key in _SUBMISSION_ID:
            headers["submissionid"] = _SUBMISSION_ID[endpoint_key]
            headers["sc-userid"] = "SYSTEM"
        cookie = self._cookie_header()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    # --- warmup / budget ---

    def _warmup(self, endpoint_key: str) -> tuple[bool, str]:
        screen = _PGJ_SCREEN.get(endpoint_key, _PGJ_SCREEN["notices"])
        if self._warmed == screen:
            return True, ""
        url = f"{self.base_url}{screen}"
        req = urllib.request.Request(url, headers=self._build_headers(endpoint_key, is_post=False), method="GET")
        # #492: transient(URLError/TimeoutError) 시 backoff 후 재시도. HTTPError 는 서버 응답이라
        # 재시도 무의미 → 즉시 반환. HTTPError 는 URLError 의 서브클래스라 except 순서가 중요하다.
        last_reason = ""
        for attempt in range(self.warmup_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                    self._ingest_cookies(resp)
                self._warmed = screen
                return True, ""
            except urllib.error.HTTPError as exc:
                return False, f"법원경매 사이트 warmup 실패(HTTP {exc.code})."
            except urllib.error.URLError as exc:
                last_reason = f"네트워크 오류로 법원경매 사이트에 닿지 못했습니다(warmup): {exc.reason}"
            except TimeoutError:
                last_reason = "법원경매 사이트 warmup이 시간 초과됐습니다."
            if attempt < self.warmup_retries:
                self._sleep(self.retry_backoff * (attempt + 1))
        return False, last_reason

    def _ensure_budget(self) -> tuple[bool, str]:
        if self._calls >= self.max_calls:
            return False, (
                f"세션 호출 budget({self.max_calls}회)을 초과했습니다. IP 차단을 피하기 위한 안전장치입니다. "
                "정말 더 필요하면 잠시 쉬었다가 새 세션으로 시작하세요."
            )
        if self._last_call_at > 0:
            wait = self.min_delay - (self._now() - self._last_call_at)
            if wait > 0:
                self._sleep(wait)
        return True, ""

    # --- POST ---

    def post_json(self, endpoint_key: str, body: dict) -> tuple[bool, dict | None, str]:
        """엔드포인트에 JSON body를 POST하고 ``(ok, payload, reason)``을 돌려준다.

        warmup → budget/throttle → POST → 차단(ipcheck)/오류 판정 순. 예외 비전파.
        """
        path = ENDPOINT_PATHS.get(endpoint_key)
        if not path:
            return False, None, f"알 수 없는 엔드포인트: {endpoint_key}"

        ok, reason = self._warmup(endpoint_key)
        if not ok:
            return False, None, reason
        ok, reason = self._ensure_budget()
        if not ok:
            return False, None, reason

        self._calls += 1
        self._last_call_at = self._now()

        url = f"{self.base_url}{path}"
        raw = json.dumps(body or {}).encode("utf-8")
        req = urllib.request.Request(
            url, data=raw, headers=self._build_headers(endpoint_key, is_post=True), method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                status = getattr(resp, "status", None) or resp.getcode()
                self._ingest_cookies(resp)
                text = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 400:
                return False, None, (
                    "법원경매 사이트가 요청을 거부했습니다(HTTP 400). 물건 자유검색은 raw 호출 차단이 "
                    "잦습니다. 조건을 줄이거나 잠시 후 다시 시도하세요."
                )
            return False, None, f"법원경매 사이트 응답 오류(HTTP {exc.code})."
        except urllib.error.URLError as exc:
            return False, None, f"네트워크 오류로 법원경매 사이트에 닿지 못했습니다: {exc.reason}"
        except TimeoutError:
            return False, None, "법원경매 사이트 응답이 시간 초과됐습니다. 잠시 후 다시 시도하세요."

        if status != 200:
            return False, None, f"법원경매 사이트 응답 오류(HTTP {status})."

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return False, None, "법원경매 응답을 해석하지 못했습니다(차단 가능성). 잠시 후 다시 시도하세요."

        errors = payload.get("errors") if isinstance(payload, dict) else None
        if isinstance(errors, dict) and errors.get("errorMessage"):
            return False, None, (
                f"법원경매 사이트 오류: {errors['errorMessage']} "
                "(세션 만료 또는 잘못된 요청일 수 있습니다. 처음부터 다시 시도하세요.)"
            )

        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict) and data.get("ipcheck") is False:
            return False, None, _BLOCKED_REASON

        return True, payload, ""
