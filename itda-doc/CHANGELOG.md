# Changelog

이 파일은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따르며,
[Semantic Versioning](https://semver.org/lang/ko/)을 준수합니다.

## [6.1.0] - 2026-09-29

### Added

- **`imagegen` 1.0.0 되살림 (itda-hyve#8·#16)** — 2026-09-25 저장소 이관 때 뺀 이미지 생성 스킬을 이 팩에 되살렸다. 생성은 itda-hyve 의 에이전트 작업 도구(`accounts_list`·`agent_run`·`job_status`, recipe `codex.imagegen`)로 한다 — codex 는 itda-hyve 창의 에이전트 탭에서 설치한 관리형 codex 만 쓰고(사용자가 따로 설치한 codex 는 쓰지 않는다), 사용자는 같은 탭에서 ChatGPT 구독으로 로그인한다(터미널 없음). 케이스 카드 9종·5층 공식·실측 썸네일을 그대로 가져오고, 5종을 codex-cli 0.157.0 으로 다시 실측했다. 설치·로그인이 없으면 `accounts_list` 의 `available`·`logged_in` 으로 생성 전에 알아챈다. 8 → 9종.
  **배포 순서**: itda-hyve 0.10.0 설치본 공개 뒤에 배포한다 — 0.9.x 에는 `agent_run` 이 없다(스킬은 `server_version` 을 보고 업데이트를 안내하고 멈춘다).

### Changed

- 팩 description·keywords·README 에 이미지 생성을 더했다.

## [6.0.0] - 2026-09-28

### BREAKING

- **자격증명 파일 별칭에서 `env.txt` 를 뺐다** (itda-work/skills#26, 사용자 결정 2026-09-28). 스킬이 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 에 키를 두었다면 **`환경변수.txt` 또는 `.env` 로 이름을 바꾼다** — 그대로 두면 키를 못 찾는다. 스킬은 `env.txt` 라는 파일을 더 이상 알아보지 못하며 별도 안내도 하지 않는다. 대상 스킬: `blog-seo` 0.10.10(파일명 별칭 안내·키 주입 규칙을 3종으로).

## [5.1.0] - 2026-09-28

### Added

- `hwpx` 1.4.0 — 공문서 표기법 검사 `lint_notation.py`(날짜·시각·금액 한글 병기·쌍점·물결표·`붙임:` 을 경고만, #14), 레이아웃 틀 표 풀기 `--unwrap-layout-tables`(옵트인, #13), 생성 매퍼 `--strict`(원고 내용을 버리는 경고면 산출하지 않음, #11), 파일 머리로 형식을 가르고 HWP 3.x·HWPML 은 kordoc 대체 경로를 안내(#16).
- `pdf-context-refinery` 1.3.0 — 전 페이지 텍스트층 판정 `page_quality.py`. 첫 3쪽 샘플이 아니라 쪽별 판정으로 스캔 쪽을 가르고, 비전으로도 못 읽은 쪽은 "미검증 쪽" 으로 결과에 남긴다(#5).
- `pdf-context-refinery` 1.4.0 — ToUnicode 가 깨진 한글 쪽(엉뚱한 음절)을 받침 분포로 판정해 비전 경로로 보내고, 문서 단위 권고 `doc_needs_ocr` 를 싣는다(#28).

### Fixed

- `hwpx` 1.3.2·1.3.3·1.4.0 — HWP5 표 셀 주소를 잘못 읽어 표가 한 행으로 뭉치던 결함(#2, #3), HWP5 글상자 텍스트 누락·밑줄 섞인 강조 잔재(#6, #7), 원문 별표(`*`) 이스케이프(#8), 채우기 `--residue` 가 값의 자리·횟수까지 대조(#9), 구조 검증기에 `secCnt`·manifest 검사를 더하고 채우기 결과에도 돌림(#10), 없는 입력 파일·암호·배포용 보호 HWP 5 에 트레이스백 대신 무엇인지와 조치를 안내(exit 2, #16 후속·#22).
- `hwpx` 1.4.1 — 사용자 HWPX·HWP 입력의 압축 폭탄·XXE(DOCTYPE)·경로 탐색을 풀기 전·푸는 중에 막고 명시 오류로 알린다(상한 `ITDA_MAX_UNZIP_MB`·`ITDA_MAX_ZIP_ENTRIES`, #27).
- `hwpx` 1.4.2 — 잘리거나 깨진 HWP·HWPX, olefile 이 없는 환경이 트레이스백 대신 exit 2 와 조치 안내(오류 종류 코드 포함, #29·#32). 개발 도구로 벤치 게이트·fuzz 게이트.

### Changed

- `hwpx` 1.4.0 — 예시 원고의 공문서 표기를 정리하고 GUIDE 그림을 다시 구웠다(#15).

## [5.0.0] - 2026-09-27

### BREAKING

- **디자인 스킬 4종 제거** — `design-core`(브랜드 디자인 토큰 허브)·`docx-design`(Word 신규 생성)·`pptx-design`(PPTX 발표자료 신규 생성)·`xlsx-design`(Excel 신규 생성). 이 팩에서 Word·PPTX·Excel 파일을 새로 만드는 경로가 없어진다 — 한글 문서는 `hwpx`, HTML 보고서는 `html-report` 가 만든다. 12 → 8종.

### Changed

- `html-report` 0.3.2 — 형제 디자인 스킬 지목 정리. 팔레트 프리셋 9종은 원래 인라인 값이라 동작 불변, `references/styles/README.md` 가 유일한 정본. 팔레트가 radius 를 정한다는 서술(값의 출처가 지운 design-core 였다)을 걷어내고 radius 는 가족 스펙이 정한다고 적었다(12.0.0 리뷰 L1).
- `draft-post` 1.2.8 · `pptx-shrink` 0.2.2 — "쓰지 않을 때" 표·`[책임 경계]` 에서 제거된 스킬 지목 정리.
- 팩 description·keywords·README 에서 Word·PPT·Excel 생성과 브랜드 디자인 토큰 광고를 뺐다.

## [4.2.0] - 2026-09-25

### Removed

- **hyve 선택 백엔드 절 정리 (itda-work/itda-hyve#6)** — hyve 앱이 폐기돼 옵션 경로를 뺐다. 기본 경로(python-docx·openpyxl·python-pptx)는 그대로.
  - `docx-design` 0.4.0 — hyve Word COM 보강(`office_compute`) 절·`references/hyve-com-option-backend.md` 삭제.
  - `xlsx-design` 0.4.0 — hyve Excel COM 보강 절·reference 삭제. 수식 실계산은 `itda-data:xlsx-recalc` 로 안내.
  - `pptx-design` 0.9.0 — 관문3-B OpenXML 백엔드(`apply_deck_ir`)·`scripts/deck_ir.py`·`tests/test_deck_ir.py`·`gallery/luxury/parity_openxml.py` 삭제, 비목표 안내에서 hyve COM 경로 삭제.

### Changed

- **빠진 스킬·hyve 안내 정리** — `pptx-shrink` 0.2.1(pptx-diff·hyve COM 안내 삭제), `design-core` 0.6.3(“hyve artifact” 매체·imagegen 연계 삭제), `hwpx` 1.3.1(hyve MCP 대안 언급 삭제), README 의 #1704 안내 문단. `human-tone` 2.1.2 — 배포되는 HANDOFF 의 개인 절대 경로 제거.

## [4.1.0] - 2026-09-21

### Removed

- **`imagegen`·`pptx-diff` 이관 → `itda-hyve`(비공개, #1704)** — 둘 다 hyve MCP 가 없으면 한 발짝도
  못 나가는데(`image.generate`·`office_read.diff`) hyve 앱이 아직 배포되지 않아, 설치해도
  Prerequisites 에서 막히는 스킬이 공개 배포되고 있었다. hyve 배포 시 다시 공개된다.
- 남은 hyve 언급은 전부 **옵션**이다 — `docx-design`·`xlsx-design`·`pptx-design` 의 COM 보강(길X)은
  1급 경로(python-docx·openpyxl·python-pptx)가 로컬이라 hyve 없이 정상 동작한다. 이관 대상이 아니다.

## [4.0.0] - 2026-09-20

### Changed

- 팩 개명 `itda-content-create` → **`itda-doc`** (#1703 — 대상 명사 축 재편).
- `pptx-diff` 편입(구 itda-evidence-verify) — PPTX 생성·축소·비교가 한 팩으로.
- `pdf-context-refinery` 편입(구 itda-knowledge-build).

## [3.16.1] - 2026-09-13

### Changed

- `xlsx-design` v0.3.5 — `[책임 경계]` 추가(수식 캐시값 재계산은 `itda-data-analysis:xlsx-recalc`, #1690).

## [3.16.0] - 2026-09-06

### Changed

- **플러그인 재정비 2·3단계 (#1648)** — 구 `itda-work` 개명(#1648 2단계). 콘텐츠 산출 12종만 남기고 웹 수집·하루 조직·검증·코칭·PDF 정제 스킬을 목적별 팩으로 분리. imagegen(구 itda-media) 편입. 폐기 이름은 별칭 없이 제거(마스터 결정 2026-09-05). 게이트: check_plugin_registry · check_plugin_refs(신설) · 카탈로그 · publish dry-run.

## [Unreleased]

### Removed

- `biz-redact` 를 `itda-privacy-gate` 로 이관 (#1648 1단계). 이 팩에서는 제거되며 구 참조 `itda-work:biz-redact` 는 마이그레이션 없이 즉시 폐기(마스터 결정 2026-09-05). 과거 항목(v0.1.0 신설·v0.2.0 부록)은 이력으로 유지. 플러그인 3.15.0.

### Added

- `pptx-shrink` v0.2.0 — 실측 표 + 선택 게이트 (#1646, 마스터 제안): `report` 가 품질 90/80/70 × 해상도 원본/220/150ppi 를 전부 실측한 조합 표를 내고, 관문 2 가 품질·해상도 축소·저장 방식을 한 번에 확인. `--downsample-ppi`(표시 크기 기준, 기본 꺼짐, 5% 이상 이득일 때만 권함 — A/L/H 실덱은 JPEG 뒤 0.2MB 수준). GUIDE 에 품질 고르기 절·그림 압축 실측 표. 플러그인 3.14.0.

- `pptx-shrink` v0.1.1 — 테스트 보강 (#1645 2차): hyve-training E 덱 기반 **실물 구조 픽스처**(원문·픽셀 합성 치환, 0.67MB, PNG 최소) + 실물 테스트 7종·가장자리 7종, `verify` 마스터·레이아웃 그림 대조, `report` URL 잔여 이름 미디어 계수 정정.

- `pptx-shrink` v0.1.0 — **스킬 신설** (#1645): 기존 pptx 의 스크린샷 PNG 를 해상도 유지 JPEG 로 재인코딩해 용량 축소(hyve-training IGM 12덱 212→57MB 실측 승격). `report` 진단 · `shrink`(기본 새 파일, `--in-place` 는 `--backup`/`--no-backup` 명시 필수 — 원본 백업 확인 게이트) · `verify.py`(슬라이드·텍스트·노트·그림 수·rels 참조 자동 대조, 실패 시 산출 폐기). GUIDE 에 "왜 pptx 가 커지는가"(레티나 PNG 스크린샷·표시 크기 무관 원본 보존·복붙 사본) + 실측 표. 플러그인 3.13.0.

- `agents/ground-verifier.md` — 공통 감사자 계약(AUDIT_SCHEMA, #1621) 정합: `tools: Read, Grep, Glob, Write, WebSearch, WebFetch, mcp__workspace__web_fetch, ToolSearch` 명시(읽기 전용 허용목록 — `Skill` 제외, web-reader 폴백은 본 세션 몫), 최종 텍스트를 `verdict`·`findings`·`recomputed`·`unverifiable` JSON 으로 고정(검증표 파일 릴레이·템플릿 1:1 정합 불변). `ground-check` v0.11.1 §Task 2 정합.

- `human-tone` v2.1.1 · `draft-post` v1.2.7 · `blog-reader` v0.12.2 · `web-reader` v7.1.2 · `web-search` v0.1.7 — description `[책임 경계]` 슬롯 + 본문 `## 이 스킬을 쓰지 않을 때` 표 파일럿 (#1620, `skill-creator-validation.md` §description 슬롯 규약). human-tone↔draft-post 는 AI 흔적 사전의 **정본을 human-tone `ai-tell-taxonomy.md` 로 선언**하고, draft-post `_anti-ai-korean.md` 의 `~를 통해` 무조건 금지를 정본(A-2 S2, #1619)에 맞춰 남발 억제로 정합. blog-reader↔web-reader 상호 지목.

- `human-tone` v2.1.0 — `scripts/verify_gates.py` 윤문 사후 결정적 판정 게이트 신설 (#1619): P0 변경률(30/50%)·P1 목표 달성/과교정·P2 수사 전멸·P3 보존 불변식, exit 0/1/2(INCONCLUSIVE, fail-closed)/3. 30/50% 문서 규율을 스크립트 판정으로 교체. 동반: 상류 `im-not-ai` 경험적 반증 3건 반영 — A-2 `~를 통해` S2 강등·I-1 `것이다` 조건부·A-16 대명사 직역 번역 맥락 한정(`references/empirical-validation.md`, 정정 이력 보존).

- `work-find` v0.15.1 — **itda-coach 에서 재편입** (#1511, 마스터 결정 2026-08-18): 코치 팩 7종 중 사용성이 높은 work-find 를 주력 팩으로 이동(#1319 편입의 원복). 스킬명·내용 불변, work-proposal·work-pilot 파이프라인이 동일 팩에서 완결. work-plan 카탈로그 경로·README·lessons 인덱스·marketplace 참조 전수 갱신.

- `hwpx` v1.0.1 — 통합 GUIDE.md 신설(읽기/채우기/생성 3경로, 게재 전 3경로 연결 실측 검증).

- `hwpx` v1.0.0 — **양식 채우기** 신설: 기존 .hwpx 양식의 서식·표를 유지한 채 placeholder 만 치환(`scripts/fill_hwpx.py`, 표준 라이브러리 전용·외부 서버 무의존). `--list` 후보 탐지 / `--set`·`--map` 치환 / 동일 서식 분절 run 자동 병합 / mimetype STORED 보존 / 미발견 키 경고(`--strict` exit 3). 테스트 8종 GREEN(report 엔진 실산출물 + validate_archive 교차 검증 포함).

- `work-proposal`·`work-pilot` 신설 (#1310) — itda-ceragem ax-proposal·ax-pilot 범용화 편입. work-find → work-proposal → work-pilot 업무 파이프라인 완성.

### Changed

- `hwpx-reader`(v4.0.1)·`hwpx-report`(v0.3.3) → **`hwpx` 단일 스킬로 병합** (마스터 지시 2026-07-28, 미배포 상태라 별칭 없이 일괄 전환). 구조: `reader/`·`report/` 엔진 서브트리 + 루트 SKILL.md 작업 라우팅(읽기/채우기/생성), 테스트 `tests/{reader,report,fill}` 단일화, requirements 병합. 참조 전수 갱신: release-skills.yml(테스트 매트릭스·requirements)·publish.py(REQUIRED_PLUGIN_FILES)·kacem-tender(탐색 경로)·work-plan 카탈로그·README·lessons 인덱스.

- `find-work` → `work-find`, `plan-work` → `work-plan` rename (#1310) — `work-*` 접두 패밀리 통일(하위 호환 미고려, 마스터 결정 2026-07-27).

- **`web-reader` 복귀 (#1301)** — #1299 에서 `itda-hyve` 로 이전했던 web-reader 를 itda-work 로
  되돌렸다. 코어는 자체 HTTP 페치(`curl_cffi` TLS impersonation)로 hyve 없이 동작하며, 본문의
  hyve `web_browse` 참조는 전부 anti-bot 차단 시 **에스컬레이션 폴백**이다 — hyve 전용 스킬이
  아니다. `blog-reader` 의 페치 위임도 같은 플러그인 형제 스킬 관계로 복원됐다(#1299 에서
  크로스-플러그인 의존으로 벌어졌던 배포 전제 소멸). `web-automation` 은 itda-hyve 에 잔류한다.




### Added

- **Claude Code 확장 부록 파일럿 (#1285)** — ground-check v0.11.0(P2 병렬 팬아웃)·biz-redact v0.2.0(P4 hooks 게이트 안내, jq 식 실측 검증). 규약 정본 `.claude/rules/itda/skills/code-extension-appendix.md` 신설 — 부록 1절 격리·본문(Cowork 기준) 불변·훅 스크립트 동봉 유보.
### Fixed

- **문서-코드 drift 일괄 정합 (#1284)** — 95스킬 감사 부수 발견분. 세부는 각 스킬 CHANGELOG 참조.
### Changed

- **플랫폼 문서 정비 4축 일괄 (#1280·#1281·#1282·#1283)** — ① compatibility 라벨을 실태 정합(`Claude Code & Cowork` 표준, 역방향 라벨 교정) ② 설치 지시에서 `uv pip install --system`·`curl|sh` 제거(`python3 -m pip` 정본, 스크립트 안내 문자열·README 포함) ③ `.env` 안내를 양 플랫폼 병기(SKILL.md+GUIDE.md, 셸 env·`~/.claude/settings.json` env 명시) ④ `allowed-tools` 의 표준명 `Bash`/`WebFetch` 에 Cowork 실명(`mcp__workspace__bash`/`mcp__workspace__web_fetch`) 병기(73스킬) + brain `Task`→`Agent`, MCP 소비 4스킬은 필드 삭제(전체 상속). 세부 버전은 각 스킬 CHANGELOG 참조.
### Changed

- **실행 경로 SKILL_DIR 규약 표준화 (#1279)** — SKILL.md 실행 명령을 SKILL_DIR 확정 블록(Code=`$CLAUDE_PLUGIN_ROOT/skills/<skill>` / Cowork=세션 마운트 find) 기준으로 통일. cwd 상대경로·저장소 경로·플레이스홀더 표기 제거. 대상: biz-redact 0.1.1 · blog-reader 0.11.5 · blog-seo 0.10.7 · calendar 0.2.5 · design-core 0.6.1 · docx-design 0.3.3 · email 0.29.1 · exchange-rate 0.10.5 · human-tone 2.0.3 · imagekit 0.10.4 · pptx-design 0.8.1 · task-brief 0.2.2 · weather-here 0.12.4 · web-reader 6.2.2 · web-search 0.1.3 · xlsx-design 0.3.3.

### Removed

- **translate-doc 스킬 제거 (#1272)** — 번역 본체(`_translate_chunk_llm`)가 NotImplementedError 스텁인 채 exit 0 으로 종료하는 거짓 성공 상태(실행 실측)로 공개 플러그인에 노출되어 있었음. release-skills CI 매트릭스 행 제거 동반. 번역 재구현 시 "에이전트가 번역, Python 은 DNT 치환·용어집·검증 담당" 2-스텝 계약으로 재설계 예정.

### Changed

- **market-scan v0.2.1 (#1272)** — 라우팅 표의 부동산 실거래 경로를 `itda-gov:realestate` → `itda-realty:realty-deals` 로 교체(realestate 제거 정합).

### Added

- **biz-redact 신설 (#1171)** — 업무 문서 영업기밀 마스킹·왕복 복원 게이트. 용어집 기반 결정론 치환(⟦카테고리_n⟧)·잔존 0 검증·왕복 복원+변형 감지·감사 기록(biz-redact v0.1.0).
- **ground-verifier 서브에이전트 신설** (#1138): `agents/ground-verifier.md` — ground-check 스킬 Task 2(독립 검증 라운드) 전용 내부 부품. 검증 대상 산출물의 결론을 신뢰하지 않고 격리 컨텍스트에서 주장별로 새 검색어·새 1차 소스로 독립 재검색해 검증표만 반환한다(기존 URL 재사용 금지·hedge 자동 FAIL 승계). 출력 계약은 ground-check `templates/verification-table.md` 6컬럼(`셀 ID·주장·새 검색어·새 URL·결과·비고`)과 1:1 정합하고, 결과값(일치/불일치/출처 부족/무효)을 PASS/FAIL 로 매핑하며 최종 라운드 미확인 강등을 오케스트레이터에 신호한다. tools 생략(Cowork 워커 전체 상속 — 독트린), 필수 섹션(입력·출력 계약·에러 핸들링) 규격(#1137) 준수. ground-check SKILL.md Task 2 에 환경 분기 절 추가(에이전트 있으면 명시 디스패치 정본, 부재 시 degraded 폴백 — 지침 블록·라운드 관리·Early Termination 불변) + 부록 SDK 매핑 Task 2 행 `subagent_type` 갱신(general-purpose 는 폴백 표기). **Codex r2 보완 3건**: ① hedge 검출을 비고 결정론 토큰 `HEDGE:<표현>` 으로 표현하고 매핑표에 "HEDGE 토큰 존재 시 결과 무관 FAIL" 명시 + 2-A canonical 결과 vocabulary 에 `무효` 추가(템플릿·워커와 4개 통일) ② 에이전트 부재 폴백에서 "자동 자율 분기" 전제 제거(능력 지도 실측 정합) — degraded 폴백(독립성 잔존 명시 또는 새 세션 handoff)으로 정직화, 부록 "정본" 을 자연어→명시 디스패치로 반전 ③ 검증표를 `outputs/verification-round-<N>.md` 파일로 릴레이하고 최종 텍스트는 경로+PASS/FAIL/무효/HEDGE 집계 요약만 반환(대량 상행 금지, 5셀 이하 병기 예외).
- **플러그인 서브에이전트 파일럿 2종** (#1121): `agents/deep-researcher.md`(investigate·market-scan 의 조사 팬아웃 — 소스 축 병렬 위임 + 수집 원문 격리, 구조화 요약만 반환)와 `agents/inbox-triager.md`(email 받은편지함 트리아지 전용 — 발송·초안·삭제 금지 계약, 분류 표만 반환) 신설. Cowork 플러그인 `agents/` 로딩 실증(2026-07-13)에 따른 스킬-에이전트 시너지 파일럿. **investigate v0.11.0 · market-scan v0.2.0 · email v0.29.0**: 각 SKILL.md 에 서브에이전트 연동 절 추가(에이전트 부재 환경은 본 컨텍스트 순차 진행으로 graceful). publish.py WHITELIST 에 `agents` 추가로 skills.pub 배송 경로 개통.

### Fixed

- **draft-post v1.2.4 — Step 0 환경 감지 역전 교정 (#1277)** — "값이 없으면 Cowork" 판정이 Claude Code(변수 부재)를 Cowork 로 오분류. "=1 이면 Cowork / 부재·그 외는 Code" 로 정정 + 결과 표에 Claude Code 행 추가.
- **미정의 변수 `${CLAUDE_SKILL_DIR}` 일소 (#1274)** — hwpx-reader v4.0.1 · hwpx-report v0.3.2 · pdf-context-refinery v1.2.1: 세 SKILL.md 의 설치·PYTHONPATH·검증 명령이 정의된 적 없는 `${CLAUDE_SKILL_DIR}` 에 의존해 Claude Code 에서 빈 문자열 전개로 조용히 깨지던 결함(실측). 각 스킬에 `SKILL_DIR` 확정 스니펫(Code=`$CLAUDE_PLUGIN_ROOT/skills/<skill>` / Cowork=`/sessions/*/mnt/.remote-plugins` find / 그 외=SKILL.md 위치) 신설 후 전 명령 통일. pdf-context-refinery 는 `python`→`python3` 교정 동반.
- **서브에이전트 2종 Cowork tools 함정 교정** (#1130): Cowork 워커의 셸·웹fetch 는 표준명(`Bash`/`WebFetch`)이 아닌 MCP 실명(`mcp__workspace__bash`/`mcp__workspace__web_fetch`)으로 존재하고 frontmatter `tools:` 는 필터라 미매칭 이름이 조용히 소실됨(스모크 13종 실측). deep-researcher·inbox-triager 의 `tools:` 를 제거(전체 상속)하고 플랫폼별 도구 지침 절을 추가 — Cowork 에서 스크립트 실행·웹 조회가 실제로 성립하도록 교정. 행동 경계(발송 금지 등)는 문서 계약으로 유지.

- **hwpx-report v0.3.1** (#374): 실측 결함 6+1 수정. 표 셀의 escaped pipe(`\|`)와 코드스팬 내 `|`를 데이터로 보존하고, XML 1.0 비허용 제어문자를 매퍼 입력·XML escape 관문에서 제거해 깨진 HWPX/validator ParseError를 차단했다. Pillow는 이미지 사용 시점에만 lazy import 하도록 바꿔 텍스트 보고서 생성은 Pillow 없이 동작하며, 이미지 사용 시 누락 안내를 명확히 반환한다. 참조형 링크·autolink·링크 정의 누출, GUIDE 번호목록 설명, Python 3.10+ 런타임 가드도 함께 교정했다.
- **hwp-report v0.2.2** (#341, #339 후속 Codex 리뷰): 강조 분해 잔여 엣지케이스 차단. (1) `***볼드이탤릭***`/`___..___` 삼중 강조를 strong+italic 토큰으로 추가 — 이전엔 `***긴급***` 이 `*긴급*` 으로 별표를 남기고 표 셀 `rich_rows` 런까지 깨지던 결함을 제거(언더스코어 삼중과의 비대칭 해소). (2) 코드 스팬을 강조 파싱 *전에* placeholder 로 마스킹 — 강조 `*` 가 코드스팬 경계를 가로질러 닫히던 `` *`a*` `` → `*a*` 교정 + 코드 내용 literal 보존, 강조가 코드스팬을 *감싸는* 정상 케이스(`` *a `c` b* ``)는 유지. (3) 내용이 구분자뿐인 degenerate 강조(`****`·`___`)는 평문 보존(별표 삭제 금지). 본문·표 셀 양쪽 적용. 신규 회귀 7종(단위 57→64 GREEN).
- **hwp-report v0.2.1** (#339): inline 마커 strip 데이터 손상 + 무성 손실 경고 정합. (P1) `_`/`*` 강조 분해에 CommonMark flanking 근사를 적용 — 여는/닫는 구분자 옆 공백·intraword 언더스코어를 강조에서 배제해 `report_2026_final.hwpx`·`snake_case`·`가로 * 세로` 같은 **실제 데이터가 본문·표 셀에서 삭제되던 무성 손상**을 제거(`strip_inline`↔`_parse_emphasis` 단일 flanking 소스로 통합). (P2-a) clamp 경고를 들여쓰기 '폭(>4칸)'이 아니라 '리스트 단계 수'(스택)로 판정 — 2칸 단위 3단계도 정확히 경고(이전엔 무성 clamp). (P2-b) front-matter/인자 제목과 **다른** `# H1` 이 본문에서 사라지던 무성 손실을 경고로 표면화(같으면 dedup 유지). (P3) GUIDE 의 근거 없는 PDF 미리보기 약속 제거(엔진·형제 hwpx 모두 PDF 미지원) + SKILL 의 죽은 "추적: GitHub issue" 포인터를 정직한 비목표 문구로 교체. 신규 회귀 12종(단위 45→57 GREEN) + 예제 6종 무손실 스모크 가드.

## [3.10.3] — 2026-07-18 (이슈 #1217)

### Changed
- 자격증명 사전 점검 금지 규칙 (#1217) — SKILL "키 주입" 실행 규칙을 실패 주도로 재서술: `ls`/`find` 사전 점검 금지(셸 패턴이 별칭 파일명을 놓쳐 오탐 — 실사용 리포트 검증), 스크립트 우선 실행 후 자격증명 누락 실패 시에만 지침 값 주입 재시도.

## [3.10.2] — 2026-07-18 (이슈 #1210·#1212)

### Changed
- 환경변수 파일명 별칭 안내 (#1210) — blog-seo·calendar·email·market-scan·web-search GUIDE/SKILL에 `환경변수.txt` 등 별칭 지원 안내 추가.
- 자격증명 출처 표시 규칙 (#1212) — blog-seo·calendar·email·web-search SKILL에 출처 표시 규칙 추가.

## [3.10.1] — 2026-07-18 (이슈 #1205)

### Changed
- 자격증명 안내 반전 (#1205) — blog-seo·calendar·email·web-search GUIDE/SKILL + market-scan GUIDE 9개 문서의 키 설정 1순위를 Claude 지침에서 **작업 폴더 루트 `.env`**(자동 탐색)로 반전. 지침 방식은 보조.

## [3.10.0] — 2026-07-12

### Added

- **task-brief 를 itda-work published 스킬로 재배치 (#1051)** — hyve `.claude/skills/`(프로젝트 운영)가 아니라 skills/ 모노레포의 itda-work published 스킬(skills.pub 배포)로 관리(마스터 지시). itda 규약 정합: SKILL.md frontmatter 풀셋(license·compatibility·metadata)·한국어 인용 트리거 4개·tags EN 한정, `scripts/check_task_brief.py`(구조 게이트 C1~C5, 검증 자기보고 금지 축) + 회귀 13건 + GUIDE.md·CHANGELOG.md. 구 `.claude/skills/task-brief/` 는 제거(중복 청산).

## [3.9.0] — 2026-06-20

### Changed

- **etf-naver → itda-stocks 이동 (#525)** — ETF 분석은 증권 도메인이라 itda-stocks로 재배치(SPEC-WORK-SPEC-RESTORE-001 "hyve 흡수 예정"의 실현). 기능은 itda-stocks에서 유지되나, itda-work 단독 사용자에겐 etf-naver가 빠지는 변경. ⚠️ etf-naver는 Apache(공개)였으나 itda-stocks(비공개)로 이동해 공개 배포에서 빠진다(skills.pub 미공개 전제로 수용).

## [3.8.1] — 2026-06-11

### Changed

- **web-automation 0.1.1** (#247): R5 에 takeover 경로 추가 — 어댑션 dogfooding run3 에서 에이전트가 `takeover_required`(hyve 의 로그인 자동입력 거부 정책) 흐름을 몰라 세션을 닫고 자격증명을 curl 평문 명령으로 우회한 갭을 봉합. R5a(takeover: 사용자 visible Chrome 인증 → `takeover.resume`)/R5b(attach) 재구성 + 함정 표에 "자격증명 스킬 밖 우회 금지" 행 추가.

## [3.8.0] — 2026-06-11

### Added

- **web-automation 0.1.0 신설** (#241, #215 어댑션 축): hyve `web_browse` MCP 19 액션의 사용 레시피 정본 — 코드 없는 가이드 스킬. 작업 유형별 레시피 5종(단발 읽기·멀티스텝 상호작용·결정론 추출·대량 수집·attach 차단 우회) + 토큰 절약 원칙(`interactive_only`/`diff` 기본값) + 실측 기반 함정 표. 사이트 특화 스킬(coupang 등)이 복붙하던 공통 호출 패턴의 단일 정본 — hyve catalog 와 같은 저장소에서 함께 진화해 레시피 drift(#141 web-reader deprecated `render` 사례)를 차단.

## [3.7.2] — 2026-06-10

### Changed

- **web-search GUIDE**: 네이버 검색 API 키 발급 안내에 발급 가이드 페이지(<https://itda.work/credentials/naver-openapi/>) 링크 추가 (SPEC-CREDENTIALS-GUIDE-001 역링크 전수 조사 보완).


## [3.7.1] — 2026-06-10

### Changed

- **GUIDE 발급 안내 정비 (SPEC-CREDENTIALS-GUIDE-001)**: blog-seo·market-scan·calendar·email·plan-work GUIDE의 API 키·앱 비밀번호 발급 안내를 발급 가이드 페이지(<https://itda.work/credentials/>) 링크로 연결. blog-seo `references/naver-api.md`의 발급 상세는 저장소 정본(`docs/credentials/`)으로 이전.


## [3.7.0] — 2026-06-10

### Added

- **hwp-report v0.2.0** — 마크다운 표·이미지 표현력 대폭 확장 (#156, #158). 표: 열 정렬(`:--`/`:-:`/`--:`)→HWPX 본문 셀 정렬, 셀 내 굵게/기울임 서식, 열 너비 내용 비례 배분, 마크다운 표 인라인 위치 보존. 이미지: BinData 임베드 + 매퍼 배선(Go) + .NET parity — `![](path.png)` 가 실제 문서 내 이미지로 들어간다. `/refine` 이중 리뷰 반영 보강. frontmatter `updated_at` 누락 정비(check_versions --strict 위반 해소).
- **web-search v0.1.1** — market-scan 핸드오프 회귀 가드(`tests/test_handoff_market_scan.py`, deployed-style) 신설: market-scan Q4 '키 감지'가 광고한 엔진 키 이름 ⊇ web-search `ENGINE_SPECS` required 키 + `--check-env` 종착점 alive 검증. 작성 즉시 market-scan `NAVER_SEARCH_CLIENT_SECRET` 축약 표기 갭 1건 적발·교정. naver 종류별 날짜 shape(web 부재/news `pubDate`/blog `postdate`) 회귀 케이스 보강(단위 66→68 GREEN). SKILL.md 사용법에 소스트리 개발자용 `PYTHONPATH=skills/shared` 캐비엇 1줄 추가(배포본은 `_inject_shared_modules` 자기치유로 무관). SPEC-WEB-SEARCH-001 status 정정(Draft→Done — 헤더 "라이브 미검증"↔본문 라이브 PASS 모순 해소). cf. #150 후속.

### Changed

- **market-scan v0.1.1** — `web-search` 스킬을 수집 엔진 포트폴리오에 편입(양방향 핸드오프 비대칭 해소 — web-search 는 이미 market-scan 을 위임 대상으로 가리켰으나 역방향이 부재했다). 내장 WebSearch 의 단일 인덱스 한계를 다중엔진 fan-out(Tavily·Naver·Serper·Exa·Perplexity)으로 보완해 교차검증의 전제인 "서로 다른 유형의 독립 출처"를 넓힌다 — **국내(지역=국내) 조사의 Naver 색인**·Exa 시맨틱이 차별점. 위계 보존(인접 **위임 경계**가 아닌 §2단계 **하위 수집 엔진**으로 자리매김), **거짓 메뉴 금지 준수**(`--check-env`/엔진 키 보유 시에만 Q4 메뉴 노출, 키 0개면 내장 WebSearch만), **비용 가드**(기본 무료 `--engines tavily,naver`; 유료 Perplexity·Exa 는 핵심 수치 교차검증 한정). cf. SPEC-WEB-SEARCH-001 §7 · #150.

## [3.6.0] — 2026-06-09

### Added

- **web-search** (신규·experimental): 다중 검색엔진 통합 조회 스킬. 질의어 하나로 키 보유 엔진(Perplexity·Tavily·Serper·Exa·Naver)을 fan-out 호출해 round-robin 병합·URL 중복 제거한 정규화 결과 목록을 돌려준다(조회 전용). `--engine auto`·`--engines` 서브셋·`--naver-type web|news|blog`·`--format json|markdown`·`--check-env`. Perplexity answer+citations 매핑, 기존 `NAVER_CLIENT_ID/SECRET` 폴백, 키 마스킹(stdout/stderr 미노출), 종료코드 매트릭스(0/2/3/4/5/6)+부분실패 `errors[]` envelope. 엔진 선택 가이드(상황별 라우팅 지침). Google CSE(2027 폐지)·Bing(2025 은퇴) 대신 Serper 채택. 표준 라이브러리만 사용. 단위 63 GREEN(0 skip) + tavily·naver·perplexity·serper·exa·auto 라이브 검증 통과. (Brave는 무료 구독 활성화 이슈로 v0.1 제외, 향후 재검토 — 구현 git 이력 보존.)
- `itda-work` 스킬 수: 17개 → **18개** (README 웹·미디어 카테고리 등재).
- `itda-work` 버전 bump: 3.5.0 → **3.6.0** (Minor — 신규 스킬 1건).

## [3.5.0] — 2026-06-09

### Changed

- **GUIDE.md 평이언어 정책 (SPEC-GUIDE-NO-SHELL-001)** — 전 플러그인 35개 `GUIDE.md`에서 셸 명령(`python3`·`pip`·`<name>.py`)·CLI 플래그를 자연어로 일괄 전환. GUIDE 는 일반 사용자 문서이며 사용자는 Claude 에게 자연어로 요청하지 터미널을 다루지 않는다 ([3.4.0] README/docs CLI 노출 금지 정책의 GUIDE 확장). 자격증명 설정값만 `dotenv` 블록으로 유지. calendar GUIDE 는 네이버 캘린더를 첫 번째로 재배치하고 지원 캘린더(네이버·iCloud·커스텀 CalDAV) 서비스 링크 표를 서두에 추가.

### Added

- **market-scan** (신규·experimental): 인터뷰 기반 시장조사 스킬. 짧은 인터뷰로 목적·범위를 잡고 1차 출처 우선·교차검증·사실/추정 분리로 의사결정용 보고서 한 장을 생성한다("검색=뉴스 클리핑"과 구분, 0단계에서 개요 vs 조사 의도 분기). 데이터 소스는 가용성 점검 후 multiSelect 로 제시(웹·`itda-gov:*` 공공API·주제별 도메인 스킬), 엄격 검증은 `ground-check`·수집 폴백은 `web-reader` 에 위임. 시장규모 top-down/bottom-up 추정 + 단일출처·리포트밀·정형 단위검증 가드. 라이브 dogfood(KOSIS·DART·ECOS) + 트리거 실측 recall/precision 100%.
- **GUIDE 셸 명령 금지 강제 (코드 게이트)** — lint `shared/scripts/check_guide_no_shell.py` + 실저장소 전수 pytest `shared/tests/test_check_guide_no_shell.py`(release.yml CI `OS_NEUTRAL_DIRS` 에 `shared/tests` 편입 — 기존 check_* pytest 도 CI 자동 검증으로 승격) + justfile `check-guide` 타겟 + 작성 원칙 rule `.claude/rules/itda/skills/guide-authoring.md`.
- **`guide-writer` v0.11.0** — 재발 방지 근본 수정. reference 3종(interview-heavy·media-generation·utility-tool) 을 자연어화본으로 동기화하고, SKILL.md REQ-GW-014/025 규칙을 "셸 명령·CLI 플래그 금지, 자연어 우선" 으로 전환. 자동 생성 시 셸 명령 재유입 차단.

### Removed

- **nano-banana 좀비 사슬 제거** — `scripts/sync_models.py`(itda-nano-banana 전용 Gemini 모델 동기화 CLI, 코드 참조 0·CI/마켓플레이스 미노출) + 테스트, `.claude/skills/itda/update-skill-nano-banana.md`, `.claude/rules/itda/skills/nano-banana-{guide,models}.md`. itda-nano-banana 스킬 본체는 이미 부재 상태로 갱신 부속물만 잔존하던 것을 묶음 폐기 (zombie 방지 — 자동화 사슬 동반 정리).

## [3.4.0] — 2026-05-21

### Removed
- `itda-setup` 스킬 폐기. reactive 워크플로우(에러 발생 시 환경변수 설정)로 충분하다고 판단. env_vars frontmatter도 함께 폐기되며 발급 가이드는 각 스킬 SKILL.md body의 "## 환경 변수" 표로 이전됨.

### Improvements

- **사용자 가이드 일괄 점검 (v6.2.5)** — `itda-work/README.md`와 `itda-work/docs/guide-data-collector-api-keys.md`에 노출된 `python3 scripts/*.py` / `py -3 scripts/*.py` 명령 총 20곳을 자연어 발화 예시로 대체. 일반 사용자용 문서에 CLI 명령 노출 금지 정책 일괄 적용. SKILL.md·HANDOFF.md·references는 Claude/개발자용 instruction으로 보존.

### Added

- **README 등재 누락 보강 — 3개 기존 스킬 공식 카탈로그 등재** ("조사·검증", "환경·설정" 카테고리 신설)
  - **itda-ground-check** (v0.10.0, 2026-05-12 도입, 2026-05-13 최신): 1차 소스 강제 조사 + 독립 검증 + 실사용 예시 확장 3단계. Cowork 우선, WebFetch 실패 시 web-reader fallback. Public Web 카테고리에 한정.
  - **itda-investigate** (v0.10.1): 원인 불명 상황의 체계적 조사. 경쟁 가설 + 반증 실험으로 증거 기반 결론 도출. 디버그·성능·아키텍처·검증·해석 5종 타입 지원.
  - **itda-setup** (v1.0.0): API 키·환경변수 스캔 + 대화형 설정 + 프로젝트 CLAUDE.md(스킬 체인 정책) 자동 생성. itda 스킬팩 메타 설정 entry-point.
  - `itda-work` 스킬 수: 11개 → **14개** (README 표 기준, find-work 등재 직후 시점에서 갱신).
  - `itda-work` 버전 bump: 3.3.0 → **3.4.0** (Minor — 신규 등재 3건, 신규 카테고리 2종).
  - 본 항목은 **신규 스킬 도입이 아니라 README 동기화**임을 명시. 각 스킬의 실제 도입·기능 변경 이력은 스킬별 CHANGELOG 및 과거 커밋(`5cacac9`, `f8cf34c`, `c072834` 등) 참조.

- **itda-find-work v0.9.1: 비개발자 업무 발굴 인터뷰 스킬 신규 도입** (업무 발굴 카테고리 신설)
  - Claude Cowork 전용. 비개발자 직장인이 "내 업무 중 뭘 Claude로 풀어볼지 모르겠다"는 막막한 상태에서 출발해 단계별 인터뷰로 후보를 끄집어낸다.
  - 두 트랙 지원: (A) 반복 업무, (B) 미지의 문제, 혼합 인정.
  - 4단계 절차: 시작 안내 → 문제 발굴 + 트랙 명시 → 집요한 Grill 6항목 → 데이터·실행 경로 → 메모 작성.
  - Progressive Disclosure 적용: SKILL.md(본문 ~255줄) + `references/{tracks,paths,data-sources}.md`(lazy load) + `GUIDE.md`(강사·운영자용, Claude 미로드).
  - 두 트랙 dry-run 검증(트랙 A 12턴 김민호 대리 페르소나, 트랙 B 17턴 박지영 차장 페르소나) 통과 후 결함 4건 수정 적용(v0.9.0 → v0.9.1).
  - `itda-work` 스킬 수: 10개 → **11개** (README 표 기준).
  - `itda-work` 버전 bump: 3.2.0 → **3.3.0** (Minor).

- **itda-setup v0.9.2 → v1.0.0: 프로젝트 CLAUDE.md 자동 생성 (스킬 체인 정책)** — Cowork 환경에 hook이 없는 한계를 극복하기 위해 KNOWLEDGE.md §3의 "CLAUDE.md = 팀 매뉴얼" 패턴을 itda-work에 이식. 산출물별 스킬 체인을 [HARD] 규칙으로 명문화하여 모델이 매 턴 자율 준수하도록 강제.
  - `references/chain-map.yaml` (128 lines, 신규): 15개 산출물(blog/report/newsletter/proposal/customer_email/internal_memo/hwp_read/pdf_extract/web_research/finance_etf/finance_fx/image_edit/debug 등) → 권장 스킬 시퀀스 + enforcement(hard/soft/none) 매핑. review_strength_policy로 사용자 검수 강도(강/표준/약)를 enforcement 변환에 적용.
  - `references/templates/CLAUDE.md.tmpl` (79 lines, 신규): 사용자 프로젝트 CLAUDE.md 템플릿. 11개 슬롯({project_name}, {chain_table}, {trigger_examples}, {user_preserved_section} 등)으로 인터뷰 응답 주입.
  - `SKILL.md` Phase 3 신규 (기존 Phase 3 완료보고 → Phase 4): 매핑 로드 → 기존 CLAUDE.md 처리 분기(머지/백업/취소 AskUserQuestion 프롬프트) → 5~7문항 인터뷰(2라운드, AskUserQuestion 4문항 한계 준수) → 정책 변환 → 슬롯 치환 → 분기별 파일 쓰기. cowork-plugins 프로젝트 컨텍스트 패턴 차용.
  - `allowed-tools`에 `Edit`, `AskUserQuestion` 추가 (머지 모드 in-place 교체 + 인터뷰).
  - 신규 스킬 추가 시 chain-map.yaml + itda-setup version bump 가이드 본문에 명시.

- **itda-human-tone tests/ 디렉토리 + SKILL.md 4단계 보완** (P0 후속 작업)
  - `tests/test_lock_preserved.py` (7 cases): 마스킹/복원 라운드트립, QUOTE/LAW 카테고리, 환각 숫자 탐지, placeholder 삭제 탐지
  - `tests/test_metrics_smoke.py` (4 cases): metrics.py CLI 회귀, baseline 로딩, AI/인간 스타일 분류, --output JSON 모드
  - `tests/test_triggers.py` (8 cases / 19 subtests): SKILL.md description 트리거/넌트리거 회귀(draft-post·blog-seo·email 충돌 방지), folded style + 한국어 첫 문장 정책 검증
  - `just test-skill human-tone` 컨벤션 호환 — 19/19 passed

### Changed

- **itda-human-tone v1.0.0 → v2.0.0: 풀패키지 전환** ([`epoko77-ai/im-not-ai`](https://github.com/epoko77-ai/im-not-ai) v1.6.1 MIT, ⭐937 stars 차용)
  - v1.0 휴리스틱 15개 본문 폐기 → 결정적 메트릭·사전·보존 가드 풀패키지로 전환
  - `references/ai-tell-taxonomy.md` (666줄) — 10대 분류 × 40+ 패턴 SSOT + 직장인 K 카테고리 5종 부록 추가
  - `references/quick-rules.md` (169줄) — Monolith Fast Path 매칭 룰 + K 압축 룰 부록
  - `references/rewriting-playbook.md` (322줄) — 카테고리별 치환 레시피 + 직장인 시나리오 4종(보고서/이메일/기획서/공지) Before/After 사례집 §6
  - `scripts/metrics.py` (404줄, 표준 라이브러리만) — 22개 지표 결정적 측정, KatFish 베이스라인(인간 470편/AI 1624편)
  - `scripts/lock_preserved.py` (298줄, 자체 작성) — 숫자·날짜·인용·법조항·고유명사를 placeholder로 잠그는 결정적 마스킹 가드. 환각·환경 변경 100% 차단
  - 4대 철칙(Fidelity First / Span-Grounded / Tone Match / No Over-Polish) + 변경률 30/50 가드 + 13항 의미 동등성 audit 통합
  - SKILL.md 본문 179줄 → 208줄 (메트릭/스크립트 명시적 호출 흐름 5단계)
  - `LICENSE-im-not-ai` 동봉 (원본 MIT 사본). README.md "차용 출처" 섹션에 자산별 변경 사항 명시
  - **itda-work 버전 bump**: 3.1.0 → **3.2.0** (Minor — 기존 호출 인터페이스 호환, 출력 품질 대폭 향상)

### Added

- **itda-human-tone v1.0.0: AI 슬롭 후처리 검수 스킬 신규 도입** (콘텐츠·마케팅 카테고리)
  - MIT 라이선스의 AI 글쓰기 탐지 패턴에서 영감을 얻되 내용은 직장인 도메인(보고서·이메일·기획서·공지)에 맞춰 전면 재집필
  - 4종 사무 한국어 AI 패턴(보고서식 군더더기·이메일 과공손·기획서 추상명사 인플레이션·ChatGPT 흔적) 우선 점검
  - 보존 영역 잠금(숫자·고유명사·인용·결재선·서명) → 환각 및 결재라인 사고 방지
  - `--scene` (report/email/proposal/notice), `--register`, `--diff` 옵션
  - `itda-draft-post`와 명시적 차별화: 생성 단계 가드(_anti-ai-korean.md) vs 후처리 검수
  - `itda-work` 스킬 수: 8개 → **9개**
  - `itda-work` 버전 bump: 3.0.0 → **3.1.0** (Minor)
  - plugin.json `keywords`에 `writing`, `검수` 추가

### Breaking Changes

- **`slide-ai`, `stt` 스킬을 `itda-egg`(인큐베이팅 비공개 스킬팩)로 이전** (SPEC-INCUBATE-001)
  - `git mv`로 히스토리 보존: `itda-work/skills/{slide-ai,stt}` → `itda-egg/skills/{slide-ai,stt}`
  - `itda-egg`는 marketplace.json 미등록 비공개 플러그인. 안정화 검증 후 공식 스킬팩으로 졸업 가능
  - 기존 `itda-work` 사용자: 두 스킬이 v3.0.0 업그레이드와 함께 사라짐. 필요 시 itda-egg를 로컬 `claude plugin install`로 추가 등록
  - `itda-work` 스킬 수: 14개 → 12개
  - `itda-work` 버전 bump: 2.0.0 → **3.0.0** (Breaking)

### Added

- **itda-web-reader v2.11.1: selector 도메인 예외 + hidden 일관성 + PARTIAL 보호** (SPEC-WEBREADER-010)
  - `extract()` 라이브러리 호출 시 selector 입력 오류로 호출자 프로세스 종료 차단 (도메인 예외 계층 도입)
  - `exceptions.py`: `SelectorError`, `SelectorNoMatchError`, `SelectorSyntaxError` 클래스 추가
  - selector 경로의 hidden 요소 제거 누락 (자동 본문 탐지 경로와 정책 일관)
  - 사용자 명시 selector가 PARTIAL_REMOVE_PATTERNS와 매칭 시 결과 소실 방지 (직속 자식 보호)
  - YouTube URL + `--selector` 시 명시적 warning 출력 후 selector 무시 (exit 0)
  - CLI 가시 메시지 및 exit code는 SPEC-009 AC-3/AC-4와 byte-level 동일 유지
  - 신규 테스트 4 파일 29 passed, 전체 web-reader 회귀 227 passed / 0 failed

- **itda-email v0.15.0: 증분 수집 (`--since-last-run`) + 폴더 처리 호환성 수정** (SPEC-EMAIL-007 + post-release fixes)
  - `email_state.py`: IMAP UID 커서 영속화 — `load_state` / `save_state` (원자적 쓰기) / `get_account_state` / `update_account_state` / `reset_account_state` / `make_account_key` 6개 순수 함수
  - `read_email.py --since-last-run`: `(provider, email, folder)` 트리플별로 마지막 본 UID를 기억해 새 메일만 반환. 첫 실행 시 최신 `--count` 개로 커서 seed, 이후 `UID prev+1:*` 조회
  - `read_email.py --reset-state`: 특정 계정+폴더의 커서만 제거 (다른 폴더/계정 보존)
  - UIDVALIDITY 변경 감지: `imap.response("UIDVALIDITY")` → `imap.status()` fallback, 변경 시 stderr 경고 + 자동 재-seed
  - 출력 스키마: `--since-last-run` 사용 시 `{since_last_run, previous_last_uid, current_last_uid, uidvalidity_changed, new_count, messages}` 객체로 래핑 (미사용 시 기존 배열 유지 — 하위 호환)
  - 상태 파일 위치: `{CWD}/.itda-skills/email/state.json` (Claude Code) 또는 `{CWD}/mnt/.itda-skills/email/state.json` (Cowork + 호스트 마운트) — `shared/itda_path.resolve_data_dir("email")` 사용
  - **한글 폴더 SELECT 지원**: `read_email.py --folder "보낸메일함"` 등 비-ASCII 폴더명을 자동으로 Modified UTF-7 인코딩 (RFC 3501 §5.1.3). 기존 v0.14.0에서는 `'ascii' codec can't encode` 에러 발생
  - **공백 포함 폴더명 지원**: `--folder "Sent Messages"`, `--folder "Deleted Messages"` 등 Naver canonical 영문 폴더명을 자동으로 double-quote 처리. imaplib이 자체 quoting을 하지 않아 기존엔 BAD 에러
  - **Naver `list_folders.py` LIST syntax 수정**: `imap.list("", "*")` → `imap.list()`. Naver의 엄격한 파서가 `LIST  *` (unquoted empty reference)를 거부하던 문제 해결. Gmail은 기존에도 동작했음
  - 191+ 테스트 통과 (SPEC-EMAIL-007 신규 31건 + `_encode_folder` regression 5건 포함)

- **itda-email v0.14.0: 폴더 탐색 (`list_folders.py`)** (SPEC-EMAIL-006)
  - `list_folders.py`: IMAP LIST + STATUS로 폴더 목록과 MESSAGES/UNSEEN 카운트를 한 번에 조회
  - `email_imap_utf7.py`: Modified UTF-7 encode/decode (RFC 3501 §5.1.3)
  - `--no-status` 플래그로 STATUS 호출 생략 (빠른 조회)
  - 응답에 `name` (디코딩된 사람이 읽는 이름), `raw_name` (Modified UTF-7 원본), `delimiter`, `flags`, `messages`, `unseen` 포함
  - 155/155 테스트 통과 (43건 신규)

- **itda-email v0.13.0: 피싱 경고 신호** (SPEC-EMAIL-005)
  - `email_security.parse_auth_results`, `build_auth_label`, `reply_to_differs` — SPF/DKIM/DMARC 결과와 Reply-To 도메인 불일치 탐지
  - `read_email.py` 출력에 `spf`, `dkim`, `dmarc`, `auth_label`, `reply_to`, `reply_to_differs`, `warnings` 필드 추가
  - 사용자가 피싱 의심 메일을 AI에게 물어볼 때 바로 판단 근거 제공

- **itda-email v0.12.0: 본문 5000자 기본 + `--max-chars`** (SPEC-EMAIL-004)
  - `read_email.py --max-chars N`: 본문 최대 글자 수 제어 (기본 5000, `-1` 무제한, `0` 빈 본문)
  - 응답에 `body`, `total_chars`, `truncated` 필드 추가
  - Truncate 안내: `...[이하 N자 생략. --max-chars=-1로 재실행하면 전체 본문을 볼 수 있습니다.]`

- **itda-email v0.11.0: Daum/Kakao 지원 + Prompt Injection 방어** (SPEC-EMAIL-003)
  - Daum/Kakao SMTP+IMAP 프로바이더 등록 (`@daum.net`, `@hanmail.net`, `@kakao.com`)
  - `email_security.sanitize_for_llm`: 수신 메일의 `from`/`subject`/`body` 필드를 LLM 컨텍스트 주입 전 sanitize
  - `wrap_email_content`: 본문을 `===EMAIL_CONTENT_START===` / `===EMAIL_CONTENT_END===` 마커로 래핑

- **itda-email v0.10.0: Gmail IMAP 수신 지원** (SPEC-EMAIL-002)
  - Gmail 앱 비밀번호로 IMAP 수신 활성화 (기존엔 Claude Gmail MCP 안내 후 거부했음)
  - `--provider gmail` 동작 방식 통합 (Naver와 동일 인터페이스)

### Changed

- **go-cli 레포 분리 + R2 배포 + 플러그인 리네임** (SPEC-R2DEPLOY-001)
  - `go-cli/` → 독립 레포 `itda-work/itda-skills` 분리 (git subtree split으로 히스토리 보존)
  - `plugins/itda/` → `plugins/itda-core/` 리네임, `plugin.json`: name=itda-core, version=0.1.0
  - `plugins/itda-stocks/`: version=0.1.0, org=itda-work 업데이트
  - `marketplace.json`: source=./plugins/itda-core, org=itda-work 업데이트
  - `release.yml`: Go 빌드/테스트 스텝 제거, itda-core 경로 적용
  - `justfile`: go-cli 레시피 제거, 잘못된 테스트 경로 수정 (itda-docs/itda-media → itda-core)
  - `pack-plugins`: 통합 버전 주입 제거 (플러그인별 독립 버전 관리)
  - `just pack-plugin <name>` 레시피 추가
  - CLI 레포 `~/Apps/itda-skills/cli/`: 5개 플랫폼 빌드(linux/arm64 추가), R2 CDN 배포 워크플로 생성

### Added

- **itda-email: 통합 이메일 스킬** (SPEC-EMAIL-001)
  - `email_providers.py`: Naver/Gmail/Custom SMTP 프로바이더 레지스트리, `detect_providers()`, `get_provider()`, `validate_email()`, `validate_port()` 헬퍼
  - `check_env.py`: 환경변수에서 프로바이더 자동 감지, JSON 상태 리포트 출력
  - `check_connection.py`: SMTP_SSL + IMAP4_SSL 연결 테스트 (10초 타임아웃)
  - `send_email.py`: SMTP SSL 이메일 전송, CC/BCC 지원, HTML/Plain 텍스트 MIME
  - `read_email.py`: IMAP SSL 수신, RFC 2047 한국어 헤더 디코딩, Gmail 거부(Claude Gmail MCP 안내)
  - 51개 테스트 통과, 93% 커버리지, stdlib only (외부 패키지 없음)

## [0.8.0] - 2026-03-12

### Removed

- **itda-http-request 스킬 제거** (SPEC-HTTPREQ-002): `itda-web-reader`로 대체됨
  - `beautifulsoup4`, `trafilatura` 의존성 제거 (Claude-native 추출로 전환)

### Changed

- **skill-list 컬럼 개선 및 정렬** (SPEC-SKILLLIST-001): `just skill-list` 출력에서 PLUGIN 컬럼 제거 → UPDATED 컬럼 추가, 최신 업데이트 역순 정렬
  - `skill_list.py`: `_extract_updated()` 추가 (SKILL.md `metadata.updated` 파싱), PLUGIN→UPDATED 컬럼 변경, 날짜 내림차순 정렬 (n/a는 맨 아래)
  - `scripts/tests/test_skill_list.py`: 단위 테스트 5개 신규 작성 (전체 77개 통과)
- **버전 단일 소스화** (SPEC-SKILLVER-002): `versions.yaml` 제거, 스킬 버전을 `SKILL.md metadata.version` 단일 소스로 통합
  - `skill_list.py`: `_load_versions()` 제거 → `_extract_version(skill_md)` 추가 (SKILL.md frontmatter 파싱)
  - `skill_get_version.py`: `versions.yaml` 읽기 제거 → SKILL.md `metadata.version` 읽기로 전환
  - `skill_bump.py`: `versions.yaml` 쓰기 제거 → SKILL.md만 업데이트
  - `skill_upgrade.py`: skill 타입은 SKILL.md, plugin 타입은 `plugin.json`에서 버전 읽기/쓰기로 전환 (`json` 모듈 사용)
  - `validate-plugin.py`: `validate_versions_yaml()` 제거 → `validate_skill_versions()` 추가 (SKILL.md `metadata.version` semver 검증)
  - `justfile`: `plugin-upgrade` 주석에서 구식 `versions.yaml` 언급 제거
- **justfile 레시피 그룹 정리** (SPEC-JUST-001): `[group]` 속성 추가로 `just --list` 출력을 `dev` / `skill` / `dist` 3개 카테고리로 구분
- **itda-law-korean API HTTPS 마이그레이션** (SPEC-LAWKR-002): API 요청 URL을 `https://`로 변경 (보안 강화)
- **법제처 OC 문서 정정** (SPEC-LAWKR-002): SKILL.md 및 api-guide.md에서 오해 소지 있는 `OC=test` 가능 문구 제거, OC 등록 필수 안내 명확화

### Added

- **itda-web-reader 스킬 추가** (SPEC-HTTPREQ-002): Claude-native 웹 콘텐츠 추출 스킬로 `itda-http-request` 대체
  - `fetch_html.py`: `requests` 기반 정적 페이지 페처 (EUC-KR/CP949 자동 감지, 재시도 로직, 쿠키/커스텀 헤더 지원)
  - `fetch_dynamic.py`: Playwright Chromium 헤드리스 (JS 렌더링 페이지, networkidle 대기)
  - `clean_html.py`: Python stdlib(`html.parser`)만 사용한 HTML 전처리기 (script/style/svg/iframe 제거, 60%+ 토큰 절감)
  - `SKILL.md`: Claude 서브에이전트 5단계 워크플로우 (Fetch→Clean→Extract→Post-process→Structured JSON)
  - 48개 테스트 (전부 mocked, 실제 네트워크 호출 없음), 커버리지 86–93%, 크로스플랫폼 (Ubuntu/macOS/Windows)
- **itda-http-request 스킬 추가** (SPEC-HTTPREQ-001): 한국 웹사이트 크롤링을 위한 HTTP 요청 스킬
  - `http_fetch.py`: Python stdlib `urllib` 기반 경량 HTTP 페치 (EUC-KR/CP949 자동 감지, 재시도 로직, 쿠키 세션 유지, CSS 셀렉터 추출)
  - `js_fetch.py`: Playwright Chromium 헤드리스 브라우저 (JS 렌더링 페이지, 지연 설치 지원)
  - `extractors.py`: HTML→텍스트, CSS 셀렉터, JSON 출력 공유 모듈
  - 87개 테스트 (전부 mocked, 실제 네트워크 호출 없음), 크로스플랫폼 (Ubuntu/macOS/Windows)
- **목(目) 파싱 지원** (SPEC-LAWKR-002): `_extract_article_content()`에서 `<호>` 하위 `<목>` 요소 파싱 추가 (예: 형법 조문의 "가.", "나." 항목)
- **display 파라미터 범위 검증** (SPEC-LAWKR-002): `search_laws()` display 값을 1-100 범위로 자동 클램핑
- **테스트 커버리지 개선** (SPEC-LAWKR-002): 23개 테스트 추가, 커버리지 96% → 98%
- **itda-law-korean 스킬 추가**: 국가법령정보 조회 (SPEC-LAW-001)
  - `law_api.py`: 법제처 DRF Open API 공통 모듈 (검색, 조문 조회, JO 파라미터 변환)
  - `search_law.py`: 법령명/키워드 검색 CLI (테이블/JSON 출력)
  - `get_law.py`: 법령 전문·특정 조문 조회 CLI (--article, --toc, --format)
  - 가지조문 지원: "76조의2" → JO=007602 자동 변환
  - Python 표준 라이브러리만 사용 (별도 설치 불필요)
  - 56개 테스트 / 95% 커버리지 / macOS·Linux·Windows 크로스플랫폼
- **itda-api-cost 스킬 추가**: Google Gemini API 호출 비용 추적
  - `track_usage.py`: API 호출 메타데이터 기록
  - `report_usage.py`: 사용량 및 비용 리포트 생성
  - 저장 위치: `.itda-skills/api-costs.jsonl` (샌드박스 상대 경로)
- **nano-banana 참조 문서** (`.claude/rules/itda/skills/`):
  - `nano-banana-models.md`: 모델 카탈로그 (조건부 로드: `**/itda-nano-banana/**`)
  - `nano-banana-guide.md`: 이미지 생성 가이드 (조건부 로드: `**/itda-nano-banana/**`)
- **`scripts/sync_models.py`**: Gemini 모델 문서 실시간 동기화 CLI (stdlib-only HTTP)
- **`update-skill-nano-banana` 스킬**: 모델 정보 신선도 유지 Claude Cowork 스킬

### Changed

- **itda-nano-banana 모델 업그레이드** (SPEC-NANOBANANA-002):
  - 기본 모델 변경: `gemini-2.5-flash-image` → `gemini-3.1-flash-image-preview`
  - `MODEL_CATALOG` 추가: 3개 모델(3.1-flash-preview, 3-pro-preview, 2.5-flash) 및 기능 정보
  - 모델/종횡비/해상도/thinking_level 유효성 검증 추가
  - `thinking_level` 옵션 파라미터 (`minimal`/`high`) — 3.x 모델 전용
  - `--list-models` CLI 플래그 추가
  - 확장 종횡비 (1:4, 4:1, 1:8, 8:1) 및 0.5K 해상도 — 3.1-flash 전용
  - SKILL.md 전면 재작성: 프로액티브 Claude 가이드, 5개 유스케이스 템플릿, 모델 선택 가이드
- **플러그인 구조 통합**: 3개 플러그인(itda-docs, itda-media, itda-stocks)을 단일 `itda` 플러그인으로 병합
  - 기존 경로: `plugins/itda-docs/`, `plugins/itda-media/`, `plugins/itda-stocks/`
  - 새 경로: `plugins/itda/skills/{itda-font-guide, itda-name-badge, itda-card-news, itda-nano-banana, itda-etf-naver, itda-api-cost}`
- **itda-name-badge**: 기본 출력 경로 변경 (바탕화면 → 현재 디렉토리)
- **데이터 저장 정책**: 모든 스킬의 데이터는 `.itda-skills/` 상대 경로 사용 (사용자 홈 제외)

### Added (Continued)

- **WIP 플러그인 배포 제외 지원** (`plugin.json`에 `"wip": true` 설정 시 `just pack-plugins` 실행 시 자동 제외)
  - Unix(bash) 및 Windows(PowerShell) `dist` 레시피 모두 적용
  - WIP 제외 시 콘솔에 `Skipping WIP plugin: <name>` 메시지 출력
  - `dist/.claude-plugin/marketplace.json`에서 WIP 항목 자동 필터링 (소스 파일 변경 없음)
  - 모든 플러그인이 WIP일 경우 경고 출력 후 빌드 정상 완료
- **`validate-plugin.py` WIP 필드 검증**: `"wip"` 필드가 boolean이 아닌 경우 에러 보고
- **테스트 추가**: `wip` 필드 타입 검증 테스트 5개, 빈 plugins 배열 경고 처리 테스트

### Changed

- `validate-plugin.py`: `plugins` 배열이 빈 경우 에러 → 경고로 변경 (모든 플러그인이 WIP인 엣지 케이스 대응)

### Notes

- 기존 플러그인(`itda-docs`, `itda-stocks`)은 `"wip"` 필드 없이 stable로 유지 (역호환성 보장)
- `"wip"` 필드 미존재 = `"wip": false`와 동일하게 처리
