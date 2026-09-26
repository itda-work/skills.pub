---
name: time-audit
description: >
  캘린더 실적(완료한 일정)을 모아 카테고리·난이도별 소요 시간, 주별 추이, 병목 후보를
  결정론 스크립트로 집계하는 업무 시간 감사 스킬입니다. "내 시간 어디에 쓰는지 분석해줘",
  "업무 시간 매핑해줘", "시간 감사 해줘", "지난달 캘린더로 업무 분석해줘", "뭐가 오래
  걸리는지 봐줘"처럼 말하면 됩니다. Google Calendar 등 사용자 MCP 커넥터·itda-work
  calendar 스킬·내보내기 파일 어느 소스든 정규화해 받고, 리포트의 모든 수치는 스크립트
  산출만 인용합니다(어림 금지). work-map.md 가 있으면 그 태스크를 카테고리로 씁니다.
license: Apache-2.0
compatibility: Claude Cowork & Code, Python 3.10+
user-invocable: true
argument-hint: "[기간(기본 최근 4주) 또는 캘린더 소스 지정]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.1.3"
  category: "productivity"
  status: "experimental"
  created_at: "2026-07-24"
  updated_at: "2026-07-26"
  aliases: "시간감사, 업무시간매핑, 시간분석, 하루용량"
  tags: "Cowork, time audit, time mapping, calendar analytics, workload, capacity, bottleneck, work map"
---

# time-audit — 내 시간이 어디로 가는지 실측하기

## 이 스킬이 푸는 문제

> "하루 용량이 100인데 120이 와도 그냥 받는다. 뭐가 오래 걸리는지 몰라 업무를 개선할
> 시간을 못 내고, 난이도를 몰라 뭘 AI에 맡길지도 못 나눈다."

감이 아니라 캘린더 실적으로 답합니다: 어떤 업무에 몇 시간을 쓰는가, 난이도(상/중/하)별
분포는 어떤가, 어떤 업무가 건당 가장 오래 걸리는가(병목 후보). 이 실측이
`work-redesign` 4분면 배치의 근거가 됩니다.

**수치 규율(핵심)**: 리포트에 적는 모든 수치는 `scripts/aggregate_time.py` 출력에서만
인용합니다. 에이전트가 시간을 암산·어림하지 않습니다.

## 발동하지 않는 경우

- 일정 조회·추가·수정 자체가 목적이면 → `itda-work:calendar` (이 스킬은 분석 전용, 캘린더에 쓰지 않음)
- 업무를 4분면으로 나누고 위임 계획을 세우려면 → `work-redesign` (이 스킬은 그 근거 공급)
- 조직·팀 단위 리소스 분석은 범위 밖(개인 단위만)

## 절차

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/time-audit}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/time-audit' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```
```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\time-audit"  # 미설정이면 SKILL.md 위치 절대경로 사용
```


### 0. 기간·소스 결정

기간 기본값은 **최근 4주**(사용자 지정 시 그 기간). 소스는 환경에서 가용한 것을 확인해
사용자에게 고르게 합니다:

1. **사용자 캘린더 MCP 커넥터** — Google Calendar 등 사용자가 연결해 둔 커넥터가 있으면
   그 도구로 기간 내 이벤트를 조회합니다(도구가 deferred 면 ToolSearch 로 로드).
2. **itda-work:calendar 스킬** — iCloud·네이버·커스텀 CalDAV:
   ```bash
   # macOS/Linux (Windows 는 py -3)
   python3 <calendar 스킬 경로>/scripts/list_events.py --provider icloud --from 2026-06-29 --to 2026-07-26 --expand
   ```
3. **내보내기 파일** — 사용자가 준 ICS/CSV 를 읽어 변환.

**캘린더에 실적이 없으면**(일정이 계획뿐이거나 비어 있으면) 분석을 강행하지 않습니다 —
"이번 주부터 완료한 업무를 캘린더에 그대로 기록"하는 운영을 안내하고 종료합니다.
빈약한 데이터로 만든 그럴듯한 리포트가 이 스킬이 막으려는 워크슬롭입니다.

**요청 기간을 다른 기간으로 대체하지 않습니다** — 조회가 0건이면(기간 오타가 의심돼도)
인접 기간을 대신 분석하지 말고, "요청 기간에 실적 0건" 사실과 확인 질문("혹시 ○○○○년을
의도하셨나요?")만 남기고 종료합니다. 대체 분석은 사용자가 기간을 다시 지정한 뒤에만
합니다(#1246 라이브 검증 D1: 2015 요청 → 2025 로 무단 대체·강행 실측 반려). 이 규율은
게이트로도 강제됩니다(#1257) — `period` 는 **사용자가 요청한 기간 그대로** 적어야 하고,
기간 밖 이벤트가 섞이면 집계 스크립트가 전수 나열 후 exit 2 로 거부합니다.

### 1. 정규화 — timelog.json 계약

소스가 무엇이든 에이전트가 아래 스키마로 변환해 작업 폴더에 저장합니다. 집계 스크립트는
이 파일만 소비합니다(Python 이 MCP·CalDAV 를 직접 호출하지 않음):

```json
{
  "period": {"from": "2026-06-29", "to": "2026-07-26"},
  "source": "calendar-mcp | itda-calendar | file",
  "provisional": true,
  "categories": {"보고서 작성": {"difficulty": "상"}},
  "events": [
    {"summary": "월간 보고서 초안", "start": "2026-07-01T09:00:00+09:00",
     "end": "2026-07-01T12:00:00+09:00", "category": "보고서 작성"},
    {"summary": "워크숍", "start": "2026-07-02", "all_day": true, "category": "보고서 작성"},
    {"summary": "점심 약속", "start": "...", "end": "...", "exclude": true}
  ]
}
```

- `period` 는 필수이며 **사용자가 요청한 기간 그대로** — 기간 밖 이벤트 혼입은 게이트가 exit 2 로 거부합니다.
- `provisional` 은 **첫 정규화에서 반드시 true** — 배정·제외·난이도를 사용자가 확인한 뒤에만 false 로 바꿉니다. true 인 동안 스크립트가 리포트에 잠정 마커를 강제 각인합니다.
- 종일 일정은 `all_day: true` — 건수만 집계되고 시간 합산에서 빠집니다(시간을 지어내지 않음).
- 업무가 아닌 일정은 지우지 말고 `exclude: true` — 제외 내역도 리포트에 남습니다.

### 2. 매핑 인터뷰 (짐작 금지)

- **카테고리 후보**: `work-map.md` 가 있으면 그 태스크 인벤토리를 후보로 제시합니다(핵심
  시너지 — 지도와 같은 축으로 실측). 없으면 이벤트 제목을 훑어 후보를 만들되 사용자
  확인을 받습니다.
- 이벤트→카테고리 배정과 업무 아님(`exclude`) 판정은 **사용자와 함께** 합니다. 애매한
  이벤트를 에이전트가 임의 배정하지 않습니다 — 모르면 미배정으로 두고 게이트가
  표면화하게 둡니다.
- **애매하면 `exclude` 가 아니라 미배정**으로 둡니다. `exclude` 는 확실한 비업무(가족·
  개인 용무)만 — 애매한 것을 제외로 빼면 미배정 WARN(>20%)이 못 봅니다(#1246 D2:
  타인 캘린더로 추정된 업무 유사 이벤트 14건을 임의 제외해 WARN 을 우회한 실측).
- **첫 실행의 배정·제외안은 사용자 확인 전까지 잠정**입니다: 확인 질문(카테고리 후보·
  제외 후보·애매 건)을 남기고, timelog.json 에 `"provisional": true` 를 유지합니다 —
  스크립트가 리포트에 잠정 마커를 각인하므로 확정처럼 보일 수 없습니다(#1257). 확정
  리포트는 사용자 답을 반영해 provisional 을 false 로 바꾼 뒤에 씁니다.
- **난이도**는 카테고리 단위로 상/중/하를 사용자가 정합니다(자기보고). 에이전트가
  임시로라도 배정하지 않습니다 — 모르면 미지정으로 두고 물어봅니다.

### 3. 결정론 집계

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/aggregate_time.py" timelog.json          # 마크다운 리포트
python3 "$SKILL_DIR/scripts/aggregate_time.py" timelog.json --json   # 기계 판독
# Windows
py -3 "$env:SKILL_DIR\scripts\aggregate_time.py" timelog.json
```

- 스키마 위반(필드 누락·end<=start·잘못된 난이도·미등록 카테고리·**period 누락·기간 밖
  이벤트**)은 **전부 나열하고 exit 2** — 조용히 건너뛰고 집계하지 않습니다.
- WARN: 미배정 시간 비율 >20%(→ 2단계로 되돌아가 배정 보완), **제외 시간 비율 >30%**
  (exclude 남용 신호 — 애매한 건 미배정으로 되돌릴 것), 겹치는 이벤트(기록 신뢰도 신호).
- `provisional: true` 면 사람용 리포트 머리와 `--json` 출력에 잠정 마커가 강제로 박힙니다 —
  이 상태의 수치를 확정처럼 인용하지 않습니다.

### 4. 리포트 — time-audit.md

스크립트 출력을 골격으로 `time-audit.md` 를 작성합니다. 수치는 출력 그대로, 에이전트는
**해석만** 덧붙입니다(예: "상 난이도가 주 7h — 이 구간이 증강 1순위 후보"). 해석과 수치를
섞어 쓰지 않고, 해석 문장에는 근거 수치를 병기합니다. 스크립트 출력 수치에서 파생한
산술(비율·카테고리 내 부분합)은 **근거 수치를 병기할 때만** 허용합니다
(예: "78% (25.0h/32.0h)") — 병기 없는 파생 수치는 어림과 구분되지 않습니다.

### 5. work-map 연계 (있을 때만)

`work-map.md` 가 있으면 갱신을 **제안**합니다 — 4분면 항목에 실측 주석(예: "주 7h 실측"),
시간 최다·병목 후보의 분면 재검토. **수정은 사용자 확인 후에만** 반영합니다.

### 6. 반복 운영

지도(work-map)가 분기 단위라면 시간 감사는 주·월 단위입니다. 월 1회 재실행을 권하고,
기간이 겹치지 않게 지난 실행의 `period` 를 이어받습니다(timelog.json 은 실행별 스냅샷).

## 한계

- 캘린더에 없는 시간(기록 안 한 업무·틈새 작업)은 보이지 않습니다 — 커버리지는 기록
  습관에 비례하며, 이 스킬은 그 습관을 만드는 온보딩을 겸합니다.
- 난이도는 자기보고입니다. 실측은 시간뿐이고 난이도 축은 사용자 판단입니다.
- 캘린더 쓰기(일정 생성·수정)는 하지 않습니다 — 조회 전용.

## 파일 구조

```
time-audit/
├── SKILL.md
├── GUIDE.md
├── CHANGELOG.md
├── scripts/
│   └── aggregate_time.py     # 결정론 집계 (스키마 검증 + WARN)
└── tests/
    ├── conftest.py
    ├── test_aggregate_time.py
    └── fixtures/
        ├── good_timelog.json  # 손계산 기대값 대조용
        └── bad_timelog.json   # 스키마 오류 4종
```
