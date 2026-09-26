"""hwpxfill — HWPX 양식 채우기 코어 (표준 라이브러리 전용, python-hwpx·lxml 비의존).

정본 진입점은 `scripts/fill_hwpx.py` 이며 이 패키지를 import 한다.

모듈:
- scan  : section XML 을 정규식 토크나이저로 훑어 문단·run·<hp:t>·표 셀 위치 레지스트리를 만든다(DOM 재직렬화 없음).
- fold  : 비교용 정규화(NFC + 혼동문자 접기 + 공백·PUA 제거).
- fill  : 문단 단위 매칭·splice, 셀/라벨/체크박스 채움, 위생(linesegarray 제거).
- check : --check 분류(ok/fixable/ctrl/multi/missing), --fix, --residue.
- cli   : argparse 진입점.
"""
