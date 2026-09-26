# Changelog — itda-harness/harness

## [1.3.1] — 2026-07-26 (이슈 #1280·#1283)

### Changed
- `compatibility` 라벨 "Designed for Claude Cowork" → **"Claude Code & Cowork"**.
- Phase 2-1 실행 모드 표 앞에 **플랫폼 분기 경고** 신설 — 팀(`SendMessage`·`TaskCreate`)·`run_in_background` 는 Claude Code 전용이며, Cowork 대상 하네스는 스타형 오케스트레이션·파일 릴레이·명시 디스패치를 기본값으로 함(cowork-agent-orchestration 독트린, #1130).

## [1.3.0] — 2026-07-12

### Changed
- **팀 API 현행화 (#946)** — 구 팀 API(TeamCreate/TeamDelete) 서술을 현행 Claude Code 팀 모델로 전면 재작성 (SKILL.md + references/orchestrator-template·agent-design-patterns·team-examples 약 20곳). upstream(revfactory/harness) 동기 상태에서의 의도적 로컬 분기:
  - 팀 구성: `TeamCreate(members)` → **`Agent(name)` 병렬 스폰 + 세션 단일 암묵 팀** (팀 생성·해체 절차 소멸). Agent 도구의 `team_name` 파라미터는 "Deprecated; ignored".
  - Phase 간 팀 재구성: `TeamDelete` 후 재생성 → **완료 확인 후 새 팀원 스폰**. 완료된 팀원 이름은 계속 유효 — `SendMessage` 전송 시 transcript 에서 컨텍스트 유지 재개(실측: SendMessage 스키마).
  - `SendMessage({to: "all"})` 브로드캐스트 제거 — 현행 스키마는 개별 수신자만 지원(실측).
  - "세션당 1팀 활성" 제약·"유휴 알림" 서술 폐기 → 백그라운드 팀원 **완료 알림** 모델로 교체.
- **모델 정책 상속 전환** — "모든 에이전트 `model: opus` 필수" → **세션 모델 상속 기본, 필요 시에만 명시 상향** (#945 하네스 자산 방침과 정합).
- **Workflow 도구 반영** — 모드 선택 가이드에 결정론적 오케스트레이션(Workflow 스크립트 — 대량 fan-out·resume·budget) 안내 추가. 사용자 명시 옵트인 전제·미지원 환경(Cowork) 제외 명시.

## [1.2.0] — 2026-06-02

### Synced
- **revfactory/harness 원본 동기화** — upstream `main` @ `b8fb858` (2026-05-30) 기준 SKILL.md 본문 + references 4종(agent-design-patterns·orchestrator-template·skill-writing-guide·team-examples) 전체 교체. upstream 1.0.x → 1.2.x 내용 도입:
  - **Phase 0 현황 감사** — 신규구축/기존확장/운영·유지보수 3분기 라우팅
  - **Phase 3-0 / 4-0 중복 검토** — 생성 전 재사용 검토 (upstream Unreleased 반영)
  - **Phase 7 진화 + Phase 7-5 운영/유지보수** — 실행 후 피드백 반영·감사·동기화
  - **하이브리드 실행 모드** · **CLAUDE.md 포인터 등록**(핵심 원칙 2→4개)
- **description을 upstream 최신 트리거로 교체** — 운영/유지보수 트리거("점검"·"감사"·"현황"·"동기화") 포함. itda description 정책 v3.0 준수(큰따옴표 한국어 트리거 ≥3 + folded scalar)로 형식 조정해 공개 배포 게이트(`publish.py`)를 통과 — upstream 트리거 내용은 100% 보존.
- frontmatter는 itda 정합 형식 유지 (metadata.version/updated_at — CI `check-versions` 요건).

## [1.0.2] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [1.0.1] — 2026-05-21

### Improvements
- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.
