"""find_images.py — native 변환 출력 디렉토리에서 이미지를 탐색한다.

신규 경로 패턴 (<stem>/image_NNNN.<ext>) 과 구버전 경로 패턴 (images/*.<ext>) 을
동시에 탐색하여 후방 호환을 유지한다.

SPEC: SPEC-HWPX-003 Track A
"""
from __future__ import annotations

from pathlib import Path

# 지원 이미지 확장자
_EXTENSIONS = ("png", "jpg", "jpeg", "gif")

# 구버전 경로 감지 시 출력할 안내 메시지
_LEGACY_WARNING = (
    "구버전 이미지 출력 패턴(images/*)이 감지되었습니다. "
    "가능하면 <stem>/image_NNNN 경로로 재변환하세요."
)


def _collect_sorted(directory: Path, patterns: tuple[str, ...]) -> list[str]:
    """directory 에서 glob 패턴 목록에 매칭되는 파일을 sorted 절대경로 list 로 반환한다."""
    found: list[Path] = []
    for pattern in patterns:
        found.extend(directory.glob(pattern))
    return sorted(str(p.resolve()) for p in found)


def _glob_new_pattern(output_dir: Path, stem: str) -> list[str]:
    """신규 패턴: <output_dir>/<stem>/image_NNNN.<ext> 탐색.

    'image_[0-9][0-9][0-9][0-9]*.<ext>' 패턴이 4자리·5자리·그 이상을 모두 흡수한다.
    E3 위험 완화: 가변 자릿수에 무감응 (SPEC-HWPX-003 §9).
    """
    stem_dir = output_dir / stem
    if not stem_dir.is_dir():
        return []
    patterns = tuple(f"image_[0-9][0-9][0-9][0-9]*.{ext}" for ext in _EXTENSIONS)
    return _collect_sorted(stem_dir, patterns)


def _glob_legacy_pattern(output_dir: Path) -> list[str]:
    """구버전 패턴: <output_dir>/images/*.<ext> 탐색.

    과거 출력 경로. fallback 으로 탐색한다.
    """
    images_dir = output_dir / "images"
    if not images_dir.is_dir():
        return []
    patterns = tuple(f"*.{ext}" for ext in _EXTENSIONS)
    return _collect_sorted(images_dir, patterns)


def find_images(output_dir: str, stem: str) -> dict:
    """native 변환 출력 디렉토리에서 추출된 이미지를 탐색한다.

    Args:
        output_dir: 변환기가 출력한 베이스 디렉토리 (예: ".itda-skills")
        stem: -o 로 명시한 MD 파일명의 stem (확장자 제외, 예: "보도자료")

    Returns:
        {
            "new": [절대경로 list, 신규 <stem>/image_NNNN.<ext>],
            "legacy": [절대경로 list, 구버전 images/*.<ext>],
            "primary": "new" | "legacy" | "none",   # 워크플로가 사용할 우선 경로
            "warning": str | None                    # legacy 만 있을 때 안내 메시지
        }

    동작:
    - 신규 패턴: glob "{output_dir}/{stem}/image_*.{png,jpg,jpeg,gif}" — 4/5자리 zero-pad 모두 흡수
    - 구버전 패턴: glob "{output_dir}/images/*.{png,jpg,jpeg,gif}"
    - 양쪽 모두 존재 → primary="new", warning=None
    - 신규만 존재 → primary="new", warning=None
    - 구버전만 존재 → primary="legacy", warning=구버전 출력 패턴 안내
    - 둘 다 없음 → primary="none", new=[], legacy=[], warning=None
    - 결과 list 는 sorted (재현 가능)
    """
    base = Path(output_dir)

    new_images = _glob_new_pattern(base, stem)
    legacy_images = _glob_legacy_pattern(base)

    # primary 결정 및 warning 설정
    if new_images:
        primary = "new"
        warning = None
    elif legacy_images:
        primary = "legacy"
        warning = _LEGACY_WARNING
    else:
        primary = "none"
        warning = None

    return {
        "new": new_images,
        "legacy": legacy_images,
        "primary": primary,
        "warning": warning,
    }
