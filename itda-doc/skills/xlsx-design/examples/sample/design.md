# 적용 디자인 — design-core 프리셋 참조

자체 DESIGN.md 없이 **design-core 라이브러리 프리셋**을 그대로 적용한다(형제 스킬, SSoT).

- 기본 프리셋: `consulting-mbb`
- 교체: `gen.py <preset>` 인자 또는 `XLSX_DESIGN_PRESET` 환경변수
  - 권장 핵심 4종: `consulting-mbb` · `warm-editorial` · `print-broadsheet` · `minimal-mono`
- 토큰 → Excel 스타일 매핑: `../../../design-core/mapping/xlsx.md`
- 한글: sheetkit 이 한글 셀을 Korean-capable 폰트(Malgun Gothic 우선)로 보장.
- 차트 색: `xlsx_styles()["chart_palette"]`(primary→accent→up→down→muted) 사용.
