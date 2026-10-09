# Changelog — itda-work/draft-post

## [1.2.9] — 2026-10-06 (itda-work/skills#46 W17)

### Changed

- 형제 지목에서 `itda-doc:blog-seo` 를 뺐다 — 그 스킬이 itda-hyve 검색광고 서명 기능(itda-work/itda-hyve#34)까지 배포 보류라 공개 사용자는 설치할 수 없다(itda-work/skills#46 W17, 사용자 결정 2026-10-06). 보류가 풀리면 되돌린다. 「이 스킬을 쓰지 않을 때」 표 한 줄과 권장 체인의 맨 앞을 지웠다.
- (W17 리뷰 m6) `references/product-brief.md` 도입 사례 예시 문장의 「itda-blog-seo로 블루키워드를 분석한 뒤」 를 스킬 이름 없는 문장으로 바꿨다.

## [1.2.8] — 2026-09-27

### Changed

- "쓰지 않을 때" 표의 조판 행에서 제거된 디자인 스킬(Word·PPT 생성) 지목을 빼고 `itda-doc:hwpx`·`itda-doc:html-report` 로 안내(2026-09-27).

## [1.2.6] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [1.2.5] — 2026-07-26 (이슈 #1280)

### Changed

- `compatibility` 라벨을 `Claude Code & Cowork` 로 교체 (#1280) — Cowork 전용 오해 제거.

## [1.2.4] — 2026-07-26 (이슈 #1277)

### Fixed

- Step 0 환경 감지 역전 교정 — "값이 없으면 Cowork" 판정이 Claude Code(변수 부재)를 Cowork 로 오분류하던 결함. "=1 이면 Cowork / 부재·그 외는 Claude Code" 로 정정하고 결과 표에 Claude Code 행 추가.

## [1.2.3] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [1.2.2] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.
