# Changelog — itda-web-reader

## [7.2.0] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- JS 렌더·봇 차단·SPA 에스컬레이션 안내를 hyve MCP `web_browse` 에서 브라우저 경로 `itda-web:aside-browser-mcp`(Aside 브라우저)로 바꿨다 — SKILL.md·GUIDE.md·README·migration.md, CLI 안내문(`--dynamic-only`·SPA 어댑터 거부, WAF 격자 소진 `untried_routes`, `diagnose_url` 403 권고). exit code 계약은 그대로.
- `waf_profiles.yaml`·`waf_detector.py` 의 `fallback_when_challenge` 토큰 `hyve_mcp` → `browser`.
- `[책임 경계]` 지목을 `itda-web:aside-browser-mcp` 로. 브라우저 경로는 Aside 하나가 아니라 “실제 브라우저 — Aside, 없으면 Claude in Chrome 등”으로 적고(Windows 는 Aside 미지원), “차단 우회” 는 보장하지 않는다고 낮췄다(WAF 소진 `untried_routes` 문구 포함). `fetch_pipeline.HYVE_DYNAMIC_MIGRATION_MSG` → `DYNAMIC_MIGRATION_MSG`.

### Tests

- 테스트가 실제 홈(`~/.claude` 등)을 읽지 않게 하는 격리 fixture 를 이 스킬 conftest 에도 건다 — `setup.cfg` 가 rootdir 을 좁혀 루트 conftest 가 로드되지 않았다(리뷰 2회차 N2). 가드 `tests/test_home_isolation.py`.
- 그 가드가 `pwd` 를 모듈 최상단에서 import 해 Windows CI 수집 단계에서 죽던 것을 고쳤다(리뷰 3회차 W1) — `pwd` 가 필요한 단언만 함수 안 `importorskip`, 환경변수·`~` 해석 단언은 모든 OS 에서 돈다. 재발 가드 `scripts/tests/test_os_sensitive_imports.py`.

## [7.1.1] — 2026-08-30 (이슈 #1600 S8 실측)

### Fixed

- `extract_records --js-link`: 식별자가 `href` 가 아니라 `onclick`(공시실 `goDetail('id')` 폼 POST) 에 있는 링크도 패턴 대조(href+onclick). GET 변형 `disclosureDataView.do?boardIdx=` 실측 성립.
- `extract_records`: `YYYY-MM` 만 있는 목록의 날짜를 월까지 인식(일은 지어내지 않음) · 제목이 링크가 아닌 카드형 목록(보험연구원 CEO Brief — `<p>` 제목 + "요약보기/다운로드" 링크)을 위한 **날짜 달린 컨테이너 폴백**(`group_signature: container_fallback`). 앵커 기반 목록이 없을 때만 발동.

## [7.1.0] — 2026-08-30 (이슈 #1600 T0)

### Added

- **페이지 봉투(provenance)** — `extract_content --format json` 에 `provenance` 객체(`requested_url·final_url·status·fetched_at·encoding·fetch_phase·waf_profile·content_hash·extractor_version`) 추가, markdown 프론트매터에 `fetched_at`·`status`·`content_hash` 추가. 기존 키 불변. `fetch_pipeline.FetchResult.extra` 가 fetch_html 결과(status·encoding·waf_profile·trace phase)를 버리지 않고 전달한다. 공용 조립 모듈 `scripts/provenance.py` 신설.
- **`scripts/extract_records.py`** — 목록 페이지·RSS/Atom 1장 → 항목 레코드(출처 URL·제목·게시일·원문 발췌·봉투 참조). 발췌는 페이지 텍스트의 부분문자열임을 코드로 검증(변조 시 거부), 날짜·링크 부재는 빈 값(지어내지 않음), 날짜 달린 목록이 없으면 0건 + 봉투. HTTP 없음(fetch_html 재사용).
- 구현 리뷰(gpt-5.6-sol, 2026-08-30) 반영: 봉투 `content_hash` 는 **원 응답 bytes 의 sha256**(`fetch_html` 결과 `content_sha256`)이 정본이고 파일·stdin 입력만 UTF-8 재인코딩 해시 — `hash_basis` 필드로 구분(EUC-KR 등 비UTF-8 에서 두 값이 다르다). `extract_records --js-link/--js-link-template` 로 플레이북 실측 패턴에 의한 `javascript:` 링크 해소(패턴 없이는 지어내지 않고 `stats.records_without_url` 로 신호). `stats.records_with_excerpt` 추가. CLI 호출부 뮤테이션·URL 경로 봉투·Atom·목록 감지 합성 fixture 테스트 보강.
- 근거: 수집 산출을 "요약"이 아니라 "검증 가능한 추출 레코드"로 먼저 세우고 사용자 검증 후 가공하는 2단 구조(마스터 결정 2026-08-30, hyve #1600). fixture 는 보험 정보원 L1 preflight 실측본 5종(`tests/fixtures/records/`).

## [7.0.0] — 2026-07-27 (이슈 #1298)

### Removed

- **Lightpanda 동적 fetch 제거 (BREAKING)** — `scripts/fetch_dynamic.py`·`scripts/install_lightpanda.py` 및 관련 테스트 삭제. `--dynamic-only` 는 legacy 호환 플래그로만 남아 exit 4 + hyve MCP `web_browse` 안내로 fail-fast (v3.0.0 LIGHTEN 체제 복귀). `--lp-markdown`·`--no-auto-install` 플래그, exit 3(미설치) 계약, `$ITDA_LIGHTPANDA_DIR`/`$ITDA_LIGHTPANDA_BIN` 검출 삭제.
- 근거 (Cowork 실측 2026-07-27): ① 설치 경로가 세션 홈(휘발)이라 세션마다 151MB/33s 재설치 반복 ② 진성 CSR SPA(wanted.co.kr·map.naver.com·musinsa.com)에서 lightpanda 0.3.6 aarch64-linux SIGILL 크래시 100% 재현 — v5.0.0 재흡수 근거("가벼운 설치 + 안정 동작") 붕괴. 정적 fetch(curl_cffi·EUC-KR·WAF 격자·쿠키·SSRF)는 회귀 없음.

## [6.2.4] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [6.2.3] — 2026-07-26 (이슈 #1280·#1281)

### Changed

- `compatibility` 라벨을 `Claude Code & Cowork` 로 교체 (#1280).
- `curl -LsSf https://astral.sh/uv/install.sh | sh` 설치 줄 삭제 — uv 부재 시 사용자에게 설치를 요청한다(에이전트가 `curl | sh` 를 실행하지 않는다). 의존성 설치는 `python3 -m pip install` 로 교체 (#1281).
- `ITDA_LIGHTPANDA_DIR` export 권장에 Cowork 한정 단서 추가 — Claude Code 는 기본값 `~/.itda-skills/bin` 이 이미 영속.

## [6.2.2] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [6.2.1] — 2026-07-04

### Fixed

- hyve MCP `naverplace` 도메인 제거(#816)에 따라, SPA 어댑터 fail-fast(`extract_content.py`)·bot challenge escalation(`fetch_dynamic.py`) 안내 문구와 마이그레이션 표(SKILL.md·README·references/migration.md)의 `naverplace` 도메인 유도를 hyve MCP `web_browse` 레시피 기준으로 정정했습니다. 네이버 부동산 등 SPA는 `web_browse`의 `observe{network}`로 XHR(API) 원본을 캡처하는 경로를 안내합니다. 실존한 적 없는 `naverplace.complex` "현행" 표기(stale 오배선)도 제거했습니다.
- AC-3 검증 키워드(`extract_content.py`)와 물린 테스트 assert(`test_extract_content_dynamic_rejection.py`·`test_fetch_dynamic.py`)를 새 안내 문구에 맞춰 동기화했습니다(`naverplace` → `네이버 부동산`).

### Notes

- 문서/메시지 교정만 포함합니다 — fetch 동작·CLI 인터페이스 변경 없음. CHANGELOG·README 의 과거 버전(v3.0.0·v5.0.0·v6.0.1 등) 기록은 사실 보존을 위해 그대로 둡니다.

## [6.2.0] — 2026-06-25

### New Features

- **정적 curl 경로 실패 게이트(R6식 machine-enforced escalation contract)** — `fetch_html.py`의 WAF/challenge 격자 소진이 더 이상 free-text `error` + exit 1로 뭉개지지 않는다. 이제 결과 dict에 `must_escalate` / `stop_reason` / `untried_routes` / `grid_exhausted` / `executed_attempts` / `content_is_challenge` / `content_available`를 담고, CLI는 `⛔ NOT EXHAUSTED` stderr 배너 + **exit 4**를 낸다(동적 경로 `fetch_dynamic`의 bot-challenge exit 4와 동일 의미). 차단 사이트를 잘못 '도달 불가'로 선언하던 실패 모드를 닫는다(upstream fivetaku insane-search R6 패턴 이식).
- **Give-up status taxonomy** (`fetch_html._classify_giveup`) — v1 validator를 재작성하지 않고 give-up 지점에서 분류한다(blast radius 최소화): `challenge`/`403`→escalate(must_escalate=True), `429`→`rate_limited`(백오프, escalate ✗), `401/407`→`auth_required`, `404/410`→`not_found`, 네트워크→`network_error`. 브라우저로 가도 무익한 실패(rate-limit·auth·404)는 escalate하지 않는다.
- **정직한 전수성 신호** — `grid_exhausted`는 격자가 budget cap(`--max-attempts`) 전에 자연 소진된 경우에만 True. capped면 `untried_routes`에 "--max-attempts 높여 재실행" 안내를 추가한다.

### Changed

- **전파**: `fetch_pipeline._do_static_fetch`가 must_escalate 신호 시 `StaticFetchEscalate`(신규, `exceptions.py`)를 raise하고, `extract_content`가 broad `ContentExtractionError` fallback보다 **먼저** catch해 `exit 4` + 에스컬레이션 안내를 surface한다. fetch_pipeline 미사용 폴백 경로도 동일 처리. 에이전트가 프로즈를 추측할 필요 없이 결정론적으로 web_browse로 라우팅된다.
- `SKILL.md`: `fetch_html.py`/`extract_content.py` exit-code 표에 exit 4(정적 WAF 격자 소진) + 실패 게이트 계약 문서화.

### Backward Compatibility

- **Additive** — dict 게이트 필드는 명시적으로 설정될 때만 존재(기존 content/error 소비자 무영향). exit-code 변경은 **WAF/challenge 소진 케이스로만 좁혀짐**: 404·network·timeout은 exit 1 유지, 정상 fetch는 exit 0 유지("정상 static ≠ 4" 불변식 보존). 전체 회귀 스위트 573 passed, 5 skipped(신규 17 테스트 포함, 회귀 0).

### Notes

- 적대적 Codex 리뷰(blocker 2 + major 5) 반영: dict-primary 전파(exit 코드 아님)·grid budget-vs-exhausted 정직성·429/401 비-escalate·SSRF 계약 분리·best_result challenge HTML을 본문으로 surface 금지(`content_available=False`). 후속(미반영): validator v2 비종결 `SUSPECT_OK`(애매 응답에서 격자 계속 탐색)는 별도 PR로 분리.

## [6.1.0] — 2026-06-20

### New Features

- **Lightpanda 설치 관리 스크립트 `scripts/install_lightpanda.py` 신설** (SPEC-WEBREADER-LIGHTPANDA-INSTALLER-001, #513). 플랫폼/아키텍처 자동 감지(aarch64/x86_64 × macos/linux), GitHub 릴리즈 해석, 다운로드 → `chmod +x` → (macOS) `xattr` 제거 → `lightpanda version` 검증 → 원자적 교체. 표준 라이브러리만 사용해 신규 의존성 0.
- **동적 fetch 자동 설치(ensure)**: `--dynamic-only`/`fetch_dynamic.py` 호출 시 바이너리가 없으면 추가 도구 호출 없이 최신 안정 버전을 자동 설치한 뒤 진행합니다. 기존 바이너리는 절대 덮어쓰지 않으며, `--no-auto-install`로 비활성(CI/테스트)할 수 있습니다.
- **설치 위치 제어**: `--install-dir` → `$ITDA_LIGHTPANDA_DIR` → `~/.itda-skills/bin` 우선순위. `$ITDA_LIGHTPANDA_DIR`로 영속 경로를 지정하면 세션 간 재사용됩니다.
- **업그레이드/다운그레이드**: `--version X.Y.Z`(다운그레이드), `--version latest --force`(업데이트), `--version nightly` 지원. `v` 접두사 유무 양쪽 태그를 시도합니다.

### Changed

- **바이너리 검출 체인 교체** (REQ-INST-006): `--lightpanda-bin` → `$ITDA_LIGHTPANDA_BIN` → `$ITDA_LIGHTPANDA_DIR/lightpanda` → `$PATH` → `~/.itda-skills/bin/lightpanda`. Cowork 세션에서 마운트와 어긋나 헛다리 + 세션 휘발하던 cwd 상대 추측 경로(`./mnt/...`·`./.itda-skills/...`)를 제거했습니다.
- **최신 안정 해석 교정**: `/releases/latest`는 rolling `nightly`를 반환하므로 사용하지 않습니다. semver 태그(`v?X.Y.Z`) 중 prerelease/draft를 제외한 최고 버전을 선택합니다. lightpanda의 `nightly` 태그는 `prerelease=false`라서 prerelease 플래그만으로는 걸러지지 않아, semver 정규식이 nightly 제외의 실제 장치입니다.
- `install_guide()`를 수동 `curl`/`brew` 안내에서 관리 스크립트 호출 안내로 교체했습니다(REQ-INST-010).
- `fetch_dynamic.py`/`install_lightpanda.py`의 `--help`가 더 이상 exit 2가 아닌 exit 0을 반환합니다(argparse `SystemExit` 코드 보존).

### Notes

- 릴리즈가 checksum을 제공하지 않아 SHA 대조 대신 `lightpanda version` 실행으로 무결성을 검증합니다. 검증 통과 시에만 기존 바이너리를 원자적으로 교체해, 손상된 다운로드가 멀쩡한 바이너리를 덮어쓰지 않습니다. Windows 네이티브는 미지원(WSL2로 위임).

## [6.0.1] — 2026-06-10

### Fixed

- 활성 안내·escalation 메시지·문서 표의 `web_browse.render` 참조를 현행 `web_browse` 로 교정했습니다. `render` 는 `snapshot` 의 deprecated alias 라, 봇 차단/JS 렌더 폴백 안내가 폐기 예정 액션명을 가리키던 문제를 해소했습니다 (#141).
- bot challenge escalation 메시지의 `chromedp` 표기를 현행 `Bun playwright` 엔진으로 정정했습니다(chromedp 는 hyve 에서 제거됨). naverplace 안내 문구의 stale 엔진 표기도 정리했습니다.

### Notes

- 문서/메시지 교정만 포함합니다 — fetch 동작·CLI 인터페이스 변경 없음. CHANGELOG·README 의 과거 버전(v3.0.0 등) 기록은 사실 보존을 위해 그대로 둡니다.

## [6.0.0] — 2026-06-04

### Breaking Changes

- 정적 HTTP fetch 백엔드를 `requests`에서 `curl_cffi` 단일 경로로 전환했습니다.
- 신규 필수 의존성: `curl_cffi>=0.11`, `PyYAML>=6.0`.

### New Features

- 기본 TLS impersonation을 `safari`로 설정했습니다. 기본 User-Agent도 impersonation family와 맞춰 자동 선택합니다.
- challenge 검증 레이어를 추가했습니다: WAF marker, known bad size fingerprint, cookie sensor, optional success selector.
- WAF 프로파일 감지와 격자 escalation을 추가했습니다. challenge/403/429 계열 응답에서만 `TLS impersonate × URL transform × Referer` 조합을 제한된 횟수로 시도합니다.
- `fetch_html.py --impersonate`, `--max-attempts`, `--trace` 옵션을 추가했습니다. `--trace`는 시도별 transform/impersonate/referer/verdict를 stderr JSON으로 출력합니다.

### Preserved

- EUC-KR/CP949 포함 기존 bytes 기반 인코딩 감지 경로를 유지했습니다.
- SSRF 방지와 redirect 대상 검증을 유지했습니다.
- cross-domain redirect 시 원본 쿠키를 제거하는 수동 redirect scoping을 유지했습니다.
- Content-Length 및 chunked transfer 양쪽의 50MB 응답 제한을 유지했습니다.


## [5.0.4] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [5.0.3] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.

## [5.0.2] — 2026-05-13

### Improvements

- **GUIDE.md 일반 사용자 문서 정책 준수**: GUIDE.md에 노출되어 있던 `python3 scripts/*.py` CLI 명령 16곳을 모두 자연어 발화 예시로 대체. 일반 사용자가 보는 문서에는 명령어를 노출하지 않는다는 정책.
- **마이그레이션 섹션 3종(v4→v5, v3→v4, v2→v3)을 `references/migration.md`로 분리**: 기존 사용자·개발자가 코드를 마이그레이션할 때 참조하는 historical reference. 일반 사용자에게는 필요 없으므로 GUIDE.md 본문에서 제거.
- **개발자용 CLI 레퍼런스 통합**: 자동화 스크립트·파이프라인에서 직접 호출할 때 필요한 CLI 명령 모음을 `references/migration.md` 하단에 통합.
- **GUIDE.md 자연어 호출 예시 강화**: 활용 시나리오·검증된 사이트·SPA 처리·팁 섹션 전반에서 "이 ~ 가져와줘" 형식 발화 예시 사용.

### Why

`web-reader` GUIDE.md는 일반 사용자가 보는 활용 가이드인데 직전 v5.0.1까지 `python3 scripts/...` CLI 명령이 16곳 노출되어 있어 정책 위반. 일반 사용자는 자연어로만 스킬을 호출하므로 CLI 명령은 references로 분리해 개발자 전용 문서로 위치 조정.

## [5.0.1] — 2026-05-13

### Improvements

- **GUIDE.md "검증된 데이터 수집 사이트" 섹션 추가**: 13개 사이트 실측 결과 표화 (한국 미디어/외산 ATS/SaaS Changelog/공공/커뮤니티/이커머스/채용 SPA). 정적 fetch로 충분한 사이트 11종, lightpanda 필수 2종(Wanted, Disquiet) 분류.
- **의사결정 휴리스틱 명시**: 정적 fetch 우선 → `words=0`이면 `--dynamic-only` → exit 4면 web-reader 범위 밖.
- **효용성 워크플로우 3종 예시**: 매일 IT 헤드라인 자동 수집, 경쟁사 Greenhouse 채용 주간 diff, Linear changelog 신규 항목.
- **실측 패턴 인사이트**: 외산 SaaS·ATS는 SEO 위해 SSR 기본이라 정적 fetch만으로 본문 회수 가능. 한국 미디어 메인도 동일. Lightpanda 진성 효용은 CSR SPA(Wanted, Disquiet)에서만 발휘.

### Why

`itda-work:find-work`로 발굴된 "정기 웹 모니터링" 후보가 web-reader로 처리 가능한지 판단할 때, 매번 사용자가 직접 시도·실패할 위험을 줄이기 위해 검증된 사이트 카탈로그를 GUIDE.md에 명문화.

## [5.0.0] — 2026-05-13 (SPEC-WEBREADER-DYNAMIC-LIGHTPANDA-001)

### Breaking Changes

- **`description` scope 재확장 (2종 → 3종)**: SKILL.md description의 use case가 `(1) EUC-KR/CP949` + `(2) 쿠키 인증 정적 페이지` + **`(3) JavaScript 동적 페이지 (Lightpanda 백엔드)`** 3종으로 확장되었습니다. progressive disclosure 매칭에서 "이 SPA 동적으로 가져와줘" 자연어 요청이 다시 web-reader를 활성화합니다.
- **`--dynamic-only` 동작 복원**: LIGHTEN(v3.0.0)에서 `exit 4 + hyve 안내`로 fail-fast 처리했던 `extract_content.py --dynamic-only`가 v5.0.0부터 정상 동작합니다. 백엔드는 **Lightpanda** subprocess wrapper.
- **신규 외부 의존성**: `lightpanda` 바이너리. Python 모듈 의존성 추가 없음. 검출 우선순위: `$PATH` → `~/.itda-skills/bin/` → `./mnt/.itda-skills/bin/` → `./.itda-skills/bin/`.
- **Exit code 신설**: `exit 3` (Lightpanda 미설치, stderr에 플랫폼별 설치 안내), `exit 4`는 bot challenge 감지로 의미 재정의(stderr에 hyve MCP escalation 안내).

### New Features

- **`scripts/fetch_dynamic.py`** (~400 LOC): Lightpanda CLI subprocess wrapper. 옵션: `--wait-until`, `--wait-selector`, `--wait-ms`, `--terminate-ms`, `--strip-mode`, `--cookie-file`, `--http-proxy`, `--dump-markdown`, `--block-private-networks` (기본 활성).
- **`extract_content.py --lp-markdown`**: Lightpanda의 `--dump markdown` 출력을 정제 파이프라인 우회하고 그대로 반환. 한국 미디어/뉴스에서 빠르고 깔끔한 출력.
- **Bot challenge 자동 감지**: `Access Denied`, `Just a moment`, `Cloudflare`, `PerimeterX` 등 7개 패턴. 감지 시 hyve MCP escalation 메시지 + exit 4.

### Validation Matrix (2026-05-13)

22-URL 직접 측정:

| 분류 | 결과 |
|------|------|
| 한국 미디어 (naver, daum, brunch, velog, n.news.naver, tistory) | 6/6 성공, 평균 1.0초 |
| 한국 정부 (gov.kr, nts.go.kr, molit.go.kr) | 3/3 성공, 평균 1.7초 |
| 한국 커뮤니티/쇼핑 (dcinside, musinsa) | 2/2 성공 |
| 영문 SPA (github, vercel) | 2/2 성공 |
| news.naver.com 실 기사 본문 추출 | 11.3KB 한글 텍스트 완전 추출 (1.5초) |
| **Anti-bot (coupang)** | **차단(Access Denied) → exit 4 + hyve escalation 자동 안내** |
| **SNS shell only (인스타·X)** | **HTML shell 응답하지만 실 데이터 없음 — hyve MCP escalation 권장** |

**진짜 성공률: 20/22 = 91%** (anti-bot/SNS 제외 시 20/20 = **100%**)

### Migration

| 이전 (v3.x ~ v4.x) | v5.0.0 대체 |
|-------------------|-------------|
| 동적 fetch는 hyve MCP `web_browse.render` (LIGHTEN-001) | `extract_content.py --url URL --dynamic-only --format markdown` |
| 한국 미디어 빠른 추출 | `extract_content.py --url URL --dynamic-only --lp-markdown` |
| 세부 옵션 필요 시 | `fetch_dynamic.py` CLI 직접 사용 |
| Anti-bot 차단 | **여전히 hyve MCP** (자동 escalation 안내) |
| SNS 인증 | **여전히 hyve MCP** |
| naverplace | **여전히 hyve MCP** |

### Rationale

LIGHTEN(v3.0.0)에서 동적 fetch를 hyve MCP로 위임한 결정의 근거는 다음과 같았다:
- Playwright/Chromium ~200MB 설치 + `playwright install chromium` 잦은 실패
- fetch_dynamic.py 1,378 LOC가 web-reader의 56% 차지

이 근거는 **Lightpanda 등장으로 해소**된다:
- 단일 바이너리 65–135MB (Node 의존 없음, Homebrew/AUR/nightly URL)
- 24MB 메모리 풋프린트, 100ms 부팅, V8 기반 JS 실행
- LLM-친화 CLI (`--dump markdown`, `--strip-mode`, `--wait-selector`)
- CDP/MCP 서버 모드 내장
- 신규 wrapper LOC ~400 (이전 1,378 LOC의 29%)

LIGHTEN의 결정 자체보다 **그 결정의 근본 동기(가벼운 설치 + 안정 동작)** 를 더 잘 만족하는 백엔드로 동적 fetch를 web-reader로 재흡수한다. hyve MCP는 폐기되지 않으며, anti-bot/SNS/도메인 어댑터 영역의 escalation 경로로 유지된다.

### Non-goals (hyve MCP escalation)

- Akamai/Cloudflare anti-bot 우회 (stealth/fingerprint 마스킹)
- SNS 인증 후 데이터 로드 (인스타·X timeline)
- 네이버 부동산 등 도메인 어댑터 (naverplace는 hyve MCP)
- Windows 네이티브 (Lightpanda는 WSL2 필수)
- musl Linux (Alpine 미지원)

### Cross-skill Impact

- `grep -rln "fetch_dynamic\|lightpanda" itda-*/ | grep -v web-reader/`: 0건 (cross-skill 외부 호출자 없음)
- 기존 정적 fetch 회귀 0건: 비-Lightpanda 테스트 스위트 통과 (473개 + 신규)

---

## [4.0.0] — 2026-05-13 (SPEC-WEBREADER-YOUTUBE-REMOVE-001)

### Breaking Changes

- **YouTube 자막 추출 기능 제거 (약 1,865 LOC 삭제)**: `scripts/fetch_youtube.py` (591 LOC), `tests/test_fetch_youtube.py` (1,133 LOC), `scripts/tests/test_youtube_selector_warning.py` (141 LOC) 가 모두 제거되었습니다. `extract_content.py` 의 YouTube URL 자동 위임 분기도 제거되었습니다.
- **YouTube URL을 `extract_content.py --url` 에 전달하면 exit code 2**: stderr에 `yt-dlp` 명령어 안내가 출력되고 종료합니다. fail-fast 정책 (silent fallback 없음).
- **`youtube-transcript-api` 의존성 제거**: `requirements.txt` 에서 제거되었습니다.
- **description scope 축소 (3종 → 2종)**: SKILL.md description 의 use case 가 `(1) EUC-KR/CP949 한글 인코딩` + `(2) 쿠키 인증 정적 페이지` 2종으로 축소되었습니다. "YouTube 자막" 자연어 요청에 더 이상 web-reader 가 활성화되지 않습니다.
- **`metadata.tags` 변경**: `youtube`, `transcript`, `caption` 태그가 제거되었습니다.

### Migration

| v3.x 호출 | v4.0.0 대체 |
|-----------|-------------|
| `python3 scripts/fetch_youtube.py --url URL` | `yt-dlp --write-auto-sub --sub-lang ko --skip-download <URL>` |
| `python3 scripts/extract_content.py --url <youtube_url>` | exit 2 + 안내 — 호출 측에서 `yt-dlp` 로 전환 |
| Python: `from fetch_youtube import fetch_youtube` | `subprocess.run(["yt-dlp", ...])` 또는 `yt-dlp` 라이브러리 |

자세한 마이그레이션은 GUIDE.md "마이그레이션 안내 (v3 → v4)" 섹션 참조.

### Rationale

2026-05-13 직접 비교 실험에서 `yt-dlp --write-auto-sub --sub-lang ko --skip-download URL` 한 줄 + Python 정규식 10줄로 `fetch_youtube.py` 와 동등한 결과(한국어 자동자막 텍스트 정리)를 생성할 수 있음을 확인했습니다. Claude 는 yt-dlp 호출과 VTT 파싱을 즉석에서 수행하며, web-reader 가 제공하던 추가 가치(YAML frontmatter, 언어 우선순위, oEmbed 메타데이터 통합)는 단일 자막 정리 작업에서 사용자가 체감하지 못합니다. 이중 유지보수 비용이 사용자 가치를 초과하므로 yt-dlp 위임 경로로 단일화합니다.

Cross-skill 외부 호출자: **0건** (`grep -rln "fetch_youtube\|youtube_transcript_api" itda-*/ | grep -v "web-reader/"` 결과). 안전하게 제거 가능.

---

## [3.0.0] — 2026-05-11 (SPEC-WEBREADER-LIGHTEN-001)

### Breaking Changes

- **동적 fetch 인프라 일체 제거 (3,702 LOC 삭제)**: Playwright/Chromium 기반 헤드리스 브라우저 fetch (`fetch_dynamic.py`, `browser_driver.py`, `spa_capture.py`, `spa_grid.py`, `spa_detector.py`, `list_adapters.py`, `spa_adapters/` 디렉토리 전체) 가 v3.0.0 에서 제거되었습니다. 동적 use case 는 hyve MCP 의 `web_browse.render` 도메인(SPEC-WEB-MCP-002)으로 위임됩니다.
- **SPA 어댑터 (naver_land 등) 제거**: `--adapter`, `--adapter-page`, `--from-capture` 플래그가 `extract_content.py` 에서 fail-fast 로 동작합니다 (exit code 4 + stderr 마이그레이션 안내). 네이버 부동산은 hyve MCP 의 `naverplace` 도메인 (이미 chromedp Go 포팅 완료) 을 사용하세요.
- **`--dynamic-only` 플래그 fail-fast**: `extract_content.py --dynamic-only` 호출은 exit code 4 + stderr 안내 메시지를 출력하고 종료합니다. 정적 fetch 만 필요하다면 플래그 없이 호출하세요.
- **`fetch_with_fallback()` Python API**: `dynamic_only=True` 또는 `site_pattern={"dynamic": True, ...}` 호출 시 `ValueError` 를 발생시키며, 메시지에 hyve MCP 마이그레이션 경로가 포함됩니다. 정적 폴백 경로(`fallback`)는 v3.0.0 부터 동적 시도를 하지 않으며, 품질 미달 시 진단 로그만 stderr 로 출력합니다.
- **Prerequisites 변경**: `playwright && playwright install chromium` 설치 단계가 SKILL.md Prerequisites 에서 제거되었습니다 (~200MB 다운로드 부담 해소).
- **description scope 축소**: SKILL.md description 의 5종 use case 가 3종 (EUC-KR/CP949 · YouTube 자막 · 쿠키 인증 정적 페이지) 으로 축소되었습니다. progressive disclosure 매칭 결과가 변경되어 SPA / "동적 페이지" 자연어 요청은 더 이상 web-reader 를 활성화하지 않습니다.
- **잘못된 문서 기술 정정**: 이전 SKILL.md L78 의 "instagram.com, x.com 등 SNS 도메인은 정적 HTML 이 빈 셸이므로 자동으로 동적 fetch 로 진입한다" 기술이 정정되었습니다 — **실제 코드에는 SNS 도메인 화이트리스트 기반 자동 진입 로직이 존재한 적이 없습니다**.

### Migration

| v2.x 호출 | v3.0.0 대체 (hyve MCP) |
|-----------|------------------------|
| `python3 scripts/fetch_dynamic.py --url URL` | hyve MCP `web_browse.render` (SPEC-WEB-MCP-002) |
| `fetch_dynamic.py --url URL --stealth` | hyve MCP `web_browse.render` (stealth 기본 적용) |
| `fetch_dynamic.py --adapter naver_land --adapter-page complexes` | hyve MCP `naverplace.search` 또는 `naverplace.complex` |
| `fetch_dynamic.py --adapter naver_land --adapter-page complex_detail` | hyve MCP `naverplace.complex` (단지 + 매물) |
| `extract_content.py --from-capture <jsonl> --adapter naver_land` | hyve MCP `naverplace.reviews` 또는 `naverplace.complex` |
| `extract_content.py --dynamic-only` | hyve MCP `web_browse.render` |
| `profile_manager.py warmup <name>` | hyve MCP 자체 프로필 관리 (별도 명령 불필요) |

마이그레이션 가이드 전체는 [GUIDE.md](GUIDE.md) 의 "마이그레이션 안내 (v2 → v3)" 섹션을 참조하세요. 호환성:
- 정적 fetch / YouTube 자막 / 쿠키 fetch / `--selector` 지정 추출은 v3.0.0 에서도 그대로 동작 (회귀 0건 검증).
- v2.x 의 `--dynamic-only` / `--adapter` / `--adapter-page` / `--from-capture` 호출은 모두 exit code 4 + 안내 메시지로 fail-fast.
- hyve MCP 가 활성화되지 않은 환경에서는 동적 use case 가 작동하지 않습니다.

### Removed

- `scripts/fetch_dynamic.py` (1,378 LOC), `scripts/browser_driver.py` (339 LOC), `scripts/spa_capture.py` (202 LOC), `scripts/spa_grid.py` (103 LOC), `scripts/spa_detector.py` (151 LOC), `scripts/list_adapters.py` (111 LOC)
- `scripts/spa_adapters/` 디렉토리 전체 (`__init__.py` + `_loader.py` 238 LOC + `base.py` 250 LOC + `naver_land.py` 926 LOC + `manifest.json`)
- `references/browser-driver.md`, `references/spa-adapters.md` — 동적 측 개발자 문서
- `tests/` (skill root) 동적 측 테스트 22개: `test_browser_driver`, `test_fetch_dynamic*` (4종), `test_spa_*` (5종), `test_list_adapters_cli`, `test_loader_default_page`, `test_profile_manager`, `test_stealth`, `test_extract_from_capture`, `test_legacy_flow_regression`, `test_adapter_*` (2종), `test_security_fixes`, `test_deep_link_block_detection`, `test_domain_verify_warning`
- `scripts/tests/` 동적 측 테스트 6개: `test_browser_driver_extract_html`, `test_fetch_dynamic_selector`, `test_naver_land_*` (4종) 및 `fixtures/naver_land/`
- `fetch_html.py` 의 SPA 감지 / deep-link advisory 블록 (L588-L610) — `spa_detector` 의존 제거
- `extract_content.py` 의 `_load_adapter_for_capture`, `_format_date_yyyymmdd`, `_render_capture_as_markdown`, `_render_capture_as_json`, `_process_from_capture` 함수 — SPA capture 처리 dead code

### Improvements

- **`fetch_pipeline.py` 슬림화 (564 → 220 LOC, -61%)**: `_PlaywrightNotAvailable`, `_resolve_effective_browsers_path`, `_attempt_playwright_install`, `_do_dynamic_fetch`, `_compare_and_select` 제거. 정적 fetch 단일 경로만 운영하며 `dynamic_only=True` 호출 시 `ValueError` 로 fail-fast.
- **README.md 슬림화 (348 → 27 LOC, -92%)**: 사용자/개발자 진입점을 GUIDE.md / SKILL.md 로 단일화.
- **`.skill` ZIP 사이즈 측정**: BEFORE 391,508 bytes → AFTER (별도 측정), 30% 이상 감소 (AC-7 게이트). 측정 결과는 baseline.md / 본 릴리스 직후 수치 비교로 확인.
- **유지 보수 부담 감소**: 동적 측이 차지하던 최근 6개월 git 커밋의 60% 이상 부담이 해소됨.
- **신규 acceptance 테스트**: `scripts/tests/test_extract_content_dynamic_rejection.py` (6 시나리오) — `--dynamic-only`, `--adapter`, `--adapter-page`, `--from-capture` 호출이 exit 4 로 fail-fast 하는지 자동 검증.

### 동작 영향 (Behavioral Impact)

1. **CLI 표면**: `--dynamic-only`, `--adapter`, `--adapter-page`, `--from-capture` 호출은 exit code 4 + stderr 안내 메시지 출력 후 종료.
2. **Python API**: `fetch_pipeline.fetch_with_fallback(..., dynamic_only=True)` 호출은 `ValueError` raise.
3. **자연어 활성화**: SPA / 동적 페이지 / 인스타그램 / 트위터 / 네이버 부동산 자연어 요청은 progressive disclosure 매칭에서 web-reader 를 더 이상 활성화하지 않음.
4. **Prerequisites**: Playwright/Chromium 설치 단계가 제거되어 신규 사용자의 설치 부담이 감소.
5. **회귀 0건 검증**: 정적 fetch / YouTube 자막 / 쿠키 fetch / `--selector` 지정 추출은 모두 v2.13.0 과 동일하게 동작. WI-0 baseline (`scripts/tests/`: 227 → 133, `tests/`: 954 → 535) 의 정적 측 테스트는 100% 통과.

### Notes

- 본 릴리스의 자매 SPEC 짝(sibling pair) 은 hyve 레포의 SPEC-WEB-MCP-002 입니다.
- 마이그레이션 가이드 전체는 [GUIDE.md](GUIDE.md) 의 "마이그레이션 안내 (v2 → v3)" 섹션을 참조.
- baseline 측정 결과: `.specs/SPEC-WEBREADER-LIGHTEN-001/baseline.md`

---

## [2.13.0] — 2026-05-10

### Improvements

- **description 트리거 범위 좁히기 (오발동 방지)**: 단순 URL 읽기 요청에서 progressive disclosure가 web-reader를 활성화하던 문제를 해결. description 첫 문장을 "WebFetch로 처리되지 않는 고급 웹 페치 전용"으로 좁히고, EUC-KR/CP949 · Playwright 동적 렌더링 · YouTube 자막 · 쿠키 인증 · SPA 어댑터 5종을 명시 활성화 조건으로 나열. "Do NOT use for" anti-trigger 절을 추가하여 일반 페치 요청은 Claude의 WebFetch로 위임되도록 유도. 기존 일반 트리거 문구("이 링크 읽어줘", "웹페이지 요약해줘", "사이트에서 ... 가져와")는 description에서 제거. SPEC-WEBREADER-TRIGGER-001 적용. (관련 SPEC: `.specs/SPEC-WEBREADER-TRIGGER-001/`)

### 동작 영향 (Behavioral Impact)

- 스크립트 동작 · CLI 인터페이스 · Python API: **변경 없음** (v2.12.0과 100% 동일)
- 변경된 부분: SKILL.md frontmatter `description` 자연어 트리거 매칭 신호만 조정
- 사용자 영향: 단순 페치 요청은 WebFetch로 자동 위임되어 토큰 소비 감소. 고급 기능 5종 또는 스킬명 명시 호출 시에는 기존과 동일하게 web-reader 활성화

## [2.12.0] — 2026-05-01

### New Features

- **`diagnose_url.py` 신규 스크립트**: fetch 실패의 root cause를 레이어별로 진단. SSRF check → DNS → TCP → SSL → HTTP HEAD → robots.txt 단계 분리 측정 + baseline 비교 (google.com:443). itda-email v0.18.0의 `diagnose_smtp.py` 패턴을 HTTP 도메인에 일반화.

#### 진단 코드 (12종)

`ssrf_blocked` / `dns_failure` / `no_internet` / `tcp_blocked` / `ssl_cert_invalid` / `ssl_handshake_fail` / `http_timeout` / `redirect_loop` / `http_403_forbidden` / `http_404_not_found` / `http_429_rate_limit` / `http_5xx_server_error` / `non_html_content` / `robots_denied` / `empty_response` / `all_ok`

#### 사용법

```bash
python3 scripts/diagnose_url.py https://example.com
# 응답 JSON의 diagnosis.code 만 보면 root cause 식별 가능
```

`fetch_html.py` 가 빈 응답 / 403 / 알 수 없는 에러를 반환할 때 다음 단계 진단 도구로 사용.

#### Verification

| 시나리오 | 진단 코드 |
|---------|----------|
| `https://example.com` | `all_ok` |
| `https://nonexistent-...invalid` | `dns_failure` |
| `http://192.168.1.1/` (private IP) | `ssrf_blocked` |
| 404 URL | `http_404_not_found` |
| PDF URL (실제로 403 응답) | `http_403_forbidden` |
