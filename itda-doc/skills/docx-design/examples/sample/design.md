# 적용 디자인 — design-core 프리셋 참조

본 예제는 자체 DESIGN.md 를 두지 않고 **design-core 라이브러리 프리셋**을 그대로 적용한다(형제 스킬, SSoT).

- 기본 프리셋: `consulting-mbb` (네이비 임원 보고 톤 — 연차 보고서에 적합)
- 교체: `gen.py <preset>` 인자 또는 `DOCX_DESIGN_PRESET` 환경변수로 핵심 프리셋 교체
  - 권장 핵심 4종: `consulting-mbb` · `warm-editorial` · `print-broadsheet` · `minimal-mono`
- 토큰 → Word 스타일 매핑: `../../../design-core/mapping/docx.md`
- 한글: dockit 이 eastAsia 안전 고딕(Malgun Gothic 우선)로 분리 바인딩(라틴 디스플레이는 ascii/hAnsi).

> 조직 브랜드 박제가 필요하면 design-core 의 프리셋을 복사해 `colors`/`motif` 만 치환한 `<org>.design.md` 를 만들어 `gen.py <path>` 로 넘기면 된다.
