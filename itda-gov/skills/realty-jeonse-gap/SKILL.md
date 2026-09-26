---
name: realty-jeonse-gap
description: >
  매매와 전월세 실거래를 단지·전용면적 기준으로 조인해 전세가율과 갭 투자 후보를 스크리닝하는 스킬입니다.
  "강남구 아파트 전세가율 80% 넘는 단지 찾아줘", "분당 연립다세대 갭 3천만 이하 목록 뽑아줘", "전세가율 임계값 스크리닝 해줘"처럼 말하면 됩니다.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork"
user-invocable: true
allowed-tools: Bash, Read, Write, mcp__workspace__bash
argument-hint: "지역명 + 기간 + 필터 (예: 강남구 2026년 1~6월 전세가율 80% 이상)"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.9.8"
  category: "domain"
  status: "active"
  created_at: "2026-05-15"
  updated_at: "2026-07-26"
  tags: "jeonse, gap, screener, realestate"
---

# realty-jeonse-gap

매매와 전월세 실거래가를 **단지·전용면적 기준으로 조인**하여 전세가율과 갭을 산출합니다.
커뮤니티 최상위 페인포인트(전세가율 시계열, 갭투자 스크리닝)를 해소하는 스킬입니다.

## 환경 변수

| Variable | Service | Guide |
|---|---|---|
| `KO_DATA_API_KEY` | 공공데이터포털 ([data.go.kr](https://www.data.go.kr)) | 공공데이터포털 가입 후 아파트 매매/전월세 서비스 개별 활용신청.<br>아파트 매매: https://www.data.go.kr/data/15126469/openapi.do<br>아파트 전월세: https://www.data.go.kr/data/15126474/openapi.do |

**권장 (비개발자 포함 모든 사용자) — 작업 폴더 `.env`에 키 등록:** 작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트, 연결한 폴더가 여러 개면 아무 폴더나) 루트에 `.env` 파일을 만들고 `KO_DATA_API_KEY=발급받은_키` 한 줄을 넣어 두면 스킬이 자동으로 찾아 읽습니다. 파일명 별칭 `.env.txt`·`env.txt`·`환경변수.txt` 도 동일하게 탐색된다. 셸 환경변수나 `~/.claude/settings.json` 의 `env` 로 설정해도 되며(로더가 자동 탐색), `.env` 가 없으면 그 값을 사용합니다.

> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find` 등으로 **사전 점검하지 않는다** — 스크립트가 `.env`·`.env.txt`·`env.txt`·`환경변수.txt` 를 스스로 탐색하므로 **우선 실행**한다(셸 glob·검색 패턴은 별칭을 놓쳐 오탐한다: `.env*`→env.txt 누락, `*env*`→환경변수.txt 누락). 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수가 선언돼 있는 경우 그 값을 환경변수로 전달해 재시도한다 — 예: `KO_DATA_API_KEY=<키> python3 "$SKILL_DIR/scripts/jeonse_gap_cli.py" ...`. 지침에도 없으면 GUIDE의 발급 안내를 제시한다. 수동 확인이 꼭 필요하면 파일명 4종(`.env`·`.env.txt`·`env.txt`·`환경변수.txt`)을 그대로 나열해 확인한다.

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수.txt 의 KO_DATA_API_KEY 를 사용했습니다") — 사용자가 어느 설정파일이 쓰였는지 인지하게 하는 계약이다. 값은 어디에도 표시하지 않는다.

**개발자 (선택) — 환경변수 / `.env`:** 작업 폴더 루트 `.env`에 `KO_DATA_API_KEY=키`, 또는 셸 환경변수도 사용할 수 있습니다.

## 계산 방식

- **전세가율** = 전세보증금 / 매매가 × 100 (%)
- **갭** = 매매가 − 전세보증금 (만원)
- 동일 단지·면적에 전세 복수 건 → 최고 전세보증금 기준

## 지원 부동산 유형

| 옵션 | 유형 |
|------|------|
| `apt` | 아파트 (기본) |
| `offi` | 오피스텔 |
| `rh` | 연립다세대 |
| `sh` | 단독다가구 |

## 사전 요구사항

먼저 스킬 디렉토리를 확정합니다 (이후 모든 실행 명령이 `$SKILL_DIR` 기준).

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/realty-jeonse-gap}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/realty-jeonse-gap' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\realty-jeonse-gap"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

## 사용 예시

### 기본 스크리닝

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/jeonse_gap_cli.py" screen \
  --region "강남구" \
  --start-month 202601 \
  --end-month 202606

# Windows
py -3 "$env:SKILL_DIR\scripts\jeonse_gap_cli.py" screen \
  --region "강남구" \
  --start-month 202601 \
  --end-month 202606
```

### 전세가율 필터 적용

```bash
python3 "$SKILL_DIR/scripts/jeonse_gap_cli.py" screen \
  --region "분당구" \
  --start-month 202601 \
  --end-month 202606 \
  --min-jeonse-ratio 80
```

### 갭 최댓값 필터

```bash
python3 "$SKILL_DIR/scripts/jeonse_gap_cli.py" screen \
  --region "마포구" \
  --start-month 202601 \
  --end-month 202606 \
  --max-gap 30000
```

### 복합 필터 (전세가율 ≥ 80% AND 갭 ≤ 2억)

```bash
python3 "$SKILL_DIR/scripts/jeonse_gap_cli.py" screen \
  --region "강남구" \
  --start-month 202601 \
  --end-month 202606 \
  --min-jeonse-ratio 80 \
  --max-gap 20000
```

### 테이블 출력

```bash
python3 "$SKILL_DIR/scripts/jeonse_gap_cli.py" --format table screen \
  --region "강남구" \
  --start-month 202601 \
  --end-month 202601
```

## 출력 형식 (JSON)

```json
{
  "status": "ok",
  "region": "강남구",
  "count": 12,
  "results": [
    {
      "apt_nm": "래미안퍼스티지",
      "exclu_use_ar": "84.00",
      "deal_amount": 155000,
      "deposit": 120000,
      "jeonse_ratio": 77.42,
      "gap": 35000,
      "deal_year": "2026",
      "deal_month": "01"
    }
  ],
  "filters": {
    "min_jeonse_ratio": 75.0
  }
}
```

## 에러 코드

| 상황 | status | error | 조치 |
|------|--------|-------|------|
| API 키 미설정 | error | config | `.env`(작업 폴더 루트)에 `KO_DATA_API_KEY=키` 넣기(권장) — 스킬이 자동 탐색. "Claude 지침"도 동작하나 컨텍스트에 노출. 개발자는 셸 환경변수도 가능 |
| 알 수 없는 지역명 | error | args | --lawd-cd로 직접 지정 |
| API 서비스 오류 | error | api | 활용신청 승인 상태 점검 |

## 테스트 실행

```bash
# macOS/Linux
python3 -m pytest itda-gov/skills/realty-jeonse-gap/tests/ -v

# Windows
py -3 -m pytest itda-gov/skills/realty-jeonse-gap/tests/ -v
```
