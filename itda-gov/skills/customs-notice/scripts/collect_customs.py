#!/usr/bin/env python3
"""관세청 공지사항 수집 CLI — itda-hyve 가 받은 파일을 가공한다(네트워크 없음).

    python3 collect_customs.py plan list --run-dir R --save-dir S [--pages N]
    python3 collect_customs.py collect list --run-dir R --next-plan [--limit --keyword --from --to --xlsx]
    python3 collect_customs.py plan attach <번호…> --run-dir R
    python3 collect_customs.py collect attach --run-dir R --next-plan

출력은 stdout JSON 한 줄(``status``: planned·incomplete·ok·partial·blocked·refused·error).
"""
from __future__ import annotations

import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10 이상이 필요합니다")

import board_common
import customs_board

if __name__ == "__main__":
    sys.exit(board_common.main(customs_board))
