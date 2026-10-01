# Changelog — stakeholder-map

## [0.1.5] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.1.4] — 2026-07-28 (이슈 #1319)

### Changed

- itda-workmap → itda-coach 팩 이동 (workmap 팩 소멸, 여정 코칭 팩 재편). 스킬 이름·계약 불변.

## [0.1.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.1.2] — 2026-07-26 (이슈 #1279)

### Changed
- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## 0.1.1 (2026-07-24)

- 라이브 검증 (#1246, S3·S5): 모호어("알아서"·"이쁘게") 반려 실측 PASS — 문서 기입 0건, 구조 재편+구체 입력 재질문. work-redesign 스텁 이어받기·협업 순서 생성·게이트 exit 0. 트리거 매칭 정답
- D3 수정: 게이트에 C4 미확정 마커 검사 추가(hard) — "❗확인 필요"·"미정"·"TBD" 류 플레이스홀더 값이 C2/C3 을 통과하는 우회 실측을 차단. "모르면 그 줄을 지워서 FAIL 로 표면화" 계약 복원(회귀 테스트 동반)

## 0.1.0 (2026-07-24)

- 최초 릴리즈 (#1245)
- 관계자별 인터뷰(역할·요청·받을 것·선행 전달물·소통) + 협업 순서(project-context.md)
- 구조 게이트 `scripts/check_stakeholder.py`(다중 파일): C1 필수 섹션 · C2 선행 전달물 ≥2건 `키: 값` 제약 구조 · C3 모호어 반려("알아서"·"잘 부탁"), 경고 W1 받을 것 · W2 기한 · W3 채널+주기 · W4 제목 역할 병기
- work-redesign stakeholders 스텁 정합(같은 섹션 어휘로 파싱, 스텁은 게이트 FAIL = 심화 신호)
- 개념 출처: 퇴근길 AI "AI에게 의존하고 계시지는 않으신가요?" (2026-07-23) 트레이닝 2
