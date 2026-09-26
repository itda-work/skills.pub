# Changelog — xlsx-design

## [0.4.0] — 2026-09-25 (itda-work/itda-hyve#6)

### Removed

- hyve 앱 폐기에 따라 **옵션 백엔드(hyve Excel COM 보강·`office_compute`) 절**과 `references/hyve-com-option-backend.md` 를 뺐다. 수식 실계산은 `itda-data:xlsx-recalc` 로 안내하고, 피벗·고급 조건부서식은 비목표로 적는다. 기본 경로(openpyxl)는 그대로. 지운 pptx-design 절을 가리키던 “백엔드 정책 (REQ-010 미러)” 제목을 “백엔드” 로.

## [0.3.5] — 2026-09-13 (이슈 #1690)

### Changed

- `[책임 경계]` 추가 · "이 스킬을 쓰지 않을 때" 절 신설 — 수식 캐시값 재계산은 `itda-data-analysis:xlsx-recalc` 로 안내.

## [0.3.4] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash, mcp__workspace__web_fetch) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## 0.3.3 (2026-07-26) — 이슈 #1279

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## 0.3.2 (2026-07-11)

표준 DESIGN.md 직해석 경로 명시 (#1021).

- 관문2 에 "표준 DESIGN.md(Stitch/getdesign) 제공 시" 분기 신설 — `design_core.load()` 비대상, 원문 직해석으로 핵심 hex 를 `gen.py` 에 직접 인용, 한글 셀 안전 폰트(sheetkit)는 그대로 방어. 반복 파이프라인은 v2 경로 유지. 레퍼런스에 getdesign 차용 포인터 추가.

## 0.3.1 (2026-07-06)

MCP 온보딩 정본화 (hyve#921).

- 옵션 백엔드 Prerequisites 의 배포 안내를 폐지된 전체 `/mcp`+Bearer 에서 **hyve 설정 > MCP 탭의 문서(office) 프리셋 등록**(`/mcp/office`, hyve#852·#887)으로 교체. stdio `hyve mcp` 는 개발·검증 전용 명시. `references/hyve-com-option-backend.md` 표 동반 갱신.

## 0.3.0 (2026-06-29)

옵션 백엔드(hyve Excel COM) 실연동 — 길X 레시피 명문화 (#669, SPEC-OFFICE-DOC-GEN-DEEPEN-001 후속).

- **옵션 백엔드 절 신설**(SKILL.md): 1급(openpyxl) 생성 후 **수식 실계산**(openpyxl 미계산 격차)을 hyve Office MCP(`office_compute` recalc/get_computed)로 보강하는 **길X 레시피** + Prerequisites. 피벗·고급 CF 는 session-based(후속 #670)임을 도달성으로 명시.
- **verb 카탈로그 reference** `references/hyve-com-option-backend.md`: file-based(`recalc`·`get_computed`·`render`) vs session-based(`add_pivot_table`·`add_cf_*`) 구분 + 인자 키(`ExcelMethodHandler.cs` 실측).
- **실증(AC-2)**: NovaTech 1급 xlsx 에 `=SUM`/`=SUMPRODUCT` 라이브 수식(pre-recalc 캐시 `None` 확인) → `recalc`(Excel COM) → 4.82·31.29 실계산값 `get_computed`/openpyxl 검수, 디스크 영속화 확인. 1급 비퇴행.
- 동반(hyve Go MCP): `office_compute` generic `params` 패스스루(docx 와 공유). 수식 실계산은 file-based 라 오늘 도달.

## 0.2.0 (2026-06-29)

8 프리셋 전체 확장 + 다크 프리셋 가독성 (#668, SPEC-OFFICE-DOC-GEN-DEEPEN-001 후속).

- **대비(가독성) 게이트 추가** `verify.py` (F): 셀 글자색 ↔ 채움색(없으면 흰 시트) WCAG 대비 → **3.0:1 미만 HARD FAIL**, 3.0~4.5 advisory. 조건부서식(up/down)은 렌더 시 Excel 적용이라 정적 셀은 `ink` 가독 유지(거짓양성 없음). HARD GATE = (빈통합문서 + 토큰누락 + 한글 비안전폰트 + **저대비**) == 0.
- **다크 프리셋 샌드위치**: design-core 0.4.0 정규화로 8 프리셋(다크 3 포함) 전부 라이트 시트에서 가독. `sheetkit.kpi_block` 값·`title_block` 텍스트가 `primary_text`(보정) 사용.
- **`title_block` fill-aware**: fill(밴드)이면 `on_color(fill)` 자동 글자색, 없으면 `primary_text`. 예제 표지 제목을 **브랜드 밴드**(`fill=primary`)로 — docx 표지 밴드와 샌드위치 동형(다크 프리셋도 안전).
- **8 프리셋 검증**: 4 핵심 + samsung-sds·equity-research-dark·tech-vivid-dark·kari 전부 Excel COM 렌더 + HARD GATE PASS + 시각 구별(브랜드 밴드·헤더·차트 팔레트).
- 동반: design-core 0.4.0, `mapping/xlsx.md` 다크 정책 명문화.

## 0.1.0 (2026-06-29)

신규 스킬 (SPEC-OFFICE-DOC-GEN-DEEPEN-001 P5, #662). `pptx-design`/`docx-design` 패턴을 xlsx 에 복제 — #655 벤치마크의 "xlsx 디자인 생성기 부재" 격차 해소.

- **sheetkit** 공개 헬퍼 API (openpyxl 래퍼): `new_book`·`apply_design`·`set_cell`·`title_block`·`styled_header`·`data_table`(헤더 fill+zebra+테두리+숫자서식)·`kpi_block`·`semantic_rules`(조건부서식)·`add_bar_chart`/`add_line_chart`(팔레트)·`set_columns`·`freeze`·`save_book`.
- **★한글 셀 폰트 가드**: Excel 은 셀 단일 폰트라 docx 의 eastAsia 분리 대신 "한글 셀 = Korean-capable 폰트(Malgun Gothic 우선)" 보장. 라틴/숫자 셀은 디스플레이 폰트로 셀 단위 분기.
- **검증 게이트** `verify.py`: HARD GATE = (빈통합문서 + 토큰누락 + 한글 비안전폰트 셀) == 0. advisory: 스타일 헤더 0·차트 0·빈 페이지·렌더 불가. 네거티브 테스트로 실효성 확인.
- **렌더** `render.py`: Windows=Excel COM(fit-to-width), 그 외=LibreOffice → PDF → PyMuPDF PNG.
- **백엔드 정책**: openpyxl 1급(크로스플랫폼), hyve Excel COM/OpenXML 옵션(피벗·CF 11종·실계산엔진).
- **예제** `examples/sample/`: NovaTech FY2025(요약·분기추이·리스크 3시트). 핵심 4 프리셋 전부 HARD GATE PASS, 한글 셀 27개 안전, 조건부서식·차트 팔레트 프리셋별 시각 구별.
- design-core 에 `xlsx_styles()` 어댑터 + `mapping/xlsx.md` 동반(design-core 0.3.0).
