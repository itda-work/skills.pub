# Changelog — itda-data/data-prep

이 파일 이전의 이력은 팩 `itda-data/CHANGELOG.md` 에 있다.

## [0.2.4] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.2.3] — 2026-09-28 (itda-work/skills#30)

### Fixed

- **엑셀 원본 입력의 오도 에러** — `.xlsx`·`.xls` 를 주면 cp949 로 풀려다 "CSV 인코딩 판별 실패"로 끝나 원인을 가렸다.
  `loader.read_grid` 가 첫 바이트(zip·OLE)로 엑셀을 알아보고 `ExcelInputError`("CSV UTF-8 로 저장해 달라")를 낸다.
  확장자가 `.csv` 여도 내용이 엑셀이면 막는다.

### Changed

- description 정정 — "엉망인 CSV·엑셀" 이 엑셀 원본을 읽는 것처럼 읽혔다. 실제 입력은 CSV·TSV 이고 GUIDE 는 이미 그렇게
  적고 있었다. xlsx 읽기를 들이지 않은 이유: 이 스킬은 stdlib 전용(설치 불요)이고 짝 스킬 `data-ask` 도 CSV 전용이다.
- SKILL_DIR 블록에 단일 `.skill` 업로드 경로(`.claude/skills`) 탐색 추가.
