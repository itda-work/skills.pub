# itda-data — 데이터 양심 vertical 스킬팩

데이터에서 **거짓 확신을 자동 차단**하는 게이트형 스킬팩입니다. 사용자 의도축으로
안내(`data-compass`) · 정리(`data-prep`) · 질문(`data-ask`) · 수식감사(`data-audit`) ·
수치검수(`data-verify`) 다섯 스킬을 제공합니다. (SPEC-DATA-VERTICAL-001, 확장 #952·#967·#1271)

## 스킬 목록

| 스킬 | 역할 | 출력 |
|------|------|------|
| [`data-compass`](skills/data-compass/SKILL.md) | 데이터 분석 **내비게이터(순수 코치)**. 처음 보는 데이터를 프로파일해 분석 지도(지형·경로·현재 위치)를 만들고, 매 단계 "이렇게 말해보세요" 복붙 지시문으로 안내. 분석은 실행하지 않고 다른 네 스킬로 라우팅(관제탑). 같은 데이터 → 같은 초기 지도(강의 재현성). | `<이름>-분석지도.md` + 요약 JSON |
| [`data-prep`](skills/data-prep/SKILL.md) | 엉망 CSV 구조 진단 + 원본 불변 정돈본 생성. 진단→[가설]→확인→정돈본. 헤더행·소계/빈행·빈열 + 값 정제(날짜·공백·중복)·가로전개(wide melt)·다중표 감지. | 진단 리포트 + `tidy_{해시}.csv` + 변환 로그 |
| [`data-ask`](skills/data-ask/SKILL.md) | 한국어 질문을 **실제 계산**으로 답하는 질문 스킬. NL→typed QueryPlan→결정론 SQL→duckdb 실행(눈대중 금지). 서술 질의는 즉시 실행, 추론(회귀·상관)은 표본·다중공선성 양심 게이트 통과 후 실행+독립검증. 소셀 N 자동 경고. cp949 무손실. | 실행 SQL + 결과 + 정직 보고(소셀 경고) |
| [`data-audit`](skills/data-audit/SKILL.md) | 엑셀 수식 오류·흔한 실수 감사. `#REF!`·하드코드(`=A1*1.05`)·범위 누락(off-by-one)·복붙 뭉갬·순환참조·깨진 링크. 보고 우선(확인 없이 셀 미변경). 파일=openpyxl 크로스플랫폼(Office 불필요). | 발견 테이블(Sheet·Cell·Severity·Category·Issue·Fix) + 요약 한 줄 / JSON |
| [`data-verify`](skills/data-verify/SKILL.md) | 엑셀·CSV **수치 검수**. 부분합↔총계 내부정합·원장 외부대조·값 규칙(음수/범위/중복/합계목표)·시트 간 교차참조. 보고 전용, 허용오차 명시(눈대중 금지). 파일=openpyxl(Office 불필요). | 검수 보고서(종류·위치·기대값·실제값·차이·심각도) + 요약 한 줄 |
| [`xlsx-recalc`](skills/xlsx-recalc/SKILL.md) | openpyxl 등이 만든 **캐시값 없는 xlsx 재계산**. LibreOffice(24.8 이상) 단독 — 대체 엔진 7종이 모두 에러 없이 틀려 1차 엔진을 두지 않는다. 계산 전 외부 링크 값 캐시·AF_UNIX·버전 확인, 계산 후 타입별 캐시·수식 보존 검증, 수식 표기 변경 보고. 원본 불변·새 파일. | 재계산 xlsx + JSON(에러 셀·외부 링크·수식 표기 변경) |

## 사용 시나리오

> "이 데이터 분석 어떻게 시작해?" → `data-compass`가 분석 지도를 만들고 다음 지시문을 안내(분석은 유저 지시로만)
> "이 엑셀 좀 정리해줘"(제목행·소계·빈열) → `data-prep`이 진단 후 정돈본 새 파일 생성
> "지역별 환불율 알려줘" → `data-ask`가 QueryPlan→실제 계산→정직 보고(소셀 경고 동반)
> "매출에 광고비가 영향 줘?"(추론) → `data-ask`가 표본·다중공선성 게이트 → 통과 시 회귀 실행+독립검증, 미달 시 거부
> messy 입력으로 질문 → `data-ask`가 `data-prep` preflight 호출 → 정돈본 재로드 후 답
> "이 시트 감사해줘"(수식 오류·하드코드·off-by-one) → `data-audit`가 위험 셀을 severity별로 보고
> "합계 검산해줘"·"원장이랑 대조해줘" → `data-verify`가 기대값 vs 실제값 vs 차이로 불일치 지적
> "openpyxl로 만든 엑셀 값이 빈칸이야" → `xlsx-recalc`가 수식 캐시값을 채운 새 파일 생성(LibreOffice)

## 환경 변수 / 의존성

- **환경 변수**: 없음. 외부 API 키·인증 불필요.
- **Python 의존성**:
  - `data-compass`: stdlib only (Python 3.10+).
  - `data-prep`: stdlib only (Python 3.10+).
  - `data-ask`: `duckdb>=1.3`(서술 SQL 실행, 항상). 추론 p-value·VIF는 `statsmodels` **lazy**(있을 때만, descriptive 경로 미로드). 없으면 다중공선성은 stdlib pairwise 상관으로 폴백. cp949 파일은 duckdb `encodings` 확장 최초 1회 온라인 설치(이후 오프라인).
  - `data-audit` · `data-verify`: `openpyxl>=3.1`(파일 감사·검수, 크로스플랫폼).
  - `xlsx-recalc`: stdlib only. LibreOffice 24.8 이상(`soffice`) 필요.
  - 설치: 각 스킬의 `scripts/requirements.txt` 참조.

## 보안

`data-ask` 실행기는 코드 강제: `enable_external_access=false`(네트워크·디스크쓰기·확장설치 차단) · SELECT-only · 강제 LIMIT · plan 리터럴 파라미터 바인딩(인젝션 차단) · 원본 인메모리 적재(원본 경로 미전달).

`data-audit`·`data-verify`는 **보고 전용** — 확인 없이 셀·값을 바꾸지 않고, 사용자가 특정 발견의 수정을 요청할 때만 해당 셀만 고치며 원본 백업을 남긴다.

## 로컬 테스트

```bash
claude --plugin-dir itda-data
# 스킬별 테스트(배포 방식): python3 -m pytest itda-data/skills/<skill>/tests/   # <skill>: data-compass · data-prep · data-ask · data-audit · data-verify · xlsx-recalc
```

## 설치

```bash
claude plugin marketplace add itda-work/skills.pub
claude plugin install itda-data@itda-skills-pub
```

## 구현 기준

- 현재 동작 기준: 각 스킬의 `SKILL.md`, `scripts/`, `tests/`, `requirements.txt`
- 정본 thesis: SPEC-DATA-VERTICAL-001 (구 ADVISOR/TIDY/RUNNER SPEC은 Superseded 히스토리). `data-audit`(#952, Claude for Excel `audit-xls` 이식)·`data-verify`(#967)는 vertical 확장.

## 라이선스

MIT (plugin.json 및 각 SKILL.md frontmatter 일치).
