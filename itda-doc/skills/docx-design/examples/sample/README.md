# 예제 — NovaTech FY2025 연차 실적 보고서

docx-design 의 동작 예제(정식 gen.py 레퍼런스). NovaTech Inc. 는 디자인 테스트용 **가상 기업**이다(실재 아님).

## 입력 (SSoT 3종)
- `content.md` — 섹션 콘텐츠 명세(고정)
- `data.json` — 수치 데이터(표·KPI)
- `design.md` — 적용 디자인(design-core 프리셋 참조)

## 실행
```bash
py -3 gen.py consulting-mbb            # 기본
py -3 gen.py warm-editorial            # 프리셋 교체 → 시각 다양성
py -3 gen.py equity-research-dark      # 다크 프리셋(샌드위치)
# ... 8 프리셋 전부 동작: print-broadsheet · minimal-mono · samsung-sds · tech-vivid-dark · kari
# 검증 + 렌더
printf '%s\n' NovaTech FY2025 '핵심 요약' 'Cloud Platform' '$4.82B' > tokens.txt
py -3 ../../scripts/verify.py novatech-consulting-mbb.docx --tokens tokens.txt
```

## 실측 결과 (2026-06-29, #662 핵심 4 + #668 전체 8)
동일 콘텐츠·데이터를 **8 프리셋 전부**로 생성 → 전부 **HARD GATE PASS**(한글 eastAsia 바인딩 + **대비 게이트**), 시각적으로 구별.

| 프리셋 | 정체성 | 라틴 디스플레이 | 다크? | 표현 |
|---|---|---|---|---|
| consulting-mbb | 네이비 임원 보고 | sans | — | 네이비 표지/클로징 밴드 + 라이트 본문 |
| warm-editorial | 코랄/틸/크림 | **serif** | — | 코랄 밴드 + 크림 zebra |
| print-broadsheet | 잉크블루 저널 | **serif** | — | 잉크블루 밴드(밀도형) |
| minimal-mono | 블랙/블루 미니멀 | sans | — | 블랙 밴드 + 미니멀 |
| samsung-sds | Samsung Blue 코퍼레이트 | sans | — | 블루 밴드 + 화이트 본문 |
| equity-research-dark | 트레이딩 골드/블랙 | mono | **다크** | **샌드위치** — 골드 밴드/헤더·헤딩, 라이트 본문 |
| tech-vivid-dark | 비비드 그린 테크 | sans(굵게) | **다크** | **샌드위치** — 그린 밴드/액센트, 라이트 본문 |
| kari | 딥스페이스 로열블루 | sans | **다크** | **샌드위치** — 인디고 밴드, 라이트 본문 |

세리프 프리셋에서 "NovaTech FY2025"(세리프 라틴) + "연차 실적 보고서"(고딕 한글)가 같은 제목에서 깔끔히 공존 — eastAsia 분리 바인딩의 이득.

**다크 프리셋(equity·tech-vivid·kari)** 은 docx 매체 한계(인쇄 가능한 페이지 배경 없음)로 **샌드위치**(표지/클로징 다크 밴드 + 라이트 본문) 로 렌더된다. 본문 텍스트·표·불릿은 흰 배경 위에서 가독하도록 design-core 가 토큰을 보정하고, `verify.py` 대비 게이트가 3.0:1 미만을 HARD 로 차단한다. 정책 SSoT: `design-core/mapping/docx.md`.

> 생성 산출물(`novatech-*.docx`·`_verify/`·`tokens.txt`)은 `.gitignore` 로 제외(재생성 가능).
