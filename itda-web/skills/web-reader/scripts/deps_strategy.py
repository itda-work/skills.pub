"""설치 전략 판정 — 순수 계층 (#1630 S3, `install_deps.py` 에서 추출).

환경 사실(`Environment`) → 전략(`Strategy`) → 복붙 가능한 명령(`render_command`).
**아무것도 설치하지 않고 아무것도 쓰지 않는다.** 소비자는 둘이다:

- `install_deps.py`   저장소 작업·진단 CLI (배포본에 없다)
- `deps_shim.py`      배포본의 스킬별 설치 정문 `scripts/install_skill_deps.py` 가 import 하는 런타임

두 소비자가 **같은 판정**을 쓰도록 여기 한 곳에 둔다(복제 금지 — 갈린다).

## 판정 축은 "site-packages 에 쓸 수 있는가" 다

PEP 668 은 그것을 막는 한 가지 사유일 뿐이다(#1627 Cowork 실측 — 비관리형인데 쓰기 불가).
그리고 **pip 은 그 경우 스스로 `--user` 로 폴백해 성공한다**(#1630 S6 1회차 실측 —
`Defaulting to user installation because normal site-packages is not writeable`, rc=0).
그래도 안내는 `--user` 를 **명시**한다: 폴백은 pip 버전·`PIP_USER`·`--no-user`·`python -s`
에 달린 동작이고 명시는 결정론이다.

stdlib only — 배포본에서 shim 과 함께 평면 복사된다(`publish.py _inject_shared_modules`).
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# 환경 사실 (순수 데이터)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Environment:
    """설치 전략 판정에 필요한 환경 사실. 관측만 담고 판단은 담지 않는다."""

    in_virtualenv: bool
    externally_managed: bool
    has_uv: bool
    #: site-packages 에 실제로 쓸 수 있는가. PEP 668 과 **별개 축**이다.
    site_packages_writable: bool = True
    #: user site 가 켜져 있는가(`python -s`·`PYTHONNOUSERSITE` 면 꺼진다 — 그때 `--user` 설치는
    #: 성공해도 재실행에서 안 보인다: 1차 리뷰 P1-1).
    user_site_enabled: bool = True
    python: str = sys.executable

    @classmethod
    def detect(cls) -> "Environment":
        return cls(
            in_virtualenv=detect_virtualenv(),
            externally_managed=detect_externally_managed(),
            has_uv=shutil.which("uv") is not None,
            site_packages_writable=detect_site_packages_writable(),
            user_site_enabled=detect_user_site_enabled(),
        )


def detect_site_packages_writable() -> bool:
    """이 인터프리터의 site-packages 에 쓸 수 있는가. 경로를 못 얻으면 보수적으로 False."""
    target = sysconfig.get_path("purelib")
    if not target:
        return False
    return os.access(target, os.W_OK)


def detect_virtualenv() -> bool:
    """`sys.prefix != sys.base_prefix` 가 표준 판별(venv·virtualenv 공통). conda 도 같은 취급."""
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return True
    return bool(os.environ.get("CONDA_PREFIX"))


def detect_externally_managed() -> bool:
    """PEP 668 마커는 `sysconfig.get_path("stdlib")` **아래**에 있다 — 경로를 짐작하지 마라(#1626 오판)."""
    stdlib = sysconfig.get_path("stdlib")
    if not stdlib:
        return False
    return Path(stdlib, "EXTERNALLY-MANAGED").exists()


def detect_user_site_enabled() -> bool:
    try:
        import site
        return bool(getattr(site, "ENABLE_USER_SITE", True)) and not sys.flags.no_user_site
    except Exception:  # noqa: BLE001
        return not sys.flags.no_user_site


# ---------------------------------------------------------------------------
# 전략 판정 (순수 함수)
# ---------------------------------------------------------------------------

USER_ISOLATED = "user-isolated"   # `--user --break-system-packages` — 관리형 + venv 밖
USER_PLAIN = "user-plain"         # `--user` — 비관리형 + 쓰기 불가
PLAIN = "plain"                   # 그대로 — venv 안 또는 쓰기 가능
UNSUPPORTED = "unsupported"       # 안전한 설치 경로 없음 — shim exit 2


@dataclass(frozen=True)
class Strategy:
    kind: str
    pip_args: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...] = field(default=())

    def command(self, python: str, targets: list[str]) -> list[str]:
        return [python, "-m", "pip", "install", *self.pip_args, *targets]


def decide_strategy(env: Environment) -> Strategy:
    """환경 사실 → 설치 전략. 부작용 없음."""
    if env.in_virtualenv:
        return Strategy(PLAIN, (), "가상환경 안에서 실행 중입니다 — 격리돼 있으므로 그대로 설치합니다.\n"
                                  f"  대상: {sys.prefix}")

    if not env.externally_managed:
        if env.site_packages_writable:
            return Strategy(PLAIN, (), "관리형이 아니고 site-packages 에 쓸 수 있습니다 — 그대로 설치합니다.")
        if not env.user_site_enabled:
            return Strategy(UNSUPPORTED, (),
                            "site-packages 에 쓸 수 없고 user site 도 꺼져 있습니다(`python -s`/PYTHONNOUSERSITE).\n"
                            "  안전한 설치 경로가 없습니다 — 전용 가상환경을 만드세요.")
        return Strategy(USER_PLAIN, ("--user",),
                        "관리형은 아니지만 site-packages 에 쓸 수 없습니다(권한).\n"
                        "  사용자 영역에 설치합니다 — PEP 668 이 아니므로 override 는 쓰지 않습니다.")

    if not env.user_site_enabled:
        return Strategy(UNSUPPORTED, (),
                        "PEP 668 관리형인데 user site 가 꺼져 있습니다 — 안전한 설치 경로가 없습니다. 전용 가상환경을 만드세요.")
    return Strategy(
        USER_ISOLATED, ("--user", "--break-system-packages"),
        "PEP 668 관리형 인터프리터입니다(homebrew·pyenv·apt 등).\n"
        "  사용자 영역에만 설치합니다 — 인터프리터 본체는 건드리지 않습니다.\n"
        f"  대상: {sysconfig.get_path('purelib', scheme='osx_framework_user') if sys.platform == 'darwin' else '사용자 site-packages'}",
        warnings=("`--break-system-packages` 는 `--user` 와 **함께** 쓸 때만 안전합니다. 단독으로 쓰면 인터프리터 본체가 오염됩니다.",),
    )


def suggest_venv(env: Environment) -> str:
    """더 깨끗한 대안(venv)을 안내한다. 실행하지는 않는다."""
    if env.has_uv:
        return ("더 깨끗한 대안 — 전용 가상환경(uv 감지됨):\n"
                "  uv venv ~/.venvs/itda && uv pip install --python ~/.venvs/itda/bin/python <패키지>\n"
                "  이후 스킬 실행 시 ~/.venvs/itda/bin/python 을 씁니다.")
    return ("더 깨끗한 대안 — 전용 가상환경:\n"
            "  python3 -m venv ~/.venvs/itda && ~/.venvs/itda/bin/pip install <패키지>\n"
            "  이후 스킬 실행 시 ~/.venvs/itda/bin/python 을 씁니다.")


# ---------------------------------------------------------------------------
# 표시용 명령 렌더링 — 실행 argv 와 **별개 계약** (1차 P1-7 · 2차 P1-3)
# ---------------------------------------------------------------------------


def render_command(argv: list[str], platform: str = sys.platform) -> str:
    """복붙 가능한 문자열. POSIX 는 `shlex.join`(sh 계약). Windows 는 `list2cmdline`(C 런타임 argv
    계약) — **PowerShell 의 `$`·백틱 escaping 은 보증하지 않는다**(라이브 round-trip 미실측, 2차 P1-3).
    공백·따옴표가 든 경로에서 argv 가 갈라지지 않는 것까지가 이 함수의 보증이다.
    """
    if platform.startswith("win"):
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)
