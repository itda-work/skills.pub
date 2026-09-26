# 판정 축과 파생 등급 (정본 — grade.py 와 1:1)

| 축 | 값 | 뜻 |
|---|---|---|
| `discovery_path` | feed · static_list · site_search · api · none | 정보가 있는 위치를 **어떻게 찾았나** |
| `repeat_access` | L1 · L2 · L3 · L4 | 다음 조회에 **어느 단**이 필요한가 (L1 정적 fetch · L2 fetch+조건 · L3 익명 API GET · L4 브라우저) |
| `auth_state` | none · required · blocked · blocked:security_module | 인증·차단 상태 |
| `env_availability` | aside · chrome · n/a | 실측에 쓴 브라우저(재현성 근거) |

파생 등급(참가자·강의용): **A** feed+L1 · **B** L1/L2/L3 정적·익명 · **C** L4 필요 · **D** auth ≠ none(범위 밖, 기록만).
등급은 축에서 **파생**된다 — 등급을 직접 쓰지 않는다.

## 반복 조회 결과 분류 (S8)

| 분류 | 처리 | 판정 |
|---|---|---|
| `fresh_nonempty` | 성공 종결 | 기대 shape 충족 + (freshness_days 있으면) 최신 항목이 N일 내 |
| `empty_valid` | 성공 종결 | 0건이지만 Content-Type·봉투 정상 — 무소식은 정상 |
| `incomplete` | 재탐색 → 제안 | 분모(사이트 총계)·최소 건수 미달 |
| `schema_drift` | 재탐색 → 제안 | Content-Type·필수 키·최신성 이탈 (정적 껍데기의 오래된 샘플 포함 — 현대해상 2021년 3건 실측) |
| `auth_expired` | typed 종결 | 인증·설치 게이트 — discovery 대상 아님 |

최소 건수 **단독** 판정 금지.
