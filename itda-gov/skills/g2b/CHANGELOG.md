# Changelog — itda-g2b

## [0.12.1] — 2026-10-01 (itda-work/skills#46)

### Changed

- `references/netbridge.md` 사본을 정본과 동기화 — `secret_missing` 은 그 소스 하나에 대한 멈춤이다: 다른 경로로 키를 넣지 않고(같은 API 를 다른 통로·다른 키로 부르지 않는다), 여러 소스를 묶는 스킬은 그 소스만 빼고 계속할 수 있다. 앞 판 뒤에 사본이 바뀌어 배포본 내용이 달라졌으므로 patch 를 올린다(skills v14.0.0 준비).

## [0.12.0] — 2026-09-30 (itda-work/skills#45)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다 — 공개된 적 없는
> 개발판(0.9.x) 표기를 걷어냈다(공개판은 0.8.1·0.9.0·0.10.1 이후뿐, `references/netbridge.md` 도 같은 기준으로 동기화).

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 계획·`--input` 가공만** (itda-work/skills#45, 규칙 `cowork-network-via-hyve`). `collect_g2b.py` 가 `plan`(기간을 달력 달 단위 창으로 나눈 `http_request` 인자·batch `plan_file`)과 `collect --input <파일…>`(itda-hyve 가 `save_as` 로 저장한 응답 가공) 두 명령이 됐다. 키는 itda-hyve GUI 시크릿 탭의 `KO_DATA_API_KEY`(Decoding 키)를 `params` 의 `{{secret:KO_DATA_API_KEY}}` 로만 가리킨다. `--api-key`·`os.environ` 키 경로·키 주입 규칙·네트워크 코드(`urllib.request`)와 단일 쪽 인자 `--rows`·`--page` 를 지웠다(단일 쪽 훑어보기는 `collect --single-page`).
- **창별 전량 대조** — 창마다 ⌈totalCount ÷ numOfRows⌉ 쪽을 대조해 모자라면 `error: "incomplete"` 와 더 받을 호출 `next_calls`(`--next-plan` 이면 batch 계획 파일도)를 준다. `--max-pages`(기본 20) 상한을 넘는 창은 종전처럼 `truncated: true` + 경고다.
- **입력 판정** — 본문 절단·HTTP 오류·itda-hyve 실패 자리와 함께, 실측으로 확인한 오류 본문 두 형태(`nkoneps.com.response.ResponseError` 의 `resultCode 07` 등, 게이트웨이 `OpenAPI_ServiceResponse` 의 `returnReasonCode 20/22/30/31`)를 `error: "api"` 로 낸다. 옛 코드는 둘 다 "예상치 못한 응답 구조" 로 뭉갰다.
- SKILL.md 를 "요청은 itda-hyve, 가공은 스크립트" 한 흐름으로 다시 썼다 — 창 × 쪽 호출 계획, `batch` + `plan_file` 묶어 받기, 쪽 이어받기, 호출 예산, 실패 코드 표. `references/netbridge.md` 사본을 동봉했다. GUIDE.md 는 시크릿 탭 등록만 안내한다. Windows 콘솔 UTF-8 출력 재설정을 넣었다.
- **batch 계획을 40호출씩 나눈다**(W4 리뷰 M1, itda-work/skills#46). itda-hyve `batch` 는 40호출을 넘으면 하나도 실행하지 않는다 — `plan --write`·`collect --next-plan` 이 40개를 넘으면 `plan-1a.json`·`plan-1b.json` … 으로 나눠 쓰고, SKILL.md 는 파일마다 batch 한 번을 부르게 한다.
- **BREAKING — 계획 출력 필드**: `plan --write` 는 `plan_file` 대신 **`plan_files`**(목록)·`call_count`·`calls_preview`(앞 3개)를 싣고 `calls` 를 빼며(호출은 파일에 있다), `--write` 가 없으면 `calls` 전부와 `call_count` 를 싣는다. `collect` 의 `incomplete` 는 `next_call_count`·`will_truncate`·`windows` 를 싣고, `--next-plan` 이 있으면 `plan_file` 대신 **`plan_files`**·`next_calls_preview`(앞 3개)만, 없으면 `next_calls` 전부를 싣는다(세 달 × `--max-pages 50` 에서 stdout 49KB → 약 3KB).
- **잘림을 받기 전에 알린다**(m3) — 창별 `need_pages`·`will_truncate` 를 첫 `incomplete` 부터 싣고(ok 출력의 `windows` 에도), SKILL.md 는 `will_truncate` 면 받기 전에 사용자에게 묻게 한다.
- **이름의 쪽과 본문 `pageNo` 를 대조한다** — 다르면 다른 호출의 응답을 그 이름으로 저장한 것이라 `error: "input"`.
- 단건 호출 `timeout_sec` 을 60 → **50** 으로(Cowork 호출 상한 60초보다 짧게 — m6). 키워드 필터가 `bidNtceNm: null` 에서 `AttributeError` 로 죽던 것을 고쳤다(m9).
- 문서: 계획 파일은 그 회차 `save_dir` 안에 쓴다(새 하위 폴더로 다시 받을 때 `plan_file` 이 `not_found` 가 되던 것 — m7), PowerShell `SKILL_DIR` 정의(m8), `scanned_count < total_count` 가 `ok` 로 나오는 세 번째 경우(받는 사이 공고 변화)와 오프셋 쪽 매김의 한계(m2), 공고 0건 창은 `00` + `totalCount 0`·31일 창은 `07` 없이 통과(2026-09-30 실측)를 적었다. `references/g2b.md` 의 오류 출력 예시를 실제 필드로 고쳤다(m10).

## [0.11.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **BREAKING — env 파일을 더 읽지 않는다** (itda-work/skills#45, 사용자 결정 2026-09-30). `.env`·`.env.txt` 를 포함해 어떤 env 파일도, `~/.claude/settings.json` 도 스크립트가 직접 열지 않는다. `KO_DATA_API_KEY` 는 Claude Code 에서 셸 환경변수 또는 `claude config set env.KO_DATA_API_KEY "키"` 로만 받는다(스크립트가 `os.environ` 에서 읽음). 스크립트가 API 를 직접 부르므로 itda-hyve 시크릿 경로는 없다. SKILL.md·GUIDE.md·references 의 키 설정 안내·키 주입 규칙·오류표를 고쳤다.

## [0.10.5] — 2026-09-30 (itda-work/skills#45, #47)

### Changed

- **자격증명 파일 별칭에서 `환경변수.txt` 제거** (itda-work/skills#45, BREAKING) — 읽는 파일명은 `.env`·`.env.txt` 두 가지다. `환경변수.txt` 로 키를 두었다면 파일 이름을 `.env.txt`(또는 `.env`)로 바꾼다 — 내용은 그대로 두면 된다. SKILL.md·GUIDE.md 의 파일명 별칭 안내·키 주입 규칙(파일명 2종·셸 glob 오탐 설명)·출처 표시 예시를 맞췄다.

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.10.4] — 2026-09-28 (itda-work/skills#26)

### Changed

- **자격증명 파일 별칭에서 `env.txt` 제거** (itda-work/skills#26) — 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 로 키를 두었다면 `환경변수.txt` 또는 `.env` 로 이름을 바꾼다. SKILL.md 의 파일명 별칭 안내·키 주입 규칙(파일명 3종·셸 glob 오탐 설명)을 맞췄다.

## [0.10.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.10.2] — 2026-07-26 (이슈 #1280·#1281·#1282)

### Changed
- compatibility 라벨을 `Claude Code & Cowork. Python 3.10+` 로 교체 (#1280).
- `.env` 위치 안내를 Cowork 연결 폴더 / Claude Code 프로젝트 루트 양쪽 표기로 교체하고 셸 환경변수·settings.json `env` 경로를 명시 (#1282).

## [0.10.1] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [Unreleased] — 키워드 검색 거짓 0건(silent under-collect) 수정

### Fixed
- **[치명] 키워드 검색 거짓 0건 수정.** 기존엔 `rows=10` 단일 페이지만 조회 후
  클라이언트 필터 → 키워드가 11번째 이후 공고에 있으면 `count:0`을 반환했다.
  나라장터는 하루 약 3,300건이 등록되므로 라이브에서 `구매`·`교육` 키워드가
  첫 10건엔 0건이나 전 범위엔 396·124건 존재함을 확인(거짓 0건 실증).
  `g2b_api.collect_all_bids()` 추가 — totalCount 소진 또는 `--max-pages`(기본 20,
  페이지당 999건) 상한까지 전 페이지를 순회·중복제거 후 누적, 그 위에서 키워드 필터.
- 페이지 경계 중복 제거: `(bidNtceNo, bidNtceOrd, refNtceNo, refNtceOrd)` 안정 키.
  같은 공고번호라도 차수가 다르면 별개 행으로 보존.

### Changed
- **출력 의미 구분.** `total_count`(API 필터 전 총계) vs `count`(필터 후) vs
  신규 `scanned_count`(실제 순회 건수) 분리. `truncated` 플래그 + `warnings` 추가 —
  `--max-pages` 상한 도달 시 "전체 N건 중 X건만 스캔, 미조회분 존재" 경고 출력.
- `--rows`/`--page` 명시 시 자동 순회를 끄고 단일 페이지만 조회(브라우즈 모드).
  미지정 시 키워드 검색은 전 페이지 자동 순회.
- 신규 옵션 `--max-pages`. SKILL.md 옵션표·argument-hint·`references/g2b.md` 동기화.
- SKILL.md "파일 구조" 환각 교정 — `env_loader.py`·`itda_path.py`는 g2b가 아니라
  `shared/`에서 주입, 존재하지 않던 `test_env_loader.py` 제거.

## [Unreleased] — SPEC-COWORK-ENV-GUIDE-001

### Changed
- Cowork에서 `claude config set` 안내 제거 — 에러 메시지 `.env` 단일 통일, 문서는 `.env` 1순위 + config set은 '로컬 CLI 전용' 펜스로만.

## [0.9.7] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.9.6] — 2026-05-21

### Changed

- `env_vars` frontmatter 블록 폐기 → SKILL.md body `## 환경 변수` 표로 이전. itda-setup·check_env_vars.py 의존성 제거.

## [0.9.5] — 2026-05-21

### Improvements

- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.

## [0.9.4] — 2026-05-13

### Improvements

- **GUIDE.md 일반 사용자 문서 정책 준수**: 자동화 팁 섹션의 `py -3 scripts/collect_g2b.py ...` cron 예시를 "AI 키워드로 지난주 신규 입찰 공고 정리해줘"라는 자연어 반복 사용 예시로 대체. 일반 사용자용 문서에 CLI 명령 노출 금지 정책 준수.
