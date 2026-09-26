# Changelog — itda-exchange-rate

## [0.10.7] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash, mcp__workspace__web_fetch) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.10.6] — 2026-07-26 (이슈 #1280·#1283)

### Changed

- `compatibility` 라벨을 `Claude Code & Cowork` 로 교체 (#1280).
- `allowed-tools` 를 공백 구분에서 쉼표 구분으로 교정 (#1283) — `Read, WebFetch, Bash(python3:*), Bash(date:*)`. 공백 구분은 도구명 매칭에 실패해 Bash·WebFetch 가 조용히 소실될 수 있었다.

## [0.10.5] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.10.4] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.10.3] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.

## [0.10.2] — 2026-05-13

### Improvements

- **GUIDE.md 일반 사용자 문서 정책 준수**: 활용 시나리오 섹션에 노출된 `python3 scripts/exchange_rate.py --month ... --currency ...` CLI 예시 블록 2개(총 3건)를 제거. 그 위의 자연어 호출 예시("2025년 1월 한 달간 달러 환율을 일별로 보여줘", "이번 달 엔화 평균과 지난달 엔화 평균을 비교해줘")만 남겨 사용자 시점 일관성 확보. 일반 사용자용 문서에 CLI 명령 노출 금지 정책 준수.
