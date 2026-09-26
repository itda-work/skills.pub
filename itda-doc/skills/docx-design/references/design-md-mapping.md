# DESIGN.md / design-core 토큰 → DOCX 매핑 가이드

design-core 매체중립 토큰을 Word 문서로 옮기는 방법과 **무엇이 잘 넘어오고 무엇이 막히는가**를 정리한다. 진입점·토큰↔스타일 대응의 SSoT 는 `../../design-core/mapping/docx.md`, 코드 SSoT 는 `../scripts/dockit.py` 다.

> **천장 규칙(한 줄)**: 정체성이 **색·헤딩 위계·표 스타일·간격 리듬**에 살면 높은 재현. **모서리 반경·그라디언트·모션**은 흐름 문서의 천장이다. pptx 와 달리 **한글은 Word 네이티브 정상 렌더**이므로 가장 큰 리스크는 "한글 폰트 폴백"이 아니라 **eastAsia 미바인딩**(라틴 폰트가 한글 글리프 잠식)이다.

---

## 1. 토큰 매핑 표 (토큰 → DOCX 3열 필터)

`scripts/dockit.py` 헬퍼 기준(`dk` = dockit).

| 토큰 | ① docx 적용 (라틴/일반) | ② 한글 적용 | ③ 필터(불가/금지) |
|---|---|---|---|
| **color.* (hex)** | `apply_design` 헤딩색·`add_table` 헤더 fill·`callout` 바·`set_run_font(color=)` 에 hex 1:1 ✅ | 동일(색은 글자 언어 무관) ✅ | — |
| **font.display (라틴)** | 헤딩·KPI 라틴 run `w:ascii`/`w:hAnsi` ✅ (세리프도 그대로 — Word 정상) | ▣ 한글엔 적용 안 함 | — |
| **font.body (kr-safe-gothic)** | 라틴 본문 = display, 한글 = eastAsia 안전 고딕 분리 | **`w:eastAsia` = `kr_font_name()`**(Malgun Gothic 우선) ✅ | ▣ eastAsia 미바인딩 = HARD FAIL |
| **type_scale (pt)** | 헤딩/본문 `w:sz` ✅ | 동일 ✅ | — |
| **semantic.up/down** | 표·KPI 수치 강조 색 ✅ | 동일 ✅ | — |
| **space.margin/gap (inch)** | 페이지 여백(`pgMar`)·문단 간격 ✅ | 동일 ✅ | — |
| **표 헤더 fill·zebra·테두리** | `dk.add_table`(`w:shd`·`w:tblBorders`) ✅ | 동일 ✅ | — |
| **헤더/푸터·페이지번호** | `dk.set_footer`(PAGE/NUMPAGES 필드) ✅ | 동일 ✅ | — |
| **radius (모서리 반경)** | — | — | ▣ Word 단락/표에 반경 개념 없음(무시) |
| **gradient / glow / motif** | Pillow PNG 인라인 임베드(표지 한정) ⚠️ | 동일 | ▣ 네이티브 도형 그라디언트 비1급, 풀블리드 흐름 제약 |
| **letterSpacing (음수)** | 라틴 트래킹 `w:spacing`(음수 허용 — Word 정상) ✅ | 한글도 허용(클램프 불요) | — (pptx 의 음수 자간 클램프는 docx 에 불필요) |
| **OpenType (tnum/ss01)** | Word 는 지원(`w:rFonts` 고급)하나 dockit 1급 미적용 ⚠️ | 동일 | 🔜 후속 |
| **do / don't** | 생성 규칙 반영(함정 체크리스트) ✅ | 동일 ✅ | — |

### 1.1 ★한글 eastAsia 분리 바인딩 (pptx 가드와의 차이 — 실증)

| | pptx-design (LibreOffice 타깃) | docx-design (Word 타깃) |
|---|---|---|
| 문제 | 한글에 세리프/thin 폰트 → LibreOffice 가 명조/붓글씨로 폴백 | 라틴 디스플레이 폰트가 한글 글리프 잠식(eastAsia 미지정 시) |
| 가드 | `set_run_font`: 비안전 폰트 강제 교체 + 음수 자간 0 클램프 | `set_run_font`: `w:rFonts` ascii/hAnsi(라틴) ↔ eastAsia(한글) **분리 바인딩** |
| 음수 자간 | 한글 0 으로 클램프(LibreOffice 결함) | **클램프 불요**(Word 정상 처리) |
| 세리프 라틴 + 한글 | 한 헤드라인에 이질 페어링(누수) | **세리프 라틴 + 고딕 한글 깔끔히 공존**(분리 바인딩의 이득) |

실증(2026-06-29, #662): NovaTech 동일 콘텐츠를 핵심 4 프리셋으로 생성 → warm-editorial·print-broadsheet(세리프 라틴 디스플레이)에서 "NovaTech FY2025"(세리프) + "연차 실적 보고서"(고딕)가 같은 제목에서 깔끔히 공존. 4종 모두 한글 run 42개 eastAsia 바인딩 OK·HARD GATE PASS.

확장(2026-06-29, #668): 나머지 4 프리셋(samsung-sds·equity-research-dark·tech-vivid-dark·kari)까지 8 프리셋 전부 Word COM 렌더 + HARD GATE PASS + 시각 구별. 다크 3종(equity·tech-vivid·kari)은 **샌드위치 정책**(표지/클로징 다크 밴드 + 라이트 본문)으로 렌더된다 — docx 는 페이지 배경을 인쇄할 수 없어 전면 다크 본문이 불가하기 때문(`design-core/mapping/docx.md` 정책 참조). 라이트 본문 위 텍스트 가독은 `verify.py` 대비 게이트(F)가 강제한다.

`verify.py` 의 (C) 검사가 한글 run 의 eastAsia 미바인딩을 **HARD** 로, 라틴 폰트 eastAsia 바인딩을 **advisory** 로 적발한다. (F) 대비 검사는 라이트 본문 위 텍스트 대비가 3.0:1 미만이면 **HARD** 로 막는다.

---

## 2. 재현 잘됨 vs 한계 (docx 매체)

### ✅ DOCX 로 잘 이식되는 것
1. **색 팔레트** — hex 1:1(헤딩·표 헤더·콜아웃·규칙선·의미색).
2. **헤딩 위계·간격 리듬** — Heading 1/2/3 스타일 + 문단 간격으로 흐름 문서의 본령.
3. **표 디자인** — 헤더 fill·zebra·헤어라인 테두리·셀 패딩(기본 Word 표 스타일 회피).
4. **헤더/푸터·페이지번호** — `PAGE / NUMPAGES` 필드(Word 가 열 때 계산).
5. **한글/라틴 분리 타이포** — 세리프 라틴 헤드 + 고딕 한글 공존(pptx 가 못 하던 것).

### ❌ DOCX 가 못 따라가는 것
1. **모서리 반경** — Word 단락/표에 없음(무시).
2. **그라디언트·glow·풀블리드 배경** — 네이티브 비1급. 표지 색 밴드(단일 셀 표 음영)로 근사, 그라디언트는 Pillow PNG 임베드 한정.
3. **독점 디스플레이 서체** — 시스템 미설치 시 Word 대체 폰트 폴백(라틴 한정, 한글은 eastAsia 안전).
4. **OpenType 미세 기능** — dockit 1급 미적용(후속).

### 충실도 우회책
- 한글은 항상 dockit 빌더(또는 `set_run_font(kr=...)`)로 — eastAsia 자동 바인딩이 한글 가독성의 지배 레버.
- 브랜드 라틴 폰트를 시스템 설치하면 라틴 손실 감소(한글은 어차피 eastAsia 안전).
- 표지/클로징 색 밴드는 `dk.band`(단일 셀 표 음영)로 — 흐름 문서에서 가장 견고한 풀폭 색면.
- 중요한 산출물은 Word 실물 검수 권장(렌더는 Word COM 이 가장 정확, 그 외 LibreOffice).
