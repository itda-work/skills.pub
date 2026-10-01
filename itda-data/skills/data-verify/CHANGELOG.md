# Changelog — itda-data/data-verify

이 파일 이전의 이력은 팩 `itda-data/CHANGELOG.md` 에 있다.

## [0.4.1] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.4.0] — 2026-09-28 (itda-work/skills#30)

### Fixed

- **희소 시트 폭주** — `ws.iter_rows()` 가 서식만 남은 먼 칸까지 빈 칸마다 Cell 을 만들어, 서식 하나(200000행×300열)로
  90초 넘게 멈췄다(2만×100 = 2.9초·439MB 실측). grid 는 이제 값이 있는 범위까지만 만들고 빈 행은 한 리스트를 함께 가리킨다.
- **거꾸로 적힌 병합**·**거대한 병합** — data-audit 과 같은 `xlsx_guard` 로 빼고 읽는다(원본 불변).

### Added

- `scripts/xlsx_guard.py`(data-audit 과 바이트 동일 — 테스트가 확인) · `loader.load_sheets_with_notes`.
  가드가 한 일(뺀 병합·겹친 병합·가려진 값)은 종류 `입력` · Warning 발견으로 싣는다 — CLI exit 1.
- 회귀 테스트 `tests/test_input_guard.py` — 희소 시트·빈 행 좌표·병합·date1904·부동소수 잔차(표기 0.3 과 0.30000000000000004 둘 다).
