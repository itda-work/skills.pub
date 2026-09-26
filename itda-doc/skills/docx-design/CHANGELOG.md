# Changelog — docx-design

## [0.4.0] — 2026-09-25 (itda-work/itda-hyve#6)

### Removed

- hyve 앱 폐기에 따라 **옵션 백엔드(hyve Word COM 보강·`office_compute`) 절**과 `references/hyve-com-option-backend.md` 를 뺐다. 코멘트·변경추적·TOC 필드는 비목표로 적는다. 기본 경로(python-docx)는 그대로. 지운 pptx-design 절을 가리키던 “백엔드 정책 (REQ-010 미러)” 제목을 “백엔드” 로.

## [0.3.4] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash, mcp__workspace__web_fetch) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.3.3] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## 0.3.2 (2026-07-11)

표준 DESIGN.md 직해석 경로 명시 (#1021).

- 관문2 에 "표준 DESIGN.md(Stitch/getdesign) 제공 시" 분기 신설 — `design_core.load()` 비대상(자동 매핑이 원문을 깎음), 원문 직해석으로 핵심 hex 를 `gen.py` 에 직접 인용, 한글 eastAsia 분리 바인딩은 dockit 이 그대로 방어. 반복 파이프라인은 v2 경로 유지. 레퍼런스에 getdesign 차용 포인터 추가.

## 0.3.1 (2026-07-06)

MCP 온보딩 정본화 (hyve#921).

- 옵션 백엔드 Prerequisites 의 배포 안내를 폐지된 전체 `/mcp`+Bearer 에서 **hyve 설정 > MCP 탭의 문서(office) 프리셋 등록**(`/mcp/office`, hyve#852·#887)으로 교체. stdio `hyve mcp` 는 개발·검증 전용 명시. `references/hyve-com-option-backend.md` 표 동반 갱신.

## 0.3.0 (2026-06-29)

옵션 백엔드(hyve Word COM) 실연동 — 길X 레시피 명문화 (#669, SPEC-OFFICE-DOC-GEN-DEEPEN-001 후속).

- **옵션 백엔드 절 신설**(SKILL.md): 1급(python-docx) 생성 후 **코멘트·변경추적·TOC 필드**를 hyve Office MCP(`office_compute`)로 보강하는 **길X 레시피**(에이전트→MCP→raw→스킬 Python 후처리) + Prerequisites(hyve 가동·`.mcp.json`). 기존 "비목표→안내" 프레이밍을 실동작 레시피로 승격.
- **verb 카탈로그 reference** `references/hyve-com-option-backend.md`: word.* file-based verb 인자 키(`add_comment`{path,text,author}·`set_track_changes`{enabled}·`get_revisions`·`accept/reject_revision`·`add_toc`·`add_field`·`update_fields`·`find_replace_text`{track}) 엔진(`WordComEngine.WriteReview/WriteStructure.cs`) 실측 + 도달성.
- **실증(AC-6/#669)**: NovaTech 1급 docx 에 변경추적 ON→추적 치환→코멘트 적용, `get_comments`(1)·`get_revisions`(delete+insert) 읽기검수 + Word COM 렌더로 말풍선·변경 바 시각 확인. 1급 디자인 비퇴행.
- 동반(hyve Go MCP): `office_compute` 에 generic `params`(타입 보존 JSON) 패스스루 추가 → file-based COM verb(코멘트·변경추적·TOC)가 에이전트→MCP 로 도달. 세션 기반 verb 는 후속 #670.

## 0.2.0 (2026-06-29)

8 프리셋 전체 확장 + 다크 프리셋 가독성 (#668, SPEC-OFFICE-DOC-GEN-DEEPEN-001 후속).

- **대비(가독성) 게이트 추가** `verify.py` (F): run 글자색 ↔ 효과적 배경(run/단락/셀 음영 → 페이지 흰색) WCAG 대비 측정 → **3.0:1 미만 HARD FAIL**, 3.0~4.5 advisory. 네거티브 테스트로 실효성 확인(라이트 위 거의-흰 텍스트 = FAIL). HARD GATE = (빈문서 + 토큰누락 + 한글 미바인딩 + **저대비**) == 0.
- **다크 프리셋 샌드위치**: design-core 0.4.0 정규화로 8 프리셋(다크 3 포함) 전부 라이트 본문에서 가독. `dockit.apply_design`/`kpi_strip` 가 헤딩·KPI 값에 `primary_text`(보정 브랜드색) 사용 — 골드/그린 등 저대비 브랜드색이 흰 본문 위에서 읽히게. 표지/클로징 다크 밴드는 fill(`primary`/`ink`)+`on_color` 로 정체성 유지.
- **8 프리셋 검증**: consulting-mbb·warm-editorial·print-broadsheet·minimal-mono·samsung-sds·equity-research-dark·tech-vivid-dark·kari 전부 Word COM 렌더 + HARD GATE PASS + 시각 구별. (이전 0.1.0 은 핵심 4종만.) warm-editorial 의 잠복 저대비(zebra 위 의미색)도 대비 게이트가 적발·해소.
- 예제 `gen.py`: 강조 텍스트는 `PRIMARY_TEXT`(보정), 밴드 fill 은 `PRIMARY`/`INK`(원본) 로 분리.
- 동반: design-core 0.4.0(샌드위치 정규화·대비 유틸·`primary_text`/`is_dark`), `mapping/docx.md` 다크 정책 명문화.

## 0.1.0 (2026-06-29)

신규 스킬 (SPEC-OFFICE-DOC-GEN-DEEPEN-001, #662). `pptx-design` 패턴을 docx 에 복제 — #655 벤치마크의 "docx 디자인 생성기 부재" 격차 해소.

- **dockit** 공개 헬퍼 API (python-docx 래퍼): `new_doc`·`apply_design`·`heading`·`body`·`kicker`·`bullet_list`·`rule`·`add_table`(헤더 fill+zebra+테두리)·`callout`·`band`·`kpi_strip`·`set_footer`(PAGE/NUMPAGES)·`save_doc`.
- **★한글 East Asian 분리 바인딩**: `set_run_font` 가 `w:rFonts` 를 ascii/hAnsi(라틴) ↔ eastAsia(안전 한글 고딕)로 분리(pptx 가드 verbatim 이식이 아닌 docx 맥락 재설계). 음수 자간 클램프 불요(Word 정상 처리).
- **검증 게이트** `verify.py`: HARD GATE = (빈문서 + 토큰누락 + 한글 eastAsia 미바인딩) == 0. advisory: 라틴 eastAsia 의심·헤딩 0·빈 셀·빈 페이지·렌더 불가.
- **렌더** `render.py`: Windows=Word COM, 그 외=LibreOffice → PDF → PyMuPDF PNG.
- **백엔드 정책**: python-docx 1급(크로스플랫폼), hyve COM/OpenXML 옵션(pptx-design REQ-010 미러).
- **예제** `examples/sample/`: NovaTech FY2025 연차보고서. 핵심 4 프리셋(consulting-mbb·warm-editorial·print-broadsheet·minimal-mono) 전부 HARD GATE PASS, 한글 run 42개 eastAsia 바인딩 OK, 시각 다양성 확인.
- design-core 에 `docx_styles()` 어댑터 + `mapping/docx.md` 동반 추가(design-core 0.2.0).
