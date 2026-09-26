# Changelog — pptx-design

모든 주요 변경사항을 기록합니다. [Keep a Changelog](https://keepachangelog.com) 포맷을 따릅니다.

## [0.9.0] — 2026-09-25 (itda-work/itda-hyve#6)

### Removed

- hyve 앱 폐기에 따라 **관문3-B (선택) OpenXML 백엔드(`apply_deck_ir`)** 절과 그 경로에만 쓰이던 `scripts/deck_ir.py`·`tests/test_deck_ir.py`·`gallery/luxury/parity_openxml.py` 를 뺐다.
- 비목표 안내에서 hyve PowerPoint COM 도메인(`office_edit`) 경로 안내를 뺐다. 기본 경로(python-pptx)는 그대로.

### Changed

- `examples/sample/README.md` 실행 경로를 새 저장소 루트 기준으로.
- 갤러리: `gallery/requirements.txt` 의 websockets(지운 패리티 빌드 전용) 삭제, INDEX·`luxury/PARITY.md`·`RECIPE.md` 의 COM/OpenXML 서술에 “기록 — 재실행 불가” 표시. `design-md-mapping.md` 의 “COM 도메인” → “범위 밖”.

## [0.8.2] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash, mcp__workspace__web_fetch) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.8.1] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.8.0] — 2026-07-25

### Added
- **레이아웃 좌표 헬퍼** (SPEC-DESIGN-TEMPLATE-INGEST-001 P0, #701/#702) — `deckkit.zone_bounds(h_in, three_zone, margin_in)`(헤더/본문/푸터 비율 분할)·`grid_cells(x,y,w,h,cols,rows,gutter)`(균일 그리드 셀). design-core `to_pptx_layout()` 토큰을 좌표로 산출하는 순수 함수(python-pptx 객체 비의존, 결정론). 그간 산문 규칙·gen.py 절대좌표 하드코딩으로만 있던 "수직 3존 리듬·균일 그리드"를 토큰 계약화.
- tests — `test_layout_zones.py`(존 합·비율 지배·margin·결정론·그리드 타일링/거터 7종).

### Changed
- `references/design-md-mapping.md` — "spacing/grid" 행을 layout 토큰 실소비로 정정 + "① 적용 ✅ = 재현 가능 ≠ 토큰 자동 소비" 주석 추가(#701 착시 제거).

### Notes
- 2026-07-01 작성분(design-core 0.6.0 layout 어댑터의 동반 변경)을 2026-07-25 회수 머지(브랜치 `feat/design-template-ingest-702`). v2 토큰 결정론 레이어 강화로 #1021 직해석 정본 경로와 무관.

## [0.7.3] — 2026-07-11

### Changed
- **표준 DESIGN.md 차용 경로 명시** (#1021) — 유명 브랜드 톤 신호("스포티파이 느낌" 등) 시 design-core getdesign-first 워크플로우(카탈로그 75종 + 한국 확장 `../design-core/catalog/`)로 원문을 획득해 관문2 "DESIGN.md 제공 시" 경로로 소비(직해석 정본 — `design_core.load()` 비대상, 한글 덱은 CJK Addendum 증보). 레퍼런스 프리셋 수 표기 6종→8종 정합.

## [0.7.2] — 2026-07-06

### Changed

- **MCP 온보딩 정본화 (hyve#921)** — OpenXML 백엔드 사전 준비의 배포 안내를 폐지된 전체 `/mcp` 에서 **hyve 설정 > MCP 탭의 문서(office) 프리셋 등록**(hyve#852·#887)으로 교체. stdio `hyve mcp` 는 개발·검증 전용 명시.

## [0.7.1] — 2026-06-26

`verify.py`가 **렌더 도구(LibreOffice/poppler) 부재 시에도 HARD GATE를 정상 판정**하도록 견고화합니다(hyve#621). 그동안 렌더 실패가 `blank_slide`(하드게이트 항목)로 기록돼, `soffice` 없는 환경에서 **깨끗한 덱조차 거짓 FAIL** 했습니다(PR #614 Windows 검증 중 표면화).

### Fixed

- **렌더 부재를 비차단 advisory로 분리** — 렌더(soffice→PDF→JPG) 실패를 `blank_slide`가 아니라 신규 `render_unavailable`(비차단)로 기록. 지오메트리·콘텐츠 하드게이트는 렌더와 무관하므로 도구가 없어도 정상 판정되고, 렌더 의존 검사(OCR 층 C + 이미지 기반 빈슬라이드 탐지)만 우아하게 생략됩니다. **실제 빈슬라이드(렌더 성공 + 단색)는 여전히 `blank_slide`로 차단**(회귀 가드).
- **JSON 산출 utf-8 고정** — 결과 JSON을 `encoding="utf-8"`로 기록. Windows 기본 cp949로 열려 비-cp949 문자(em-dash 등)에서 `UnicodeEncodeError`가 나던 잠재 버그 해소.
- **CLI stdout utf-8 강제** — `main()`이 Windows 콘솔(cp949)에서 한국어·em-dash 출력에 죽지 않도록 stdout/stderr를 utf-8로 reconfigure(실패 시 무시).

### Verified

- `test_verify.py` 14건 PASS(신규 2건: 렌더 부재 비차단 + 실제 빈슬라이드 차단 회귀). soffice 미설치 Windows에서 기존 거짓 FAIL 3건이 PASS로 전환. CLI 스모크 exit 0(soffice 없이 `HARD GATE: PASS`).

## [0.7.0] — 2026-06-26

`verify.py`에 **wrap 유발 오버플로 advisory** 검출을 추가합니다(hyve#413). PowerPoint `view_issues`의 L1 휴리스틱(문단수×폰트×1.2)이 놓치던 — 긴 단일 문단이 좁은 박스에서 래핑돼 박스 높이를 넘는 — 오버플로를, Office/COM 없이 크로스플랫폼으로 1차 포착합니다.

### Added

- **wrap 유발 오버플로 advisory(`text_wrap_overflow`)** — 문자 클래스 기반 em 폭 근사(폰트 비의존·결정론)로 폭 보정 줄 수를 추정해 `needed_height > box`를 적발. 신호 조건은 `needed > box×1.05 AND 보정 줄 수 > 문단 수`(= naive 문단수로는 통과하나 wrap으로 넘침 = #413 사각지대만 가둠). `SHAPE_TO_FIT_TEXT`(python-pptx 텍스트박스 기본값)는 선언 높이를 침범하므로 검사 대상, `word_wrap=False`·`TEXT_TO_FIT_SHAPE`·배경 도형은 제외. **advisory — HARD GATE 산식 불변**(오탐이 덱 빌드를 깨지 않음).
- 라이브 6종(정상 4 오탐 0 · 결함 2 정탐 — hyve#426 킥커 칩 wrap 재현 포함) + 단위 4종 검증.

### Changed

- **SKILL.md 관문4** — "자동 게이트는 [wrap을] 잡지 못하니 육안이 유일한 방어선"([#426]에서 자인)을, "`text_wrap_overflow` advisory가 1차 자동 포착 + orphan·미세 래핑은 육안 보강"으로 갱신.
- **`view_issues` L1(COM) autosize parity 정합** — `PowerPointComEngine.View.cs`의 L1 오버플로 게이트를 `autoSize==0`(None 한정)에서 verify.py와 동일 기준(`TextToFitShape`=글자 축소만 제외, `TextFrame2.AutoSize`로 판정)으로 확장. PowerPoint 기본 `ShapeToFitText` 텍스트박스(생성 덱 대부분)의 wrap 오버플로가 이제 COM `view_issues`에서도 발화 — 기존엔 `text_wrap_overflow`(verify.py) advisory만 잡던 사각지대를 양 게이트가 함께 포착(진짜 1:1 parity). Windows COM 런타임 검증: wrap·naive 정탐 / good·shrink 오탐 0 / 단위 points(0.6in≈43pt) 확정 / 기존 L1 테스트(SPEC-DOTNET-018 Phase 4) 회귀 0.

## [0.6.1] — 2026-06-16

갤러리 재현 프롬프트의 트리거를 결정적으로 만들고, GUIDE에서 디자인을 눈으로 확인할 길을 연다(hyve#429). 문서 패치(생성·검증 로직 무변경).

### Documentation

- **갤러리 RECIPE 트리거 명시** — `gallery/*/RECIPE.md` 20종의 "이렇게 말하면 이 덱이 나온다" 프롬프트 맨 앞에 `pptx-design 스킬로` 접두. 웹 갤러리(itda.work/pptx-design)에 노출돼 복붙되는 프롬프트가 정확히 이 스킬을 트리거하도록 보장(다른 스킬 끼어듦 방지).
- **GUIDE 갤러리 링크** — 상단에 [PPT 디자인 갤러리](https://itda.work/pptx-design/) 링크 추가. 텍스트 문서인 GUIDE에서 못 보던 20종 실제 덱 미리보기·PDF·PPTX를 웹에서 시각 확인. SPEC-GUIDE-NO-SHELL-001 준수.

## [0.6.0] — 2026-06-16

무신호("그냥 맡기기") 시 톤을 자동 선택하던 동작을, **후보를 엄선해 사용자가 고르게 하는 대화형 게이트**로 바꿉니다(SPEC-PPTX-DESIGN-006, hyve#426). 자동 선택은 "알아서 골라줘" 옵션 + 비대화형 폴백으로 보존합니다.

### Changed

- **★관문2 — 무신호 대화형 톤 선택 게이트(REQ-601)** — DESIGN.md·프리셋 이름·톤 키워드가 **하나도 없을 때만**, 주제에 맞는 프리셋(6종)·톤 변형(20종) 중 **후보 2~3종 + "주제에 맞게 알아서 골라줘"**(총 3~4보기, AskUserQuestion 4보기 상한 준수)를 `AskUserQuestion`으로 제시해 사용자가 고르게 합니다. 신호가 하나라도 있으면(프리셋/톤/DESIGN.md) 기존대로 **되묻지 않고** 바로 진행.
- **자동 선택 = 옵션 + 폴백으로 보존(REQ-602)** — 후보의 "알아서" 항목, 그리고 비대화형(MCP/Cowork/자동화)·물을 수 없는 상황에서는 기존 자동 선택으로 폴백합니다. **품질 하한 계약(REQ-101)은 두 경로 모두 동일** — 게이트는 톤 선택권만 줄 뿐 품질 기준을 낮추지 않습니다.
- **frontmatter `allowed-tools`에 `AskUserQuestion` 추가** — 톤 선택 게이트 실행 도구.

### Documentation

- **SKILL.md 관문1/관문2** — 1급 경로를 "디자인 신호 유무 3분기(신호 있음 → 바로 진행 / 무신호+대화형 → 게이트 / 무신호+비대화형·"알아서" → 자동 폴백)"로 재작성. 어느 경로든 선택 근거 한 줄 유지.
- **GUIDE.md §1·§2.1** — "없으면 자동 선택"을 "후보를 보여주고 고르게 함(\"알아서\"도 가능)"으로 갱신(사용자 언어, 셸·CLI 비노출).
- **SPEC-PPTX-DESIGN-006 신설**(Draft) — 무신호 대화형 톤 큐레이션 계약.

## [0.5.0] — 2026-06-14

OpenXML 생성 백엔드 추가(SPEC-PPTX-DESIGN-004, #352). 스파이크 #351 → "Python/OpenXML 생성 → COM 협업 편집" 파이프라인의 생성 절반.

### New Features

- **OpenXML 생성 백엔드 (`apply_deck_ir`)** — `gen.py`(python-pptx) 외에 hyve `PowerPointOpenXmlEngine` 으로 생성하는 백엔드 추가. `scripts/deck_ir.py` 로 백엔드 중립 Deck IR(`pptx-design-ir/v1`)을 산출 → 에이전트가 hyve MCP verb `openxml.powerpoint.apply_deck_ir` 호출 → 크로스플랫폼 덱 생성(Office 불필요). **네이티브 편집 차트**(matplotlib 래스터 한글 tofu 회피) + custom_visual 슬라이더 + semantic id 도형 각인. 그라디언트/모티프는 Pillow baked PNG(picture 배경)로 Python 파리티.

### Documentation

- **SKILL.md 관문3-B(OpenXML 백엔드 경로) 신설** + 백엔드 선택(기본 Python / OpenXML 옵션, REQ-010).
- **한글 가드 정책 명확화(REQ-008)** — `set_run_font` 한글 가드의 가치는 **LibreOffice 렌더 한정**(PowerPoint 렌더는 전 백엔드 한글 정상). 스파이크 실측 근거.

## [0.4.1] — 2026-06-13

### Documentation

- **GUIDE.md §3 — 60초 소개 영상 추가** — itda-work 채널 게시 영상(`https://www.youtube.com/watch?v=oJ9jvtLQHxg`, Remotion 제작 + ElevenLabs 나레이션, 모든 장면이 2026-06-11 실측 슬라이드). 단독 URL 문단은 itda.work 가이드 페이지에서 자동으로 플레이어로 임베드된다(website SPEC-SKILLS-013 remark-youtube).

## [0.4.0] — 2026-06-13

사용자 피드백("대충 입력해도 뽀대나게 — 엉성한 스타일 절대 금지" + AI 기본값 안티패턴 5종 인사이트) 반영(SPEC-PPTX-DESIGN-003, #325). 디자인 시스템 없는 범용 AI 의 기본값 — 수직 중앙 몰림·여백 부조화·좌측 액센트 바 남발·깔맞춤 실패·구분 부호(`·`/`—`) 남발 — 을 문서 규칙 + 자동 트립와이어로 차단합니다.

### New Features

- **★verify (E) 스타일 휴리스틱 층(REQ-105)** — advisory 3종 신설(HARD GATE 산식 불변): `style_punct_overuse`(큰 글씨 run 의 `·`/`—`/`–` 슬라이드당 5 초과 — 메타 줄 작은 글씨는 제외), `style_edge_bar_overuse`(도형 왼쪽 모서리 흡착 세로 바 덱당 3 초과 시에만 보고 — 절제 사용 무죄), `style_v_center_cram`(비배경 union 이 높이 55%H 미만으로 캔버스 중앙 ±8%H 에 몰림). 임계는 모듈 상수로 튜닝 가능. 출력에 `[ADVISORY/스타일]` 라인 + 슬라이드별 교정 힌트.
- **★품질 하한 계약(REQ-101)** — SKILL.md 관문2: 빈약/대충 입력에도 디자인 문법 풀 적용, 콘텐츠 부족 시 **장수 축소(슬라이드 헐겁게 금지)**. "엉성한 스타일"을 산출 불가 기준으로 명문화.

### Changed

- **`references/anthropic-pptx-design-ideas.md`** — §4 에 수직 3존 리듬(헤더/콘텐츠/푸터, "여백은 배치한 공간")·동종 오브젝트 깔맞춤 규칙(REQ-102), §5 에 안티패턴 4종 금지(중앙 몰림·좌측 바 남발·부호 남발·깔맞춤 실패) 추가, §6 시각 QA 체크리스트 4항 확장.
- **SKILL.md** — 관문3 준수사항(3존 리듬·깔맞춤·부호 절제) + 관문4 advisory 목록·교정 루프에 스타일 3종 연결. version 0.4.0.
- **GUIDE.md** — "짧게 말해도 결과 기준은 같습니다" 안내 + 산출물 체크리스트에 스타일 경고 0 항목.

### Tests

- 신규 7종(`test_verify_style.py`) — 부호 남발 적발/메타 줄 면제 · 좌측 바 남발 적발/절제 사용 무죄 · 중앙 몰림 적발/3존 리듬 무결 · 클린 덱 종합 0 + HARD GATE 불변. 기존 57 + 신규 7 = **64 GREEN**.

## [0.3.1] — 2026-06-13

차별점 포지셔닝 박제(#314). 0.3.0의 A/B 실측 우위(90.0 vs 83.5)가 사용자 문서에 드러나지 않고, 비교 근거 포인터가 삭제된 디렉토리를 가리키던 공백을 메웠습니다. 스킬명은 검토 끝에 `pptx-design` 유지로 확정(개명안 `pptx-enhanced`는 상대어로 단독 정보 0·사용자 발화 비정합·변경 비용 과다로 기각).

### Changed

- **GUIDE.md** — §1 직후 "기본 pptx 스킬과 무엇이 다른가요?" 섹션 신설: 실측 5축 비교표(한글 타이포 가드·자동 게이트·프리셋/박제·차트 이원화·제작 안정성) + **기본 스킬로 충분한 경우의 정직한 안내**(기존 덱 읽기/편집·영문 초안·저요구 내부 공유).
- **`references/anthropic-pptx-design-ideas.md` §7** — 삭제된 `out-pptx-design/_compare/COMPARISON.md` 포인터를 인라인 경로 판단 기준 + 실측 수치 + 저장소 아카이브 출처로 교체(발행본 자족성 확보).
- **README.md·`references/design-md-mapping.md`** — 사멸 경로(`out-pptx-design/`) 참조 제거, 결과 흡수 사실 명시.

### Docs (저장소 전용 — 발행본 미포함)

- **`skills/docs/analysis-pptx-design-ab-compare/`** — 2026-06-11 동일 브리프 A/B 실측 풀 아카이브 박제: 10차원 채점 리포트 + 양 덱 콘택트시트 + 에이전트 SUMMARY 2건 + 공유 브리프·data.json + 개선 처리 현황 + 이름 결정 기록. 휘발성 /tmp 의존 제거.

## [0.3.0] — 2026-06-11

"MBB 티어1 컨설팅펌 스타일 삼성전자 주가 보고서" 동일 브리프 A/B 실측 비교(#303 — 공식 `pptx` 스킬 83.5 vs 본 스킬 90.0/100, 한글 처리·제작 비용 모두 역전 확인) 후속. 검증된 디자인 문법을 **프리셋으로 박제**하고, 조직 브랜드 박제 경로와 그림자 잔존 결함을 정비했습니다.

### New Features

- **★디자인 프리셋 6종(`references/design-presets/`)** — ready-to-use DESIGN.md: `consulting-mbb`(이번 실측 12장 덱의 문법 박제) · `equity-research-dark` · `warm-editorial` · `print-broadsheet` · `tech-vivid-dark` · `minimal-mono`. 각각 awesome-design-md 호환 frontmatter(colors 9키·typography·semantic_convention·motif·do/dont) + 슬라이드 문법 레시피(표지/요약/차트/그리드/클로징) 포함. 선택 표는 내부 `README.md`. SKILL.md 관문2의 1급 경로 ①로 승격 — 톤 키워드("컨설팅 스타일"…)가 오면 프리셋을 DESIGN.md 로 통째 적용.
- **★DESIGN.md 생성 모드(조직 브랜드 박제)** — SKILL.md 관문1 라우팅 분기 + 관문2 생성 모드 신설: "우리 조직 DESIGN.md 만들어줘" 요청 시 브랜드 토큰 수집(말/문서/웹) → 톤 최근접 프리셋 베이스 복사 → hex·motif·do/dont 치환 → 파일 산출(덱 생성 없이 종료 가능). 외부 선례(Anthropic theme-factory 프리셋 디렉토리 + 커스텀 테마 플로우) 교차검증.
- **의미색 관행 토글** — 프리셋 frontmatter `semantic_convention: international|krx`(국제 상승=그린 vs 한국 증시 상승=레드)로 가정을 명시화.

### Fixed

- **★deckkit `rect()` 그림자 잔존(#303 실측)** — `_kill_shadow` 가 빈 `effectLst` 만 주입해 LibreOffice 가 `<p:style><a:effectRef idx="2">` 테마 참조로 프리셋 드롭섀도를 계속 렌더하던 결함. shadow=False 시 `<p:style>` 을 통째로 제거해 플랫 의도를 복원(fill/line 은 항상 명시 지정이므로 시각 동등). shadow=True 는 `p:style` 보존.

### Changed

- **GUIDE.md 전면 개편** — 스타일 프리셋 6종 표("이렇게 말하세요")·MBB 실측 사례(12장 구성 표)·조직 DESIGN.md 박제 시나리오(§4.3)를 자연어 중심으로 추가, 내부 API 식별자 제거(SPEC-GUIDE-NO-SHELL-001 준수).
- **`references/pptx-toolkit.md`·`design-md-mapping.md`** — 한글 인접 em-dash(U+2014) 글리프 드롭 함정을 일반화(음수 자간 한정 → 한글 인접 일반 run 실측, en-dash/middle-dot 대체 규칙). mapping §3 에 프리셋 우선 안내 추가.

### Tests

- 신규 11종 — rect `p:style` 제거/보존 회귀 2 + design-presets 구조·계약 9(디렉토리/README/≥6종/frontmatter 계약 키/colors 9키 hex 유효성/한글 필터 토큰 부재/semantic_convention enum/body 센티널/README 전수 나열). 기존 46 + 신규 11 = **57 GREEN**.

## [0.2.0] — 2026-06-08

기본 Anthropic `pptx` 스킬의 **superset 재설계**(SPEC-PPTX-DESIGN-002). 0.1.0 의 단일 치명 결함 — 표지·섹션 **한글 제목이 자간 벌어진 명조/붓글씨로 렌더** — 를 폰트 체인 + 타이포 가드로 제거하고, 네이티브 편집 차트·기본 가이드 흡수·타이포 검증을 추가했습니다.

### New Features

- **★한글 타이포 가드(REQ-001)** — `deckkit.set_run_font` 가 한글 포함 run 에 대해 (1) 비-한글 폰트(라틴 세리프/thin 디스플레이)를 `kr_font_name()` 안전 고딕으로 **강제 교체**, (2) 음수 자간을 0 으로·과대 자간을 `KR_SPACING_CAP_PT(2.0pt)` 로 **클램프**. 라틴 전용 run 은 DESIGN.md 음수 자간·세리프 디스플레이 그대로 허용. `force=True` 로 우회 가능. 헬퍼 `has_hangul` · `is_kr_capable_font` 공개.
- **★LibreOffice 안정 폰트 체인(REQ-006)** — `kr_font_name()`·`_KR_FONT_FILES` 를 실측 기반 재정렬: **Noto Sans KR → Pretendard** 우선(또렷한 굵은 고딕), NanumGothic·Apple SD Gothic Neo 후순위(LibreOffice 비결정적 명조 치환). 결정론적 선택. matplotlib 는 `_MPL_FONT_FILES`(정적 폰트 우선)로 분리.
- **★네이티브 편집 차트(REQ-003)** — `deckkit.add_native_chart` 추가. python-pptx `add_chart` 로 **PowerPoint 에서 편집 가능한 차트 객체** 생성(받는 사람이 수치 직접 수정). DESIGN.md 팔레트(series/point 별 hex) + CJK 안전 폰트(latin/ea/cs) 자동 주입. column·bar·line·pie·doughnut·stacked·area 등 13종. matplotlib 래스터 차트는 고디자인/특수 시각 옵션(편집 불가)으로 유지.
- **★타이포 검증 보강(REQ-005)** — `verify.py` 에 (D) 한글 타이포 정적 검사 추가. 한글 run 의 음수/과대 자간·비안전 폰트를 **advisory** 로 적발(HARD GATE 불변). 가드 우회·구버전 결함 덱의 회귀 트립와이어.
- **★기본 스킬 흡수(REQ-002)** — `references/anthropic-pptx-design-ideas.md` 신설. Anthropic `pptx` 스킬의 design-ideas(팔레트·타이포 페어링·레이아웃·"모든 슬라이드에 시각 요소"·QA 루프)를 흡수·인용. SKILL.md 관문2 가 DESIGN.md 미제공 시 **기본 가이드 + 내장 팔레트를 1급 경로**로 사용.

### Changed

- **`references/design-md-mapping.md`** — 토큰별 **3열 필터**(① pptx 적용 / ② 한글 적용 / ③ 필터)로 갱신(REQ-004). `letterSpacing(음수)`·`fontWeight(thin)`·`serif display` 를 **한글=필터**로 명시 + 실측 폰트 렌더 표.
- **SKILL.md** — superset 원칙·관문2(기본 가이드 1급 + DESIGN.md 한글 필터 인지)·관문3(네이티브 차트 우선 + matplotlib 고디자인 옵션 + 가드 자동)·관문4(타이포 advisory) 반영. `metadata.version` 0.2.0.
- **`references/pptx-toolkit.md`** — §4.5 네이티브 차트 레시피 + CJK 폰트 가드 + verify (D) 타이포 층 추가.
- **`examples/sample/gen.py`** — S3 HBM 차트를 `add_native_chart`(네이티브 편집)로 전환해 REQ-003 시연. 한글은 새 폰트 체인 + 가드로 또렷한 굵은 고딕 렌더(DESIGN.md 음수 자간은 가드가 자동 클램프).
- **라이선스 정합** — SKILL.md frontmatter `license` 를 README(`Apache-2.0`) + 저장소 다수 컨벤션에 맞춰 `MIT`→`Apache-2.0` 으로 통일(0.1.0 부터 내부 모순이던 것 교정). `anthropic-pptx-design-ideas.md` 흡수 출처(Anthropic, Proprietary)의 귀속 표기를 "공개 원칙·기능 데이터의 한국어 번안·내부 참조" 로 명확화.

### Fixed

- **표지·섹션 한글 제목의 명조/붓글씨 폴백·자간 벌어짐 결함 제거** — 폰트 체인(Noto Sans KR 우선) + 가드로 전 슬라이드 한글이 또렷한 굵은 고딕. `examples/sample/_verify/deck_render/slide-0*.jpg` 육안 확인, `out-pptx-design/_compare/` 3자 비교 갱신(한글 처리 6→9, 재현성 6→8).

### Tests

- 신규 19종(가드: 음수 자간 클램프·과대 캡·라틴 보존·세리프→안전 고딕·capable 보존·force 우회·라틴 헤드 유지·has_hangul·is_kr_capable_font·kr_font_name / 네이티브 차트: 데이터 일치·팔레트·CJK 폰트·도넛 point·제목 토글·알 수 없는 kind / 타이포 advisory: 구버전 적발·HARD GATE 불변·클린 무결). 기존 27 + 신규 19 = **46 GREEN**.

## [0.1.0] — 2026-06-08

### New Features

- **초기 릴리스** (SPEC-PPTX-DESIGN-001). 콘텐츠 명세(Markdown 아웃라인) + 수치 데이터(JSON/표)를 받아, 웹 DESIGN.md 디자인 토큰을 적용한 16:9 PPTX를 macOS/Linux·헤드리스·Office 없이 신규 생성하는 스킬. hyve PowerPoint COM 도메인(Windows·편집·시연·실물 fidelity)의 보완재로 포지셔닝.
- **`scripts/deckkit.py`** — per-invocation 생성 스크립트가 import 하는 공개 헬퍼 API(REQ-006). `hexrgb` · `new_deck` · `blank_slide` · `set_bg` · `rect`(기본 테두리·그림자 제거) · `set_run_font`(latin/ea/cs 동시 지정으로 한글 안전) · `add_text` · `add_paragraph` · `add_table` · `add_picture` · `linear_gradient` · `radial_glow`(Pillow PNG) · `mpl_korean` · `kr_font_name` · `save_deck`. 시그니처 안정 유지.
- **`scripts/verify.py`** — 3층 자동 검증기 CLI(REQ-005). (A) 지오메트리(경계이탈·퇴화도형 HARD, 텍스트박스 겹침 advisory), (B) 콘텐츠 대조(필수 토큰 존재 HARD), (C) OCR 렌더 대조(산출률·한글 명칭 advisory). HARD GATE = (경계이탈 + 퇴화도형 + 빈슬라이드 + 토큰누락) == 0, PASS 시 exit 0. 플래그 주석 몽타주 PNG 산출.
- **`scripts/render.py`** — soffice headless PPTX→PDF→JPG 썸네일(REQ-007). 슬러그별 격리 프로파일(`-env:UserInstallation`)로 병렬 안전.
- **`references/pptx-toolkit.md`** — 레시피·함정·CJK 폰트·렌더 명령 레퍼런스.
- **`references/design-md-mapping.md`** — 웹 DESIGN.md → pptx 디자인 토큰 매핑 + 재현 가능/불가 카탈로그.
- **`examples/`** — 콘텐츠 + 데이터 + DESIGN.md(또는 내장 팔레트) 예제. DESIGN.md 핵심 팔레트 hex가 생성물 도형/차트에 실제 반영됨을 입증.
- **`tests/`** — deckkit 헬퍼(CJK 폰트 XML·hexrgb·gradient), verify 검출(크래프트한 OOB pptx 적발·토큰 대조), 구조 정책(scripts 1-depth) 검증.

### Design

- **콘텐츠·데이터 SSoT, 디자인만 변수**: 동일 콘텐츠를 여러 DESIGN.md로 분기 생성. 결정론(난수 미사용, 동일 입력 → 동일 산출).
- **CJK 안전 폰트**: `set_run_font` 가 latin/ea/cs typeface 를 동시 지정하고 LibreOffice 치환 안전 폰트(Apple SD Gothic Neo / Noto Sans KR / Nanum Gothic)를 사용해 tofu·세리프 폴백·weight drift 회피(REQ-004).
- **그라디언트·모티프 베이크**: python-pptx 그라디언트 fill 미지원 대응으로 Pillow+numpy PNG 합성 후 풀블리드 임베드. 차트는 matplotlib로 디자인 팔레트에 맞춰 렌더(기본 파랑/주황 금지)(REQ-003).

### Notes

- 비목표(= hyve COM 도메인 책임): 기존 덱 편집·병합, Windows 실물 WYSIWYG fidelity, Visible=true 실시간 시연, 발표자 노트·코멘트·SmartArt·전환/애니메이션. officecli 미사용(python-pptx 직접 생성).
- 전 과정이 macOS/Linux 에서 Office 없이 동작(생성=순수 Python, 검증=LibreOffice)(REQ-008).
