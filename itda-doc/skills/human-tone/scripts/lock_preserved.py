"""
lock_preserved.py — 보존 영역 placeholder 마스킹/복원 가드

itda-human-tone 스킬의 결정적 안전장치. 윤문 전 텍스트에서
숫자·날짜·이메일·전화·고유명사 후보·인용문·법조항 패턴을
재출현 안전한 토큰으로 치환한 뒤, 윤문 결과에서 원형 복원한다.

핵심 원리:
- LLM이 절대 건드리면 안 되는 영역을 사전에 빼서 placeholder로 가린다
- LLM은 placeholder를 의미 단위로만 인식 (가나다 또는 숫자 토큰)
- 윤문 결과에서 placeholder를 원본 문자열로 1:1 복원
- 복원 누락 또는 placeholder 변형이 있으면 비조건 실패 보고

표준 라이브러리만 사용. 외부 의존 0.

CLI:
  python lock_preserved.py mask <input.txt> > <masked.txt>      # 마스킹
  python lock_preserved.py restore <masked.txt> <map.json>      # 복원
  python lock_preserved.py audit <original.txt> <restored.txt>  # 무결성 감사

라이브러리:
  from lock_preserved import mask, restore, audit
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Iterable

# ──────────────────────────────────────────────────────────────────
# 패턴 사전 — 보존 카테고리별 정규식
# ──────────────────────────────────────────────────────────────────

# 우선순위 순 (앞이 먼저 매칭). URL > 이메일 > 전화 > 날짜 > 인용 > 숫자.
# 매칭 후 마스킹된 영역은 후속 패턴이 다시 매칭하지 않는다.
_PATTERNS: list[tuple[str, str]] = [
    # URL: scheme + host + path
    (
        "URL",
        r"https?://[^\s\"\'<>(){}\[\]]+",
    ),
    # 이메일
    (
        "MAIL",
        r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
    ),
    # 한국 전화번호: 010-1234-5678 / 02-123-4567 / +82-10-... / 1588-1234
    (
        "TEL",
        r"(?:\+?\d{1,3}-)?\d{2,4}-\d{3,4}-\d{4}|\d{4}-\d{4}",
    ),
    # 날짜: 2026-05-11 / 2026.05.11 / 2026/05/11 / 2026년 5월 11일 / 2026년 5월
    (
        "DATE",
        r"\d{4}[-./]\d{1,2}[-./]\d{1,2}|\d{4}년\s*\d{1,2}월(?:\s*\d{1,2}일)?",
    ),
    # 시간: 14:30 / 오후 2:30 / 14시 30분
    (
        "TIME",
        r"(?:오전|오후)?\s*\d{1,2}:\d{2}(?::\d{2})?|\d{1,2}시\s*\d{1,2}분",
    ),
    # 큰따옴표 인용문 (한국어 곧은/굽은 따옴표 모두)
    (
        "QUOTE",
        r"[\"“][^\"“”]{1,400}[\"”]",
    ),
    # 법조항: 제N조, 제N항, 제N호 (연속 가능)
    (
        "LAW",
        r"제\s*\d+\s*(?:조|항|호|목|관|장|편)(?:\s*제\s*\d+\s*(?:조|항|호|목))*",
    ),
    # 통화·금액: 1,234,000원 / 1.5억 / $1,234.56 / ₩1,234
    (
        "MONEY",
        r"[$₩€¥£]\s*\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s*(?:원|달러|만원|억원|억|만|천만|백만)",
    ),
    # 퍼센트: 18% / 18.5% / 0.5%p
    (
        "PCT",
        r"\d+(?:\.\d+)?\s*(?:%|퍼센트|%p|%P)",
    ),
    # 일반 숫자 (단위 포함): 12건 / 5명 / 3.14 / 1,234
    # 위 패턴들에서 안 잡힌 잔여 숫자 — 마지막에 위치
    (
        "NUM",
        r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?",
    ),
]

# 한국어에서 안전하게 토큰으로 동작하는 placeholder 형식.
# 영문+숫자 조합으로 형태소 분석기가 단일 토큰으로 인식.
# 'KEEP'은 의도적으로 짧고 고유한 시퀀스. 윤문가가 변경할 가능성 최소화.
_PH_FORMAT = "⟦KEEP{idx:04d}⟧"
_PH_PATTERN = re.compile(r"⟦KEEP(\d{4})⟧")


@dataclass
class PreserveMap:
    """마스킹 → 복원 사이의 1:1 매핑."""

    items: list[dict] = field(default_factory=list)
    """[{ 'placeholder': '⟦KEEP0001⟧', 'category': 'NUM', 'original': '15%', 'offset': 42 }, ...]"""

    def to_json(self) -> str:
        return json.dumps({"items": self.items}, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "PreserveMap":
        obj = json.loads(text)
        return cls(items=obj.get("items", []))


# ──────────────────────────────────────────────────────────────────
# Mask
# ──────────────────────────────────────────────────────────────────


def mask(text: str) -> tuple[str, PreserveMap]:
    """원문에서 보존 카테고리 패턴을 placeholder로 치환.

    Returns:
        (masked_text, preserve_map)

    Notes:
        매칭 우선순위는 _PATTERNS 순서. URL > 이메일 > ... > NUM.
        이미 마스킹된 placeholder 영역은 후속 패턴이 절대 건드리지 못하도록
        split-by-placeholder 방식으로 격리한다 (placeholder 안의 숫자가 NUM에
        다시 매칭되는 사고 방지).
    """
    pmap = PreserveMap()
    counter = [0]

    def _apply(category: str, pattern: str, src: str) -> str:
        # placeholder를 경계로 텍스트를 쪼개고, 비-placeholder 조각에만 매칭 적용
        parts = _PH_PATTERN.split(src)
        # split 결과: [text0, idx1, text1, idx2, text2, ...]
        # 짝수 인덱스만 비-placeholder 텍스트, 홀수는 placeholder의 idx 캡처
        out: list[str] = []
        for i, chunk in enumerate(parts):
            if i % 2 == 0:
                # 비-placeholder 텍스트 — 패턴 매칭
                def _replace(match: re.Match) -> str:
                    ph = _PH_FORMAT.format(idx=counter[0])
                    pmap.items.append({
                        "placeholder": ph,
                        "category": category,
                        "original": match.group(0),
                    })
                    counter[0] += 1
                    return ph

                out.append(re.sub(pattern, _replace, chunk))
            else:
                # placeholder idx — 원래 형태로 복원
                out.append(_PH_FORMAT.format(idx=int(chunk)))
        return "".join(out)

    masked = text
    for category, pattern in _PATTERNS:
        masked = _apply(category, pattern, masked)

    return masked, pmap


# ──────────────────────────────────────────────────────────────────
# Restore
# ──────────────────────────────────────────────────────────────────


def restore(masked_text: str, pmap: PreserveMap) -> tuple[str, list[str]]:
    """윤문된 masked_text의 placeholder를 원본으로 복원.

    Returns:
        (restored_text, missing_placeholders)
        missing_placeholders: 윤문가가 삭제했거나 변형한 placeholder 목록
    """
    restored = masked_text
    missing: list[str] = []

    for item in pmap.items:
        ph = item["placeholder"]
        if ph not in restored:
            missing.append(ph)
            continue
        restored = restored.replace(ph, item["original"])

    # placeholder 잔존 검사 (윤문가가 변형한 placeholder 탐지)
    leftover = _PH_PATTERN.findall(restored)
    if leftover:
        for idx in leftover:
            missing.append(f"⟦KEEP{idx}⟧ (변형 또는 중복)")

    return restored, missing


# ──────────────────────────────────────────────────────────────────
# Audit
# ──────────────────────────────────────────────────────────────────


def audit(original: str, restored: str, pmap: PreserveMap) -> dict:
    """원본과 복원된 텍스트의 보존 영역이 100% 일치하는지 감사.

    Returns:
        {
          'pass': bool,
          'preserved_count': int,
          'mismatches': list[{'category', 'expected', 'found_in_restored'}],
          'missing': list[str],
          'extra_numeric': list[str],  # 복원본에 새로 등장한 숫자 (LLM 환각 의심)
        }
    """
    # 모든 원본 토큰이 복원본에 존재해야 함
    mismatches = []
    for item in pmap.items:
        if item["original"] not in restored:
            mismatches.append({
                "category": item["category"],
                "expected": item["original"],
                "placeholder": item["placeholder"],
            })

    # 복원본의 숫자가 원본에 없으면 환각 의심
    original_nums = set(re.findall(r"\d+(?:[.,]\d+)*", original))
    restored_nums = set(re.findall(r"\d+(?:[.,]\d+)*", restored))
    extra = sorted(restored_nums - original_nums)

    return {
        "pass": not mismatches and not extra,
        "preserved_count": len(pmap.items),
        "mismatches": mismatches,
        "extra_numeric": extra,
    }


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────


def _main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="보존 영역 placeholder 마스킹/복원 가드",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mask = sub.add_parser("mask", help="원문 → masked + map.json")
    p_mask.add_argument("input", help="원문 파일 경로")
    p_mask.add_argument("--map-out", default="preserve_map.json")

    p_restore = sub.add_parser("restore", help="masked + map → 복원")
    p_restore.add_argument("masked", help="마스킹된 텍스트 파일")
    p_restore.add_argument("map", help="preserve_map.json 경로")

    p_audit = sub.add_parser("audit", help="원본 vs 복원본 무결성 감사")
    p_audit.add_argument("original")
    p_audit.add_argument("restored")
    p_audit.add_argument("map")

    args = parser.parse_args(list(argv) if argv else None)

    if args.cmd == "mask":
        with open(args.input, encoding="utf-8") as f:
            text = f.read()
        masked, pmap = mask(text)
        sys.stdout.write(masked)
        with open(args.map_out, "w", encoding="utf-8") as f:
            f.write(pmap.to_json())
        sys.stderr.write(f"[mask] {len(pmap.items)} placeholders → {args.map_out}\n")
        return 0

    if args.cmd == "restore":
        with open(args.masked, encoding="utf-8") as f:
            masked = f.read()
        with open(args.map, encoding="utf-8") as f:
            pmap = PreserveMap.from_json(f.read())
        restored, missing = restore(masked, pmap)
        sys.stdout.write(restored)
        if missing:
            sys.stderr.write(f"[restore] WARNING: {len(missing)} missing/altered placeholders\n")
            for m in missing:
                sys.stderr.write(f"  - {m}\n")
            return 2
        return 0

    if args.cmd == "audit":
        with open(args.original, encoding="utf-8") as f:
            original = f.read()
        with open(args.restored, encoding="utf-8") as f:
            restored = f.read()
        with open(args.map, encoding="utf-8") as f:
            pmap = PreserveMap.from_json(f.read())
        report = audit(original, restored, pmap)
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
        return 0 if report["pass"] else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
