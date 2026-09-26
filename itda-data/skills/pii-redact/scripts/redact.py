#!/usr/bin/env python3
"""pii-redact 코어 — 한국 CS 텍스트의 PII 결정론 검출·마스킹.

stdlib only (re, json, sys, os, argparse). 외부 의존 없음.

설계 원칙:
  1. 결정론 로컬 우선 — raw를 LLM에 먼저 넣지 않는다. 정규식/룰로 먼저 가린다.
  2. 재현율 우선 — 누락(PII 유출) < 과제거(본문 훼손). 단 카드/계좌처럼 충돌이
     큰 유형은 강한 구조 또는 문맥이 없으면 마스킹을 '보류'하고 리포트에 투명 기록.
  3. 체크섬은 필터가 아니라 confidence 태그 — 주민번호 mod11·카드 Luhn 실패해도
     마스킹은 하되 confidence를 낮춘다(틀린 번호라고 유출을 허용하지 않는다).
  4. 마스킹 = 플레이스홀더([전화_1]) + 문서 내 일관 가명화(같은 값→같은 토큰).

제공 함수:
  redact_text(text, ...)  — 비식별 텍스트 + 마스킹 리포트 dict
  detect(text)            — 매치 목록 [{type, start, end, raw, confidence}]
  rrn_checksum_ok(digits) — 주민번호 mod11 체크섬
  luhn_ok(digits)         — 카드 Luhn 체크섬
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다.")

SCHEMA_VERSION = "1.0"

# ── 유형 메타 ────────────────────────────────────────────────
# label: 플레이스홀더 표기, priority: 겹침 해소 우선순위(높을수록 우선)
TYPE_META = {
    "rrn":            {"label": "주민번호",   "priority": 9},
    "card":           {"label": "카드번호",   "priority": 8},
    "email":          {"label": "이메일",     "priority": 8},
    "biz_no":         {"label": "사업자번호", "priority": 7},
    "driver_license": {"label": "운전면허",   "priority": 7},
    "phone":          {"label": "전화",       "priority": 6},
    "passport":       {"label": "여권번호",   "priority": 5},
    "account":        {"label": "계좌번호",   "priority": 5},
    "address":        {"label": "주소",       "priority": 4},
}

_CONF_RANK = {"high": 2, "candidate": 1, "low": 0}

# 문맥 키워드 (앞뒤 window 안에 있으면 가점)
_CARD_CTX = ("카드", "결제", "승인", "할부", "체크카드", "신용")
_ACCOUNT_CTX = ("계좌", "입금", "환불", "송금", "예금주", "이체", "은행",
                "농협", "국민", "신한", "우리", "하나", "기업", "카카오뱅크",
                "토스", "새마을", "수협", "씨티", "sc제일", "케이뱅크")
_BIZ_CTX = ("사업자", "사업자등록", "법인", "대표자")
_PASSPORT_CTX = ("여권", "passport")
# 부정 문맥 — 주문/접수/배송 식별자는 PII 아님(과탐 방지)
_NEG_CTX = ("주문", "접수", "송장", "운송장", "예약", "티켓", "문의번호",
            "상품코드", "수량", "재고", "버전")


# ── 체크섬 ───────────────────────────────────────────────────

def rrn_checksum_ok(digits: str) -> bool:
    """주민등록번호 13자리 mod11 체크섬. 가중치 [2..9,2..5]."""
    if len(digits) != 13 or not digits.isdigit():
        return False
    weights = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]
    s = sum(int(d) * w for d, w in zip(digits[:12], weights))
    check = (11 - (s % 11)) % 10
    return check == int(digits[12])


def luhn_ok(digits: str) -> bool:
    """카드번호 Luhn 체크섬."""
    if not digits.isdigit() or len(digits) < 12:
        return False
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _valid_rrn_date(yy: str, mm: str, dd: str) -> bool:
    m, d = int(mm), int(dd)
    return 1 <= m <= 12 and 1 <= d <= 31


def _has_context(text: str, start: int, end: int, keywords, window: int = 20) -> bool:
    left = text[max(0, start - window):start]
    right = text[end:end + window]
    ctx = left + right
    return any(k in ctx for k in keywords)


# ── 정규식 ───────────────────────────────────────────────────
# 숫자 경계: 한국어 인접을 허용하되 숫자 런 중간 매칭은 막는다.
_RRN = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})[- ]?([1-8])(\d{6})(?!\d)")

_PHONE = re.compile(
    r"(?<![\d])"
    r"(?:\+82[-\s]?|0)"
    r"(?:1[016789]|2|[3-6][1-5]|70|50\d|80)"
    r"[-\s.]?\d{3,4}[-\s.]?\d{4}"
    r"(?!\d)"
)

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# 카드: 4-4-4-4(구분자 -, 공백 허용) 또는 13~19 연속숫자
_CARD = re.compile(r"(?<!\d)(?:\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{1,7}|\d{13,19})(?!\d)")

# 사업자등록번호: 3-2-5 (하이픈 필수 = high) / bare 10자리는 문맥 게이트
_BIZ_HYPHEN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{5}(?!\d)")
_BIZ_BARE = re.compile(r"(?<!\d)\d{10}(?!\d)")

_DRIVER = re.compile(r"(?<!\d)\d{2}-\d{2}-\d{6}-\d{2}(?!\d)")

# 여권: 구형 1글자+8자리 / 신형 1글자+3자리+1글자+4자리
_PASSPORT = re.compile(r"(?<![A-Za-z0-9])[A-Z]\d{8}(?![A-Za-z0-9])")
_PASSPORT_NEW = re.compile(r"(?<![A-Za-z0-9])[A-Z]\d{3}[A-Z]\d{4}(?![A-Za-z0-9])")

# 계좌: 하이픈 포함 10~16자리 숫자열(문맥 게이트 — 문맥 없으면 미검출)
_ACCOUNT = re.compile(r"(?<![\d-])\d[\d-]{8,18}\d(?!\d)")

# 주소: 시·도 앵커 + 시/군/구 + 동/읍/면/리/로/길 + (선택)번지·호.
# 꼬리는 임의 텍스트를 삼키지 않는다(뒤따르는 다른 PII를 흡수해 통째 누락되는 것 방지).
_SIDO = (r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|"
         r"전북|전남|경북|경남|제주)"
         r"(?:특별자치시|특별자치도|특별시|광역시|특별시|도|시)?")
_ADDRESS = re.compile(
    _SIDO + r"\s*\S{1,10}?(?:시|군|구)"
    # 상세 토큰을 반복 소비하되, 진짜 주소 토큰 형태로만 한정한다.
    # - 행정동/읍/면/리: 토큰 경계(공백·숫자·쉼표·끝) 앞에서만
    # - 도로명(로/길): 뒤에 번호가 와야 함 → "추가로 요청" 같은 부사 오인 배제
    # - 번호+단위(번지/호/동/층 등) 또는 짧은 건물번호(긴 ID·전화 배제: bare 4자리 이하 + 숫자/하이픈 비후행)
    r"(?:\s*(?:"
    r"\S{1,10}?(?:동|읍|면|리)(?=\s|\d|$|[.,;:!?)\]}·…」』）])"
    r"|\S{1,10}?(?:로|길)(?=\s*\d)"
    r"|\d{1,5}(?:-\d{1,5})?(?:번지|번길|호|동|층|가|번)"  # 번호+단위 (본번-부번 = 하이픈 1개)
    r"|\d{1,5}(?:-\d{1,5})?(?![\d-])"                    # 단위 없는 건물번호(긴 ID·하이픈 체인 제외)
    r"))*"
)


def _norm(pii_type: str, raw: str) -> str:
    """일관 가명화용 정규화 키."""
    if pii_type == "email":
        return raw.lower()
    if pii_type == "address":
        return re.sub(r"\s+", " ", raw.strip())
    return re.sub(r"\D", "", raw)  # 숫자형: 구분자 제거


def detect(text: str) -> list:
    """텍스트에서 PII 매치를 검출. [{type,start,end,raw,confidence}]."""
    out = []

    def add(t, m, conf, s=None, e=None):
        s = m.start() if s is None else s
        e = m.end() if e is None else e
        out.append({"type": t, "start": s, "end": e,
                    "raw": text[s:e], "confidence": conf})

    # 주민등록번호
    for m in _RRN.finditer(text):
        yy, mm, dd, g, rest = m.groups()
        if not _valid_rrn_date(yy, mm, dd):
            continue
        digits = yy + mm + dd + g + rest
        conf = "high" if rrn_checksum_ok(digits) else "candidate"
        add("rrn", m, conf)

    # 전화
    for m in _PHONE.finditer(text):
        add("phone", m, "high")

    # 이메일
    for m in _EMAIL.finditer(text):
        add("email", m, "high")

    # 카드
    for m in _CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        ctx = _has_context(text, m.start(), m.end(), _CARD_CTX)
        neg = _has_context(text, m.start(), m.end(), _NEG_CTX)
        if luhn_ok(digits) or ctx:
            conf = "high"  # Luhn 통과 또는 카드 문맥 = 강한 신호(부정 문맥 무시)
        elif neg:
            conf = "low"   # 주문·송장 문맥 → 주문번호 오인 → 마스킹 보류
        elif "-" in m.group() or " " in m.group():
            conf = "candidate"  # 4-4-4-4 구조
        else:
            conf = "low"  # bare 연속숫자, Luhn·문맥 없음 → 주문번호 등 오인 위험
        add("card", m, conf)

    # 사업자등록번호(하이픈)
    for m in _BIZ_HYPHEN.finditer(text):
        add("biz_no", m, "high")
    # 사업자등록번호(bare 10자리) — 문맥 있을 때만
    for m in _BIZ_BARE.finditer(text):
        if _has_context(text, m.start(), m.end(), _BIZ_CTX):
            add("biz_no", m, "candidate")

    # 운전면허
    for m in _DRIVER.finditer(text):
        add("driver_license", m, "candidate")

    # 여권
    for m in _PASSPORT.finditer(text):
        conf = "high" if _has_context(text, m.start(), m.end(), _PASSPORT_CTX) else "candidate"
        add("passport", m, conf)
    for m in _PASSPORT_NEW.finditer(text):
        conf = "high" if _has_context(text, m.start(), m.end(), _PASSPORT_CTX) else "candidate"
        add("passport", m, conf)

    # 계좌 — 문맥 게이트(문맥 없으면 미검출, 과탐 회피)
    for m in _ACCOUNT.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if not (10 <= len(digits) <= 16):
            continue
        if _has_context(text, m.start(), m.end(), _ACCOUNT_CTX):
            add("account", m, "candidate")

    # 주소
    for m in _ADDRESS.finditer(text):
        add("address", m, "candidate")

    return out


def _resolve_overlaps(matches: list) -> list:
    """겹치는 매치를 우선순위·confidence·길이로 해소.

    높은 우선순위 매치가 낮은 매치 안에 들어가면(예: 주소가 뒤따르는 전화를 흡수),
    낮은 매치의 끝을 높은 매치 시작점까지 **트리밍**해 둘 다 살린다. 시작점이 이미
    높은 매치에 덮인 경우만 드롭. → 주소가 전화를 삼켜 통째 누락되는 일을 막는다.
    """
    ranked = sorted(
        matches,
        key=lambda x: (TYPE_META[x["type"]]["priority"],
                       _CONF_RANK[x["confidence"]],
                       x["end"] - x["start"]),
        reverse=True,
    )
    accepted = []
    for m in ranked:
        start, end = m["start"], m["end"]
        # 시작점이 이미 채택된 매치에 덮이면 드롭
        if any(a["start"] <= start < a["end"] for a in accepted):
            continue
        # (start, end) 안에서 시작하는 채택 매치 중 가장 앞으로 끝을 자른다
        cut = min((a["start"] for a in accepted if start < a["start"] < end), default=end)
        raw = m["raw"][:cut - start].rstrip()
        if not raw:
            continue
        nm = dict(m)
        nm["end"] = start + len(raw)
        nm["raw"] = raw
        accepted.append(nm)
    accepted.sort(key=lambda x: x["start"])
    return accepted


def redact_text(text: str, *, mask_low: bool = False) -> dict:
    """비식별 텍스트 + 마스킹 리포트.

    mask_low=False(기본): confidence='low'(카드 bare 등)는 마스킹 보류,
    low_confidence_skipped에 투명 기록. True면 low도 마스킹(최대 재현율).
    """
    matches = detect(text)

    # low(보류 대상)는 겹침 해소 *이전*에 분리한다. 그래야 같은 구간을 두고
    # 마스킹될 candidate(예: 문맥 있는 계좌)가 low 카드에 가려져 유출되지 않는다.
    if mask_low:
        maskable, low_src = matches, []
    else:
        maskable = [m for m in matches if m["confidence"] != "low"]
        low_src = [m for m in matches if m["confidence"] == "low"]

    to_mask = _resolve_overlaps(maskable)

    def _overlaps(m, others):
        return any(not (m["end"] <= o["start"] or m["start"] >= o["end"]) for o in others)

    # 보류 기록: 마스킹된 구간에 이미 덮인 low는 제외(중복 보고 방지)
    skipped = [{"type": m["type"], "span": [m["start"], m["end"]],
                "reason": "구조/문맥 부족 — 마스킹 보류(주문번호 등 오인 위험)"}
               for m in low_src if not _overlaps(m, to_mask)]

    # 일관 가명화 토큰 부여
    counters = {}          # type -> 다음 번호
    token_of = {}          # (type, norm) -> token
    redactions = []
    for m in sorted(to_mask, key=lambda x: x["start"]):
        key = (m["type"], _norm(m["type"], m["raw"]))
        if key not in token_of:
            counters[m["type"]] = counters.get(m["type"], 0) + 1
            label = TYPE_META[m["type"]]["label"]
            token_of[key] = f"[{label}_{counters[m['type']]}]"
        token = token_of[key]
        redactions.append({"type": m["type"], "token": token,
                            "confidence": m["confidence"],
                            "span": [m["start"], m["end"]]})

    # 뒤→앞 치환(span 무손상)
    redacted = text
    for r in sorted(redactions, key=lambda x: x["span"][0], reverse=True):
        s, e = r["span"]
        redacted = redacted[:s] + r["token"] + redacted[e:]

    by_type = {}
    for r in redactions:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "redacted_text": redacted,
        "n_redactions": len(redactions),
        "by_type": by_type,
        "redactions": redactions,
        "low_confidence_skipped": skipped,
        "policy": {
            "mask_format": "placeholder",
            "consistent_pseudonym": True,
            "recall_first": True,
            "mask_low_confidence": mask_low,
            "llm_second_pass": False,
        },
        "residual_risk_note": (
            "결정론 룰 기반 — 정규식이 못 잡는 자유텍스트 이름·구어체 주소·변형 표기는 "
            "남을 수 있다. 이미 마스킹된 텍스트에 한해 LLM 2차 리뷰(옵션)를 권장한다. "
            "low_confidence_skipped 항목은 검토 후 수동 처리 권장."
        ),
    }


def main():
    ap = argparse.ArgumentParser(description="한국 CS 텍스트 PII 결정론 비식별화")
    ap.add_argument("path", nargs="?", help="입력 텍스트 파일(생략 시 stdin)")
    ap.add_argument("--mask-low", action="store_true",
                    help="low confidence(카드 bare 등)도 마스킹(최대 재현율)")
    ap.add_argument("--text-only", action="store_true",
                    help="리포트 JSON 대신 비식별 텍스트만 출력")
    args = ap.parse_args()

    if args.path:
        if not os.path.exists(args.path):
            sys.exit(f"파일 없음: {args.path}")
        with open(args.path, encoding="utf-8") as fh:
            text = fh.read()
    else:
        text = sys.stdin.read()

    report = redact_text(text, mask_low=args.mask_low)
    if args.text_only:
        sys.stdout.write(report["redacted_text"])
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
