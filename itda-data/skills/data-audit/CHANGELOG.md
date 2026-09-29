# Changelog — itda-data/data-audit

이 파일 이전의 이력은 팩 `itda-data/CHANGELOG.md` 에 있다.

## [0.4.0] — 2026-09-28 (itda-work/skills#30)

### Fixed

- **희소 시트 폭주** — 로더가 `ws.max_row × max_column` 전체를 `iter_rows` 로 돌며 빈 칸마다 Cell 을 만들었다.
  먼 칸에 서식 하나만 남은 시트(200000행×300열)에서 90초 넘게 멈췄다(1만×100 = 6.6초·447MB 실측).
  이제 파일에 실제로 있는 칸만 읽는다(같은 파일 0.02초). `SheetView.max_row/max_col` 은 값이 있는 범위다.
- **거꾸로 적힌 병합**(`B1:A1`) — openpyxl 이 워크북 전체를 못 열어 트레이스백으로 끝났다. 그 병합만 빼고 읽는다.
- **거대한 병합** — `D5:Z100000`(230만 칸) 하나로 여는 데만 21.6초·653MB. 병합 하나 1만 칸·시트 합계 20만 칸을 넘으면 빼고 읽는다.

### Added

- `scripts/xlsx_guard.py` — openpyxl 보다 먼저 시트 XML 의 병합 목록을 읽어 위 두 경우를 뺀 임시 사본으로 연다(원본 불변).
  겹친 병합과 **병합에 가려진 값**(openpyxl 이 조용히 버림)도 센다. 한 일은 전부 category `입력` · Warning 발견으로 싣는다.
- 회귀 테스트 `tests/test_input_guard.py` — 희소 시트·병합 4종·date1904(파일이 1904 체계인지까지 확인)·부동소수 잔차·원본 불변.
