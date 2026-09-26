# Changelog — itda-work/task-brief

## [0.2.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.2.2] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.2.1] — 2026-07-12

### Fixed
- 구조 게이트 공허 통과(vacuous pass) 차단 (#1083, skill-creator 기준 행동 테스트에서 발견).
  검증방법 섹션 부재/공백 시 C3 를 OK 대신 "판정 불가" FAIL 로, 4개 hard 섹션이 전부 빈
  헤딩 없는 생짜 초안은 C5 가 원문 전체를 스캔해 실제 모호어("빠르게" 등)를 지목 + 판정 불가
  FAIL. 섹션이 하나라도 있으면 기존 동작 불변(미배정 서두 인사말 오탐 방지). 회귀 3건 추가.

### Changed
- description 에 위임 계열 트리거 보강 — "브리프" 무언급 요청("이 작업 맡기기/위임하기 전
  정리")의 undertrigger 완화.

## [0.2.0] — 2026-07-12

### Added
- clarify(사용자 전역 Socratic questioning 커맨드) 노하우 선별 이식 (#1080). 인터뷰 규율 4종:
  ① 질문 전 컨텍스트 탐색(Glob/Grep/Read 로 추천 기본값을 실측 근거화) ② 답변 누적 참조
  (각 질문은 이전 답 위에 쌓기) ③ 불완전 답 심화 프로빙(넘어가기 전 파고들기·구체 예시 요구)
  ④ 마무리 상호확인("이 브리프가 의도를 담았습니까?" 후 제시).
- **의도(선택) 섹션** — 브리프 최상단 "왜 이 작업인가" 한 줄. hard 검사(C1~C5) 제외 맥락 산문.
  게이트 파서에 INTENT 섹션 키워드 추가(내용이 인접 hard 섹션으로 새는 bleed 방지) + 회귀 4건.
- frontmatter `allowed-tools` 에 Glob·Grep·AskUserQuestion 추가(추천 기본값 수락/수정 UX).

### Notes
- 비이식 결정: clarify 의 Background/Problem 앞단 인터뷰 레이어는 경량 정체성(30초~2분)과
  충돌해 제외 — SPEC 급 핸드오프 경계 유지. Non-goals·Constraints·모드 분기·한 질문 규율은
  기존 보유(일부는 기계 게이트로 더 강함)로 이식 불요 판정.

## [0.1.0] — 2026-07-12

### Added
- 초안 (#1051). 모호한 일상 요청을 에이전트에 던지기 전 3요소(작업 범위·검증 방법·완료 정의)를
  채운 브리프 한 장으로 다듬는 스킬. 채점/인터뷰 2모드.
- `scripts/check_task_brief.py` — 구조 게이트 C1~C5(+W1/W2 경고). 핵심 축은 **검증 자기보고 금지**
  (`SELF_REPORT_TERMS`) — 받는 쪽이 재현 가능한 명령·파일·수치인지로 판정. Windows cp949 stdout
  utf-8 재구성.
- `tests/` — AC-1(5샘플 3요소 비어있지 않음)·AC-2(축별 결손 지적) 회귀 13건.
- `fixtures/good_brief.md`(통과)·`bad_brief.md`(실패).

### Notes
- goal-spec(자율 루프 목표 조건) 동형 경량 계층. `.claude/skills/`(프로젝트 운영)에서 착안했으나
  마스터 지시로 itda-work published 스킬로 관리(skills.pub 배포 대상).
- 외부 기준 교차검증 1회(`skill-creator`): description 트리거 정본화·near-miss 상호배타·imperative·
  why 우선 반영.
