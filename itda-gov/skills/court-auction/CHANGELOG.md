# Changelog — court-auction

이 스킬의 주요 변경 사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)를 따릅니다.

## [0.1.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.1.2] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.1.1] — 2026-06-21

### Fixed

- 라이브 조회(`codes courts` 등)의 warmup GET이 일시적 네트워크/타임아웃(예: 해외 CI 러너→KR 사이트 지연)에 단발 실패하던 문제를 backoff 재시도로 보강 (#492). transient(`URLError`/`TimeoutError`)만 재시도하고 `HTTPError`(서버 응답)는 즉시 반환하며, warmup은 호출 budget을 차감하지 않는다(기본 1회 재시도). 지속 장애는 종전대로 실패해 외부 점검을 유도한다.

## [0.1.0] — 2026-06-05

### Added

- 신규 스킬: 대법원 법원경매정보(courtauction.go.kr) 부동산 매각공고·사건·물건 **read-only 조회**.
- 5개 서브커맨드:
  - `codes` — 법원사무소코드(동적 조회) · 입찰구분 · 용도 · 지역(시도) 코드표.
  - `notices` — 매각공고 목록(월 단위 조회 + 일자 로컬 필터).
  - `notice-detail` — 공고 펼치기(사건번호·용도·주소·감정평가액·최저매각가).
  - `case` — 사건번호 직접 조회(진행상태·기일별 결과·이해관계인).
  - `search` — 물건 자유 조건검색(지역·용도·가격·감정가·면적·유찰횟수).
- WebSquare XHR 어댑터: warmup 세션 쿠키, 호출 간 2초 throttle, 세션 10회 budget,
  `ipcheck=false` 즉시 중단(자동 재시도 없음). 자격증명 불필요(표준 라이브러리만).
- 응답 정규화: raw 한국어/약어 키 → 영문 키, HTML·금액·일자·시각 파싱.
- 정직 고지: 참고용·입찰 전 법원 원문 재확인·IP 차단 위험·공고 시점 기준.

### Notes

- NomaDamas k-skill `court-auction-notice-search`의 컨셉·엔드포인트를 참조해 itda 스타일로
  Python 재작성했습니다. SPEC-COURT-AUCTION-001 (itda-skills/hyve#101).
- 라이브 검증(2026-06-05): codes(60 법원)·notices(서울중앙 5건)·search(서울 건물 2602건) 정상.
  Workflow C 자유검색이 raw HTTP+warmup 쿠키로 작동해 Playwright 폴백은 불필요(미구현).
