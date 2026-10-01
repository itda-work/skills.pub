# Open-Meteo 를 계속 쓴다 — robots.txt 판단 기록 (사용자 결정 2026-10-01)

## 사실

- `https://api.open-meteo.com/robots.txt` 는 `User-agent: *` / `Disallow: /` 다(2026-09-30 itda-hyve 로 조회한 원문).
- 이 스킬은 0.12.0(2026-05-19, SPEC-WEATHER-HERE-001 v0.4.0) 부터 날씨 값을 Open-Meteo Forecast `https://api.open-meteo.com/v1/forecast` 에서 받는다. 키·가입이 없다.
- 키 없는 스킬을 itda-hyve 로 옮기는 작업(itda-work/skills#46)의 규칙은 "robots 불허 경로는 부르지 않는다. 기존 스킬이 쓰고 있었으면
  멈추고 사용자에게 묻는다" 였다. 그래서 W9 는 이 스킬에서 멈췄고, 사용자가 결정했다.

## 결정

Open-Meteo 를 계속 쓴다. 호출은 itda-hyve `http_request` 로만 보낸다. 스크립트는 네트워크를 열지 않는다.

## 근거

- `api.open-meteo.com` 은 공개 문서로 안내하는 **무키 API 전용 호스트**다. 그 호스트의 존재 이유가 프로그램 호출이다.
  `Disallow: /` 는 검색 크롤러가 API 응답을 색인하지 못하게 막는 것으로 읽는다.
- 이 스킬은 **사용자 요청 1건당 1회**(현재값 + 오늘 요약, `forecast_days=1`) 부른다. 링크를 따라가며 모으는 크롤링이 아니다.
- Open-Meteo 무료 API 의 비상업 이용 조건은 사용자가 확인했다.

## 기각한 대안

| 대안 | 기각 사유 |
|---|---|
| 기상청 단기예보(공공데이터포털)로 교체 | `KO_DATA_API_KEY` 가 필요해진다(지금은 키가 없는 것이 이 스킬의 장점이다). 해외 위치 best-effort 가 사라진다. 격자 변환·발표 시각 계산이 필요해 작업량이 크다 |
| 보류(직접 호출 스크립트를 그대로 둠) | Cowork 에서 스크립트 직접 호출은 간헐적으로 막힌다(`cowork-network-via-hyve`). 네트워크 가드 `LEGACY` 에 계속 남는다 |

## bai-notice 와 무엇이 다른가

같은 날 itda-gov bai-notice 는 robots 때문에 공개 팩에서 뺐다(W10). 감사원 `https://www.bai.go.kr/api/` 는 **웹 화면이 내부적으로 부르는
비공개 API** 이고, robots 가 사이트의 다른 경로는 허용하면서 `/api/` 만 **골라서** 막았다. Open-Meteo 는 문서화된 공개 API 호스트 전체에
대한 색인 차단이다. 둘 다 `Disallow` 지만 막는 대상과 그 호스트의 용도가 다르다.

## 다시 볼 때

- Open-Meteo 이용 약관이나 robots 에 **API 호출 자체를 제한**하는 문구가 생기면 이 결정을 다시 연다.
- 호출 모양(파라미터·횟수)을 바꾸면 "요청 1건당 1회" 전제가 유지되는지 확인한다.
