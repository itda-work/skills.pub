# Changelog — itda-realty/realty-meta

## [0.11.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **키 안내를 itda-hyve 시크릿 탭 하나로** (itda-work/skills#45) — realty-jeonse-gap·realty-supply·realty-price-stats 도 이제 스크립트가 네트워크를 하지 않고 itda-hyve 가 요청을 보낸다. 셸 환경변수·`claude config set env.<KEY>` 안내, 키 주입·출처 표시 규칙, "itda-hyve 시크릿 경로는 아직 없다" 문구를 지우고 키별로 쓰는 스킬·요청 호스트 표를 뒀다. 청약홈(`api.odcloud.kr`)은 `KO_DATA_API_KEY` 허용 호스트 추가가 필요하다는 안내를 더했다.
- 스킬 표 — realty-supply 의 청약은 경쟁률이 아니라 분양 공고다(realty-supply 0.11.0), realty-price-stats 에 실거래 파생 통계를 적었다.

## [0.10.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **BREAKING — env 파일을 더 읽지 않는다** (itda-work/skills#45, 사용자 결정 2026-09-30). `.env`·`.env.txt` 를 포함해 어떤 env 파일도, `~/.claude/settings.json` 도 realty 스킬 스크립트가 직접 열지 않는다. 키 설정 안내를 스킬별 표로 바꿨다 — realty-deals 의 `KO_DATA_API_KEY` 는 itda-hyve 시크릿 탭(`{{secret:KO_DATA_API_KEY}}`), realty-jeonse-gap·realty-supply·realty-price-stats 의 `KO_DATA_API_KEY`·`KOSIS_API_KEY`·`RONE_API_KEY` 는 Claude Code 셸 환경변수 또는 `claude config set env.<KEY> "키"`(itda-hyve 시크릿 경로 없음). 키 주입 규칙·출처 표시 예시를 맞췄다.

## [0.9.6] — 2026-09-30 (itda-work/skills#45)

### Changed

- **자격증명 파일 별칭에서 `환경변수.txt` 제거** (itda-work/skills#45, BREAKING) — 읽는 파일명은 `.env`·`.env.txt` 두 가지다. `환경변수.txt` 로 키를 두었다면 파일 이름을 `.env.txt`(또는 `.env`)로 바꾼다 — 내용은 그대로 두면 된다. SKILL.md 의 파일명 별칭 안내·키 주입 규칙(파일명 2종·셸 glob 오탐 설명)·출처 표시 예시를 맞췄다.

## [0.9.5] — 2026-09-28 (itda-work/skills#26)

### Changed

- **자격증명 파일 별칭에서 `env.txt` 제거** (itda-work/skills#26) — 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 로 키를 두었다면 `환경변수.txt` 또는 `.env` 로 이름을 바꾼다. SKILL.md 의 파일명 별칭 안내·키 주입 규칙(파일명 3종·셸 glob 오탐 설명)을 맞췄다.

## [0.9.4] — 2026-07-26 (이슈 #1284)

### Fixed

- 색인 정정 — court-auction 행 추가(5스킬 완결) + realty-price-stats 필요 키를 RONE_API_KEY 로 정정.

## [0.9.3] — 2026-07-26 (이슈 #1280·#1282)

### Changed

- compatibility 라벨 "Designed for Claude Cowork" → "Claude Code & Cowork. Python 3.10+".
- `.env` 안내를 "작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트)" 로 교체하고 셸 환경변수·settings.json `env` 경로 병기.

## [0.9.2] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.9.1] — 2026-05-21

### Improvements

- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.
