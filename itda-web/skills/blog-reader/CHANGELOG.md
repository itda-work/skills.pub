# Changelog — itda-work/blog-reader

이 스킬의 변경 이력입니다. [Keep a Changelog](https://keepachangelog.com) 포맷을 따릅니다.

## [0.12.3] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- 로그인·JS 렌더 사이트 안내에서 빠진 스킬(구 itda-hyve 팩의 web-automation)을 지우고 `itda-web:aside-browser-mcp` 만 남겼다.

## [0.12.1] — 2026-07-30

### Changed

- GUIDE.md 빠른 시작을 **자기완결 예시**로 교체 (마스터 피드백) — 블로그 미지정 예시("네이버 블로그 글 가져와줘")는 되묻기를 유발하므로, 그대로 입력하면 결과까지 나오는 예시(discover 키워드 검색·블로그 ID 지정·포스트 URL 지정)로 전면 교체. 시나리오 예시에도 URL/ID 포함형 병기, "이 블로그" 화법은 대화 맥락용으로 명시.

## [0.12.0] — 2026-07-30 (이슈 #1334)

### Added

- `discover` 서브커맨드 — 네이버 블로그 **전역** 키워드 검색 (#1334). section.blog.naver.com 섹션 검색 ajax(`SearchList.naver`) 기반, 자격증명·로그인 불필요. 제목·요약·URL·blogId·logNo 메타데이터만 반환하고 본문은 `read`로 이어읽는 발견→정독 파이프라인. `--order sim|date`(관련도/최신순), 차단 신호(`blockedByBifrostShield`) 감지 시 exit 4 즉시 표면화(우회 없음), 결과 0건 exit 3. 실응답 fixture 기반 테스트 + 라이브 E2E(discover→read) 실측 PASS.
- SKILL.md에 web-search와의 라우팅 경계 명문화 (#1332 흡수) — 범용·다엔진 = web-search(공식 OpenAPI), 네이버 블로그 한정 무자격 = `discover`, 정독은 `read`.

## [0.11.7] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.11.6] — 2026-07-26 (이슈 #1281)

### Changed

- web-reader 의존성 설치를 `uv pip install --system -r` 에서 `python3 -m pip install -r` 로 교체하고 Windows `py -3` 병기 (#1281).

## [0.11.5] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.11.4] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.11.3] — 2026-05-21

### Changed

- `env_vars` frontmatter 블록 폐기 → SKILL.md body `## 환경 변수` 표로 이전. itda-setup·check_env_vars.py 의존성 제거.

## [0.11.2] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.

## [0.11.0] — 2026-05-18 (SPEC-BLOGREADER-001 REQ-003.9)

### New Features

- **`--no-image-urls` 옵션 추가 (`post`·`read`).** 이미지가 많은 블로그에서 본문 이미지 URL이 컨텍스트를 크게 차지하는 문제 대응. 켜지면 본문 인라인 이미지 `![alt](url)` → `[이미지: alt]` 플레이스홀더로 치환(`--body-format html`이면 `<img>` 태그 → 동일 치환), 별도 `images[]` 배열은 `[]`로 비운다. 이미지 위치·alt는 보존되어 글 흐름·맥락은 유지하면서 URL 문자열만 제거한다.
  - 기본값 **OFF**(이미지 URL 포함) — 기존 동작과 완전 호환, BREAKING 아님.
  - 변환 핵심: `post_parser.strip_image_urls_from_body(body, *, is_html)` 신규 공개 함수. `parse_post_html(..., strip_image_urls=False)` / `NaverBlogAdapter.get_post(..., strip_image_urls=False)` / `read_post` options `strip_image_urls` 키로 스루패스.
  - SKILL.md "Claude 라우팅 가이드": 사용자가 명시적으로 이미지 제외를 요청할 때만("이미지는 빼고", "본문 텍스트만" 등) 적용. 단순 "요약해줘"는 기본 조회.

### Improvements

- 라이브 실측(이미지 26장 여행 포스트 `todaytravels/224287192534`): JSON 응답 **18,723 B → 6,522 B (-65.2%)**, body 8,148자 → 2,630자, `images[]` 26 → 0, 본문 URL 누출 0건, 표·장소임베드·텍스트 전량 보존. `read`·`--body-format html` 경로 동일 검증.
- 테스트 482 → **496**(+14: `test_post_parser.py` strip 단위·통합 11, `test_cli.py` 옵션 배선 3). 회귀 0, 1 skip 유지. 코어 3개 파일 신규 코드 ruff CLEAN.

## [0.10.2] — 2026-05-18 (SPEC-BLOGREADER-001 v0.9.3)

### Bug Fixes

- **`tags`(포스트 태그)가 항상 빈 리스트였던 결함 수정 (라이브 발견).** 기존 구현은 본문 HTML의 `class="post_tag"`를 스크래핑하는 가정이었으나, 실제 네이버 마크업(모바일·PC 모두)에는 해당 클래스가 없어 `tags`가 항상 `[]`로 반환되던 죽은 경로였다. 태그는 댓글 cbox와 동형의 별도 API `https://blog.naver.com/BlogTagListInfo.naver?blogId=&logNo=`로만 제공됨을 라이브 실측으로 확인하고 재구현.
  - 신규 `tag_parser.py` (`parse_tag_list_json`): API 응답 JSON → `logno` 매칭 → `tagName` URL 디코딩 → 쉼표 분리 → 순서 보존 중복 제거. 모든 실패는 빈 리스트로 graceful 처리.
  - `naver_adapter._fetch_post_tags()`: `web_reader_client` 경유(직접 HTTP import 0 유지) + throttle 게이트. 태그 API 실패는 비치명(본문 조회 우선).
  - `post`/`read` 결과의 `tags`가 이제 실제 태그로 채워진다. 토큰 부담이 작고 글 주제 파악에 유용하므로 별도 옵션 없이 기본 포함.
  - 라이브 검증: 태그 사용 블로그 3건 — theokh `224277175985`(12개)·`224275061280`(11개), uggang2 `224269704086`(13개) 전부 정확 추출. PC `PostView.naver?blogId=&logNo=&redirect=Dlog` 쿼리형 URL도 정상(url_normalize 기존 지원 확인, 무변경).

### Improvements

- 테스트 467 → **482**(+15: `test_tag_parser.py` 14 단위 + 어댑터 통합 신규 2 − 의미 변경 rename 1). 회귀 0, `py_compile -W error::SyntaxWarning` 전 모듈 CLEAN.
- SPEC-BLOGREADER-001 마지막 미검증 한계(`tags` 경로)가 해소되어 status **In Progress → Completed**.

## [0.10.1] — 2026-05-16 (SPEC-BLOGREADER-001 v0.9.2)

### Bug Fixes

- **se-placesMap chrome 누출 차단**: 장소 임베드(`se-placesMap`) 컴포넌트가 unknown fallback으로 처리되어 `이 블로그의 체크인` / `이 장소의 다른 글` UI 버튼 텍스트 + 공백 패딩 주소 덤프가 본문에 누출되던 결함 수정.
  `_render_se_placesmap()` 렌더러 신규: `data-linkdata` JSON → `name`/`address` 추출 → `> [장소] 광화문광장 — 서울특별시 종로구 세종대로 175 세종이야기` 형태로 구조화 출력. UI chrome 일절 미포함.

- **se-imageGroup(캐러셀) chrome 누출 차단**: 이미지 슬라이드 갤러리(`se-imageGroup`) 컴포넌트 fallback이 `Previous image` / `Next image` 스크린리더용 span 텍스트를 본문에 그대로 누출. `_render_se_imagegroup()` 렌더러 신규: `se-module-image` 단위로 `data-lazy-src`(정상해상도 w400) 우선 추출 → inline `![alt](url)` 목록. navigation button 구조 완전 무시.

- **images[] blur URL 정규화**: `_IMG_SRC_ATTRS` 속성 탐색 순서가 `src`(w80_blur lazy thumb) → `data-lazy-src`(w400 정상) 순이라 images[] 배열이 저화질 blur URL을 수집하던 결함 수정. 순서를 `data-lazy-src` → `data-src` → `src`로 역전.

- **OGQ storep 스티커 images[] 혼입 차단**: `storep-phinf.pstatic.net/ogq_...` 스티커 URL이 본문 이미지로 혼입. `_EXCLUDED_IMG_URL_PREFIXES` 도입 + `_render_se_sticker()` 명시적 empty 렌더러로 unknown fallback 차단.

### Quality

- 신규 테스트 11개 추가 (456 → 467 통과): `TestSEPlacesMapRendering`(4) / `TestSEImageGroupRendering`(3) / `TestSEStickerRendering`(1) / `TestImagesArrayNormalization`(3)
- 실 fixture `se_imagegroup_post.html` (todaytravels/224287192534, 여행 장르) 추가
- 라이브 검증: 12개 블로그 전부 `post`+`comments` CLEAN (여행/일상/디자인/주식 장르 혼합)
  - todaytravels / handani11 / k30935 / bodmi2019 / pretty9121 / designersroom
  - tosoha1 / smgcstory / kirbylove1 / lsb35788 / sdedy / nunoslash77
- **잔존 한계(정직)**: `tags` 추출은 12개 블로그 모두 `[]` — 태그 사용 블로그 미검증 상태 유지. `updated_at` 모두 `null` (설계 결정 v0.5.3 불변).

## [0.9.0] — 2026-05-15 (SPEC-BLOGREADER-001 v0.3.0)

### New Features

- 네이버 블로그 5개 CLI 서브커맨드 신규 출시 — `list`, `post`, `comments`, `search`, `read`
- `read`: 포스팅 URL 하나로 본문 + 댓글 트리를 통합 응답으로 반환 (REQ-014, AC-21)
- `comments --filter-author`: 특정 닉네임의 댓글만 평탄 리스트로 추출 (REQ-013, AC-19/AC-20)
- `--format markdown` / `--format json`(기본) 양쪽 지원 (REQ-008)
- argparse `parents=[]` 패턴으로 공통 옵션(`--format`/`--output`/`--user-agent`/`--timeout`) 위치 자유화 (AC-16)
- exit code 7단(0~6)으로 실패 모드 구분, anti-bot 차단 시 stderr 명확 메시지 (REQ-009)
- PC URL → 모바일 URL(`m.blog.naver.com`) 자동 정규화 (REQ-001)

### Quality

- **314 단위/통합 테스트 전부 통과** (mock 기반, 네트워크 호출 0건) — 합성 fixture 16개 전면 제거 후 최종 수
- AC-01 ~ AC-21 전체 인수 기준 충족
- `import requests` / `import httpx` / `from urllib.request import urlopen` 0건 (REQ-006 준수)
- Python 3.10 표준 라이브러리만 사용 (외부 HTTP 의존성 0)
- 직접 HTTP 라이브러리 없이 web-reader/fetch_html.py subprocess 경유 100%
- **라이브 검증 완료**: 4개 블로그(astroyuji, bwt8307, tenbagger10x, ddorokipapa) × 5개 서브커맨드 모두 정상 동작 확인
  - 미검증 한계(정직 기록): 검증한 4개 블로그 모두 금융/투자 장르이며 post `tags` 추출 경로는 실 태그 사용 블로그에서 미검증
