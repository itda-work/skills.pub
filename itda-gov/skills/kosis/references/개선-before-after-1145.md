# kosis 스킬 개선 — before/after 실증 (#1145)

MCP(kosismcp2026, 10종) 벤치마크 기반으로 KOSIS OpenAPI 기능을 스킬에 흡수(풀 파리티, `validate`·벡터검색 제외). 아래는 **동일 KOSIS 인증키로 실제 API를 호출한 라이브 실측**(2026-07-15)이다.

## 1. 표면 대비

| | BEFORE (v0.10.4) | AFTER (v0.11.0) |
|---|---|---|
| 서브커맨드 | `search`, `data` (2종) | `search`, `data`, **`info`, `list`, `meta`, `indicator`, `region`** (7종) |
| `data` 분류축 | objL1/objL2 (2중까지) | objL1~**objL4** (4중 분류표까지) |
| 코드(objL·itmId) 발견 | **수단 없음** → KOSIS 웹 수동 검색 | `info --type ITM` 한 번으로 발견 |
| 국제·OECD·지역 탐색 | 통합검색 의존(잘 안 잡힘) | `list --vw-cd MT_RTITLE/MT_ATITLE01` |
| 통계 맥락(작성목적·법적근거) | 없음 | `meta` |

## 2. 핵심 시나리오 — "경제활동인구(T20)" 조회

사용자 실제 작업축. **BEFORE에는 T20이라는 코드를 알 방법이 스킬에 없었다.**

### BEFORE — 코드를 추측하면 실패한다

`info`가 없으니 에이전트는 `itmId`를 추측해야 한다. 인구 통계표(`DT_1B04005N`)에서 `T2`=총인구수였으므로 `T2`를 추측하는 것은 그럴듯하다. 그러나:

```
$ collect_stats.py data --org-id 101 --tbl-id DT_1DA7001S --item T2 --recent 1
{"status":"error","error":"api","error_code":"21",
 "detail":"KOSIS API 오류 (21): 잘못된 요청 변수를 호출 하였습니다."}
```

→ **err21, 데이터 0건.** 코드를 모르면 조회 자체가 실패한다(= "답변 데이터 부족"의 실체).

### AFTER — `info`로 코드를 발견하면 조회가 완결된다

**① 코드 발견** (신규 `info`, 라이브):

```
$ collect_stats.py info --org-id 101 --tbl-id DT_1DA7001S --type ITM
분류/항목 코드 — 17건
OBJ_ID   분류명    ITM_ID   항목명          단위
ITEM     항목      T10      15세이상인구     천명
ITEM     항목      T20      경제활동인구     천명   ← 사용자가 찾던 그 코드
ITEM     항목      T30      취업자          천명
ITEM     항목      T40      실업자          천명
...
B        성별      2        남자
B        성별      3        여자
```

**② 발견한 코드로 조회** (라이브):

```
$ collect_stats.py data --org-id 101 --tbl-id DT_1DA7001S --item T20 --obj1 2 --recent 3
성별 경제활동인구 총괄
시점    분류   항목          값        단위
2023   남자   경제활동인구   16,386   천명
2024   남자   경제활동인구   16,375   천명
2025   남자   경제활동인구   16,408   천명
```

→ **정확한 실수치 확보.** BEFORE의 err21이 AFTER에서 완결된 데이터로 바뀐다.

## 3. 그 외 신규 기능 라이브 검증

| 기능 | 호출 | 결과(라이브) |
|---|---|---|
| `list` 국제통계 | `list --vw-cd MT_RTITLE` | 국제통계연감(2025), 국제기구별 통계 — 통합검색에 안 잡히던 진입로 확보 |
| `meta` 통계설명 | `meta --org-id 101 --tbl-id DT_1DA7001S` | 조사명=경제활동인구조사, 작성목적·조사주기(월) 등 26개 필드 |
| `region` 지역코드 | `region --tbl-id INH_1DA7014S_02 --region 인천` | code=23(인천광역시), 축=시도별 |
| `info --type PRD` | 수록주기 조회 | 월(1999.06~2026.05)·분기·년 |
| `indicator` | `indicator --jipyo-id N` | 엔드포인트 배선·인증·에러파싱 정상(err30=요청형식 정상, 데이터만 없음) |

## 4. 의도적 비목표 (매칭하지 않음)

- **`validate` 미추가** — 스킬 모델에선 에이전트가 곧 적합성 판정자. 도구화는 불필요한 세리머니.
- **벡터 `item_search` 미구현** — stdlib 범위 밖. 지자체 통계는 `list` 드릴다운(MT_ATITLE01)+`info`로 대체.
- **대형 로컬 카탈로그(11,758) 번들 안 함** — remote `search`는 항상 fresh. 정적 스냅샷은 staleness 리스크([[data-accuracy]]).
- **MCP 보일러플레이트 미도입** — 시범서비스 안내·출처 강제·형식 강제 문구 없이 순수 데이터 유지(스킬의 기존 강점 보존).
- **`indicator` jipyoId 발견 경로 없음** — MCP도 동일한 공통 한계(목록 API 미구현). 저우선.

## 5. 검증

- 결정론 코어: pytest **73 passed**(48 baseline 무회귀 + 25 신규). `test_parity_expansion.py`.
- 라이브 실측: 위 전 기능 실제 KOSIS API 호출로 확인. `region`은 초기 필드 가정(OBJ_NM) 오판을 라이브에서 실측 교정(지역명=ITM_NM).
- skill-creator: quick_validate 구조 PASS(유일 지적 `argument-hint`/`user-invocable`는 알려진 divergence — 결함 아님).
