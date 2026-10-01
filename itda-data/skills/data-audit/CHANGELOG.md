# Changelog — itda-data/data-audit

이 파일 이전의 이력은 팩 `itda-data/CHANGELOG.md` 에 있다.

## [0.4.1] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

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
