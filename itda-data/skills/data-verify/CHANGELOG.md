# Changelog — itda-data/data-verify

이 파일 이전의 이력은 팩 `itda-data/CHANGELOG.md` 에 있다.

## [0.4.0] — 2026-09-28 (itda-work/skills#30)

### Fixed

- **희소 시트 폭주** — `ws.iter_rows()` 가 서식만 남은 먼 칸까지 빈 칸마다 Cell 을 만들어, 서식 하나(200000행×300열)로
  90초 넘게 멈췄다(2만×100 = 2.9초·439MB 실측). grid 는 이제 값이 있는 범위까지만 만들고 빈 행은 한 리스트를 함께 가리킨다.
- **거꾸로 적힌 병합**·**거대한 병합** — data-audit 과 같은 `xlsx_guard` 로 빼고 읽는다(원본 불변).

### Added

- `scripts/xlsx_guard.py`(data-audit 과 바이트 동일 — 테스트가 확인) · `loader.load_sheets_with_notes`.
  가드가 한 일(뺀 병합·겹친 병합·가려진 값)은 종류 `입력` · Warning 발견으로 싣는다 — CLI exit 1.
- 회귀 테스트 `tests/test_input_guard.py` — 희소 시트·빈 행 좌표·병합·date1904·부동소수 잔차(표기 0.3 과 0.30000000000000004 둘 다).
