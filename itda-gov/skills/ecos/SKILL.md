---
name: ecos
description: >
  한국은행 ECOS API로 거시경제 지표를 조회하는 스킬입니다.
  "GDP 추이 알려줘", "금리 환율 정리해줘", "100대 경제지표 확인해줘"처럼 말하면 됩니다.
  GDP·금리·환율·CPI·100대 핵심 지표 데이터셋을 다룹니다.
license: Apache-2.0
compatibility: "Claude Code & Cowork. Python 3.10+. 네트워크가 막힌 환경은 itda-hyve 0.9.0 이상(로컬 MCP 서버)."
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, Bash, Read, Write, mcp__workspace__bash"
user-invocable: true
argument-hint: "[key|search|word|items|tables] [--stat 통계코드] [--start 시작연도] [--end 종료연도]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  status: "active"
  recommended: true
  version: "0.10.10"
  created_at: "2026-03-29"
  updated_at: "2026-09-27"
  tags: "GDP, ECOS, CPI, economics, interest rate, exchange rate, Bank of Korea"
---

# ecos

한국은행 ECOS(경제통계시스템) API로 거시경제 지표를 수집합니다.
GDP·금리·환율·물가·100대 경제지표 등 정책 보고서와 사업계획서에 필요한 경제 데이터를 제공합니다.

> Python 표준 라이브러리만 사용 — 추가 의존성 없음

## 환경 변수

| Variable | Service | Guide |
|---|---|---|
| `ECOS_API_KEY` | 한국은행 경제통계시스템 ECOS ([링크](https://ecos.bok.or.kr/api/)) | ECOS 회원가입 → 인증키 신청 → **즉시 발급** (가입 시 자동 부여) |

## API 키 설정

| 환경변수 | 발급처 | 승인 방식 |
|---------|-------|----------|
| `ECOS_API_KEY` | https://ecos.bok.or.kr/api/ | 회원가입 → 인증키 신청 → **즉시 발급 (가입 시 자동 부여)** |

**권장 (비개발자 포함 모든 사용자) — 작업 폴더 `.env`에 키 등록:**

작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트, 여러 개면 아무 폴더나) 루트에 `.env` 파일을 만들고 아래 한 줄을 넣어 두면 스킬이 자동으로 찾아 읽습니다. 파일명 별칭 `.env.txt`·`env.txt`·`환경변수.txt` 도 동일하게 탐색된다. 셸 환경변수나 `~/.claude/settings.json` 의 `env` 로 설정해도 되며, 로더가 자동으로 탐색합니다.

```
ECOS_API_KEY=발급받은_키
```

> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find` 등으로 **사전 점검하지 않는다** — 스크립트가 `.env`·`.env.txt`·`env.txt`·`환경변수.txt` 를 스스로 탐색하므로 **우선 실행**한다(셸 glob·검색 패턴은 별칭을 놓쳐 오탐한다: `.env*`→env.txt 누락, `*env*`→환경변수.txt 누락). 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수가 선언돼 있는 경우 그 값을 환경변수로 전달해 재시도한다 — 예: `ECOS_API_KEY=<키> python3 "$SKILL_DIR/scripts/..."`. 지침에도 없으면 GUIDE의 발급 안내를 제시한다. 수동 확인이 꼭 필요하면 파일명 4종(`.env`·`.env.txt`·`env.txt`·`환경변수.txt`)을 그대로 나열해 확인한다.

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수.txt 의 ECOS_API_KEY 를 사용했습니다") — 사용자가 어느 설정파일이 쓰였는지 인지하게 하는 계약이다. 값은 어디에도 표시하지 않는다.

**개발자 (선택) — 환경변수 / `.env`:** 작업 폴더 루트 `.env`에 `ECOS_API_KEY=키`, `claude config set env.ECOS_API_KEY "키"`, 또는 셸 환경변수도 사용할 수 있습니다.

> **네트워크가 막힌 환경(Cowork 샌드박스 등):** **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`)로 대신 호출하고, 규약은 동봉한 `references/netbridge.md`(정본 저장소 루트 `shared/netbridge.md`)를 따른다. API 키 값은 어떤 경우에도 대화로 받지 않는다. 이 스킬의 itda-hyve 전용 절차는 아직 없다 — 스크립트의 가공(정규화·집계)은 이 경로에서 재현되지 않으므로 원 응답임을 밝힌다.
> 키 소스 우선순위: `--api-key` > `os.environ`(Claude 주입 포함) > `~/.claude/settings.json` > `.env`(자동 탐색).

### 첫 호출 실패 시 점검 절차

1. **키 문자열 정확성**: 앞뒤 공백 없는지 확인
2. **URL 인코딩**: 본 스크립트가 자동 처리 (수동 인코딩 불필요)
3. **시간 후 재시도**: 발급 직후 일시적 미반영 가능 — 수 분 대기 후 재시도
4. **권한 오류 (HTTP 403)**: 게이트웨이 단계 거부 → 마이페이지에서 활용 상태 확인

## Prerequisites

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/ecos}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/ecos' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

Windows(PowerShell):

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\ecos"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

## 사용법

### 100대 주요 경제지표 (key)

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/collect_econ.py" key
python3 "$SKILL_DIR/scripts/collect_econ.py" key --format table

# Windows
py -3 "$env:SKILL_DIR\scripts\collect_econ.py" key
```

### 통계 데이터 조회 (search)

```bash
# 소비자물가지수 2020~2024 연간
python3 "$SKILL_DIR/scripts/collect_econ.py" search --stat 901Y009 --start 2020 --end 2024
python3 "$SKILL_DIR/scripts/collect_econ.py" search --stat 901Y009 --start 2020 --end 2024 --format table

# 분기별 실질 GDP (경제활동별, 원계열) — 분기 날짜는 YYYYQn 형식
python3 "$SKILL_DIR/scripts/collect_econ.py" search --stat 200Y106 --start 2020Q1 --end 2024Q4 --period quarter
```

### 경제 용어 정의 (word)

```bash
python3 "$SKILL_DIR/scripts/collect_econ.py" word --word "GDP디플레이터"
python3 "$SKILL_DIR/scripts/collect_econ.py" word --word "기준금리"
```

### 통계표 항목 조회 (items)

```bash
# 항목 코드 확인 (통계 조회 전 사전 확인용) — 소비자물가지수 항목
python3 "$SKILL_DIR/scripts/collect_econ.py" items --stat 901Y009
```

### 전체 통계표 목록 (tables)

```bash
python3 "$SKILL_DIR/scripts/collect_econ.py" tables
```

## CLI 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--stat` | 통계표 코드 (search/items) | — |
| `--start` | 시작 기간 (연도 또는 YYYYQ) | — |
| `--end` | 종료 기간 | — |
| `--period` | `annual` / `quarter` / `month` / `day` | `annual` |
| `--item1` | 1차 항목 코드 | — |
| `--item2` | 2차 항목 코드 | — |
| `--word` | 경제 용어 (word 서브커맨드) | — |
| `--format` | `json` / `table` | `json` |
| `--api-key` | ECOS API 키 (CLI 직접 전달) | 환경변수 |

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 실행 오류 (API 키 미설정, 인증 실패, 데이터 없음) |
| 2 | 인자 오류 |

## 트리거 키워드

GDP, 금리, 환율, 물가, CPI, ECOS, 한국은행, 거시경제, 100대 지표,
경제지표, 소비자물가, 생산자물가, 기준금리, 달러환율,
economics, interest rate, exchange rate, inflation, Bank of Korea

## 파일 구조

```
ecos/
  SKILL.md
  scripts/
    ecos_api.py                       # ECOS API 모듈
    collect_econ.py                   # 경제지표 수집 CLI
    # env_loader.py / itda_path.py 는 이 폴더에 없습니다 —
    # publish 시 shared/ 에서 주입됩니다 (소스: skills/shared/).
  tests/
    test_ecos_api.py                  # ecos_api 단위 테스트 (HTTP mock)
    test_collect_econ_arg_position.py # CLI 인자 위치 회귀 테스트
  references/
    ecos.md                           # ECOS API 상세 가이드
    ecos-매뉴얼/                       # 한국은행 정본 명세 (xls + 발췌 md 6종)
```

## 오류 처리

### 일반 오류

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `ECOS_API_KEY가 설정되지 않았습니다` | API 키 미설정 | `.env`(작업 폴더 루트)에 `ECOS_API_KEY=키` 추가(권장) — 스킬이 자동 탐색. "Claude 지침"도 동작하나 컨텍스트에 노출. 개발자는 셸 환경변수도 가능 |
| `통계표를 찾을 수 없습니다` | 통계표 코드 오류 | `tables` 서브커맨드로 전체 목록 확인 |
| `데이터가 없습니다` | 기간 또는 항목 오류 | `items` 서브커맨드로 항목 코드 확인 |

### 정본 RESULT 코드 (ECOS API 6개 공통)

#### 정보 (INFO) 타입

| 코드 | 의미 | 권장 조치 |
|------|------|----------|
| INFO-100 | 인증키 무효 | 활용신청 URL 확인 |
| INFO-200 | 데이터 없음 | 정상 응답 (결과 0건) |

#### 에러 (ERROR) 타입

| 코드 | 의미 | 권장 조치 |
|------|------|----------|
| ERROR-100 | 필수 값 누락 | 인자 형식 확인 |
| ERROR-101 | 주기/날짜 형식 불일치 | A:2024 / Q:2024Q1 / M:202401 / D:20240101 |
| ERROR-200 | 파일타입 오류 | xml 또는 json 사용 |
| ERROR-300 | 조회건수 누락 | 시작/종료 건수 명시 |
| ERROR-301 | 조회건수 타입 오류 | 정수 입력 |
| ERROR-400 | 검색범위 초과 (60초 TIMEOUT) | 검색 범위를 좁혀 재요청 |
| ERROR-500 | 서버 오류 / 서비스명 오류 | 잠시 후 재시도 |
| ERROR-600 | DB Connection 오류 | 잠시 후 재시도 |
| ERROR-601 | SQL 오류 | 잠시 후 재시도 |
| ERROR-602 | 호출 제한 (과도한 호출) | 백오프 후 재시도 |

> 응답은 XML 또는 JSON으로 `RESULT.CODE` + `RESULT.MESSAGE` 형식. 인증키 무효(INFO-100)는 시스템이 활용신청 URL(`https://ecos.bok.or.kr/api/`)을 자동 부착하며, HTTP 403 게이트웨이 거부도 동일하게 처리됩니다.

## Troubleshooting

### 한글 경로가 인식되지 않을 때

Cowork sandbox 등 일부 환경의 bash는 `LANG`/`LC_ALL` 미설정 시 한글 디렉토리명을 직접 인자로 받지 못합니다.

**증상:** `/sessions/.../mnt/실습-클로드-1기/` 경로에서 `No such file or directory`.

**해결 — 변수 캡처 우회:**

```bash
WORKSPACE=$(ls /sessions/*/mnt/ | grep -v '^lost+found$' | head -1)
WORKSPACE_PATH=$(ls -d /sessions/*/mnt/"$WORKSPACE" 2>/dev/null | head -1)

python3 "$SKILL_DIR/scripts/collect_econ.py" key > "$WORKSPACE_PATH/result.json"
```

> 이 패턴은 스크립트 코드 결함이 아니라 sandbox bash의 locale 설정 문제입니다.
> macOS native bash 및 Windows PowerShell에서는 한글 경로가 정상 동작합니다.

## 상세 API 가이드

`references/ecos-매뉴얼/` 디렉토리에 한국은행 ECOS API 6개 서비스의 정본 명세 (xls + 발췌 md)를 보관합니다.

| API 서비스 | 정본 xls + 발췌 md |
|-----------|------------------|
| StatisticTableList (서비스 통계 목록) | [01-StatisticTableList.md](references/ecos-매뉴얼/01-StatisticTableList.md) |
| StatisticWord (통계용어사전) | [02-StatisticWord.md](references/ecos-매뉴얼/02-StatisticWord.md) |
| StatisticItemList (통계 세부항목 목록) | [03-StatisticItemList.md](references/ecos-매뉴얼/03-StatisticItemList.md) |
| StatisticSearch (통계 조회) | [04-StatisticSearch.md](references/ecos-매뉴얼/04-StatisticSearch.md) |
| KeyStatisticList (100대 통계지표) | [05-KeyStatisticList.md](references/ecos-매뉴얼/05-KeyStatisticList.md) |
| StatisticMeta (통계메타DB) | [06-StatisticMeta.md](references/ecos-매뉴얼/06-StatisticMeta.md) |
| 통합 인덱스 + 공통 에러 코드 | [README.md](references/ecos-매뉴얼/README.md) |

기존 요약본: [references/ecos.md](references/ecos.md)
정본 xls (한국은행 발간): `references/ecos-매뉴얼/API개발명세서_*.xls` (6종)
