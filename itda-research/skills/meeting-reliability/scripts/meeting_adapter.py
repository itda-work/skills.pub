"""meeting_adapter.py — 회의 raw 녹취 → 발화(turn) 정규화.

신뢰성 검수 엔진의 회의록 타깃 어댑터. 코어 규칙(reliability_rules)은
타깃 비종속이며, 본 모듈은 회의 입력을 turn 리스트로 정규화하는 책임만 진다.
다른 타깃(전표·통제)은 같은 엔진에 다른 어댑터를 붙인다.

근거 span 단위 = 여기서 매기는 발화 인덱스(0-base, 헤더·빈 줄 제외 순번).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# 직함 suffix — 발화자 토큰 인식용
_TITLE = (
    r"(?:과장|차장|부장|팀장|대리|사원|주임|선임|책임|수석|대표|이사|상무|전무|"
    r"부사장|사장|회장|본부장|실장|국장|원장|센터장|매니저)"
)
_SPEAKER_RE = re.compile(r"^(\S+?" + _TITLE + r")\s+(.+)$")


@dataclass
class Turn:
    """녹취 발화 한 줄."""

    idx: int
    speaker: str
    text: str


def parse_transcript(raw: str) -> list[Turn]:
    """raw 녹취 텍스트를 발화 리스트로 파싱.

    - '#'로 시작하는 헤더 줄과 빈 줄은 건너뛴다.
    - 줄 첫 토큰이 직함으로 끝나면 발화자로, 나머지를 발화로 분리한다.
    - 발화자 인식 실패 시 speaker=''.
    """
    turns: list[Turn] = []
    idx = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _SPEAKER_RE.match(line)
        if m:
            speaker, text = m.group(1), m.group(2).strip()
        else:
            speaker, text = "", line
        turns.append(Turn(idx=idx, speaker=speaker, text=text))
        idx += 1
    return turns


def load_transcript(path: str | Path) -> list[Turn]:
    """파일 경로에서 녹취를 읽어 파싱."""
    return parse_transcript(Path(path).read_text(encoding="utf-8"))


def context_window(turns: list[Turn], idx: int, radius: int = 2) -> list[Turn]:
    """발화 idx 기준 앞뒤 radius개 맥락 창(기본 ±2)."""
    lo = max(0, idx - radius)
    hi = min(len(turns), idx + radius + 1)
    return turns[lo:hi]


def full_text(turns: list[Turn]) -> str:
    """전체 발화 텍스트(날짜 실재 대조 등에 사용)."""
    return "\n".join(t.text for t in turns)


def _cli(argv: list[str]) -> int:
    """녹취를 번호 매긴 발화로 출력 — 에이전트가 근거(evidence) 인덱스 확인용.

    출력: 'idx<TAB>speaker<TAB>text' (행마다 한 발화).
    """
    import sys

    if len(argv) < 1 or argv[0] in ("-h", "--help"):
        # --help 를 위치 인자로 흘리면 그 이름의 파일을 열려다 죽는다(#1630 실측)
        print("usage: python meeting_adapter.py <transcript.md>", file=sys.stderr)
        return 0 if argv else 2
    for t in load_transcript(argv[0]):
        print(f"{t.idx}\t{t.speaker or '—'}\t{t.text}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
