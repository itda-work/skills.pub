---
name: dart
description: >
  금융감독원 DART 전자공시 API로 기업 정보를 수집하는 스킬입니다.
  "삼성전자 재무제표 조회해줘", "경쟁사 직원수 알려줘", "사업보고서 비교해줘",
  "네이버 배당 현황", "셀트리온 소송 이력"처럼 말하면 됩니다.
  기업 프로필·재무·인력·사업보고서·공시 목록에 더해 배당·증자·소송·전환사채 등 주요사항도 반환합니다.
license: Apache-2.0
compatibility: "Claude Code & Cowork. Python 3.10+. 네트워크는 itda-hyve 0.9.0 이상(로컬 MCP 서버)."
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, Bash, Read, Write, mcp__workspace__bash"
user-invocable: true
argument-hint: "[search|info|finance|employees|profile|disclosure|business|compare|raw] [--name 회사명] [--corp-code 코드] [--year 연도] [--report annual|q1|q2|q3] [--prefer annual|latest] [--detail] [--unit auto|million|eok|jo] [--with-ratios] [--with-prior] [--endpoint 엔드포인트] [--param key=value] [--format json|table|csv]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  status: "active"
  recommended: true
  version: "0.19.2"
  created_at: "2026-03-29"
  updated_at: "2026-09-28"
  tags: "DART, CSV, company, financial, disclosure, competitor, business report, compare"
---

# dart

금융감독원 DART 전자공시시스템 API로 기업 정보를 수집합니다.
경쟁사 분석, 입찰 제안서, 사업계획서에 필요한 기업 재무·직원 데이터를 제공합니다.

## 환경 변수

| Variable | Service | Guide |
|---|---|---|
| `DART_API_KEY` | 금융감독원 DART ([링크](https://opendart.fss.or.kr)) | 회원가입 → 오픈 API → 인증키 신청/관리 → 40자리 키 즉시 발급<br>형식: `[A-Za-z0-9]{40}` |

## Prerequisites

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/dart}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/dart' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용

# 의존성 설치(defusedxml — XML 보안 파싱) — 정문
python3 "$SKILL_DIR/scripts/install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

Windows(PowerShell):

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\dart"  # 미설정이면 SKILL.md 위치 절대경로 사용
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
```

## API 키 설정

| 환경변수 | 발급처 | 승인 방식 |
|---------|-------|----------|
| `DART_API_KEY` | https://opendart.fss.or.kr | 회원가입 → 오픈API → 인증키 신청/관리 → **즉시 발급** (40자리, 수동 승인 없음) |

**권장 (비개발자 포함 모든 사용자) — 작업 폴더 `.env`에 키 등록:**

작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트, 여러 개면 아무 폴더나) 루트에 `.env` 파일을 만들고 아래 한 줄을 넣어 두면 스킬이 자동으로 찾아 읽습니다. 파일명 별칭 `.env.txt`·`환경변수.txt` 도 동일하게 탐색된다. 셸 환경변수나 `~/.claude/settings.json` 의 `env` 로 설정해도 되며, 로더가 자동으로 탐색합니다.

```
DART_API_KEY=발급받은_키
```

> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find` 등으로 **사전 점검하지 않는다** — 스크립트가 `.env`·`.env.txt`·`환경변수.txt` 를 스스로 탐색하므로 **우선 실행**한다(셸 glob·검색 패턴은 별칭을 놓쳐 오탐한다: `.env*`·`*env*` 는 `환경변수.txt` 를, `*.env` 는 `.env.txt` 를 놓친다). 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수가 선언돼 있는 경우 그 값을 환경변수로 전달해 재시도한다 — 예: `DART_API_KEY=<키> python3 "$SKILL_DIR/scripts/..."`. 지침에도 없으면 GUIDE의 발급 안내를 제시한다. 수동 확인이 꼭 필요하면 파일명 3종(`.env`·`.env.txt`·`환경변수.txt`)을 그대로 나열해 확인한다.

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수.txt 의 DART_API_KEY 를 사용했습니다") — 사용자가 어느 설정파일이 쓰였는지 인지하게 하는 계약이다. 값은 어디에도 표시하지 않는다.

**개발자 (선택) — 환경변수 / `.env`:** 작업 폴더 루트 `.env`에 `DART_API_KEY=키`, `claude config set env.DART_API_KEY "키"`, 또는 셸 환경변수도 사용할 수 있습니다.

> **네트워크는 itda-hyve 가 한다(#1707).** 요청은 **itda-hyve 의 `http_request`**
> (`mcp__remote-devices__itda-hyve__http_request`)로 보내고, 키는 사용자가 GUI 시크릿 탭에 등록한
> `DART_API_KEY` 를 `{{secret:DART_API_KEY}}` 자리표시자로만 가리킨다(값을 묻지 않는다).
> 규약은 동봉한 [references/netbridge.md](references/netbridge.md). 아래 [기업 개황(info)](#기업-개황-info) 이
> `--input` 패턴의 정본이며, **나머지 명령의 itda-hyve 흐름은 후속 이슈**다 — 그 명령들은 아직 스크립트가 직접 호출한다.
> 키 소스 우선순위: `--api-key` > `os.environ`(Claude 주입 포함) > `~/.claude/settings.json` > `.env`(자동 탐색).

### 첫 호출 실패 시 점검 절차

1. **키 문자열 정확성**: 40자리 영숫자, 앞뒤 공백 없는지 확인
2. **URL 인코딩**: 본 스크립트가 자동 처리 (수동 인코딩 불필요)
3. **시간 후 재시도**: 발급 직후 일시적 미반영 가능 — 수 분 대기 후 재시도
4. **권한 오류 (HTTP 403)**: 게이트웨이 단계 거부 → 동일 발급처에서 활용 상태 확인

## 사용법

### 기업 검색 (search)

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/collect_company.py" search --name "삼성전자"
python3 "$SKILL_DIR/scripts/collect_company.py" --format table search --name "카카오"

# Windows
py -3 "$env:SKILL_DIR\scripts\collect_company.py" search --name "삼성전자"
```

### 기업 개황 (info)

**정본은 itda-hyve 경로다.** itda-hyve 가 응답을 파일로 받고, 스크립트는 그 파일을 읽어 표시만 한다.

1. itda-hyve 의 `http_request` 로 조회하고 `save_as` 로 저장한다.

```json
{"url": "https://opendart.fss.or.kr/api/company.json",
 "params": {"crtfc_key": "{{secret:DART_API_KEY}}", "corp_code": "00126380"},
 "legacy_tls": true,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "dart/company-00126380.json"}
```

`legacy_tls: true` 는 OpenDART 의 구형 핸드셰이크 때문에 필요하다(handshake failure 실측).
`save_dir` 에는 **Cowork 연결 폴더의 호스트 경로**(절대 경로, 사용자 홈 아래 폴더 — 홈 자체·숨김 폴더·`AppData`·`~/Library` 제외, 클라우드 드라이브는 허용)를 넣는다 — 생략하면 itda-hyve 기본 저장 폴더에 쓴다.
그 폴더에 같은 이름이 있으면 덮어쓰지 않고 `invalid_input` 으로 거부되므로 **회차마다 겹치지 않는 이름**을 짓는다(덮어쓰기는 사용자 확인 후 `overwrite: true`).

2. 저장된 파일을 `--input` 으로 가공한다. 연결 폴더는 샌드박스의 `$HOME/mnt/<폴더 이름>` 에 마운트되므로
   `save_dir` 의 폴더 이름 + `saved_path` 로 경로가 정해진다(파일을 찾아 헤매지 않는다).

```bash
# save_dir 가 /Users/me/Projects/작업폴더 였다면
INPUT="$HOME/mnt/작업폴더/dart/company-00126380.json"

python3 "$SKILL_DIR/scripts/collect_company.py" info --input "$INPUT"
python3 "$SKILL_DIR/scripts/collect_company.py" --format table info --input "$INPUT"
```

Claude Code CLI 처럼 같은 머신에서 도는 환경이면 `save_dir`/`saved_path` 를 이어 붙인 절대 경로를 그대로 쓴다.

`--input` 은 네트워크를 타지 않는다. 저장된 응답의 `status` 가 `000` 이 아니면 그대로 `error: api` 로 표면화한다
(HTTP 200 이어도 성공이 아니다).

```bash
# 네트워크가 열린 환경에서 스크립트가 직접 부르는 기존 경로(유지)
python3 "$SKILL_DIR/scripts/collect_company.py" info --corp-code 00126380
```

### 재무제표 (finance)

```bash
# 주요계정 조회 (기본)
python3 "$SKILL_DIR/scripts/collect_company.py" finance --corp-code 00126380 --year 2024
python3 "$SKILL_DIR/scripts/collect_company.py" --format table finance --corp-code 00126380 --year 2024

# 전체 재무제표 (v0.16.0+, --detail → fnlttSinglAcntAll, 176항목류)
python3 "$SKILL_DIR/scripts/collect_company.py" finance --corp-code 00126380 --year 2023 --detail
python3 "$SKILL_DIR/scripts/collect_company.py" --format table finance --corp-code 00126380 --year 2023 --detail
```

> JSON 출력에는 공시원문 링크(`source.url`)가 기본 포함됩니다 (v0.16.0+).
> 개별재무제표만 있는 기업은 자동으로 OFS 폴백 + stderr 안내합니다 (v0.16.0+).

### 직원현황 (employees)

```bash
python3 "$SKILL_DIR/scripts/collect_company.py" employees --corp-code 00126380 --year 2024
```

### 종합 프로필 (profile) — 권장

```bash
# 회사명으로 검색 → 코드 자동 확인 → 프로필·재무·직원 일괄 조회
python3 "$SKILL_DIR/scripts/collect_company.py" profile --name "삼성전자" --year 2024
python3 "$SKILL_DIR/scripts/collect_company.py" --format table profile --name "카카오" --year 2023
```

### 공시 목록 (disclosure) — 신규

```bash
# 특정 기간 공시 목록 조회
python3 "$SKILL_DIR/scripts/collect_company.py" disclosure --corp-code 00126380 --bgn 20240101 --end 20241231
python3 "$SKILL_DIR/scripts/collect_company.py" --format table disclosure --corp-code 00126380 --bgn 20240101 --end 20241231 --type A

# Windows
py -3 "$env:SKILL_DIR\scripts\collect_company.py" disclosure --corp-code 00126380 --bgn 20240101 --end 20241231
```

> **`--type`(pblntf_ty) 공시유형 코드:** A=정기공시, B=주요사항보고, C=발행공시, D=지분공시,
> E=기타공시, F=외부감사관련, G=펀드공시, H=자산유동화, I=거래소공시, J=공정위공시. 미지정 시 전체 조회.
>
> **gotcha:** DART `list.json`은 `corp_name`(회사명)을 **요청 파라미터로 받지 않습니다**(응답에만 존재).
> 회사명으로 특정 기업 공시를 좁히려면 `--corp-code`(8자리 고유번호)를 먼저 확보하세요(`search`/`profile`).

### 사업보고서 텍스트 (business) — 신규

```bash
# 접수번호로 사업보고서 원문 추출
python3 "$SKILL_DIR/scripts/collect_company.py" business --rcept-no 20240401000123

# 섹션 지정 (정규식 매칭)
python3 "$SKILL_DIR/scripts/collect_company.py" business --rcept-no 20240401000123 --section "사업의 내용"

# 기업코드만으로 자동 폴백 (최신 사업보고서 자동 선택)
python3 "$SKILL_DIR/scripts/collect_company.py" business --corp-code 00126380

# 출력 길이 제한
python3 "$SKILL_DIR/scripts/collect_company.py" business --rcept-no 20240401000123 --max-chars 2000
```

### 미구현 엔드포인트 직접 호출 (raw) — 신규 (v0.17.0)

`references/`에 명세는 있으나 전용 서브커맨드가 없는 80여 개 엔드포인트(배당·소송·전환사채·증자·해외상장 등)를
직접 호출합니다. **JSON 원문만 반환** — 단위변환·CSV·출처링크는 미보장입니다(가공이 필요하면 `finance`/`compare` 사용).

```bash
# 배당에 관한 사항 (alotMatter)
python3 "$SKILL_DIR/scripts/collect_company.py" raw --endpoint alotMatter \
  --param corp_code=00126380 --param bsns_year=2023 --param reprt_code=11011

# 소송 등의 제기 (lwstLg) — 기간 필요
python3 "$SKILL_DIR/scripts/collect_company.py" raw --endpoint lwstLg \
  --param corp_code=00126380 --param bgn_de=20240101 --param end_de=20241231

# 전환사채 발행결정 (cvbdIsDecsn)
python3 "$SKILL_DIR/scripts/collect_company.py" raw --endpoint cvbdIsDecsn \
  --param corp_code=00126380 --param bgn_de=20200101 --param end_de=20241231
```

> `--endpoint`는 영숫자만 허용합니다(경로·URL·쿼리 주입 차단). `crtfc_key`는 자동 주입됩니다.
> 엔드포인트 이름·파라미터는 [references/dart.md](references/dart.md)의 disambiguation 표와 각 분류 가이드를 참고하세요.
> status `013`(데이터 없음)은 에러가 아니라 빈 결과로 반환됩니다.

### 재무제표 자동 폴백 (finance) — 갱신

```bash
# --year 없이 corp-code만 → 최신 사업보고서 자동 선택
python3 "$SKILL_DIR/scripts/collect_company.py" finance --corp-code 00126380

# --prefer latest → 분기·반기 포함 가장 최신 보고서 자동 선택
python3 "$SKILL_DIR/scripts/collect_company.py" finance --corp-code 00126380 --prefer latest
```

### 다기업 재무 비교 (compare)

```bash
# 회사명으로 비교 (쉼표 구분) — 자동 단위 변환(억/조)
python3 "$SKILL_DIR/scripts/collect_company.py" --format table compare \
  --names "삼성전자,LG전자,SK하이닉스" \
  --year 2024 \
  --accounts "매출액,영업이익,자산총계"

# 기업코드로 비교 + 회사명 매핑(v0.15.0+: 둘 다 지정 가능 — 헤더에 회사명 표시)
python3 "$SKILL_DIR/scripts/collect_company.py" --format table compare \
  --corp-codes "00159023,00190321,00231363" \
  --names "SKT,KT,LGU+" \
  --year 2024 --report q1

# 파생 지표 함께(v0.15.0+) — 영업이익률·순이익률 행 추가
python3 "$SKILL_DIR/scripts/collect_company.py" --format table compare \
  --names "삼성전자,LG전자" --year 2024 --with-ratios

# 단위 강제(v0.15.0+) — 백만원/억/조
python3 "$SKILL_DIR/scripts/collect_company.py" --format table compare \
  --names "삼성전자" --year 2024 --unit eok

# CSV로 저장 (엑셀 호환) — formatted_amount 컬럼 신설(v0.15.0+)
python3 "$SKILL_DIR/scripts/collect_company.py" --format csv compare \
  --names "삼성전자,LG전자" \
  --year 2024 --unit auto > compare.csv

# --year 미지정 → 첫 기업 기준 최신 사업보고서 자동 선택 (stderr 안내)
python3 "$SKILL_DIR/scripts/collect_company.py" compare \
  --names "삼성전자,LG전자,SK하이닉스"

# --prefer latest → 분기·반기 포함 가장 최신 보고서 자동 선택
python3 "$SKILL_DIR/scripts/collect_company.py" compare \
  --names "삼성전자,LG전자" --prefer latest

# 전기 열 포함 (v0.16.0+)
python3 "$SKILL_DIR/scripts/collect_company.py" --format table compare \
  --names "삼성전자" --year 2023 --with-prior

# 전기 + 증감률 동시 (v0.16.0+)
python3 "$SKILL_DIR/scripts/collect_company.py" compare \
  --names "삼성전자" --year 2023 --with-prior --with-ratios
```

> compare 계정 매칭은 정규화가 아닙니다. "영업이익" 검색어는 라벨로 표시되며,
> 정확 일치 우선 + 부분 일치 fallback으로 동작합니다 (`_match_account` 동작).
> 예: "영업이익" 검색 시 "영업이익(손실)"에도 매칭됩니다.
> JSON 출력에 기업별 `source.rcept_no` + 공시원문 URL이 기본 포함됩니다 (v0.16.0+).

### 분기 데이터가 필요할 때 — `--report` 옵션

`finance`·`compare`·`employees`·`profile` 모두 `--report annual|q1|q2|q3` 옵션을 받습니다.
(연 보고서 = `annual`, 1분기 = `q1`, 반기 = `q2`, 3분기 = `q3`)

> **v0.15.0 BREAKING**: 구 `--report half` 는 제거되었습니다. `--report q2` 로 마이그레이션하세요.
> `--report half` 입력 시 친절한 안내 메시지와 함께 즉시 에러로 안내됩니다.

```bash
# 단일 기업의 1분기 재무 (2026 1분기보고서)
python3 "$SKILL_DIR/scripts/collect_company.py" finance \
  --corp-code 00159023 --year 2026 --report q1

# 다기업의 반기(2분기) 비교 — 회사명 헤더 + 비율
python3 "$SKILL_DIR/scripts/collect_company.py" --format table compare \
  --corp-codes "00159023,00190321,00231363" \
  --names "SKT,KT,LGU+" \
  --year 2026 --report q2 \
  --accounts "매출액,영업이익,당기순이익" \
  --with-ratios --unit auto
```

> 미공시 연도(예: 2026 사업보고서가 아직 안 나온 시점)는 `--year`를 빼고 호출하면
> 첫 기업 기준 최신 보고서를 자동 채택합니다. 채택된 보고서는 stderr로 안내됩니다.

### CSV 출력 — 모든 커맨드 지원

```bash
# 재무제표 CSV (엑셀에서 바로 열기)
python3 "$SKILL_DIR/scripts/collect_company.py" --format csv \
  finance --corp-code 00126380 --year 2024 > finance.csv

# 공시 목록 CSV
python3 "$SKILL_DIR/scripts/collect_company.py" --format csv \
  disclosure --corp-code 00126380 --bgn 20240101 --end 20241231 > disc.csv
```

## CLI 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--name` | 회사명 (search/profile 서브커맨드) | — |
| `--corp-code` | DART 기업 코드 (8자리). `info` 에서는 `--input` 이 있으면 생략 | — |
| `--input` | itda-hyve 가 `save_as` 로 저장한 `company.json` 경로. `info` 전용 — 네트워크 없이 가공만 한다 | — |
| `--year` | 사업연도 (미지정 시 자동 폴백) | — |
| `--report` | 보고서 유형: `annual`(사업) / `q1`(1분기) / `q2`(반기) / `q3`(3분기). `finance`·`compare`·`employees`·`profile` 공통 | `annual` |
| `--prefer` | 폴백 범위: `annual`=사업보고서만, `latest`=분기·반기 포함. `finance`·`compare` 공통 | `annual` |
| `--detail` | 전체 재무제표(fnlttSinglAcntAll, 176항목류) 반환. `finance` 전용. 기본 OFF(주요계정 ~30항목) | OFF |
| `--bgn` | 시작일 YYYYMMDD (disclosure) | — |
| `--end` | 종료일 YYYYMMDD (disclosure) | — |
| `--type` | 공시 유형 A/B/None (disclosure) | None=전체 |
| `--page` | 페이지 번호 (disclosure) | 1 |
| `--page-count` | 페이지당 건수 최대100 (disclosure) | 10 |
| `--rcept-no` | 접수번호 14자리 (business) | — |
| `--section` | 섹션 정규식 (business) | None=전체 |
| `--max-chars` | 최대 문자수 0=무제한 (business) | 5000 |
| `--names` | 회사명 목록 쉼표 구분 (compare). `--corp-codes`와 병기 시 헤더 표시명 | — |
| `--corp-codes` | 기업코드 목록 쉼표 구분 (compare) | — |
| `--accounts` | 계정명 목록 쉼표 구분 (compare) | `매출액,영업이익,당기순이익,자산총계` |
| `--unit` | 금액 단위 (compare): `auto`(>=1조 jo, >=1억 eok, 미만 million) / `million` / `eok` / `jo` | `auto` |
| `--with-ratios` | 영업이익률·순이익률 행 추가 (compare, 매출액 기준) | OFF |
| `--with-prior` | 전기(frmtrm_amount) 열/필드 추가 (compare). `--with-ratios` 병행 시 전기 대비 증감률 추가 | OFF |
| `--endpoint` | DART 엔드포인트 이름 (raw 전용, 영숫자) | — |
| `--param` | 쿼리 파라미터 `key=value` (raw 전용, 반복 가능). `crtfc_key` 자동 주입 | — |
| `--format` | `json` / `table` / `csv` (raw는 json 전용) | `json` |
| `--api-key` | DART API 키 (CLI 직접 전달) | 환경변수 |

## 출력 형식

- `--format json` (기본): 구조화된 JSON 출력
- `--format table`: 사람이 읽기 쉬운 테이블
- `--format csv`: UTF-8 BOM CSV (엑셀 한글 호환, RFC 4180)

## 응답 규칙 (모델 표현)

스크립트는 JSON/table/CSV를 **출력**합니다. 그 위에서 사용자에게 답할 때의 표현 규칙입니다
(단위 변환·status 분류는 이미 코드가 처리하므로 여기서 중복 기술하지 않습니다).

- **요약 우선**: 정상 응답이어도 JSON 원문을 그대로 붙여넣지 말고 핵심만 요약합니다.
  - `info`: 회사명·대표자·업종·주소·결산월
  - `finance`·`compare`: 매출액·영업이익·당기순이익·자산총계·부채총계·자본총계 우선
  - `disclosure`: 최근 5~10건의 보고서명·접수일·제출인
  - `business`: 요청 섹션의 요지
- **원본 병기**: 금액을 억/조로 풀어 보여줄 때 원본 수치(원 단위)도 함께 남깁니다.
- **비정상 status 안내**: `status`가 `000`이 아니면(스크립트가 error JSON·`error_code` 반환)
  코드 의미를 사용자 언어로 안내합니다(예: `013`=해당 기간/보고서에 데이터 없음, `020`=요청 한도 초과 → 잠시 후 재시도).
- **출처 동봉**: `finance`·`compare` JSON의 `source.url`(공시원문 링크)을 답변에 함께 제시합니다.
- **면책 푸터**: 답변 말미에 한 줄 — `※ 금융감독원 DART 공시 데이터 기준이며 투자 조언이 아닙니다`.

### Done when (작업 완료 기준)

- `DART_API_KEY`(또는 작업 폴더 `.env`)를 확인했다.
- 회사명만 받았으면 `search`/`profile`로 `corp_code`를 먼저 확보했다.
- 요청에 맞는 서브커맨드를 실행하고 결과를 위 규칙대로 요약했다.
- `source.url`(공시원문)을 동봉하고 면책 푸터를 남겼다.

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 실행 오류 (API 키 미설정, 인증 실패, 데이터 없음) |
| 2 | 인자 오류 |

## 트리거 키워드

기업정보, 재무제표, 매출, 영업이익, 경쟁사 분석, DART, 전자공시,
직원수, 직원현황, 기업 비교, 상장사, 공시, 사업보고서, 회사 검색, 기업개황,
company info, financial statements, competitor analysis, DART

## 파일 구조

```
dart/
  SKILL.md
  CHANGELOG.md
  GUIDE.md
  requirements.txt
  scripts/
    dart_api.py         # DART API 모듈 (공시목록·사업보고서 텍스트 포함)
    collect_company.py  # 기업정보 수집 CLI (9개 커맨드: search/info/finance/disclosure/business/employees/profile/compare/raw)
  tests/
    test_dart_api.py
    test_collect_company.py
    test_collect_company_arg_position.py
  references/
    dart.md             # 요약 가이드
    공시정보/                  # DS001 (4)
    정기보고서-주요정보/         # DS002 (28)
    정기보고서-재무정보/         # DS003 (7)
    지분공시-종합정보/           # DS004 (2)
    주요사항보고서-주요정보/      # DS005 (36)
    증권신고서-주요정보/         # DS006 (6)
```

> API 키 관리(`env_loader.py`)와 데이터 경로 유틸리티(`itda_path.py`)는
> 저장소 전역 `shared/` 디렉토리에 위치하며, PYTHONPATH로 import됩니다
> (dart 직속 파일이 아님 — SPEC-DART-FEEDBACK-001 REQ-002a로 광고 정정됨).

## 오류 처리

### 일반 오류

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `DART_API_KEY가 설정되지 않았습니다` | API 키 미설정 | `.env`(작업 폴더 루트)에 `DART_API_KEY=키` 추가(권장) — 스킬이 자동 탐색. "Claude 지침"도 동작하나 컨텍스트에 노출. 개발자는 셸 환경변수도 가능 |
| `기업을 찾을 수 없습니다` | 회사명 불일치 | 공식 법인명 전체로 재검색 |
| `재무 데이터가 없습니다` | 해당 연도 미공시 | 이전 연도로 재시도 |

### 정본 status 코드 (DART API)

| 코드 | 의미 | 권장 조치 |
|------|------|----------|
| 000 | 정상 | — |
| 010 | 등록되지 않은 키 | 활용신청 URL 확인 |
| 011 | 사용할 수 없는 키 (일시 중지) | 활용신청 URL 확인 |
| 012 | 접근할 수 없는 IP | DART 콘솔에서 IP 등록 |
| 013 | 조회된 데이터 없음 | 정상 응답 (결과 0건) |
| 014 | 파일이 존재하지 않습니다 | 접수번호 재확인 |
| 020 | 요청 제한 초과 (일 20,000건) | 자동 재시도(1s, 2s) |
| 021 | 조회 가능 회사 개수 초과 (최대 100건) | 분할 호출 |
| 100 | 필드의 부적절한 값 | 인자 형식 확인 |
| 101 | 부적절한 접근 | 활용신청 URL 확인 |
| 800 | 시스템 점검으로 인한 서비스 중지 | 잠시 후 재시도 |
| 900 | 정의되지 않은 오류 | 재시도 또는 문의 |
| 901 | 사용자 계정 개인정보 보유기간 만료 | 재가입 또는 갱신 |

권한 관련 오류(010/011/012/101/901)는 시스템이 활용신청 URL(`https://opendart.fss.or.kr`)을
자동 부착합니다. HTTP 403 게이트웨이 거부도 동일하게 처리됩니다.

## Troubleshooting

### 한글 경로가 인식되지 않을 때

Cowork sandbox 등 일부 환경의 bash는 `LANG`/`LC_ALL` 미설정 시 한글 디렉토리명을 직접 인자로 받지 못합니다.

**증상:** `/sessions/.../mnt/실습-클로드-1기/` 경로에서 `No such file or directory`.

**해결 — 변수 캡처 우회:**

```bash
WORKSPACE=$(ls /sessions/*/mnt/ | grep -v '^lost+found$' | head -1)
WORKSPACE_PATH=$(ls -d /sessions/*/mnt/"$WORKSPACE" 2>/dev/null | head -1)

python3 "$SKILL_DIR/scripts/collect_company.py" search --name "삼성전자" > "$WORKSPACE_PATH/result.json"
```

> 이 패턴은 스크립트 코드 결함이 아니라 sandbox bash의 locale 설정 문제입니다.
> macOS native bash 및 Windows PowerShell에서는 한글 경로가 정상 동작합니다.

## 상세 API 가이드

`references/` 디렉토리에 OpenDART 공식 가이드 6개 분류 · 83개 API의 정본 명세를 보관합니다.

| 분류 | API 수 | 위치 |
|------|--------|------|
| 공시정보 | 4 | [references/공시정보/](references/공시정보/) |
| 정기보고서 주요정보 | 28 | [references/정기보고서-주요정보/](references/정기보고서-주요정보/) |
| 정기보고서 재무정보 | 7 | [references/정기보고서-재무정보/](references/정기보고서-재무정보/) |
| 지분공시 종합정보 | 2 | [references/지분공시-종합정보/](references/지분공시-종합정보/) |
| 주요사항보고서 주요정보 | 36 | [references/주요사항보고서-주요정보/](references/주요사항보고서-주요정보/) |
| 증권신고서 주요정보 | 6 | [references/증권신고서-주요정보/](references/증권신고서-주요정보/) |

기존 요약본: [references/dart.md](references/dart.md)

> **미구현 엔드포인트 호출**: 위 분류의 대부분은 전용 서브커맨드가 없습니다. 명세만 읽고 끝내지 말고
> `collect_company.py raw --endpoint <이름> --param k=v ...`로 직접 호출하세요
> (위 "미구현 엔드포인트 직접 호출 (raw)" 섹션 참고). 헷갈리는 엔드포인트(유무상/유상/무상 증자,
> 주요계정/전체 재무제표 등)는 [references/dart.md](references/dart.md)의 disambiguation 표를 확인하세요.
