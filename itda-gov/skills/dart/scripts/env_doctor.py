"""env doctor — 환경변수 파일 발견·API 키 출처 진단 (값 비노출).

find_env_files() 로 발견된 환경변수 파일들(.env·.env.txt·env.txt·환경변수.txt,
별칭 4종 #1210), ~/.claude/settings.json env, os.environ
을 대조해 **각 키가 어디서 정의됐고 어느 출처가 승자인지**를 리포트한다.
env_loader 의 resolve_api_key 조회 우선순위(cli > os.environ > settings.json >
.env(뒤일수록 강함, ITDA_DATA_ROOT/.env 는 명시 오버라이드 최강))와 동일한
순서로 승자를 판정한다 (SPEC-DATAPATH-002).

⚠️ 보안 계약: 이 모듈은 **값·값 길이·값 일부를 절대 담지 않는다** — 키 이름과
출처(파일 경로 / "~/.claude/settings.json" / "os.environ")만 노출한다.
os.environ 은 관심 키(.env·settings 에 등장한 키)에 한해 **존재 여부만** 겹쳐본다
(전체 environ 키 덤프 금지 — 관심 밖 키 노출·노이즈 방지).

사용법:
    # macOS/Linux
    python3 env_doctor.py            # 사람용 한국어 리포트
    python3 env_doctor.py --json     # JSON

    # Windows
    py -3 env_doctor.py [--json]

    from env_doctor import collect_diagnosis, format_diagnosis
    diag = collect_diagnosis()
    print(format_diagnosis(diag))
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import env_loader
import itda_path

# 출처 라벨 (파일 경로가 아닌 특수 출처).
# settings 라벨은 CLAUDE_CONFIG_DIR 재지정을 반영해 동적으로 얻는다(#1330) —
# env_loader.claude_settings_label() 참조 (기본: "~/.claude/settings.json").
_ENVIRON_LABEL = "os.environ"


def _sanitize_control(text: str) -> str:
    r"""사람용 출력에 삽입되는 문자열의 제어문자를 가시 escape 로 무해화한다.

    경로·키 이름이 개행·ANSI escape(ESC)·기타 C0/C1 제어문자를 포함하면 사람용
    리포트가 깨지거나 터미널 제어 시퀀스가 주입될 수 있다. **경로·키 이름은
    전체를 그대로 노출**하되(관측 가능성이 목적) 제어문자만 `\xNN` 형태로 치환한다.
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


def collect_diagnosis() -> dict:
    """.env 발견 상태와 키별 출처를 진단한다 (값 비노출).

    Returns:
        {
          "env_files": [<.env 경로 문자열>, ...],  # 병합 순서(뒤일수록 우선)
          "keys": {
            "<키이름>": {
              "winner_source": "<승자 출처>",         # 최종 우선 출처
              "sources": ["<약>", ..., "<강>"],        # 등장 출처(병합 순서)
            }, ...
          },
        }

    값은 어떤 필드에도 담기지 않는다 — 키 이름과 출처만.
    """
    env_files = itda_path.find_env_files()  # 병합 순서: 뒤일수록 강함
    env_file_strs = [str(p) for p in env_files]

    # 병합 순서(약 → 강)로 각 출처의 "키 집합"만 훑는다 — 값은 읽지 않는다.
    #   [.env(약) ... .env(강)] < settings.json
    # (os.environ 은 아래에서 관심 키에 한해 겹쳐본다 — 전체 덤프 방지)
    layered: list[tuple[str, list[str]]] = []
    for path in env_files:
        layered.append((str(path), list(env_loader.load_env(path).keys())))
    settings_keys = list(env_loader._load_claude_settings_env().keys())
    layered.append((env_loader.claude_settings_label(), settings_keys))

    keys: dict[str, dict] = {}
    for source, key_names in layered:
        for key in key_names:
            info = keys.setdefault(key, {"winner_source": None, "sources": []})
            info["sources"].append(source)
            info["winner_source"] = source  # 뒤(더 강함)로 갱신 → 최종 = 승자

    # os.environ 은 관심 키(.env·settings 에 등장)에 한해 존재 여부만 겹쳐본다.
    # 전체 environ 키를 나열하지 않는다(관심 밖 키 노출·노이즈 방지).
    for key, info in keys.items():
        if key in os.environ:
            info["sources"].append(_ENVIRON_LABEL)
            info["winner_source"] = _ENVIRON_LABEL  # os.environ = 최강

    return {"env_files": env_file_strs, "keys": keys}


def format_diagnosis(diag: dict) -> str:
    """진단 결과를 사람용 한국어 리포트 문자열로 변환한다 (값 비노출)."""
    lines: list[str] = ["=== itda-skills env doctor ===", ""]

    env_files = diag.get("env_files", [])
    if env_files:
        lines.append(
            f"발견된 환경변수 파일(.env 등) ({len(env_files)}개, 병합 순서 — 뒤일수록 우선):"
        )
        for i, path in enumerate(env_files, 1):
            lines.append(f"  {i}. {_sanitize_control(path)}")
    else:
        lines.append("발견된 환경변수 파일(.env 등): 없음")
    lines.append("")

    keys = diag.get("keys", {})
    if keys:
        lines.append(f"키 출처 ({len(keys)}개, 환경변수 파일(.env 등)·settings.json 등장 키 기준):")
        for key in sorted(keys):
            info = keys[key]
            raw_winner = info.get("winner_source", "?")
            sources = info.get("sources", [])
            # 승자 제외 비교는 원본 문자열로, sanitize 는 표시 시점에만 —
            # 제어문자 포함 승자가 자기 자신을 "가려짐"으로 표시하는 모순 방지.
            shadowed = [_sanitize_control(s) for s in reversed(sources) if s != raw_winner]
            line = f"  - {_sanitize_control(key)}: 승자={_sanitize_control(raw_winner)}"
            if shadowed:
                line += f"  (가려짐: {', '.join(shadowed)})"
            lines.append(line)
    else:
        lines.append("키 출처: 없음 (환경변수 파일(.env 등)·settings.json 에서 발견된 키 없음)")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점 — 사람용 리포트(기본) 또는 --json."""
    parser = argparse.ArgumentParser(
        description="itda-skills env doctor — 환경변수 파일(.env 등) 발견·키 출처 진단 (값 비노출)",
    )
    parser.add_argument("--json", action="store_true", help="JSON 형식으로 출력")
    args = parser.parse_args(argv)

    diag = collect_diagnosis()
    if args.json:
        print(json.dumps(diag, ensure_ascii=False, indent=2))
    else:
        print(format_diagnosis(diag))
    return 0


if __name__ == "__main__":
    if sys.version_info[0] < 3:  # pragma: no cover - 방어적 버전 가드
        sys.exit("Python 3 필요")
    raise SystemExit(main())
