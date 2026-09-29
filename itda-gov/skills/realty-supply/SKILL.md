---
name: realty-supply
description: >
  KOSIS 주택 공급 지표(미분양·인허가·착공·준공·입주)와 청약홈 청약 통계를 수집하는 스킬입니다.
  "올해 강남구 아파트 미분양 추이 보여줘", "2024년 전국 인허가·착공·준공 통계 가져와줘", "최근 청약 경쟁률 높은 단지 목록 보여줘"처럼 말하면 됩니다.
  [책임 경계] 본 스킬은 KOSIS 공급 지표·청약 통계 전담 — 개별 실거래 원본은 itda-gov:realty-deals, 가격지수·파생 통계는 itda-gov:realty-price-stats.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork"
user-invocable: true
allowed-tools: Bash, Read, Write, mcp__workspace__bash
argument-hint: "지표 종류 + 기간 (예: 미분양 2024년 전국 / 청약경쟁률 2026년 1~6월)"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.9.9"
  category: "domain"
  status: "active"
  created_at: "2026-05-15"
  updated_at: "2026-09-28"
  tags: "KOSIS, supply, subscription, housing"
---

# realty-supply

KOSIS(국가통계포털)와 청약홈 공공데이터를 기반으로 **주택 공급 지표**와 **청약 통계**를 수집합니다.

## 환경 변수

| Variable | Service | Guide |
|---|---|---|
| `KOSIS_API_KEY` | KOSIS 국가통계포털 Open API ([kosis.kr](https://kosis.kr/openapi/)) | KOSIS 회원가입 후 Open API 활용신청.<br>https://kosis.kr/openapi/index/index.jsp |
| `KO_DATA_API_KEY` (선택) | 공공데이터포털 ([data.go.kr](https://www.data.go.kr)) — 청약 서브커맨드 필요 | subscription 서브커맨드 사용 시 필요.<br>청약정보 활용신청: https://www.data.go.kr/data/15056640/openapi.do |

**권장 (비개발자 포함 모든 사용자) — 작업 폴더 `.env`에 키 등록:** 작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트, 연결한 폴더가 여러 개면 아무 폴더나) 루트에 `.env` 파일을 만들고 `KOSIS_API_KEY=발급받은_키` (청약 통계까지 쓰면 `KO_DATA_API_KEY=발급받은_키`도) 한 줄씩 넣어 두면 스킬이 자동으로 찾아 읽습니다. 파일명 별칭 `.env.txt`·`환경변수.txt` 도 동일하게 탐색된다. 셸 환경변수나 `~/.claude/settings.json` 의 `env` 로 설정해도 되며(로더가 자동 탐색), `.env` 가 없으면 그 값을 사용합니다.

> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find` 등으로 **사전 점검하지 않는다** — 스크립트가 `.env`·`.env.txt`·`환경변수.txt` 를 스스로 탐색하므로 **우선 실행**한다(셸 glob·검색 패턴은 별칭을 놓쳐 오탐한다: `.env*`·`*env*` 는 `환경변수.txt` 를, `*.env` 는 `.env.txt` 를 놓친다). 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수가 선언돼 있는 경우 그 값을 환경변수로 전달해 재시도한다 — 예: `KOSIS_API_KEY=<키> python3 "$SKILL_DIR/scripts/supply_cli.py" ...`. 지침에도 없으면 GUIDE의 발급 안내를 제시한다. 수동 확인이 꼭 필요하면 파일명 3종(`.env`·`.env.txt`·`환경변수.txt`)을 그대로 나열해 확인한다.

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수.txt 의 KOSIS_API_KEY 를 사용했습니다") — 사용자가 어느 설정파일이 쓰였는지 인지하게 하는 계약이다. 값은 어디에도 표시하지 않는다.

**개발자 (선택) — 환경변수 / `.env`:** 작업 폴더 루트 `.env`에 `KOSIS_API_KEY=키`·`KO_DATA_API_KEY=키`, 또는 셸 환경변수도 사용할 수 있습니다.

## 주의사항

청약경쟁률 데이터는 **2020년 2월(202002)부터** 제공됩니다.
그 이전 구간은 보간 없이 처리됩니다 (R18 — 인위적 데이터 생성 금지).

## 지원 KOSIS 지표

| 키 | 지표 |
|----|------|
| `unsold` | 미분양 |
| `permitted` | 인허가 |
| `started` | 착공 |
| `completed` | 준공 |

## 사전 요구사항

먼저 스킬 디렉토리를 확정합니다 (이후 모든 실행 명령이 `$SKILL_DIR` 기준).

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/realty-supply}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/realty-supply' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\realty-supply"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

## 사용 예시

### KOSIS 미분양 timeseries 수집

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/supply_cli.py" kosis \
  --indicator unsold \
  --start-month 202401 \
  --end-month 202412

# Windows
py -3 "$env:SKILL_DIR\scripts\supply_cli.py" kosis \
  --indicator unsold \
  --start-month 202401 \
  --end-month 202412
```

### KOSIS 인허가 수집

```bash
python3 "$SKILL_DIR/scripts/supply_cli.py" kosis \
  --indicator permitted \
  --start-month 202601 \
  --end-month 202606
```

### 청약홈 경쟁률·분양 수집

```bash
python3 "$SKILL_DIR/scripts/supply_cli.py" subscription \
  --start-month 202601 \
  --end-month 202606
```

## 출력 형식 (JSON)

```json
{
  "status": "ok",
  "count": 6,
  "results": [
    {"indicator": "unsold", "period": "202601", "value": 1500},
    {"indicator": "unsold", "period": "202602", "value": 1420}
  ],
  "meta": {
    "subscription_data_start": "202002"
  }
}
```

## 에러 코드

| 상황 | status | error | 조치 |
|------|--------|-------|------|
| KOSIS API 키 미설정 | error | config | `.env`(작업 폴더 루트)에 `KOSIS_API_KEY=키` 넣기(권장) — 스킬이 자동 탐색. "Claude 지침"도 동작하나 컨텍스트에 노출. 개발자는 셸 환경변수도 가능 |
| data.go.kr 키 미설정 (subscription) | error | config | `.env`(작업 폴더 루트)에 `KO_DATA_API_KEY=키` 넣기(권장) — 스킬이 자동 탐색. "Claude 지침"도 동작하나 컨텍스트에 노출. 개발자는 셸 환경변수도 가능 |
| API 서비스 오류 | error | api | 활용신청 승인 상태 점검 |

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 실거래 개별 건 원본(매매·전월세) | itda-gov:realty-deals |
| 가격지수·전월세전환율·평균/중위 통계 | itda-gov:realty-price-stats |
| 전세가율·갭 스크리닝 | itda-gov:realty-jeonse-gap |
| 법원 경매 물건 | itda-gov:court-auction |

## 테스트 실행

```bash
# macOS/Linux
python3 -m pytest itda-gov/skills/realty-supply/tests/ -v

# Windows
py -3 -m pytest itda-gov/skills/realty-supply/tests/ -v
```
