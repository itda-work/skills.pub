# docx-design

콘텐츠 마크다운 + 수치 데이터 → **디자인된 Word 문서(.docx)** 를 크로스플랫폼(Office 불필요)으로 신규 생성하는 스킬. `pptx-design` 의 docx 형제이며 **design-core** 매체중립 토큰을 공유한다.

## 핵심
- **백엔드 = python-docx**(macOS/Linux/Windows, Office 불필요).
- **디자인 프리셋**: `../design-core/library/` 8종을 그대로 적용(consulting-mbb·warm-editorial·print-broadsheet·minimal-mono 등).
- **★한글 eastAsia 분리 바인딩**: run 의 `w:rFonts` 를 라틴(ascii/hAnsi) ↔ 한글(eastAsia 안전 고딕)로 분리 — 세리프 라틴 헤드 + 고딕 한글이 깔끔히 공존(pptx LibreOffice 경로가 못 하던 것).
- **검증 게이트(HARD)**: 빈문서·토큰누락·한글 eastAsia 미바인딩 == 0.

## 빠른 시작
```bash
py -3 -m pip install -r requirements.txt
cd examples/sample
py -3 gen.py consulting-mbb              # 또는 warm-editorial / print-broadsheet / minimal-mono
py -3 ../../scripts/verify.py novatech-consulting-mbb.docx --tokens tokens.txt
```

## 구조
- `scripts/dockit.py` — 공개 헬퍼 API(문서·헤딩·표·콜아웃·KPI·밴드·푸터 + eastAsia 바인딩)
- `scripts/verify.py` — HARD GATE 검증기 · `scripts/render.py` — Word COM/LibreOffice 렌더
- `examples/sample/` — NovaTech FY2025 동작 예제(content·data·design·gen)
- `references/design-md-mapping.md` — 토큰 → docx 3열 필터 + 재현 카탈로그

자세한 오케스트레이션은 `SKILL.md` 의 5관문을 따른다. 토큰↔Word 스타일 대응은 `../design-core/mapping/docx.md`.

> SPEC-OFFICE-DOC-GEN-DEEPEN-001 (#662) — #655 벤치마크에서 드러난 "docx 디자인 생성기 부재" 격차를 pptx-design 패턴 복제로 해소.
