# Changelog — itda-data-analysis/xlsx-recalc

## [0.1.0] — 2026-09-14 (이슈 #1690)

### Added

- 스킬 신설. openpyxl 등이 만든 캐시값 없는 xlsx 를 **LibreOffice 단독**으로 재계산해 새 파일로 쓴다.
  - 계산 전: 외부 링크 참조의 링크 값 캐시 확인(없으면 exit 8) · AF_UNIX 소켓 선감지(exit 7) · LibreOffice 24.8 이상 확인(exit 6).
  - 계산: 실행마다 격리 프로필 + OOXML 재계산 모드 "항상", timeout 시 프로세스 그룹·프로필 경로/URI 기준 잔존 정리 후 exit 4.
  - 계산 후: 타입별 캐시 판정(빈 숫자 `<v></v>` 는 캐시 없음) · 입력 수식 보존 · 외부 링크 파트 보존(exit 5) ·
    LibreOffice 재직렬화 셀을 `formula_rewritten` 으로 보고(값이 바뀔 수 있는 변화는 위험 표시).
- 계산 전 exit 9: Strict Open XML · 데이터 테이블(LibreOffice 가 Excel 에 없는 `TABLE()` 로 바꿈) 거부.
- 외부 링크: 정의된 이름(시트 범위·유니코드·체인)·값 유효성·범위 연속·OFFSET/INDIRECT 를 검사하고, 산출에서 종류·대상 경로·시트
  이름을 대조한다. LibreOffice 가 표기만 바꾼 절대 경로는 같은 위치일 때만 원문으로 되돌린다(`external_link_targets_restored`).
- 입력은 같은 폴더의 다른 이름(`book.input`)으로 둔다 — 폴더가 다르면 상대 링크가 깨지고, 같은 이름이면 저장 실패인데 exit 0 이다.
- 링크 파트 없이 파일 이름으로 쓴 외부 참조(openpyxl 이 `'[other.xlsx]Sheet1'!A1` 을 그대로 저장한 모양)를 계산 전에 exit 8 로 거부한다 — `[숫자]` 표기만 보던 검사를 통과해 LibreOffice 를 돌린 뒤 exit 5("외부 링크가 보존되지 않았다")로 끝나던 것을 Cowork 실측으로 확인했다. 이 모양은 오류 문구도 따로 쓴다("0 을 성공으로 쓴다"는 링크 파트가 있는 경우의 실측이다).
- 사전 준비의 `SKILL_DIR` 탐색이 Cowork 단일 `.skill` 업로드 위치(`/sessions/<id>/mnt/.claude/skills/`)도 찾는다 — 플러그인 경로(`.remote-plugins`)만 찾아 설치본을 놓치던 것을 Cowork 실측으로 확인했다.
- 대체 엔진 7종 비교에서 조용한 오답이 0 인 엔진이 없어 1차 계산 엔진은 두지 않는다. 개발 중의 excelize 1차 경로는 릴리즈 전에 제거했다.
