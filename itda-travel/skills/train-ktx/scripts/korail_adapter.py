"""train-ktx 코레일 어댑터 — korail2 계열 라이브러리 래핑.

⚠️ 코레일 비공식 모바일 API(letskorail.com)를 사용한다(SPEC-KTX-BOOKING-001).
라이브러리·네트워크 의존을 이 모듈 한 곳에 격리하고(NFR-005), 순수 로직
(역명 정규화·검색결과 파싱·운임 표기)은 stations.py / format.py 에 둔다.

책임:
- korail2 계열 라이브러리 지연 import + 부재 시 fail-loud 설치 안내(EXC-2)
- 로그인/안티봇/매진/결과없음을 사람이 읽을 우리 예외 계층으로 변환(SAFE-4)
- 자격증명(KORAIL_USER_ID / KORAIL_PASSWORD) resolve + 마스킹(SAFE-3, REQ-006)

이 모듈은 korail2가 설치되지 않은 환경에서도 import 가능해야 한다
(단위 테스트는 mock 사용). 따라서 korail2는 함수 안에서 지연 import 하고,
예외 변환은 클래스명 문자열로 판별해 import 시점 결합을 피한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# shared/ 모듈 — 저장소 루트 기준 PYTHONPATH=skills/shared 또는 테스트 conftest.py 로 주입된다.
from env_loader import resolve_api_key  # noqa: E402

# ---------------------------------------------------------------------------
# 예외 계층 — 모든 실패는 사람이 읽을 사유를 담아 KtxError 하위로 표면화(SAFE-4)
# ---------------------------------------------------------------------------


class KtxError(Exception):
    """train-ktx 공통 예외. 메시지는 사용자에게 그대로 보일 수 있는 사유."""


class KtxDependencyMissing(KtxError):
    """korail2 계열 라이브러리 미설치 (EXC-2)."""


class KtxAuthError(KtxError):
    """로그인 실패 — 자격증명 오류·세션 만료 등."""


class KtxBlockedError(KtxError):
    """코레일 안티봇 차단 (MACRO ERROR 등, EXC-1)."""


class KtxNoResults(KtxError):
    """조건에 맞는 열차가 없음."""


class KtxSoldOut(KtxError):
    """매진."""


# ---------------------------------------------------------------------------
# 자격증명 (REQ-006, SAFE-3)
# ---------------------------------------------------------------------------

KORAIL_USER_ID_VAR = "KORAIL_USER_ID"
KORAIL_PASSWORD_VAR = "KORAIL_PASSWORD"

_ID_GUIDE = (
    "KORAIL_USER_ID가 설정되지 않았습니다.\n\n"
    "코레일 회원 자격증명을 아래 중 한 곳에 설정하세요"
    " (회원번호 8자리 / 휴대폰번호 / 이메일):\n"
    "  - 셸 환경변수 KORAIL_USER_ID\n"
    "  - ~/.claude/settings.json 의 env\n"
    "  - 작업 폴더 또는 홈의 .env 파일\n\n"
    "코레일 회원이 아니면 https://www.letskorail.com 에서 가입하세요.\n"
)
_PW_GUIDE = (
    "KORAIL_PASSWORD가 설정되지 않았습니다.\n\n"
    "KORAIL_USER_ID와 같은 위치에 KORAIL_PASSWORD(코레일 로그인 비밀번호)를 설정하세요.\n"
    "⚠️ 비밀번호 평문이 셸 히스토리·공유 파일에 남지 않도록 주의하세요.\n"
)


def mask_secret(value: str, keep: int = 2) -> str:
    """자격증명 마스킹 (SAFE-3). 앞 ``keep``자만 남기고 나머지를 가린다.

    로그·출력·예외 메시지에 ID/PW 평문이 새지 않도록 항상 이 함수를 거친다.
    """
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)


def resolve_credentials(
    cli_id: str | None = None, cli_pw: str | None = None
) -> tuple[str, str]:
    """KORAIL_USER_ID / KORAIL_PASSWORD 를 resolve (REQ-006).

    조회 우선순위는 env_loader.resolve_api_key 를 그대로 따른다
    (CLI 인자 > 환경변수 > settings.json > .env). 누락 시 가이드를 담은
    MissingAPIKeyError 가 발생한다.
    """
    korail_id = resolve_api_key(KORAIL_USER_ID_VAR, cli_arg=cli_id, guide_msg=_ID_GUIDE)
    korail_pw = resolve_api_key(KORAIL_PASSWORD_VAR, cli_arg=cli_pw, guide_msg=_PW_GUIDE)
    return korail_id, korail_pw


# ---------------------------------------------------------------------------
# korail2 지연 로드 (fail-loud, EXC-2)
# ---------------------------------------------------------------------------

#: 설치 안내에 싣는 패키지 — requirements.txt 와 **같은 것**이어야 한다.
#: 이름을 바꾸면 `tests/test_install_guide.py` 가 RED 로 잡는다.
REQUIRED_PACKAGES = ("korail2-ncard", "pycryptodome")

_INSTALL_GUIDE = (
    "korail2 계열 라이브러리를 불러올 수 없습니다.\n\n"
    "KTX 예약은 코레일 비공식 모바일 API를 사용하며, 안티봇(Dynapath) 대응이\n"
    "된 korail2 계열 라이브러리가 필요합니다. 설치 후 다시 시도하세요:\n\n"
    f"  python3 -m pip install {' '.join(REQUIRED_PACKAGES)}\n"
    "  (Windows: py -3 -m pip install …)\n\n"
    "korail2-ncard 는 라이브 동작 검증으로 확정된 패키지입니다"
    "(SPEC-KTX-BOOKING-001 OQ-1 종결, 2026-06-22).\n"
)


def load_korail_module():
    """korail2 모듈을 지연 import 한다. 부재 시 KtxDependencyMissing(EXC-2)."""
    try:
        import korail2  # type: ignore  # noqa: F401
    except ImportError as exc:
        raise KtxDependencyMissing(_INSTALL_GUIDE) from exc
    return korail2


# ---------------------------------------------------------------------------
# 예외 변환 — korail2 예외/메시지를 우리 계층으로 (클래스명 문자열로 판별)
# ---------------------------------------------------------------------------


def translate_error(exc: Exception, context: str) -> KtxError:
    """korail2 측 예외를 우리 예외 계층으로 변환한다(SAFE-4).

    korail2 를 import 하지 않고도 동작하도록 예외 클래스명과 메시지 문자열로
    판별한다. 미분류 오류도 원문 사유를 보존해 KtxError 로 표면화한다
    (빈 결과·침묵 크래시 금지, REQ-007).
    """
    name = type(exc).__name__
    msg = str(exc)
    upper = msg.upper()

    if name == "NeedToLoginError" or "P058" in msg or "로그인" in msg:
        return KtxAuthError(
            f"로그인이 필요하거나 자격증명이 올바르지 않습니다 ({context})."
        )
    if name == "SoldOutError" or "ERR211161" in msg or "매진" in msg:
        return KtxSoldOut(f"해당 열차/좌석이 매진되었습니다 ({context}).")
    if name == "NoResultsError" or "P100" in msg or "WRG000000" in msg:
        return KtxNoResults(f"조건에 맞는 열차가 없습니다 ({context}).")
    if "MACRO" in upper or "DYNAPATH" in upper or "차단" in msg:
        return KtxBlockedError(
            f"코레일 안티봇에 차단되었습니다 ({context}). "
            "라이브러리 업데이트가 필요할 수 있습니다."
        )
    return KtxError(f"코레일 요청 실패 ({context}): {msg}")


# ---------------------------------------------------------------------------
# 클라이언트 래퍼 — Korail 객체를 감싸고 모든 예외를 변환
# ---------------------------------------------------------------------------


class KorailClient:
    """korail2 Korail 래퍼. 네트워크 호출을 한 곳에 모으고 예외를 변환한다.

    자격증명은 인스턴스에 보관하되, repr/로그에 평문이 새지 않도록 마스킹한다.
    """

    def __init__(self, korail_id: str, korail_pw: str):
        self._id = korail_id
        self._pw = korail_pw
        self._module = load_korail_module()
        self._korail = None  # 로그인 후 korail2.Korail 인스턴스

    def __repr__(self) -> str:  # 자격증명 노출 방지(SAFE-3)
        return f"KorailClient(id={mask_secret(self._id)!r}, logged_in={self._korail is not None})"

    @property
    def masked_id(self) -> str:
        """마스킹된 로그인 ID (SAFE-3). check 등 사용자 출력은 항상 이 값을 쓴다."""
        return mask_secret(self._id)

    def login(self) -> "KorailClient":
        """코레일 로그인. 실패/차단을 우리 예외로 변환(SAFE-4)."""
        try:
            self._korail = self._module.Korail(self._id, self._pw, auto_login=True)
        except Exception as exc:  # noqa: BLE001 — 모든 실패를 사유와 함께 표면화
            raise translate_error(exc, context="로그인") from exc
        logined = getattr(self._korail, "logined", True)
        if not logined:
            raise KtxAuthError(
                "로그인에 실패했습니다. KORAIL_USER_ID / KORAIL_PASSWORD 를 확인하세요."
            )
        return self

    def search(
        self,
        dep: str,
        arr: str,
        date: str | None = None,
        time: str | None = None,
        train_type: str | None = None,
        passengers=None,
        include_no_seats: bool = False,
    ) -> list:
        """열차 검색(REQ-001). 결과 없음/차단을 우리 예외로 변환."""
        self._require_login()
        kwargs = {
            "date": date,
            "time": time,
            "passengers": passengers,
            "include_no_seats": include_no_seats,
        }
        if train_type is not None:
            kwargs["train_type"] = train_type
        try:
            return self._korail.search_train(dep, arr, **kwargs)
        except Exception as exc:  # noqa: BLE001
            raise translate_error(exc, context="열차 검색") from exc

    def reserve(self, train, passengers=None, option: str | None = None):
        """예약 실행(REQ-004). 호출자(reserve.py)가 확인 게이트를 통과한 뒤에만 부른다."""
        self._require_login()
        kwargs = {"passengers": passengers}
        if option is not None:
            kwargs["option"] = option
        try:
            return self._korail.reserve(train, **kwargs)
        except Exception as exc:  # noqa: BLE001
            raise translate_error(exc, context="예약") from exc

    def reservations(self) -> list:
        """내 예약 목록(REQ-005, read-only)."""
        self._require_login()
        try:
            return self._korail.reservations()
        except Exception as exc:  # noqa: BLE001
            raise translate_error(exc, context="예약 조회") from exc

    def _require_login(self) -> None:
        if self._korail is None:
            raise KtxAuthError("로그인하지 않았습니다. login() 을 먼저 호출하세요.")


def connect(cli_id: str | None = None, cli_pw: str | None = None) -> KorailClient:
    """자격증명 resolve → 클라이언트 생성 → 로그인까지 한 번에(편의 함수)."""
    korail_id, korail_pw = resolve_credentials(cli_id=cli_id, cli_pw=cli_pw)
    return KorailClient(korail_id, korail_pw).login()
