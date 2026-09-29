# Changelog — itda-data/data-prep

이 파일 이전의 이력은 팩 `itda-data/CHANGELOG.md` 에 있다.

## [0.2.3] — 2026-09-28 (itda-work/skills#30)

### Fixed

- **엑셀 원본 입력의 오도 에러** — `.xlsx`·`.xls` 를 주면 cp949 로 풀려다 "CSV 인코딩 판별 실패"로 끝나 원인을 가렸다.
  `loader.read_grid` 가 첫 바이트(zip·OLE)로 엑셀을 알아보고 `ExcelInputError`("CSV UTF-8 로 저장해 달라")를 낸다.
  확장자가 `.csv` 여도 내용이 엑셀이면 막는다.

### Changed

- description 정정 — "엉망인 CSV·엑셀" 이 엑셀 원본을 읽는 것처럼 읽혔다. 실제 입력은 CSV·TSV 이고 GUIDE 는 이미 그렇게
  적고 있었다. xlsx 읽기를 들이지 않은 이유: 이 스킬은 stdlib 전용(설치 불요)이고 짝 스킬 `data-ask` 도 CSV 전용이다.
- SKILL_DIR 블록에 단일 `.skill` 업로드 경로(`.claude/skills`) 탐색 추가.
