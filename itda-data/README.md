# itda-data — 데이터 양심 vertical 스킬팩

데이터에서 **거짓 확신을 자동 차단**하는 게이트형 스킬팩입니다. 엑셀 수식감사(`data-audit`) · 수치검수(`data-verify`) ·
재계산(`xlsx-recalc`)과 외부 AI 반입 전 비식별(`pii-redact`·`biz-redact`)을 제공합니다. (SPEC-DATA-VERTICAL-001, 확장 #952·#967·#1271)

> 에이전트 `cs-batch-extractor`·`data-profiler` 는 저장소에서 지웠습니다(git 이력에는 남아 있음). 데이터 정리·질의·CS 분석은 Claude 에게 바로 요청하세요.

## 스킬 목록

| 스킬 | 역할 | 출력 |
|------|------|------|
| [`data-audit`](skills/data-audit/SKILL.md) | 엑셀 수식 오류·흔한 실수 감사. `#REF!`·하드코드(`=A1*1.05`)·범위 누락(off-by-one)·복붙 뭉갬·순환참조·깨진 링크. 보고 우선(확인 없이 셀 미변경). 파일=openpyxl 크로스플랫폼(Office 불필요). | 발견 테이블(Sheet·Cell·Severity·Category·Issue·Fix) + 요약 한 줄 / JSON |
| [`data-verify`](skills/data-verify/SKILL.md) | 엑셀·CSV **수치 검수**. 부분합↔총계 내부정합·원장 외부대조·값 규칙(음수/범위/중복/합계목표)·시트 간 교차참조. 보고 전용, 허용오차 명시(눈대중 금지). 파일=openpyxl(Office 불필요). | 검수 보고서(종류·위치·기대값·실제값·차이·심각도) + 요약 한 줄 |
| [`pii-redact`](skills/pii-redact/SKILL.md) | 정형 개인정보(전화·이메일·주민번호 등) 결정론 마스킹 — 외부 AI 반입 전 입구 게이트. | 마스킹본 + 치환 로그 |
| [`biz-redact`](skills/biz-redact/SKILL.md) | 용어집 기반 영업기밀 마스킹·복원 — 외부 AI 반입 전 비식별, 돌아온 결과 복원. | 마스킹본 + 매핑 / 복원본 |
| [`xlsx-recalc`](skills/xlsx-recalc/SKILL.md) | openpyxl 등이 만든 **캐시값 없는 xlsx 재계산**. LibreOffice(24.8 이상) 단독 — 대체 엔진 7종이 모두 에러 없이 틀려 1차 엔진을 두지 않는다. 계산 전 외부 링크 값 캐시·AF_UNIX·버전 확인, 계산 후 타입별 캐시·수식 보존 검증, 수식 표기 변경 보고. 원본 불변·새 파일. | 재계산 xlsx + JSON(에러 셀·외부 링크·수식 표기 변경) |

## 사용 시나리오

> "이 시트 감사해줘"(수식 오류·하드코드·off-by-one) → `data-audit`가 위험 셀을 severity별로 보고
> "합계 검산해줘"·"원장이랑 대조해줘" → `data-verify`가 기대값 vs 실제값 vs 차이로 불일치 지적
> "openpyxl로 만든 엑셀 값이 빈칸이야" → `xlsx-recalc`가 수식 캐시값을 채운 새 파일 생성(LibreOffice)

## 환경 변수 / 의존성

- **환경 변수**: 없음. 외부 API 키·인증 불필요.
- **Python 의존성**:
  - `data-audit` · `data-verify`: `openpyxl>=3.1`(파일 감사·검수, 크로스플랫폼).
  - `xlsx-recalc`: stdlib only. LibreOffice 24.8 이상(`soffice`) 필요.
  - 설치: 각 스킬의 `scripts/requirements.txt` 참조.

## 보안

`data-audit`·`data-verify`는 **보고 전용** — 확인 없이 셀·값을 바꾸지 않고, 사용자가 특정 발견의 수정을 요청할 때만 해당 셀만 고치며 원본 백업을 남긴다.

## 로컬 테스트

```bash
claude --plugin-dir itda-data
# 스킬별 테스트(배포 방식): python3 -m pytest itda-data/skills/<skill>/tests/   # <skill>: biz-redact · data-audit · data-verify · pii-redact · xlsx-recalc
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
