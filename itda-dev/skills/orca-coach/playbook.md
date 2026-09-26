# Orca Coach Playbook — 상황 → 기능 매핑

각 행의 "문서" 열은 `orca-guide/docs/` 하위 경로 포인터다(정본은 그쪽 — 여기에 사용법을 복제하지 않는다). 추천 시 이 표에서 진단과 맞는 행 2~3개를 고른다.

## 카테고리 지도 (전체 조망 질문용)

1. **병렬 개발** — worktree, 병렬 에이전트 경쟁, Quick Open 점프
2. **리뷰 루프** — diff 뷰어, AI diff 주석 배치 리뷰, attribution
3. **UI/브라우저** — 워크트리별 브라우저, Design Mode, 프로필
4. **자동화·오케스트레이션** — CLI, automations(cron), orchestration, computer-use
5. **연동** — GitHub/GitLab, Linear, Jira, 커스텀 CLI 에이전트
6. **원격·모바일** — SSH 워크트리, orca serve, 모바일 컴패니언
7. **운영 위생** — 상태 점·알림·Activity 피드, hibernation, 사용량 추적, 세션 복원

## 상황 매핑

### 개발 중

| 상황 신호 | 추천 기능 | 문서 |
|---|---|---|
| 어려운 버그/설계인데 어떤 접근이 맞는지 모름 | 같은 프롬프트로 에이전트 3개 경쟁 → 승자만 남김 | `recipes/parallel-agents.md` |
| 리뷰 중인 PR 브랜치 위에 이어 작업하고 싶음 | worktree start-from을 그 브랜치로 지정 | `model/worktrees.md` |
| 새 worktree마다 `pnpm install`·`.env` 복구를 손으로 함 | worktree 생성 후 셋업 훅 자동 실행 | `agents/hooks-memory.md` |
| 어제 하던 에이전트 대화를 이어받고 싶음 | 세션 히스토리 검색 → 원래 cwd에서 resume | `agents/session-history.md` |
| 긴 작업 전 구독 한도가 남았는지 궁금 | 상태바 사용량 추적(잔여 한도·리셋 시각) | `agents/usage-tracking.md` |
| 주 계정이 한도에 걸림 | 계정 핫스왑 (Claude/Codex, 재로그인 없이) | `agents/codex-hot-swap.md`, `agents/claude-code.md` |
| 에이전트 터미널 하나만 보며 diff·브라우저를 못 봄 | 탭 드래그 중첩 분할 레이아웃 | `model/tabs-panes-splits.md` |

### 리뷰·배포

| 상황 신호 | 추천 기능 | 문서 |
|---|---|---|
| AI가 만든 대형 변경에 지적이 20군데 | diff 라인 인라인 코멘트 → 배치로 한 번에 되돌려 보내기 | `review/annotate-ai-diff.md`, `recipes/review-ai-diff.md` |
| 어느 라인이 AI 산출물인지 구분해 정독하고 싶음 | attribution 거터 마커 | `review/attribution.md` |
| 헝크/라인 단위로 골라 스테이징하고 싶음 | diff 뷰어 (j/k/n/p 키보드 리뷰) | `review/diff-viewer.md` |
| rebase 후 안전하게 강제 푸시해야 함 | commit&push (lease 강제푸시, 실패 시 Fix with AI) | `review/commit-push.md` |
| CI 체크 깨진 PR을 에이전트에 고치게 하고 싶음 | GitHub 연동 — 실패 체크 목록을 그대로 프롬프트로 | `review/github.md` |
| 이슈 트래커(Linear/Jira)에서 바로 작업 시작하고 싶음 | 이슈→worktree 연결(이슈 내 이미지도 컨텍스트로) | `review/linear.md`, `review/jira.md` |

### UI 작업

| 상황 신호 | 추천 기능 | 문서 |
|---|---|---|
| "이 버튼 패딩" 수준의 시각 버그를 말로 설명하기 귀찮음 | Design Mode — 요소 클릭이 HTML·CSS·스크린샷으로 에이전트에 투입 | `browser/design-mode.md`, `recipes/design-mode-fix.md` |
| 반응형/모바일 뷰포트 확인이 필요 | worktree별 내장 브라우저 (뷰포트 에뮬레이션) | `browser/overview.md` |
| 관리자/일반 계정 권한별 버그 재현 | 브라우저 프로필 분리 (쿠키·스토리지 격리) | `browser/profiles.md` |

### 자동화·스케일

| 상황 신호 | 추천 기능 | 문서 |
|---|---|---|
| 매일/매주 반복하는 프롬프트 작업 (트리아지 등) | automations — cron/RRULE 예약 실행 | `cli/automations.md` |
| 에이전트가 다른 터미널의 결과를 기다렸다 이어가야 함 | `orca terminal wait --for tui-idle` 등 CLI 제어 | `cli/overview.md`, `cli/reference.md` |
| 코디네이터가 여러 워커에 작업 분배·집계 | orchestration (메시지·태스크·decision gate) | `cli/orchestration.md` |
| 터미널·브라우저 밖 네이티브 앱을 조작해야 함 | computer-use (접근성 트리 기반) | `cli/computer-use.md` |
| 사내 전용 CLI 에이전트를 1급으로 쓰고 싶음 | 커스텀 CLI 등록 | `agents/custom-cli.md` |

### 원격·이동

| 상황 신호 | 추천 기능 | 문서 |
|---|---|---|
| 노트북 성능 부족 / 절전에도 계속 돌 빌드 필요 | SSH 원격 worktree (실행은 원격, 편집·diff는 로컬) | `ssh.md`, `recipes/remote-worktrees.md` |
| 항상 켜진 서버가 런타임을 소유하고 여러 기기에서 접속 | `orca serve` (베타) | `remote-servers.md` |
| 외출 중 에이전트가 확인 질문에서 멈춰 있음 | 모바일 컴패니언 — 폰으로 "continue" 답장 | `mobile.md` |

### 운영 위생 (worktree가 늘어날 때)

| 상황 신호 | 추천 기능 | 문서 |
|---|---|---|
| worktree 10개+, 어디부터 볼지 모름 | Cmd-J 점프 + 상태 점 + 벨 순회 동선 | `recipes/jump-worktrees.md`, `model/quick-open.md` |
| 몇 시간 비웠다 돌아와 무슨 일이 있었는지 훑고 싶음 | Activity 피드 (완료·차단·응답 프리뷰 스레드) | `activity.md` |
| 방치한 worktree들의 진행 상황을 사이드바에서 파악 | worktree checkpoint (에이전트가 comment 필드 갱신) | `cli/worktree-checkpoints.md` |
| worktree 수십 개로 메모리 압박, 맥락은 유지하고 싶음 | hibernation (유휴 세션 일시정지→자동 resume) | `agents/hibernation.md` |
| 에이전트 여럿 돌려놓고 자리 비울 예정 | working→idle 알림 + 커스텀 사운드 | `notifications.md` |

## Claude Code × Orca 조합 레시피

Orca는 **실행 표면**(워크트리·터미널·이종 에이전트)을, Claude Code는 **세션 내부 능력**(hooks·서브에이전트·세션 간 메시징)을 소유한다는 구분선으로 조합한다.

| 상황 | 조합 | 비고 |
|---|---|---|
| 같은 머신의 다른 CC 세션(다른 워크트리)과 대화 | CC `ListAgents` + `SendMessage` | 경량 메시지·질문. 소유권 이양은 orca-cli handoff |
| Codex/Cursor 등 이종 에이전트가 끼는 협업 | Orca orchestration / `terminal send·wait` | CC SendMessage는 CC 세션끼리만 |
| 작업 완료를 자리 비운 채 알림 받기 | CC Stop hook → `orca` CLI 알림 or 텔레그램 curl | Orca notifications와 이중화 가능 |
| 세션 안 반복 (폴링·감시) | CC `/loop` | 세션 밖 정기 실행은 Orca automations |
| 세션 밖 정기 실행 (야간 리뷰 봇 등) | Orca automation → `claude -p` headless | 결과를 worktree comment로 남기면 checkpoint와 결합 |
| 실험적 리팩토링의 안전망 | Orca worktree(격리) + checkpoint + CC 커밋 단위 작업 | 실패 시 worktree 폐기가 가장 싼 롤백 |
| 다른 워크트리의 빌드/테스트 완료 후 이어 작업 | CC 백그라운드 Bash/`Monitor` + `orca terminal wait` | 어느 쪽이 결과를 소유하는지로 선택 |
| 새 worktree에 이 Orca 버전 맞춤 CLI 지식 주입 | `orca skills get` / `npx skills add` | `cli/skills.md` |

## 유지보수 메모

- 신기능 추가 시: `changelog` 스킬 → orca-guide 문서 동기화 → 이 표에 행 추가 (이 순서여야 포인터가 유효).
- 행 추가 기준: "상황 신호"를 구체적으로 — 기능 이름을 아는 사람용 색인이 아니라, 모르는 사람이 자기 상황으로 찾는 표다.
