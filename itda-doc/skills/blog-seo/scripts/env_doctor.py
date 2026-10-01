"""env doctor — API 키가 프로세스 환경변수에 들어와 있는지 진단 (값 비노출).

스킬 스크립트는 env 파일(``.env``·``.env.txt`` 등)을 읽지 않는다(itda-work/skills#45).
키는 두 경로로만 들어온다:

1. **프로세스 환경변수**(``os.environ``) — Claude Code CLI 에서는 셸 환경변수 또는
   ``claude config set env.KEY "값"``.
2. **itda-hyve 시크릿** — itda-hyve GUI 시크릿 탭에 등록한 키를 hyve MCP 도구(``http_request`` 등)가
   요청에 넣는다. 스크립트는 그 값을 보지 못하므로 이 도구도 진단하지 못한다.

그래서 이 도구는 **지목된 키가 os.environ 에 있는지**만 본다. 없는 키가 있으면 위 두 경로를 안내한다.

⚠️ 보안 계약: 이 모듈은 **값·값 길이·값 일부를 절대 담지 않는다** — 키 이름과 존재 여부만.
지목되지 않은 environ 키는 나열하지 않는다(전체 environ 덤프 금지).

사용법:
    # macOS/Linux
    python3 env_doctor.py DART_API_KEY KOSIS_API_KEY          # 사람용 한국어 리포트
    python3 env_doctor.py DART_API_KEY --json                 # JSON

    # Windows
    py -3 env_doctor.py DART_API_KEY [--json]

    from env_doctor import collect_diagnosis, format_diagnosis
    diag = collect_diagnosis(["DART_API_KEY"])
    print(format_diagnosis(diag))
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable

_ENVIRON_LABEL = "os.environ"


def _sanitize_control(text: str) -> str:
    r"""사람용 출력에 삽입되는 문자열의 제어문자를 가시 escape 로 무해화한다.

    키 이름이 개행·ANSI escape(ESC)·기타 C0/C1 제어문자를 포함하면 사람용
    리포트가 깨지거나 터미널 제어 시퀀스가 주입될 수 있다. 문자열은 그대로
    노출하되(관측 가능성이 목적) 제어문자만 `\xNN` 형태로 치환한다.
    값은 애초에 다루지 않는다(마스킹 계약).
    """
    out: list[str] = []
    for ch in text:
        cp = ord(ch)
        # C0(0x00~0x1F, ESC 0x1B 포함) · DEL(0x7F) · C1(0x80~0x9F)
        if cp < 0x20 or cp == 0x7F or 0x80 <= cp <= 0x9F:
            out.append(f"\\x{cp:02x}")
        else:
            out.append(ch)
    return "".join(out)


def setup_guide_lines(var_names: Iterable[str]) -> list[str]:
    """키를 넣는 두 경로 안내 줄 (env_loader 의 부재 안내와 같은 내용)."""
    names = ", ".join(_sanitize_control(v) for v in var_names) or "<KEY>"
    return [
        "키를 넣는 경로 (스킬은 .env 같은 파일을 읽지 않습니다):",
        f"  - Claude Code: 셸 환경변수로 넣거나 `claude config set env.<KEY> \"<키>\"` 로 등록한 뒤"
        f" 세션을 다시 시작하세요 (대상: {names}).",
        "  - itda-hyve GUI 의 시크릿 탭에 같은 이름으로 등록한 키는 스크립트가 읽지 못합니다 —"
        " 스킬 문서에 itda-hyve 의 http_request 절차가 있는 경우에만 쓰이며, 이 진단은 그 값을 보지 못합니다.",
        "  키 값을 대화에 붙여 넣지 마세요.",
    ]


def collect_diagnosis(var_names: Iterable[str] = ()) -> dict:
    """지목된 키가 os.environ 에 있는지 진단한다 (값 비노출).

    Returns:
        {
          "keys": {"<키이름>": {"present": bool, "source": "os.environ" | None}, ...},
          "missing": ["<없는 키>", ...],
        }

    값은 어떤 필드에도 담기지 않는다 — 키 이름과 존재 여부만.
    """
    keys: dict[str, dict] = {}
    missing: list[str] = []
    for var in var_names:
        present = bool(os.environ.get(var))
        keys[var] = {"present": present, "source": _ENVIRON_LABEL if present else None}
        if not present:
            missing.append(var)
    return {"keys": keys, "missing": missing}


def format_diagnosis(diag: dict) -> str:
    """진단 결과를 사람용 한국어 리포트 문자열로 변환한다 (값 비노출)."""
    lines: list[str] = ["=== itda-skills env doctor ===", ""]

    keys = diag.get("keys", {})
    if keys:
        lines.append(f"키 확인 ({len(keys)}개, 프로세스 환경변수 기준):")
        for key in keys:
            mark = "있음 (os.environ)" if keys[key].get("present") else "없음"
            lines.append(f"  - {_sanitize_control(key)}: {mark}")
    else:
        lines.append("확인할 키 이름을 인자로 주세요 — 예: env_doctor.py DART_API_KEY")
    lines.append("")

    missing = diag.get("missing", [])
    if missing or not keys:
        lines.extend(setup_guide_lines(missing))

    return "\n".join(lines).rstrip("\n")


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점 — 사람용 리포트(기본) 또는 --json. 없는 키가 있으면 exit 1."""
    parser = argparse.ArgumentParser(
        description="itda-skills env doctor — API 키가 프로세스 환경변수에 있는지 진단 (값 비노출)",
    )
    parser.add_argument("keys", nargs="*", help="확인할 키 이름 (예: DART_API_KEY)")
    parser.add_argument("--json", action="store_true", help="JSON 형식으로 출력")
    args = parser.parse_args(argv)

    diag = collect_diagnosis(args.keys)
    if args.json:
        print(json.dumps(diag, ensure_ascii=False, indent=2))
    else:
        print(format_diagnosis(diag))
    return 1 if diag["missing"] else 0


if __name__ == "__main__":
    if sys.version_info[0] < 3:  # pragma: no cover - 방어적 버전 가드
        sys.exit("Python 3 필요")
    for _stream in (sys.stdout, sys.stderr):  # Windows 콘솔 cp949 대비
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
    raise SystemExit(main())
