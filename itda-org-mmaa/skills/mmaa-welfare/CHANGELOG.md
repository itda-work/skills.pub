# Changelog — mmaa-welfare

## [0.4.0] — 2026-10-01 (itda-work/skills#46)

> ⚠️ **배포 차단** — itda-hyve 0.10.4 공개 **뒤에** 배포한다. 0.10.4 는 기본 User-Agent 를 범용 `Mozilla/5.0` 으로 바꾼다 —
> 재수집 호출은 UA 헤더를 싣지 않으므로, 그 전 판에서는 군인공제회 서버 로그에 제품명이 남는다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다.
> 검색·답변(동봉 스냅샷)은 네트워크를 쓰지 않아 이 경계와 무관하다.

### Changed

- **BREAKING — 재수집은 itda-hyve, `collect.py` 는 판독만** (itda-work/skills#45, 규칙 `cowork-network-via-hyve`). `requests` 직접 호출과
  0.7초 순차 대기(`--delay`)를 지웠다.
  - 옛판: `collect.py [--output-dir D] [--delay S] [--limit N]` 한 번(스크립트가 요청).
  - 새판: `collect.py plan --run-dir R --save-dir S [--limit N]` → itda-hyve `batch`(`plan_file`) → `collect.py collect --run-dir R [--output-dir D]`
    를 `status: "ok"` 가 될 때까지 되풀이한다(진입 → 메뉴·목록 → 상세, 계획 파일 하나에 8개 — batch 동시 실행 한 번, 저속 수집).
    회차 상태는 `R/mmaa-state.json`. `--save-dir` 는 같은 폴더의 호스트 절대 경로(`/…`·`C:\…`·`C:/…`·UNC).
  - 기본 출력이 스킬 `data/` 에서 **회차 폴더의 `snapshot/`** 으로 바뀌었다(배포본 `data/` 는 읽기 전용). 스킬 `data/` 갱신은 `--output-dir` 로.
- **BREAKING — 전량 대조** — 옛판은 받지 못한 페이지를 로그만 찍고 건너뛴 채 스냅샷을 썼다. 이제 계획한 페이지가 **전부** 와야 저장한다.
  실패 자리·누리집 페이지가 아닌 본문(WAF 차단 "Page Not Found (wf)" — GNB `dep1a`·`</html>` 부재로 판정, 잘린 본문)은 다시
  계획하고, 한 페이지가 세 번 나쁘게 오면 `partial`(exit 2)로 끝내며 스냅샷을 쓰지 않는다. 바퀴 상한 30 — 앞 계획이 전부
  판정된(안 온 파일 0) `collect` 만 센다(상태 `cycles`; 계획 파일 이름의 `round` 는 판정마다 오른다 — W13 재확인 b3).
  아직 안 온 파일은 실패로 세지 않는다 — batch 가 끝나기 전에 `collect` 를 불러도 같은 계획을 다시 낼 뿐이고(`waiting`, 바퀴 그대로),
  새 파일 없이 5번 연달아 부르면 상태를 그대로 둔 채 `not_fetched`(exit 1)로 멈춘다(W13 리뷰 m2 — 세 번 헛부르면 되살릴 수 없는 `partial` 이었다).
  스냅샷 직전에 받은 파일이 사라졌으면 traceback 대신 그 페이지만 다시 계획한다(`lost`, W13 리뷰 m3).
  목록이 로그인 셸이 아닌데 1쪽에서 상세 id 를 하나도 못 읽으면 `warnings` 에 싣는다(W13 리뷰 m1 — 조용한 `ok` 였다).
- **BREAKING — 출력** — stdout JSON(`status`: `planned`·`incomplete`·`ok`·`smoke`·`partial`·`error`, 계획이면 `plan_files`·`batch_args`,
  끝나면 `meta`·`warnings`). 진행 로그는 stderr 그대로. `--limit` 스모크 결과는 `status: "smoke"` 로 전량(`ok`)과 구분한다.
- `meta.json` 에 `menu_count`(GNB 에서 발견한 복지포털 메뉴 수)·`listing_auth_count`(로그인 셸이었던 목록 수)·`listing_ids`(목록에서 읽은 상세 수)·`limited` 추가.
- 요청 허용 범위를 코드로 고정: `https://www.mmaa.or.kr/web/contents/` 아래만 계획한다(밖이면 받지 않고 `warnings`).
- 저장 이름 `mmaa/<p|l|v>-<경로 이름>-<URL 해시>.html` — 대소문자만 다른 경로(`WF-…`·`Wf-…`)도 대소문자 무시 파일 시스템에서 겹치지 않는다.
- `requests` 의존성 제거(`requirements.txt`·`deps.json` — beautifulsoup4 만).

### Added

- 로그인 영역 확인(2026-10-01 itda-hyve 실측): 메뉴 39개 발견, 콘도 예약 등 로그인 셸은 `auth_required`·본문 비움 그대로, **제휴복지 카테고리 8개와
  특별할인소식 목록 1쪽도 전부 로그인 셸**이다(목록을 따라가도 상세가 나오지 않는다). 동봉 스냅샷(2026-09-04)은 로그인 영역 25쪽이 이미 본문 없이
  들어 있어 다시 만들지 않았다. robots.txt 는 없다(WAF 의 "Page Not Found (wf)" HTML 을 200 으로 준다 — 규칙 없음).
- hyve 층 판독은 공용 `shared/hyve_input.py`. `references/netbridge.md` 동봉. Windows 콘솔(cp949) UTF-8 재설정(테스트로 고정).
- 실측 픽스처 5종(`tests/trim_fixture.py` 로 GNB 복지포털 블록·본문 컨테이너·로그인 스크립트만 남김)과 흐름 테스트 `tests/test_collect_flow.py`.
## [0.3.3] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.3.2] — 2026-09-27

### Changed

- 수집 User-Agent 끝의 `itda-skills-mmaa-welfare` 를 뺐다(outbound-identity-leak) — 브라우저 UA 부분은 그대로.

## [0.3.1] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- 라이브 확인 브라우저 후보에서 hyve `web_browse` 를 aside 브라우저(`itda-web:aside-browser-mcp`)로 바꿨다.

## [0.3.0] — 2026-09-04 (이슈 #1643)

### Changed

- 스냅샷 재수집(`generated_at` 2026-09-04): 41페이지 — 공개 본문 15 · 로그인 영역 25.
  공개 본문 텍스트는 7/27 대비 변화 0건, GNB 메뉴에서 「사이판 월드리조트」·「베트남
  하이퐁 대명(소노)」 2개 소멸.
- 범위·한계 정정: 콘도 예약(대명·한화)·제휴복지 전체·기타복지 전체는 **회원 로그인
  영역**이다. 구 문서의 "특별할인소식·제휴업체 상세는 WAF 경유 JS 렌더라 미수집"은
  오판이었다(브라우저로 열어도 `webLogin.do` 로 리다이렉트 — aside 실측).
  최신화 요청 절도 로그인 영역은 라이브 조회 대상이 아님을 명시.

### Fixed

- `collect.py` 로그인 벽 판정: 회원 전용 페이지의 정적 HTML(≈176KB)은 본문 없이
  최상위 `<script>` 에 `alert("로그인 후 이용 가능합니다."); location.href='…webLogin.do'`
  두 문장만 싣는데, 종전 판정(`html[:4000]` + `len < 8000`)이 이를 못 잡고
  `div.content` 폴백이 GNB 메뉴 문자열(37자)을 본문으로 세어 **22페이지가 본문으로
  오분류**됐다(구 "본문 34페이지" 중 실체는 12). 스크립트 본문이 그 두 문장뿐인
  형태를 전문 대상으로 판정하고(공개 페이지의 ajax 오류 콜백·onclick 속성 안 같은
  문자열은 제외), `div.content` 폴백을 제거했다. 회귀 테스트 3종 + 뮤테이션 3종 RED 실측.
- 동봉 스냅샷 계약 테스트: "본문 20개 이상"(오분류 위의 계약) → 본문 10개 이상 +
  본문 페이지 최소 100자 + 실측 로그인 셸 3종 `auth_required` 단언.

## [0.2.0] — 2026-07-27 (이슈 #1316)

### Changed

- 스킬명 `welfare-portal` → `mmaa-welfare` — 구 mmaa-welfare(공지·카탈로그 얕은 목록 수집, IGM 7기 자동 생성 부산물)를 제거하고 본 스킬(복지 본문 스냅샷 + 출처 명시 Q&A)이 이름을 승계, 군인공제회 복지 스킬 단일화.

## v0.1.1 (2026-07-27, 이슈 #1302 후속)

### Changed

- description 압축 (마스터 결정 — 절충안): 예시 발화 나열을 제거하고 WHAT+WHEN
  2문장으로 최소화. "군인공제회 복지" 맥락 자동 발동은 유지하되 상시 컨텍스트
  비용·오발동을 축소. 명시 호출(`/mmaa-welfare`)은 기존대로 가능.

## v0.1.0 (2026-07-27, 이슈 #1302) — PoC 초판

### Added

- 복지포털(`welfaremain.do`) 공개 콘텐츠 스냅샷 수집기 `collect.py` — GNB 에서
  복지포털 메뉴 트리를 동적 발견, 본문 추출(표 행 보존), 로그인 벽 감지
  (`auth_required` 마킹, 본문 미수집), 저속 순차(0.7s) 수집.
- 스냅샷 검색기 `search.py` — 제목·breadcrumb 가중 키워드 스코어링, 출처 URL·
  수집일 포함 JSON 출력.
- 동봉 스냅샷 `data/` (2026-07-27 수집, 본문 34페이지 + 로그인영역 9페이지 마킹).
- 답변 계약: 항목별 출처 URL, 스냅샷 수집일 명시, 패키징 데이터 불변 한계 고지,
  최신화 요청 시 실브라우저(Claude in Chrome / hyve web_browse) 라이브 조회 절차.

### Known Limitations

- 특별할인소식 게시글·제휴업체 상세(WFL-Category)는 서버가 정적 요청에 본문을
  주지 않아(WAF 경유 JS 렌더) 스냅샷 미포함 — 라이브 조회 경로로 안내.
- 복지포털 외 섹션(저축·대여·주택 등)은 범위 밖 (v2 후보).
