---
name: fuel-price
description: >
  오피넷(한국석유공사) 주유소 평균 유가 조회 스킬입니다. 전국·시도(16개) × 일간/주간/월간 평균가와 전기 대비 등락,
  과거 특정 시점(--end) 조회를 제공합니다. "오늘 기름값 얼마야", "서울 휘발유 가격", "이달 전국 경유 월평균",
  "지난 7월 인천 휘발유 평균", "최근 두 달 휘발유 추세"처럼 말하면 됩니다. API 키 없이 동작합니다.
  [책임 경계] 본 스킬은 평균 유가 조회 전담 — 주유소 위치·최저가 검색, 유류비 정산 단가·공지문 생성은 하지 않고,
  환율은 itda-work:exchange-rate 가 맡습니다.
license: Apache-2.0
compatibility: Claude Code & Cowork
user-invocable: true
argument-hint: "[지역] [제품] [--term day|week|month] [--end YYYY-MM(-DD)] [--format json|table]"
allowed-tools: Read, Bash(python3:*), mcp__workspace__bash
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.3.0"
  created_at: "2026-09-02"
  updated_at: "2026-09-02"
  tags: "fuel-price, opinet, gasoline, diesel, oil-price, korea, keyless"
---

# Fuel Price (오피넷 평균 유가 조회)

오피넷 **평균 판매가격**(부가세 포함, 원/리터)을 조회합니다 — 전국·시도 × 일간/주간/월간, 전기 대비 등락, 과거 시점.
**조회 전용**입니다: 유류비 정산 단가 계산·공지문 생성은 범위 밖이며(간단한 산식이라 회사 규정대로 소비자가 적용),
주유소 단위 검색도 하지 않습니다.

## Instructions for Claude

### Step 1: Determine the Skill Directory

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/fuel-price}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/fuel-price' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

### Step 2: Parse the Request

`$ARGUMENTS` 와 사용자 발화에서 아래를 뽑는다. 없으면 기본값.

| 축 | 인자 | 기본값 | 예 |
|---|---|---|---|
| 지역 | `--region` | `전국` | 아래 **지원 지역 16개**(시도 단위). 시군구·개별 주유소는 비지원 |
| 제품 | `--product` | `휘발유` | 휘발유·고급휘발유·경유(디젤)·등유 (LPG 비지원 — 평균판매가격 화면 4제품) |
| 기간 단위 | `--term` | `month` | `day`(일간) · `week`(주간) · `month`(월간) |
| 기간 수 | `--periods` | `3` | 전기 대비 계산용 — 추세를 보려면 6~12 |
| 종료 시점 | `--end` | 최신 | 특정 시점 조회 — 일간 `YYYY-MM-DD`, 주간·월간 `YYYY-MM` (예: "7월 평균" → `--term month --end 2026-07`). 오피넷 최신 시점 이후는 거부 |
| 출력 | `--format` | `json` | `json`(기본, compact — 필드+`summary`·`detail_table` 문자열 동봉) / `table`(사람용 텍스트) |

- "오늘·어제·현재 기름값"이면 `--term day`(오피넷은 전일까지 확정 통계 — "오늘" 값은 새벽에 갱신된 **전일자**가 최신이다. 출력의 기간 라벨이 기준일이니 그대로 보여준다).
- "월평균·이달 평균"이면 `--term month`, "추세"면 `--term week --periods 8`.
- 지난 특정 날/달을 물으면 `--end`. 두 시점 비교("6월 대비 8월")는 `--end 2026-08 --periods 3`.
- **유류비 단가·공지문을 요구받으면**: 조회 결과(기준가)를 주고, 단가는 회사 규정 산식(예: 기준가 ÷ 연비 × 보정계수)으로
  에이전트가 대화에서 계산해 준다 — 스킬 스크립트의 몫이 아니다. 연비 등 규정값은 사용자에게 묻고 지어내지 않는다.

**지원 지역(`--region`, 시도 16개 — 오피넷 지역별 화면 코드 순)**: 서울 · 부산 · 대구 · 인천 · 전남광주 · 대전 · 울산 · 경기 · 강원 · 충북 · 충남 · 전북 · 경북 · 경남 · 제주 · 세종.
"광주"·"전남"·"광주광역시"·"전라남도"는 모두 **전남광주**(2026-07-01 통합 — 오피넷이 통합특별시 통계로 제공)로 해석된다. "경기도"·"인천광역시" 같은 정식 명칭·약칭 모두 허용. 목록 밖(시군구·"수도권" 등)은 오류로 거부하며 지원 목록을 함께 안내한다.

### Step 3: Run

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/fuel_price.py" [--region 인천] [--product 경유] [--term month] [--periods 3] \
    [--end 2026-07] [--format json|table]

# Windows
py -3 "$env:SKILL_DIR\scripts\fuel_price.py" --region 서울 --product 휘발유 --term day
```

Windows 에서 `SKILL_DIR` 확정: `$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\fuel-price"` (미설정이면 SKILL.md 위치 절대경로).
표준 라이브러리만 쓰므로 추가 설치가 없다(Python 3.10+).

예:
- `python3 "$SKILL_DIR/scripts/fuel_price.py"` — 전국 휘발유 월간 3개월 (compact JSON)
- `python3 "$SKILL_DIR/scripts/fuel_price.py" --region 서울 --term day --periods 7` — 서울 최근 7일
- `python3 "$SKILL_DIR/scripts/fuel_price.py" --term month --end 2026-07 --region 부산` — 지난 7월 부산 월평균
- `python3 "$SKILL_DIR/scripts/fuel_price.py" --term day --source api` — `OPINET_API_KEY` 가 있을 때만

### Step 4: Display

기본 출력은 **compact JSON**(itda-gov 팩 관례) — 필드(`series`·`latest_price`…)와 함께 표시용 완성 문자열
`summary`·`detail_table`·`source_note` 가 동봉된다. 사용자에게 보여줄 때는 **`summary`(+필요 시 `detail_table`)
문자열을 그대로** 쓰고 숫자를 다시 타이핑하지 않는다(전사 오류 방지). 후속 계산(단가·비교)은 JSON 필드로 한다.
`source_note`(출처)는 항상 함께 표시한다. 사람이 직접 읽을 원문이 필요하면 `--format table`.

### Error Handling

stderr 의 한국어 오류를 그대로 전달한다. 대표 케이스:

| 메시지 | 뜻 | 대응 |
|---|---|---|
| `숨김 필드 미발견` / `가격 표(tbl_type10)를 찾지 못했습니다` | 오피넷 화면 구조 변경 | 결함 신고 — 추측 수정 금지 |
| `기간 행이 없습니다` | 조회 기간에 통계 없음 | `--term`·`--periods` 조정 |
| `오피넷 API 가 빈 결과` | 키 누락·오류(오피넷은 에러 대신 빈 배열을 준다) | `OPINET_API_KEY` 확인 또는 `--source web` |
| `주간·월간 평균이 없습니다` / `최근 7일만 제공합니다` | API 경로는 최근 7일 일별만 | `--source web` |
| `까지만 있습니다` | `--end` 가 오피넷 최신 확정 시점 이후 | 종료 시점을 앞당기거나 `--end` 생략 |
| `알 수 없는 지역` | 시도 16개 밖(시군구·권역명) | 위 지원 지역 목록에서 고른다 |

## 데이터 경로와 지원 범위 (실측 2026-09-02)

**API 키가 없어도 아래 "웹 통계" 열 전부가 된다** — 현재(최신 일간) 시세, 시도 16곳, 과거 임의 시점(`--end`), 일/주/월 시계열.
키는 `--source api` 를 **명시**했을 때만 쓰이며, 제공 범위가 웹 경로보다 **좁다**(최근 7일 일별만).

| 축 | 웹 통계 (기본, 키 불요) | Open API (`--source api`, `OPINET_API_KEY`) |
|---|---|---|
| 현재(최신) 시세 | ✅ `--term day` 최신 확정일(전일) | ✅ 최근 7일 중 최신 |
| 지역 | ✅ 전국 + 시도 16 | ✅ 전국 + 시도(`areaAvgRecentPrice`) |
| 날짜별(일간) 시계열 | ✅ 최신에서 N일, 또는 `--end` 로 과거 임의 날짜 | ⚠️ 최근 7일만, 과거 지정 불가 |
| 주간 평균 | ✅ | ❌ (`avgLastWeek` 는 최근 1주만 — 미채택) |
| 월간 평균 | ✅ **정본** | ❌ 없음 |
| 과거 시점(`--end`) | ✅ 1997년~ (화면 지원 범위) | ❌ |
| 시군구·개별 주유소 | ❌ 비목표 | ❌ 비목표(API 는 있으나 스킬 범위 밖) |

| 경로 | 구현 | 비고 |
|---|---|---|
| **웹 통계** — `국내유가통계 > 주유소 > 평균판매가격` 화면의 폼 POST 를 브라우저와 **바이트 동일**하게 재현 | `scripts/opinet_web.py` | NetFunnel 토큰 불요. 화면 숨김 필드(최신 가용 시점)를 GET 으로 읽어 되돌린다 |
| Open API — `avgRecentPrice` · `areaAvgRecentPrice` (`Opinet_API_Free.pdf` 계약) | `scripts/opinet_api.py` | 키 발급: https://www.opinet.co.kr/user/custapi/custApiInfo.do 하단 「일반 API 이용 신청」(회원가입 → 자동 승인 즉시, 무료). 절차는 GUIDE.md. 키 없음/오류 → 200 + 빈 배열(조용히 빔) → 명시 에러로 표면화 |

- 요청에 우리 식별자·부가 파라미터를 싣지 않는다(`outbound-identity-leak`·`request-profile-first`). payload 골든은
  `tests/test_payload_golden.py`.
- 저작권: 산출물에 항상 **출처 "오피넷(한국석유공사)"** 를 명시한다(오피넷 저작권 정책). 내부 이용은 무방,
  재배포·수익 목적은 공사와 사전 협의 대상.

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 |
|---|---|
| 특정 주유소·최저가·반경 검색 | 오피넷 앱/사이트 직접 (본 스킬 비목표) |
| 유류비 정산 단가·공지문 생성 | 조회 결과 + 회사 규정 산식으로 대화에서 계산 (v0.1.x 의 단가·공지문 기능은 제거됨 — 마스터 결정 2026-09-02) |
| 환율·원자재 시황 | itda-work:exchange-rate · itda-gov:ecos |
| 국제유가(WTI·두바이) | 별도 — 본 스킬은 국내 주유소 판매가만 |

## 부록: Claude Code 확장 (선택)

이 절은 Claude Code 세션에만 적용된다. Cowork 는 본문 절차 그대로 진행한다(부록 미적용이 결함이 아니다).

### 후속 요청 이어가기
"경유도 같이", "인천으로 다시" 같은 후속은 인자만 바꿔 재실행한다 — 응답이 결정론적이라 재조회 비용이 낮다.
