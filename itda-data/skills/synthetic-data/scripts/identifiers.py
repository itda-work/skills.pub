#!/usr/bin/env python3
"""공통 식별자 가짜 생성기 — 도메인 무관 (stdlib only).

계약(#1647):
- 이름: 가상 성명. 동명이인을 dup_ratio 만큼 **의도적으로** 삽입한다(재식별 게임·biz-redact 실습 재료).
- 주민등록번호: 형식은 맞고 **검증자리를 일부러 틀리게** 만든다 — 실존 번호와 충돌할 수 없다.
- 연락처: 010-0000-XXXX — 전기통신번호관리세칙상 이동전화는 010-ABYY-YYYY(A=2~9)라 부여될 수 없는 형식 밖 대역이다.
- 주소: 실재하지 않는 가상 지명(가상시·가상구·예시동…).
난수는 호출자가 넘기는 random.Random 만 쓴다(결정론 — 같은 seed 면 같은 산출).
"""
from __future__ import annotations

import datetime as _dt
import random

SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "류", "전"]
GIVEN_A = ["서", "지", "민", "하", "예", "도", "은", "수", "정", "현", "영", "재", "태", "준", "유", "채", "다", "소", "성", "경"]
GIVEN_B = ["준", "윤", "우", "연", "린", "아", "빈", "호", "율", "희", "진", "환", "영", "석", "원", "미", "주", "람", "훈", "혜"]
FAKE_DONG = ["예시", "모형", "가상", "표본", "연습", "시험", "견본", "임시"]


def person_name(rng: random.Random) -> str:
    return rng.choice(SURNAMES) + rng.choice(GIVEN_A) + rng.choice(GIVEN_B)


def person_names(rng: random.Random, n: int, dup_ratio: float = 0.06) -> list[str]:
    """n 개의 가상 성명. dup_ratio(0~1) 비율만큼 앞선 이름을 그대로 복사해 동명이인을 만든다.
    n>=2 이고 dup_ratio>0 이면 최소 1쌍은 반드시 만든다(테스트 가능한 계약)."""
    names = [person_name(rng) for _ in range(n)]
    if n >= 2 and dup_ratio > 0:
        k = max(1, int(round(n * dup_ratio)))
        idx = rng.sample(range(1, n), min(k, n - 1))
        for i in idx:
            names[i] = names[rng.randrange(0, i)]
    return names


def rrn_check_digit(first12: str) -> int:
    weights = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]
    s = sum(int(c) * w for c, w in zip(first12, weights))
    return (11 - (s % 11)) % 10


def rrn(rng: random.Random, birth: _dt.date | None = None, gender: str | None = None) -> str:
    """검증자리를 고의로 틀린 주민등록번호. 형식 YYMMDD-GNNNNNC."""
    if birth is None:
        birth = _dt.date(1930, 1, 1) + _dt.timedelta(days=rng.randrange(0, 365 * 40))
    g = gender or rng.choice(["남", "여"])
    if birth.year >= 2000:
        gd = "3" if g == "남" else "4"
    else:
        gd = "1" if g == "남" else "2"
    body = birth.strftime("%y%m%d") + gd + f"{rng.randrange(0, 100000):05d}"
    wrong = (rrn_check_digit(body) + 1 + rng.randrange(0, 9)) % 10  # 정답과 절대 같지 않다
    return f"{body[:6]}-{body[6:]}{wrong}"


def rrn_is_valid(value: str) -> bool:
    digits = value.replace("-", "")
    if len(digits) != 13 or not digits.isdigit():
        return False
    return rrn_check_digit(digits[:12]) == int(digits[12])


def phone(rng: random.Random) -> str:
    return f"010-0000-{rng.randrange(0, 10000):04d}"


def address(rng: random.Random) -> str:
    return f"가상시 가상구 {rng.choice(FAKE_DONG)}동 {rng.randrange(1, 300)}-{rng.randrange(1, 40)}"


def code(rng: random.Random, pattern: str) -> str:
    """'#'→숫자, 'A'→대문자, 그 외 문자는 그대로. 예: 'L##########', 'P-####'."""
    out = []
    for ch in pattern:
        if ch == "#":
            out.append(str(rng.randrange(0, 10)))
        elif ch == "A":
            out.append(chr(ord("A") + rng.randrange(0, 26)))
        else:
            out.append(ch)
    return "".join(out)
