---
name: realty-deals
description: >
  국토교통부 부동산 실거래 12개 유형을 단일 인터페이스로 수집하는 스킬입니다.
  "최근 6개월 강남구 아파트 실거래 전부 받아줘", "분당 연립다세대 매매 2025년 데이터 CSV로 줘", "강서구 오피스텔 전월세 조회해줘"처럼 말하면 됩니다.
  전체 페이지네이션·다개월 범위·CSV/JSON 출력을 지원합니다.
  [책임 경계] 본 스킬은 국토교통부 실거래 raw 수집 전담 — 가격지수·평균/중위 파생 통계는 itda-gov:realty-price-stats, 미분양·인허가·청약은 itda-gov:realty-supply.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.9.0 이상(로컬 MCP 서버, 구 itda-butler)이 한다."
user-invocable: true
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, Bash, Read, Write, mcp__workspace__bash"
argument-hint: "지역명 + 기간 + 유형 (예: 강남구 2026년 1~6월 아파트 매매)"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.12.0"
  category: "domain"
  status: "active"
  created_at: "2026-05-15"
  updated_at: "2026-09-25"
  tags: "realestate, molit, trade, rent, csv, json"
---

# realty-deals

국토교통부 공공데이터포털의 실거래가 API 12개 유형을 단일 인터페이스로 수집합니다.

- **절단 버그 교정**: `page=1` 단일 요청이 아니라 `totalCount` 전량까지 페이지를 돈다
- **12유형**: 아파트·오피스텔·연립다세대·단독다가구·토지·상업업무용·공장창고·분양입주권 × 매매/전월세
- **다월 수집**: 달마다 따로 조회해 합친다

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`) 하나로만 나간다.
스크립트는 네트워크를 하지 않는다 — itda-hyve 가 `save_as` 로 저장한 응답 XML 을 `--input` 으로 읽어 정규화·요약·전량 대조만 한다.
공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
지역코드 확정(regions) → 달·페이지마다 http_request + save_as → deals_cli.py collect --input …
```

API 키는 사용자가 itda-hyve GUI 시크릿 탭에 **`KO_DATA_API_KEY`** 로 등록해 둔 것을 **이름으로만** 가리킨다.
값을 묻지 않고, 대화에 붙여 넣어도 쓰지 않는다. 공공데이터포털은 **Decoding 키**를 등록해야 한다
(`params` 가 한 번 인코딩하므로 Encoding 키는 이중 인코딩돼 `resultCode 30` 이 난다).

## 1단계 — 지역코드 확정 (네트워크 불요)

사용자가 5자리 법정동코드를 주지 않았으면 스크립트로 찾는다. 목록에 없으면 사용자에게 묻는다 — **코드를 짐작하지 않는다.**

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/realty-deals}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins /sessions/*/mnt/.claude/skills -type d -path '*/skills/realty-deals' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용

python3 "$SKILL_DIR/scripts/deals_cli.py" regions     # Windows: py -3 "$env:SKILL_DIR\scripts\deals_cli.py" regions
```

출력의 `name` → `lawd_cd` 를 쓴다. 별도 패키지 설치는 필요 없다(표준 라이브러리만 사용).

> **저장소 체크아웃에서 직접 실행 시(개발자)**: 공용 모듈(`deals_collector`·`data_go_client`·`lawd_codes`)이
> `itda-gov/shared/` 에 있어 `PYTHONPATH=itda-gov/shared:shared` 를 붙여야 한다. 배포본은 publish 주입으로 불필요.

## 2단계 — itda-hyve 의 http_request 로 달·페이지마다 조회

**달마다 따로** 부른다(`DEAL_YMD` 는 한 달). 한 달 안에서는 `pageNo` 를 1부터 올린다. 응답은 `save_as` 로 저장한다.

```json
{"url": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",
 "params": {"serviceKey": "{{secret:KO_DATA_API_KEY}}", "LAWD_CD": "11680", "DEAL_YMD": "202601",
            "pageNo": "1", "numOfRows": "100"},
 "timeout_sec": 30,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "realty/apt_trade-11680-202601-p1.xml"}
```

- `serviceKey` 는 반드시 `params` 에 둔다. URL 쿼리에 자리표시자를 쓰면 `invalid_input` 으로 거부된다.
- `params` 값은 전부 **문자열**이다(`"pageNo": "1"`).
- **`save_dir` 에는 Cowork 연결 폴더의 호스트 경로**(절대 경로, 사용자 홈 아래 폴더 — 홈 자체·숨김 폴더·`AppData`·`~/Library` 제외, 클라우드 드라이브는 허용)를 넣는다. 생략하면 itda-hyve 기본 저장 폴더에 쓴다.
- `save_as` 는 그 폴더 기준 **상대 경로**이고 응답의 `saved_path` 가 같은 값이다 — 3단계에 그대로 쓴다.
- **파일 이름을 겹치지 않게 짓는다**(`<유형>-<코드>-<연월>-p<페이지>.xml`). `save_dir` 폴더에 같은 이름이 있으면 덮어쓰지 않고 `invalid_input` 으로 거부된다(사용자 파일 보호). 덮어써도 된다고 확인됐을 때만 `overwrite: true`.
- URL 은 유형별로 `https://apis.data.go.kr/1613000/<서비스>/get<서비스>` 다.

| 키 | `<서비스>` | 키 | `<서비스>` |
|---|---|---|---|
| `apt_trade` | `RTMSDataSvcAptTrade` | `apt_rent` | `RTMSDataSvcAptRent` |
| `offi_trade` | `RTMSDataSvcOffiTrade` | `offi_rent` | `RTMSDataSvcOffiRent` |
| `rh_trade` | `RTMSDataSvcRHTrade` | `rh_rent` | `RTMSDataSvcRHRent` |
| `sh_trade` | `RTMSDataSvcSHTrade` | `sh_rent` | `RTMSDataSvcSHRent` |
| `land_trade` | `RTMSDataSvcLandTrade` | `biz_trade` | `RTMSDataSvcNrgTrade` |
| `factory_trade` | `RTMSDataSvcFctTrade` | `presale_trade` | `RTMSDataSvcSilvTrade` |

### 전량 수집 — 페이지를 끝까지 돈다

`body/totalCount` 가 그 달의 전체 건수다. 받은 `<item>` 누적 수가 `totalCount` 에 닿거나 `<items>` 가 비면 그 달을 끝낸다.
**1페이지만 받고 끝내지 않는다**(이 스킬이 교정한 절단 버그 그대로다). 3단계 스크립트가 달마다 `totalCount` ↔ 수집 건수를 다시 대조한다.

### 응답 판정 — HTTP 200 은 성공이 아니다

- 루트가 `<response>` 이고 `header/resultCode` 가 `000`(또는 `00`·`0000`)일 때만 성공이다.
- 그 밖의 `resultCode` 는 실패다: `03` 데이터 없음(다른 달·지역) · `20` 활용 미승인(해당 유형의 활용신청, 승인 후 동기화 5~30분) ·
  `22` 일일 트래픽 초과 · `30` 등록되지 않은 키(**GUI 에 Decoding 키로 등록했는지** 먼저 확인) · `31` 키 기간 만료.
- 루트가 `<OpenAPI_ServiceResponse>` 이거나 `<header>` 가 없으면 **게이트웨이 오류**다. `returnAuthMsg`·`returnReasonCode` 를
  그대로 사용자에게 보여 준다. 0건으로 접지 않는다.
- `save_as` 로 저장했으면 본문 대신 `saved_path` 만 온다 — 판정은 3단계 스크립트가 파일을 읽어 대신 한다(오류 응답이면 `error: api`).

### 호출 예산

요청마다 도구 호출 1회다. 강남구 아파트 매매 한 달이 수백 건(수 페이지)이므로, 6개월 이상·여러 유형을 한 번에 요청받으면
**예상 호출 수(달 × 페이지)를 먼저 알리고** 범위를 확인한다. 연달아 부르다 `22`·HTTP 429 가 나면 멈춘다(재시도는 itda-hyve 가 한다).

## 3단계 — 저장한 XML 을 스크립트로 가공

Cowork 에서는 연결 폴더가 샌드박스의 `$HOME/mnt/<폴더 이름>` 에 마운트된다 —
`save_dir` 에 넣은 호스트 경로의 **폴더 이름**을 앞에 붙이고 `saved_path` 를 이어 붙인다(파일을 찾아 헤매지 않는다).

```bash
# save_dir 가 /Users/me/Projects/작업폴더 였다면
python3 "$SKILL_DIR/scripts/deals_cli.py" collect \
  --input "$HOME/mnt/작업폴더/realty/apt_trade-11680-202601-p1.xml" \
  --region "강남구" \
  --type apt_trade \
  --summary
```

여러 달·여러 페이지는 파일을 **전부 나열**한다(순서 무관).

```bash
python3 "$SKILL_DIR/scripts/deals_cli.py" collect \
  --input "$HOME/mnt/작업폴더/realty/apt_trade-11680-202601-p1.xml" \
          "$HOME/mnt/작업폴더/realty/apt_trade-11680-202601-p2.xml" \
          "$HOME/mnt/작업폴더/realty/apt_trade-11680-202602-p1.xml" \
  --region "강남구" --type apt_trade --summary
```

Claude Code CLI 처럼 같은 머신에서 도는 환경이면 `save_dir`/`saved_path` 를 이어 붙인 절대 경로를 그대로 쓴다.

인자: `--input`(필수, 1개 이상) · `--region` 또는 `--lawd-cd`(출력 라벨) · `--type`(기본 `apt_trade`) ·
`--name`(단지명 부분 일치) · `--summary` · `--format json|table`.

## 지원 엔드포인트 유형

| 키 | 유형 | 거래 | 키 | 유형 | 거래 |
|---|---|---|---|---|---|
| `apt_trade` | 아파트 | 매매 | `apt_rent` | 아파트 | 전월세 |
| `offi_trade` | 오피스텔 | 매매 | `offi_rent` | 오피스텔 | 전월세 |
| `rh_trade` | 연립다세대 | 매매 | `rh_rent` | 연립다세대 | 전월세 |
| `sh_trade` | 단독다가구 | 매매 | `sh_rent` | 단독다가구 | 전월세 |
| `land_trade` | 토지 | 매매 | `biz_trade` | 상업업무용 | 매매 |
| `factory_trade` | 공장창고 | 매매 | `presale_trade` | 분양입주권 | 매매 |

## 출력 형식

```json
{
  "status": "ok",
  "region": "강남구",
  "lawd_cd": "11680",
  "type": "apt_trade",
  "count": 1234,
  "results": [
    {"apt_nm": "래미안퍼스티지", "deal_amount": 155000, "deal_year": "2026", "deal_month": "01",
     "deal_day": "05", "exclu_use_ar": "84.98", "floor": "12", "build_year": "2009",
     "umd_nm": "도곡동", "jibun": "467-1"}
  ],
  "sources": [{"path": "…/apt_trade-11680-202601-p1.xml", "month": "202601", "total_count": 1234, "page": 1, "item_count": 100}],
  "months": [{"month": "202601", "total_count": 1234, "collected": 1234}],
  "warnings": [],
  "summary": {"avg": 120000, "median": 115000, "max": 200000, "min": 80000, "count": 1234}
}
```

전월세 유형은 `deal_amount` 대신 `deposit`·`monthly_rent` 가 들어간다.

**`status` 판정**: 달마다 `collected` 가 `total_count` 에 못 미치면 `status: "incomplete"` + `warnings` 다.
그때는 **수집 성공으로 말하지 않는다** — 모자란 달의 페이지를 더 받아 다시 가공한다.

## 에러 코드

| 상황 | status | error | 조치 |
|---|---|---|---|
| 입력 파일 없음·알 수 없는 지역명 | error | args | 경로·지역명 확인(`regions` 로 지역명 조회) |
| 저장된 XML 이 오류 응답(resultCode 20/30 등) | error | api | 유형별 활용신청 승인 상태, Decoding 키 등록 확인 |
| `secret_missing` (itda-hyve) | — | — | GUI 시크릿 탭에 `KO_DATA_API_KEY` 등록 안내 후 멈춤 |
| `secret_host_denied` (itda-hyve) | — | — | URL 호스트가 `apis.data.go.kr` 인지 먼저 확인 |

## 테스트 실행

```bash
python3 -m pytest itda-gov/skills/realty-deals/tests/ -v     # Windows: py -3 -m pytest …
```

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 가격지수·전월세전환율·평균/중위 통계 | itda-gov:realty-price-stats |
| 미분양·인허가·착공·청약 통계 | itda-gov:realty-supply |
| 전세가율·갭 스크리닝 | itda-gov:realty-jeonse-gap |
| 법원 경매 물건 | itda-gov:court-auction |

## 마이그레이션 안내

구 itda-gov 팩 `realestate` 에서 이전하는 사용자:

- 키 이름은 `KO_DATA_API_KEY` 그대로다 — 다만 이제 **itda-hyve GUI 시크릿 탭**에 등록한다(`.env`·환경변수 경로는 쓰지 않는다).
- 기존 4유형(apt_trade, apt_rent, offi_trade, offi_rent) 동일하게 동작
- 새 스킬명: `realty-deals` (in plugin `itda-gov`)
