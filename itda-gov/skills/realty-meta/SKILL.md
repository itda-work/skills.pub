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
  version: "0.11.0"
  created_at: "2026-05-15"
  updated_at: "2026-09-30"
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
| **realty-supply** | KOSIS 미분양·인허가·착공·준공 + 청약홈 분양 공고 | KO_DATA_API_KEY, KOSIS_API_KEY |
| **realty-price-stats** | 한국부동산원 R-ONE 주간/월간 아파트 매매가격지수·전월세전환율 + 실거래 파생 통계 | RONE_API_KEY (파생 통계는 KO_DATA_API_KEY) |
| **court-auction** | 대법원 법원경매정보 매각공고·사건·물건 read-only 조회 | 불필요 |

## 빠른 시작

```
1. "강남구 아파트 매매 실거래 최근 3개월 수집해줘"
2. "분당 전세가율 70% 이상 단지 스크리닝해줘"
3. "서울 미분양 추이 2023년부터 보여줘"
4. "전국 아파트 매매가격지수 올해 월별 가져줘"
```

## API 키 설정

**키는 전부 itda-hyve GUI 시크릿 탭에 등록한다** — realty 스킬 스크립트는 네트워크를 하지 않고, 요청은 itda-hyve 의 `http_request` 가
`{{secret:<KEY>}}` 자리에 키를 채워 보낸다(Cowork·Claude Code 공통, itda-work/skills#45). 어느 스킬도 `.env` 같은 파일이나 환경변수를 읽지 않는다.

| 키 | 쓰는 스킬 | 요청 호스트 |
|---|---|---|
| `KO_DATA_API_KEY` (data.go.kr **Decoding 키**) | realty-deals · realty-jeonse-gap · realty-price-stats(derive) · realty-supply(청약) | `apis.data.go.kr`, 청약홈은 `api.odcloud.kr` |
| `KOSIS_API_KEY` | realty-supply(공급 지표) | `kosis.kr` |
| `RONE_API_KEY` | realty-price-stats(R-ONE 지수) | `www.reb.or.kr` |

> 청약홈 분양정보(realty-supply)는 `api.odcloud.kr` 로 나간다. itda-hyve 0.10.4 전에 `KO_DATA_API_KEY` 를 등록했다면 GUI 시크릿 탭에서
> 허용 호스트에 `api.odcloud.kr` 를 추가한다(프리셋 변경은 새 등록에만 적용된다 — 안 하면 `secret_host_denied`). 데이터셋 15098547 활용신청도 따로 필요하다.

> 키 값을 묻지 않고, 대화에 붙여 넣어도 쓰지 않는다. `secret_missing` 이 나오면 시크릿 탭 등록을 안내하고 멈춘다.

API 키 발급: [data.go.kr](https://www.data.go.kr) | [KOSIS Open API](https://kosis.kr/openapi)

## 주의사항

- 민간 사이트(네이버부동산·아실·호갱노노·직방 등) 스크래핑은 절대 지원하지 않습니다.
- 시세 예측·투자 자문은 제공하지 않습니다.
- 외지인·법인 매입비중은 국토부 API에 해당 필드가 없어 수집 불가입니다.
