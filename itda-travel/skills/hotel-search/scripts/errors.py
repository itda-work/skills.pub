#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""errors.py - exit code 및 예외 정의 (coupang 컨벤션과 동일)."""
from __future__ import annotations

EXIT_OK = 0
EXIT_GENERAL = 1      # 네트워크/파싱 실패
EXIT_ARGS = 2         # 인자 오류 (필수 누락·잘못된 값)
EXIT_NO_RESULT = 3    # 결과 없음 (호텔 매칭 0건 등)
EXIT_BLOCKED = 4      # anti-bot 차단 (403 / Access Denied / CAPTCHA)


class HotelSearchError(Exception):
    """스킬 공통 예외. code 로 exit code 를 전달한다."""

    def __init__(self, message: str, code: int = EXIT_GENERAL) -> None:
        super().__init__(message)
        self.code = code


class BlockedError(HotelSearchError):
    def __init__(self, message: str = "봇 차단(403/CAPTCHA) — 세션을 재워밍업하거나 잠시 후 재시도하세요") -> None:
        super().__init__(message, EXIT_BLOCKED)


class NoResultError(HotelSearchError):
    def __init__(self, message: str = "결과 없음") -> None:
        super().__init__(message, EXIT_NO_RESULT)


class ArgsError(HotelSearchError):
    def __init__(self, message: str = "인자 오류") -> None:
        super().__init__(message, EXIT_ARGS)
