"""work-plan 스킬 — 메모 작성 유틸리티.

- mirror-back 반복 한도 상수 (AC-5)
- PrereqItem 데이터클래스 (AC-8: 4필드 강제)
- human-tone 정제 (AC-9: 기술 용어 치환)
- 확정 게이트 선택지 (AC-10)
- should_save_full / should_save_partial (AC-11)
- 파일명 생성: YYYY-MM-DD_HHmm_<slug>.md (AC-12)
- get_memo_base_dir: resolve_data_dir("work-plan") (AC-12)
- apply_미정_markers: 빈 섹션 채우기 (AC-13)
- is_exit_keyword: 종료 키워드 감지 (AC-14)
- parse_plan_work_memo: 6섹션 파싱 (AC-15)
- contains_absolute_path: 절대 경로 감지 (AC-16)
- build_memo_content: 6섹션 순서대로 마크다운 생성 (AC-17)
- prepend_warning_box: ground-check 실패 경고 박스 삽입 (DP-3)
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# shared itda_path 주입
_SHARED = Path(__file__).parent.parent.parent.parent.parent.parent / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from itda_path import resolve_data_dir  # noqa: E402


# ---------------------------------------------------------------------------
# Mirror-back 반복 한도 (AC-5)
# ---------------------------------------------------------------------------

MIRRORBACK_MAX_ITERATIONS: int = 3
"""mirror-back 최대 반복 횟수. 초과 시 항목 단위 확인 모드로 전환."""


# ---------------------------------------------------------------------------
# PrereqItem — 선행 자료 4필드 (AC-8)
# ---------------------------------------------------------------------------

@dataclass
class PrereqItem:
    """선행 자료 안내 한 항목.

    Attributes:
        name: 자료 이름 (예: "거래처 이메일 목록").
        content: 자료 내용 설명 1~2문장.
        format_plain: 자료 형식 (plain Korean, 예: "엑셀 파일", "텍스트 메모").
        location_plain: 보관 위치 안내 (GUI 수준, 예: "바탕화면에 새 폴더 만들어서").
    """
    name: str
    content: str
    format_plain: str
    location_plain: str


# ---------------------------------------------------------------------------
# Human-tone 정제 (AC-9)
# ---------------------------------------------------------------------------

# (기술 용어, 평이한 한국어 대체) 매핑
_JARGON_MAP: list[tuple[str, str]] = [
    ("API 호출", "데이터 요청"),
    ("API", "데이터 연결"),
    ("엔드포인트", "연결 주소"),
    ("디렉터리", "폴더"),
    ("디렉토리", "폴더"),
    ("포맷", "형식"),
    ("format", "형식"),
    ("directory", "폴더"),
    ("endpoint", "연결 주소"),
    ("JSON", "데이터 파일"),
    ("CSV", "표 형식 파일"),
    ("파라미터", "설정값"),
    ("parameter", "설정값"),
    ("인스턴스", "실행 프로그램"),
    ("repository", "저장소"),
    ("레포지토리", "저장소"),
    ("터미널", "명령 창"),
    ("CLI", "명령 창 도구"),
    ("스크립트", "자동화 파일"),
    ("프로세스", "처리 과정"),
    ("수행됩니다", "이렇게 진행됩니다"),
    ("처리됩니다", "처리해드립니다"),
]

# 흐릿한 마케팅 슬롭 패턴 — SKILL.md §Stage 4 'human-tone 정제' 정책 enforcement.
# (정규식 패턴, 권장 대체 가이드)
# detect만 하고 직접 치환하지 않는다 — 문맥 보존이 어렵기 때문.
# 발견된 슬롭은 메모 상단에 한 줄 경고로 누적해 사용자가 수동 정제하도록 안내한다.
_SLOP_PATTERNS: list[tuple[str, str]] = [
    (r"효율적인\s*워크플로우", "구체 작업·절감 시간으로 표현"),
    (r"최적화된\s*솔루션", "구체 도구·결과로 표현"),
    (r"사용자\s*친화적", "구체 사용 방식으로 표현"),
    (r"매끄러운\s*경험", "구체 동작으로 표현"),
    (r"혁신적인", "구체 변화로 표현"),
    (r"원활하게", "구체 동작으로 표현"),
    (r"손쉽게", "구체 단계로 표현"),
]


def detect_marketing_slop(text: str) -> list[str]:
    """흐릿한 마케팅 표현을 detect해 경고 라벨 리스트를 반환한다.

    SKILL.md §Stage 4 'human-tone 정제'의 슬롭 금지 정책을 enforcement.
    치환은 하지 않고 detection만 — 문맥 보존이 어려운 표현이라 사용자가
    직접 다듬도록 메모 상단 경고에 누적한다.

    Args:
        text: 원본 텍스트.

    Returns:
        발견된 슬롭 패턴의 권장 가이드 문자열 리스트.
    """
    findings: list[str] = []
    for pattern, guide in _SLOP_PATTERNS:
        if re.search(pattern, text):
            findings.append(f"흐릿한 표현 발견 — {guide}")
    return findings


def apply_human_tone(text: str) -> str:
    """기술 용어를 평이한 한국어로 치환해 human-tone 정제를 수행한다 (AC-9).

    Args:
        text: 원본 텍스트.

    Returns:
        기술 용어가 치환된 텍스트.
    """
    result = text
    for jargon, replacement in _JARGON_MAP:
        result = result.replace(jargon, replacement)
    return result


# ---------------------------------------------------------------------------
# 확정 게이트 선택지 (AC-10)
# ---------------------------------------------------------------------------

def get_confirm_gate_choices() -> list[str]:
    """Stage 4 컨펌 게이트 4지선다 선택지를 반환한다 (AC-10).

    Returns:
        4개 문자열 리스트. 인덱스 0이 권장(옵션 1).
    """
    return [
        "(권장) 이대로 진행 — 메모로 저장할게요.",
        "특정 항목만 수정하고 싶어요.",
        "처음부터 다시 정리할게요.",
        "지금은 여기까지 — 보류할게요 (지금까지 정리한 부분만 메모에 남깁니다).",
    ]


# ---------------------------------------------------------------------------
# 저장 여부 판단 (AC-11)
# ---------------------------------------------------------------------------

def should_save_full(selected_option: int) -> bool:
    """옵션 1 선택 여부 → 정상 저장 여부를 반환한다 (AC-11).

    Args:
        selected_option: 사용자가 선택한 옵션 번호 (1~4).

    Returns:
        옵션 1이면 True, 그 외 False.
    """
    return selected_option == 1


def should_save_partial(selected_option: int) -> bool:
    """옵션 4 선택 여부 → 부분 저장 여부를 반환한다 (AC-11).

    Args:
        selected_option: 사용자가 선택한 옵션 번호 (1~4).

    Returns:
        옵션 4이면 True, 그 외 False.
    """
    return selected_option == 4


# ---------------------------------------------------------------------------
# 파일명 생성 (AC-12)
# ---------------------------------------------------------------------------

def build_filename(slug: str, dt: datetime | None = None) -> str:
    """YYYY-MM-DD_HHmm_<slug>.md 형식의 파일명을 생성한다 (AC-12).

    Args:
        slug: 메모 핵심 키워드 (공백은 하이픈으로 변환).
        dt: 날짜/시각 (None이면 현재 시각 사용).

    Returns:
        파일명 문자열.
    """
    if dt is None:
        dt = datetime.now()
    slug_safe = slug.replace(" ", "-").replace("/", "-")
    return f"{dt.strftime('%Y-%m-%d_%H%M')}_{slug_safe}.md"


def get_memo_base_dir() -> Path:
    """메모 저장 기본 디렉토리를 반환한다 (AC-12, resolve_data_dir 위임).

    Returns:
        Path 객체.
    """
    return resolve_data_dir("work-plan")


# ---------------------------------------------------------------------------
# 미정 마커 처리 (AC-13)
# ---------------------------------------------------------------------------

_SECTION_KEYS = (
    "requirements",
    "plan",
    "prereqs",
    "keys",
    "next_session",
    "failure",
)


def apply_미정_markers(sections: dict[str, str | None]) -> dict[str, str]:
    """빈 섹션에 '미정' 마커를 채운다 (AC-13).

    Args:
        sections: 섹션명 → 내용 딕셔너리 (None 또는 빈 문자열은 미정으로 처리).

    Returns:
        모든 값이 문자열인 딕셔너리.
    """
    result: dict[str, str] = {}
    for key, value in sections.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            result[key] = "미정"
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# 종료 키워드 감지 (AC-14)
# ---------------------------------------------------------------------------

_EXIT_KEYWORDS: frozenset[str] = frozenset({
    "여기까지", "그만", "보류",
    "이제 됐어요", "메모로 정리해줘", "저장해줘", "다음에 이어서 할게요",
})


def is_exit_keyword(text: str) -> bool:
    """입력 텍스트에 종료 키워드가 포함되어 있는지 확인한다 (AC-14).

    Args:
        text: 사용자 발화 문자열.

    Returns:
        종료 키워드가 포함되어 있으면 True.
    """
    stripped = text.strip()
    return stripped in _EXIT_KEYWORDS or any(kw in stripped for kw in _EXIT_KEYWORDS)


# ---------------------------------------------------------------------------
# work-plan 메모 6섹션 파싱 (AC-15)
# ---------------------------------------------------------------------------

_SECTION_HEADER_MAP: dict[str, str] = {
    "## 요구사항": "requirements",
    "## 단계별 계획": "plan",
    "## 선행 자료 안내": "prereqs",
    "## 필요한 키·접근 권한": "keys",
    "## 다음 세션에서 시작하기": "next_session",
    "## 실패 시 대처": "failure",
}


def parse_plan_work_memo(memo_text: str) -> dict[str, str]:
    """work-plan 메모에서 6개 섹션을 파싱해 반환한다 (AC-15).

    Args:
        memo_text: work-plan 메모 마크다운 전문.

    Returns:
        {"requirements": ..., "plan": ..., "prereqs": ...,
         "keys": ..., "next_session": ..., "failure": ...}
    """
    sections: dict[str, str] = {k: "" for k in _SECTION_KEYS}
    current_key: str | None = None
    current_lines: list[str] = []

    def _flush() -> None:
        if current_key is not None:
            sections[current_key] = "\n".join(current_lines).strip()

    for line in memo_text.splitlines():
        matched = False
        for header, key in _SECTION_HEADER_MAP.items():
            if line.strip() == header:
                _flush()
                current_key = key
                current_lines = []
                matched = True
                break
        if not matched and current_key is not None:
            current_lines.append(line)

    _flush()
    return sections


# ---------------------------------------------------------------------------
# 절대 경로 감지 (AC-16)
# ---------------------------------------------------------------------------

_ABS_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"/Users/"),
    re.compile(r"/home/"),
    re.compile(r"/root/"),
    re.compile(r"C:\\\\Users\\\\"),
    re.compile(r"C:/Users/"),
    re.compile(r"C:\\Users\\"),
    re.compile(r"/var/"),
    re.compile(r"/tmp/[^\s]+"),
]


def contains_absolute_path(text: str) -> bool:
    """텍스트에 절대 파일시스템 경로가 포함되어 있는지 감지한다 (AC-16).

    Args:
        text: 검사할 텍스트.

    Returns:
        절대 경로가 있으면 True.
    """
    return any(pat.search(text) for pat in _ABS_PATH_PATTERNS)


# ---------------------------------------------------------------------------
# 메모 콘텐츠 빌드 (AC-17)
# ---------------------------------------------------------------------------

def build_memo_content(slug: str, sections: dict[str, str]) -> str:
    """6섹션을 순서대로 포함한 메모 마크다운을 반환한다 (AC-17).

    Args:
        slug: 메모 주제 키워드 (파일명 slug).
        sections: 6개 섹션 본문 딕셔너리.
            한국어 키(권장)와 영문 키 모두 지원한다 — LLM이 SKILL.md
            한국어 섹션 헤더를 그대로 키로 쓰는 자연스러운 호출 경로와
            테스트·코드 내부 영문 키 경로를 동시에 충족하기 위한 호환층.
            한국어 키: "요구사항", "단계별 계획", "선행 자료 안내",
                       "필요한 키·접근 권한", "다음 세션에서 시작하기",
                       "실패 시 대처"
            영문 키: "requirements", "plan", "prereqs", "keys",
                     "next_session", "failure"

    Returns:
        마크다운 문자열.
    """
    # 한국어 키 우선, 없으면 영문 키 fallback, 둘 다 없으면 "미정"
    req = sections.get("요구사항") or sections.get("requirements", "미정")
    plan = sections.get("단계별 계획") or sections.get("plan", "미정")
    prereqs = sections.get("선행 자료 안내") or sections.get("prereqs", "미정")
    keys = (
        sections.get("필요한 키·접근 권한")
        or sections.get("필요한 키")
        or sections.get("keys", "미정")
    )
    next_session = (
        sections.get("다음 세션에서 시작하기")
        or sections.get("next_session", "미정")
    )
    failure = sections.get("실패 시 대처") or sections.get("failure", "미정")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# 실행 계획: {slug}",
        "",
        f"작성일: {now}",
        "",
        "## 요구사항",
        "",
        req,
        "",
        "## 단계별 계획",
        "",
        plan,
        "",
        "## 선행 자료 안내",
        "",
        prereqs,
        "",
        "## 필요한 키·접근 권한",
        "",
        keys,
        "",
        "## 다음 세션에서 시작하기",
        "",
        next_session,
        "",
        "## 실패 시 대처",
        "",
        failure,
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Ground-check 경고 박스 삽입 (DP-3)
# ---------------------------------------------------------------------------

def prepend_warning_box(memo: str, warnings: list[str]) -> str:
    """메모 상단에 ground-check 실패 경고 박스를 삽입한다 (DP-3).

    Args:
        memo: 원본 메모 마크다운.
        warnings: 경고 메시지 목록.

    Returns:
        경고 박스가 앞에 추가된 메모 문자열.
    """
    if not warnings:
        return memo

    warning_lines = ["---", "> ⚠️ **확인이 필요한 항목이 있습니다**", ">"]
    for w in warnings:
        warning_lines.append(f"> - {w}")
    warning_lines += [">", "> 아래 계획을 실행하기 전에 위 항목을 확인해주세요.", "---", ""]

    return "\n".join(warning_lines) + "\n" + memo
