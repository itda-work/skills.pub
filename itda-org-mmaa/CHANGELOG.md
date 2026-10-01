# Changelog — itda-org-mmaa

## [0.2.0] - 2026-10-01

> 요구: **itda-hyve 0.10.4 이상**(mmaa-welfare 재수집). itda-hyve 0.10.4 를 먼저 설치·업데이트한 뒤 이 판을 설치한다 — 0.10.3 이하는 응답 `final_url` 등에 시크릿이 되비치고 기본 User-Agent 에 제품명이 실린다.

### BREAKING

- `mmaa-welfare` 0.4.0 — **재수집은 itda-hyve, `collect.py` 는 판독만** (itda-work/skills#46, 규칙 `cowork-network-via-hyve`). `plan` → itda-hyve `batch` → `collect` 바퀴를 돌고, 계획한 페이지가 전부 와야 스냅샷을 쓴다(부분본 금지). 동봉 스냅샷으로 답하는 Q&A 는 그대로다.

### Changed

- README 사전 준비 절의 "여러 스킬이 같은 키를 쓰면 작업 폴더 `.env` 한 곳에 두면 된다" 안내를 고쳤다 — 스킬은 어떤 env 파일도 읽지 않는다(itda-work/skills#45).

### Fixed

- **SKILL_DIR 확정 블록**(itda-work/skills#47) — 새 Cowork 배치(`/root/.claude/plugins/synced/…`, `CLAUDE_PLUGIN_ROOT` 없음)에서 빈 값을 내던 옛 블록을 바꿨다. 스킬을 불러올 때 받은 base directory 를 먼저 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾으며, 후보가 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다(PowerShell 블록도 같은 계약). `mmaa-welfare`.

## [0.1.2] - 2026-09-27

### Changed

- 외부로 나가는 User-Agent 에서 우리 신원(저장소 URL·조직·스킬 이름)을 뺐다(outbound-identity-leak) — `mmaa-welfare` 0.3.2 — 수집 UA 끝의 `itda-skills-mmaa-welfare` 제거.

## [0.1.1] - 2026-09-25

### Changed

- `mmaa-welfare` 0.3.1 — 라이브 확인 브라우저 후보를 hyve `web_browse` 에서 aside 브라우저로 (itda-work/itda-hyve#6).

## [0.1.0] - 2026-09-05

- **팩 신설 (#1648 2단계)** — 군인공제회 구성원에게만 의미 있는 복지포털 Q&A. 조직 전용 팩 규칙(`itda-org-*`)의 첫 사례.
- 포함 스킬: mmaa-welfare.
