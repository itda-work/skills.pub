#!/usr/bin/env python3
"""이 스킬의 의존성 설치 정문 — 정본은 옆의 deps.json (deps_manifest.py gen-specs 생성물 · 손대지 마라).

    python3 install_skill_deps.py            # 기본 그룹(시작·기능 필수)
    python3 install_skill_deps.py --all      # 선택 의존까지
    python3 install_skill_deps.py --check    # 설치하지 않고 상태만
    python3 install_skill_deps.py --dry-run  # 고른 명령만 출력
exit 0 성공 · 2 안전한 설치 경로 없음 · 3 pip 실패 · 4 deps.json 부재/손상
"""
import sys
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit(f"Python 3.10 이상이 필요합니다 (현재 {sys.version_info.major}.{sys.version_info.minor}).")

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))          # 배포본: deps_shim·deps_strategy 가 여기 평면 복사돼 있다
try:
    import deps_shim
except ImportError:                     # 소스 체크아웃: skills/shared 를 찾는다(양쪽에서 같은 명령 — 2차 리뷰 P0-2)
    for _p in _HERE.parents:
        if (_p / "shared" / "deps_shim.py").is_file():
            sys.path.insert(0, str(_p / "shared"))
            break
    import deps_shim

if __name__ == "__main__":
    raise SystemExit(deps_shim.main(_HERE.parent))
