---
name: realty-price-stats
description: >
  한국부동산원 R-ONE 가격지수·전월세전환율과 realty-deals raw 데이터 기반 파생 통계를 제공하는 스킬입니다.
  "강남구 아파트 주간 가격지수 6개월치 가져와줘", "분당구 최근 3개월 평균·중위 매매가 통계 보여줘", "전월세전환율 추이 조회해줘"처럼 말하면 됩니다.
  [책임 경계] 본 스킬은 R-ONE 가격지수와 파생 통계 전담 — 실거래 원본 행 수집은 itda-gov:realty-deals(derive 의 입력), 공급·청약 지표는 itda-gov:realty-supply.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork"
user-invocable: true
allowed-tools: Bash, Read, Write, mcp__workspace__bash
argument-hint: "지수 유형 + 기간 (예: 주간 가격지수 2026년 1~6월 / 강남구 아파트 매매 통계 2026년 1월)"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.9.9"
  category: "domain"
  status: "active"
  created_at: "2026-05-15"
  updated_at: "2026-09-01"
  tags: "R-ONE, price index, statistics, realestate, reb"
---

# realty-price-stats

한국부동산원 **R-ONE** 가격지수·전월세전환율과 `realty-deals` raw 데이터 기반 **파생 통계**를 제공합니다.

## 환경 변수

| Variable | Service | Guide |
|---|---|---|
| `RONE_API_KEY` | 한국부동산원 R-ONE Open API ([reb.or.kr](https://www.reb.or.kr/r-one/openapi/)) | 한국부동산원 R-ONE 회원가입 후 Open API 활용신청.<br>https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do |
| `KO_DATA_API_KEY` (선택) | 공공데이터포털 ([data.go.kr](https://www.data.go.kr)) — derive 서브커맨드 필요 | derive 서브커맨드로 실거래가 파생 통계 산출 시 필요.<br>realty-deals 스킬과 동일한 키 사용. |

**권장 (비개발자 포함 모든 사용자) — 작업 폴더 `.env`에 키 등록:** 작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트, 연결한 폴더가 여러 개면 아무 폴더나) 루트에 `.env` 파일을 만들고 `RONE_API_KEY=발급받은_키` (derive 통계까지 쓰면 `KO_DATA_API_KEY=발급받은_키`도) 한 줄씩 넣어 두면 스킬이 자동으로 찾아 읽습니다. 파일명 별칭 `.env.txt`·`env.txt`·`환경변수.txt` 도 동일하게 탐색된다. 셸 환경변수나 `~/.claude/settings.json` 의 `env` 로 설정해도 되며(로더가 자동 탐색), `.env` 가 없으면 그 값을 사용합니다.

> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find` 등으로 **사전 점검하지 않는다** — 스크립트가 `.env`·`.env.txt`·`env.txt`·`환경변수.txt` 를 스스로 탐색하므로 **우선 실행**한다(셸 glob·검색 패턴은 별칭을 놓쳐 오탐한다: `.env*`→env.txt 누락, `*env*`→환경변수.txt 누락). 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수가 선언돼 있는 경우 그 값을 환경변수로 전달해 재시도한다 — 예: `RONE_API_KEY=<키> python3 "$SKILL_DIR/scripts/price_stats_cli.py" ...`. 지침에도 없으면 GUIDE의 발급 안내를 제시한다. 수동 확인이 꼭 필요하면 파일명 4종(`.env`·`.env.txt`·`env.txt`·`환경변수.txt`)을 그대로 나열해 확인한다.

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수.txt 의 RONE_API_KEY 를 사용했습니다") — 사용자가 어느 설정파일이 쓰였는지 인지하게 하는 계약이다. 값은 어디에도 표시하지 않는다.

**개발자 (선택) — 환경변수 / `.env`:** 작업 폴더 루트 `.env`에 `RONE_API_KEY=키`·`KO_DATA_API_KEY=키`, 또는 셸 환경변수도 사용할 수 있습니다.

## 주의사항

- KB 데이터허브는 공식 API가 없으므로 스크래핑하지 않습니다 (R21).
  KB 데이터가 필요하면 공식 다운로드 페이지(https://data.kbland.kr)에서 직접 파일을 받아 활용하세요.
- R-ONE API는 한국부동산원 Open API 가입이 필요합니다.

## 지원 R-ONE 지수 유형

| 키 | 지수 |
|----|------|
| `weekly` | 주간 아파트 가격지수 |
| `monthly` | 월간 아파트 가격지수 |
| `jeonse_rate` | 전월세전환율 |

## 사전 요구사항

먼저 스킬 디렉토리를 확정합니다 (이후 모든 실행 명령이 `$SKILL_DIR` 기준).

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/realty-price-stats}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/realty-price-stats' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\realty-price-stats"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

## 사용 예시

### R-ONE 주간 가격지수 수집

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/price_stats_cli.py" rone \
  --index-type weekly \
  --start-month 202601 \
  --end-month 202606

# Windows
py -3 "$env:SKILL_DIR\scripts\price_stats_cli.py" rone \
  --index-type weekly \
  --start-month 202601 \
  --end-month 202606
```

### R-ONE 전월세전환율

```bash
python3 "$SKILL_DIR/scripts/price_stats_cli.py" rone \
  --index-type jeonse_rate \
  --start-month 202601 \
  --end-month 202606
```

### 실거래 파생 통계 (전체)

```bash
python3 "$SKILL_DIR/scripts/price_stats_cli.py" derive \
  --region "강남구" \
  --start-month 202601 \
  --end-month 202601 \
  --type apt_trade
```

### 단지별 파생 통계

```bash
python3 "$SKILL_DIR/scripts/price_stats_cli.py" derive \
  --region "강남구" \
  --start-month 202601 \
  --end-month 202606 \
  --type apt_trade \
  --group-by apt_nm
```

## 출력 형식 (JSON)

### R-ONE 지수

```json
{
  "status": "ok",
  "count": 6,
  "results": [
    {"index_type": "weekly", "period": "202601", "value": 100.5},
    {"index_type": "weekly", "period": "202602", "value": 101.2}
  ]
}
```

### 파생 통계

```json
{
  "status": "ok",
  "count": 0,
  "results": [],
  "derived_summary": {
    "avg": 120000,
    "median": 115000,
    "max": 200000,
    "min": 80000,
    "count": 87
  },
  "region": "강남구"
}
```

## 에러 코드

| 상황 | status | error | 조치 |
|------|--------|-------|------|
| RONE_API_KEY 미설정 | error | config | `.env`(작업 폴더 루트)에 `RONE_API_KEY=키` 넣기(권장) — 스킬이 자동 탐색. "Claude 지침"도 동작하나 컨텍스트에 노출. 개발자는 셸 환경변수도 가능 |
| KO_DATA_API_KEY 미설정 (derive) | error | config | `.env`(작업 폴더 루트)에 `KO_DATA_API_KEY=키` 넣기(권장) — 스킬이 자동 탐색. "Claude 지침"도 동작하나 컨텍스트에 노출. 개발자는 셸 환경변수도 가능 |
| API 서비스 오류 | error | api | 활용신청 승인 상태 점검 |

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 실거래 개별 건 원본(CSV/JSON) | itda-gov:realty-deals |
| 미분양·인허가·청약 | itda-gov:realty-supply |
| 전세가율·갭 | itda-gov:realty-jeonse-gap |
| 스킬팩 전체 안내·키 발급 | itda-gov:realty-meta |

## 테스트 실행

```bash
# macOS/Linux
python3 -m pytest itda-gov/skills/realty-price-stats/tests/ -v

# Windows
py -3 -m pytest itda-gov/skills/realty-price-stats/tests/ -v
```
