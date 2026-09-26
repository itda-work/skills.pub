#!/usr/bin/env python3
"""HWPX 양식 채우기 (표준 라이브러리 전용) — 정본 진입점. 구현은 `hwpxfill/` 패키지.

기존 .hwpx 양식의 서식·구조를 그대로 두고 본문 텍스트 placeholder 를 값으로 치환하고, 빈 셀을 채운다.
Contents/section*.xml 을 문자열 splice 로만 고친다(DOM 재직렬화 없음).

사용:
  # 0) 문단 전수 조사 — 번호·위치(본문/표i r c)·플래그(OK/CTRL/EMPTY)·텍스트. 마지막 탭 뒤 전체가 키.
  python3 fill_hwpx.py 양식.hwpx --dump

  # 1) 후보 placeholder 나열 (괄호·{{}}·《》 마커 휴리스틱)
  python3 fill_hwpx.py 양식.hwpx --list

  # 2) 사전검증 — 키마다 ok / fixable(교정안) / ctrl(컨트롤 분절) / multi(문단 합침) / missing. 문제 있으면 exit 2
  python3 fill_hwpx.py 양식.hwpx --check --map m.json [--fix m.fixed.json] [--json]

  # 3) 채우기 (문단 단위 매칭: run 분절·charPr 차이 무관, fwSpace 는 공백으로 정규화, tab·lineBreak 를 가로지르는 키는 매칭 안 됨)
  python3 fill_hwpx.py 양식.hwpx -o 결과.hwpx --set "(부서명)=내부감사팀" --map m.json
  #    빈 셀: --cell "표0 r2 c1=값"  라벨 옆/아래 빈 셀: --label "성명=홍길동"  체크박스: --tick "해당"
  #    순차 치환: 같은 키를 --set 으로 반복하거나 --map 값을 배열로. 위생 옵트인: --strip-lineseg --refresh-preview

  # 4) 사후 대조 — 원본 안내문이 결과에 남았는지. 남으면 exit 2 (의도한 고정 문구는 --keep)
  python3 fill_hwpx.py 결과.hwpx --residue 양식.hwpx --map m.json [--keep "법정 문구"] [--json]

원칙:
- 무성 실패 금지: 치환 0회 키·값 없이 남은 순차 자리·미발견 체크박스는 반드시 경고(--strict 면 exit 3).
- 값은 첫 run 의 서식을 따르고, 값 안의 글자는 다시 치환되지 않는다.
- 치환 전후 <hp:t>·fwSpace 를 제외한 태그 시퀀스 동일을 자기검사한다. mimetype 은 첫 엔트리·STORED 보존.
- 치환 후 각 section XML 의 well-formedness 를 검사한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hwpxfill.cli import build_parser, main  # noqa: E402
from hwpxfill.fill import apply_edits, fill_texts, FillReport  # noqa: E402,F401
from hwpxfill.scan import scan_section, xml_escape  # noqa: E402,F401

__all__ = ["main", "build_parser", "scan_section", "fill_texts", "apply_edits", "FillReport", "xml_escape"]

if __name__ == "__main__":
    sys.exit(main())
