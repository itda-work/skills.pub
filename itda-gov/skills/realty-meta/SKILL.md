---
name: realty-meta
description: >
  itda-gov 부동산 스킬팩의 색인·도움말 가이드입니다.
  "부동산 스킬 목록 보여줘", "itda-gov 도움말", "실거래가 스킬 뭐 있어"처럼 말하면 됩니다.
  사용 가능한 스킬·필요한 API 키·빠른 시작 예시를 안내합니다.
license: Apache-2.0
compatibility: "Claude Code & Cowork. Python 3.10+"
user-invocable: true
allowed-tools: Read
argument-hint: "부동산 스킬 목록 / itda-gov 도움말"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.9.5"
  created_at: "2026-05-15"
  updated_at: "2026-09-28"
  tags: "realty, real-estate, meta, guide"
---

# 부동산 데이터 스킬팩 (itda-gov)

한국 부동산 공식 공개 API 기반 데이터 수집·분석 스킬팩입니다.
data.go.kr · 한국부동산원 R-ONE · KOSIS · 건축HUB 공식 API만 사용합니다.

## 제공 스킬

| 스킬 | 설명 | 필요 키 |
|------|------|:-------:|
| **realty-deals** | 국토부 12개 유형 실거래가 통합 수집 (아파트·오피스텔·연립다세대·단독다가구·토지·상업·공장·분양입주권 × 매매/전월세) | KO_DATA_API_KEY |
| **realty-jeonse-gap** | 전세가율·갭 스크리너 — 매매×전월세 단지·면적 조인, 임계값 필터 | KO_DATA_API_KEY |
| **realty-supply** | KOSIS 미분양·인허가·착공·준공·입주물량 + 청약홈 경쟁률·분양·당첨 | KO_DATA_API_KEY, KOSIS_API_KEY |
| **realty-price-stats** | 한국부동산원 R-ONE 주간/월간 가격지수·전월세전환율 | RONE_API_KEY (파생 지표는 KO_DATA_API_KEY) |
| **court-auction** | 대법원 법원경매정보 매각공고·사건·물건 read-only 조회 | 불필요 |

## 빠른 시작

```
1. "강남구 아파트 매매 실거래 최근 3개월 수집해줘"
2. "분당 전세가율 70% 이상 단지 스크리닝해줘"
3. "서울 미분양 추이 2023년부터 보여줘"
4. "전국 아파트 매매가격지수 올해 월별 가져줘"
```

## API 키 설정

**권장 (비개발자 포함 모든 사용자) — 작업 폴더 `.env`에 키 등록:**

작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트, 연결한 폴더가 여러 개면 아무 폴더나) 루트에 `.env` 파일을 만들고 아래 내용을 넣어 두면 스킬이 자동으로 찾아 읽습니다. 파일명 별칭 `.env.txt`·`환경변수.txt` 도 동일하게 탐색된다. 셸 환경변수나 `~/.claude/settings.json` 의 `env` 로 설정해도 되며(로더가 자동 탐색), `.env` 가 없으면 그 값을 사용합니다.

```dotenv
KO_DATA_API_KEY=발급받은_키
KOSIS_API_KEY=발급받은_키
```

> `KO_DATA_API_KEY` = data.go.kr 범용(국토부 실거래가·청약홈·공시가격 공통), `KOSIS_API_KEY` = KOSIS(공급통계).
> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find` 등으로 **사전 점검하지 않는다** — 스크립트가 `.env`·`.env.txt`·`환경변수.txt` 를 스스로 탐색하므로 **우선 실행**한다(셸 glob·검색 패턴은 별칭을 놓쳐 오탐한다: `.env*`·`*env*` 는 `환경변수.txt` 를, `*.env` 는 `.env.txt` 를 놓친다). 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수(`KO_DATA_API_KEY`·`KOSIS_API_KEY`)가 선언돼 있는 경우 그 값을 각 realty 스킬 실행 시 환경변수로 전달해 재시도한다. 지침에도 없으면 발급 안내를 제시한다. 수동 확인이 꼭 필요하면 파일명 3종(`.env`·`.env.txt`·`환경변수.txt`)을 그대로 나열해 확인한다.

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수.txt 의 KO_DATA_API_KEY 를 사용했습니다") — 사용자가 어느 설정파일이 쓰였는지 인지하게 하는 계약이다. 값은 어디에도 표시하지 않는다.

**개발자 (선택):** `claude config set env.KO_DATA_API_KEY "키"`·`claude config set env.KOSIS_API_KEY "키"`, 작업 폴더 `.env`, 또는 셸 환경변수.

API 키 발급: [data.go.kr](https://www.data.go.kr) | [KOSIS Open API](https://kosis.kr/openapi)

## 주의사항

- 민간 사이트(네이버부동산·아실·호갱노노·직방 등) 스크래핑은 절대 지원하지 않습니다.
- 시세 예측·투자 자문은 제공하지 않습니다.
- 외지인·법인 매입비중은 국토부 API에 해당 필드가 없어 수집 불가입니다.
