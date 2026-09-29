# Changelog — web-search

이 스킬의 주요 변경 이력입니다. (Keep a Changelog 형식)

## [0.1.10] — 2026-09-28 (itda-work/skills#26)

### Changed

- **자격증명 파일 별칭에서 `env.txt` 제거** (itda-work/skills#26) — 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 로 키를 두었다면 `환경변수.txt` 또는 `.env` 로 이름을 바꾼다. SKILL.md 의 파일명 별칭 안내·키 주입 규칙(파일명 3종·셸 glob 오탐 설명)을 맞췄다.

## [0.1.9] — 2026-09-27

### Changed

- User-Agent `itda-web-search/0.1 (+https://github.com/itda-skills)` → `Mozilla/5.0`. 검색 API 로그에 저장소 URL·스킬 이름을 남기지 않는다(outbound-identity-leak). 호출자가 준 UA 는 그대로 쓴다. 회귀: `tests/test_search_http.py`.

## [0.1.8] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- 로그인·JS 렌더 사이트 안내에서 빠진 스킬(구 itda-hyve 팩의 web-automation)을 지우고 `itda-web:aside-browser-mcp` 만 남겼다.

## [0.1.6] — 2026-07-30 (이슈 #1334)

### Changed

- blog-reader `discover`와의 라우팅 경계·핸드오프 명문화 (#1332·#1334) — 네이버 블로그 한정 무자격 검색은 blog-reader `discover`(→`read` 이어읽기), 범용·다엔진 교차검증은 본 스킬 naver 엔진(공식 OpenAPI). 결과 중 blog.naver.com URL 본문·댓글은 blog-reader `read`로 위임.

## [0.1.5] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.1.4] — 2026-07-26 (이슈 #1282)

### Changed

- `.env` 위치 안내를 "작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트)" 로 일반화하고 셸 환경변수·`~/.claude/settings.json` 의 `env` 경로를 명시 (#1282).

## [0.1.3] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.1.2] — 2026-07-11

### Fixed

- **Windows cp949 stdio 크래시** (#1036) — 진입점에서 stdout/stderr 를 utf-8 로 reconfigure. locale(cp949) 콘솔·파이프에서 `--check-env` 의 `✓`/`✗`(U+2713/2717)·결과 렌더링의 em-dash(U+2014) 출력이 `UnicodeEncodeError` 로 죽고, cp949 로 나간 한국어 stderr 가 utf-8 부모 프로세스의 파이프 디코드를 깨뜨리던 문제 해소. deployed-style 테스트 4건이 Windows 에서 GREEN 복귀(저장소 관례 — etf-naver·docx-design 동형).

## [0.1.1] — 2026-06-10

### Added

- **market-scan 핸드오프 회귀 가드** (`tests/test_handoff_market_scan.py`) — market-scan Q4 '키 감지' 점검이 광고한 엔진 키 이름이 web-search `ENGINE_SPECS` required 키와 정합하는지 + `--check-env` 종착점이 격리 실행에서 살아있는지 검증(deployed-style, conftest 미의존). DATA-TIDY-001(광고된 파이프라인 실측 단절) 패턴 차단. 작성 즉시 market-scan 측 `NAVER_SEARCH_CLIENT_SECRET` 축약 표기로 인한 키 미감지 갭 1건 적발·교정.
- **naver 종류별 날짜 shape 회귀 케이스** (`tests/test_naver_client.py`) — live-prober 실측 기반: web(webkr 날짜 필드 부재 → `published_at` None)·news(`pubDate` RFC-822)·blog(`postdate` YYYYMMDD) 3종을 `pubDate or postdate` 폴백이 graceful 처리하는지 검증(기존 fixture는 blog 1종만 표현). 단위 66→68 GREEN.

### Changed

- **SKILL.md 사용법에 소스트리 개발자 PYTHONPATH 캐비엇 1줄 추가** — 배포본은 `publish.py`의 `_inject_shared_modules`가 `shared/`를 번들해 그대로 동작하나, 소스트리 직접 실행 시 `PYTHONPATH=skills/shared`가 필요함을 명시(미설정 시 `ModuleNotFoundError: env_loader`). 일반 사용자는 무관.

## [0.1.0] — 2026-06-09

### Added

- 다중 검색엔진(Perplexity · Tavily · Serper · Exa · Naver) 통합 조회 신설.
- `--engine auto`: 키 보유 엔진 fan-out → round-robin 병합 + URL 중복 제거 + count cap.
- 정규화 스키마(`rank·title·url·snippet·source·engine·score·published_at`) + `--format json|markdown`.
- Perplexity 요약 답변(`answer`) + 인용(citations) 매핑.
- 네이버 `--naver-type web|news|blog` 분기, 기존 `NAVER_CLIENT_ID/SECRET` 폴백.
- 키 주입(Claude 지침) 계약 + `--check-env` 진단 + 키 마스킹(stdout/stderr 미노출).
- 종료코드 매트릭스(0/2/3/4/5/6) + 부분 실패 `errors[]` envelope.
- 표준 라이브러리만 사용(추가 의존성 0).
- **엔진 선택 가이드**: SKILL.md에 상황별 라우팅 지침(AN Score 에이전트 검색 벤치마크 + 키워드 vs 시맨틱 근거), GUIDE.md에 평이언어 버전.
- **엔진별 무료 한도·요금·키 발급** 안내(2026-06 기준) — SKILL.md·GUIDE.md.
- **Serper 회색지대 경고**: 제3자 Google SERP 스크래퍼(Google v. SerpApi DMCA 제소 2025-12 · SearchGuard 차단) 명시, 보조용·키 설정 시에만 동작(미설정 시 auto 자동 제외).

### Notes

- Google Custom Search(2027 폐지)·Bing(2025 은퇴)은 채택하지 않음 — Serper·Tavily 등으로 대체.
- 각 엔진 응답 shape: tavily·naver·perplexity·serper·exa·auto **라이브 검증 완료**(P1).
- Brave는 무료 구독($5/월 크레딧 플랜) 활성화가 반복 실패해 **v0.1 활성 세트에서 제외**(향후 재검토, 구현 git 이력 보존). 라이브에서 발견한 "422-인증 신호" 재분류 가드(`search_http._looks_like_auth`)는 일반 방어로 유지.
