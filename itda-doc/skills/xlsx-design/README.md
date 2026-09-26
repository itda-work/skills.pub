# xlsx-design

수치 데이터 → **디자인된 Excel 통합문서(.xlsx)** 를 크로스플랫폼(Office 불필요)으로 신규 생성하는 스킬. `pptx-design`/`docx-design` 의 xlsx 형제이며 **design-core** 매체중립 토큰을 공유한다.

## 핵심
- **백엔드 = openpyxl**(macOS/Linux/Windows, Office 불필요). 수식 실계산은 `itda-data:xlsx-recalc`.
- **디자인 프리셋**: `../design-core/library/` 8종(consulting-mbb·warm-editorial·print-broadsheet·minimal-mono 등).
- **★한글 셀 폰트 가드**: 한글 셀 = Korean-capable 폰트(Malgun Gothic 우선), 라틴/숫자 셀 = 디스플레이 폰트(셀 단위 분기).
- **디자인 요소**: 헤더 fill·zebra·테두리·숫자서식·**조건부서식(의미색)**·**차트 팔레트**·freeze·열폭.
- **검증 게이트(HARD)**: 빈통합문서·토큰누락·한글 비안전폰트 셀 == 0.

## 빠른 시작
```bash
py -3 -m pip install -r requirements.txt
cd examples/sample
py -3 gen.py consulting-mbb           # 또는 warm-editorial / print-broadsheet / minimal-mono
py -3 ../../scripts/verify.py novatech-consulting-mbb.xlsx --tokens tokens.txt
```

## 구조
- `scripts/sheetkit.py` — 공개 헬퍼 API(통합문서·표·KPI·조건부서식·차트 + 한글 폰트 가드)
- `scripts/verify.py` — HARD GATE 검증기 · `scripts/render.py` — Excel COM/LibreOffice 렌더
- `examples/sample/` — NovaTech FY2025 동작 예제(요약·분기추이·리스크 3시트)
- `references/design-md-mapping.md` — 토큰 → Excel 매핑 + 재현 카탈로그

토큰↔Excel 스타일 대응은 `../design-core/mapping/xlsx.md`. 오케스트레이션은 `SKILL.md` 5관문.

> SPEC-OFFICE-DOC-GEN-DEEPEN-001 P5 (#662) — #655 벤치마크 "xlsx 디자인 생성기 부재" 격차를 pptx-design 패턴 복제로 해소.
