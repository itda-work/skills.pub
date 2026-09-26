# 예제 — NovaTech FY2025 실적 통합문서

xlsx-design 의 동작 예제(정식 gen.py 레퍼런스). NovaTech Inc. 는 디자인 테스트용 **가상 기업**(실재 아님). docx-design 예제와 동일 데이터.

## 입력
- `content.md` — 시트 콘텐츠 명세 · `data.json` — 수치 데이터 · `design.md` — 적용 디자인

## 실행
```bash
py -3 gen.py consulting-mbb            # 8 프리셋 전부 동작(이름만 교체)
py -3 gen.py equity-research-dark      # 다크 프리셋(샌드위치 — 브랜드 표지 밴드 + 라이트 본문)
printf '%s\n' NovaTech FY2025 '사업부별 실적' 'Cloud Platform' > tokens.txt
py -3 ../../scripts/verify.py novatech-consulting-mbb.xlsx --tokens tokens.txt
```

## 실측 결과 (2026-06-29, #662 핵심 4 + #668 전체 8)
동일 데이터를 **8 프리셋 전부**로 생성 → 전부 **HARD GATE PASS**(한글 Korean-capable + **대비 게이트**), 표지 밴드·헤더·차트 팔레트가 프리셋별로 시각 구별.

| 프리셋 | 표지 밴드/헤더 | 제목 폰트 | 다크? |
|---|---|---|---|
| consulting-mbb | 네이비/아이스블루 | sans | — |
| warm-editorial | 코랄/틸 | serif | — |
| print-broadsheet | 잉크블루 | serif | — |
| minimal-mono | 블랙/블루 | sans | — |
| samsung-sds | Samsung Blue | sans | — |
| equity-research-dark | 골드 | mono | **다크(샌드위치)** |
| tech-vivid-dark | 비비드 그린 | sans | **다크(샌드위치)** |
| kari | 로열블루/시안 | sans | **다크(샌드위치)** |

3시트(요약·분기추이·리스크), 차트(막대·라인), 조건부서식, freeze panes 포함. 다크 프리셋은 **샌드위치**(브랜드 표지 밴드 + 라이트 데이터 시트) — 스프레드시트 가독·인쇄를 위해 전면 다크를 피한다. 셀 글자색↔채움색 대비를 `verify.py` 가 강제(<3.0:1 HARD). 정책: `design-core/mapping/xlsx.md`.

> 생성 산출물(`novatech-*.xlsx`·`_verify/`·`tokens.txt`)은 `.gitignore` 로 제외(재생성 가능).
