# Changelog

## [0.2.0] - 2026-09-30 (itda-work/skills#46)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다.
> 0.10.4 는 기본 User-Agent 도 범용 `Mozilla/5.0` 으로 바꾼다 — 이 스킬의 호출은 UA 헤더를 싣지 않으므로, 그 전 판에서는 금감원 서버 로그에 제품명이 남는다.

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 계획·판정만** (규칙 `cowork-network-via-hyve`). `collect_fss.py` 은 사이트를 직접 부르지 않는다(`requests` 제거).
  하위 명령이 생겼다 — 인자만 주던 옛 호출(`collect_fss.py --limit 10`)은 없어졌다.
  - `plan list --run-dir R --save-dir S [--pages N]` → itda-hyve batch `plan_file`(쪽 상한 20, 40개 단위로 나눔)
  - `collect list --run-dir R --next-plan [--limit --keyword --from --to --xlsx]` → 전량 대조 뒤 `ok`·`incomplete`(다음 계획)·`partial`·`blocked`
  - `plan attach <번호…>`·`collect attach --next-plan` → 첨부 받기·검사(새 기능, 아래)
- **BREAKING — 출력은 stdout JSON 한 줄**(`status` 필드). 표는 `table` 문자열로 싣는다. `--format table|json` 은 없어졌다. 옛 판의 "stderr 오류 + exit 1" 대신
  `{"status":"error","error":<종류>,"detail":…}`(`not_fetched`·`input`·`args`·`output`). exit 0 ok·planned / 1 incomplete·error / 2 partial·refused / 3 blocked.
- **BREAKING — 인자 오류도 stdout JSON**(`error: args`, exit 1) — 옛 판은 argparse 가 stderr 에 쓰고 exit 2 였다(exit 2 는 이제 `partial`·`refused`).
  날짜는 형식뿐 아니라 있는 날인지 본다(`2026-13-99` 거절). xlsx 저장 실패는 traceback 이 아니라 `error: output`.
- **BREAKING — xlsx 첫 열이 `번호`** 다.
- **BREAKING — 행 필드** — `no` 가 정수이고 `id`(게시물 식별자)가 붙는다. 표 첫 열이 `번호` 다. `attachments` 가 파일 이름 목록에서 `{name, url}` 목록으로 바뀌었다.
- 목록 요청은 사이트의 GET 폼(`frm`) 필드 중 `menuNo`·`pageIndex` 만 싣는다 — 사이트는 폼 전체(`bbsId`·`viewType`·`cl1Cd`·`sdate`·`edate`·`searchCnd=1`·`searchWrd` 포함)를
  싣는다(2026-10-01 aside 실측). 두 키만으로 같은 목록이 옴을 확인했고 사용자 결정으로 유지한다. 초안의 "사이트 그대로" 서술을 바로잡았다.
- 호출에 `User-Agent`·`Cookie` 를 싣지 않는다 — 2026-09-30 itda-hyve 실측으로 범용 UA 만으로 목록·첨부 모두 응답함을 확인했다(옛 판은 Chrome UA 고정).
- HTML 파서를 `lxml` 에서 표준 `html.parser` 로 — 의존성은 `beautifulsoup4`(+ 엑셀 저장 시 `openpyxl`)만 남았다.

### Fixed

- **첨부 수가 늘 0건이던 결함** — 금감원 목록 마크업이 바뀌어(`a.file-single` → 행 안의 `ul.list-board-attach-file`) 옛 판은 첨부를 한 건도 못 읽고 "-" 로 표시했다(2026-09-30 실측: 첫 3쪽 30건 모두 첨부 있음). 첨부 아이콘이 있는데 목록을 못 읽으면 이제 구조 변경으로 멈춘다. 담당부서·등록일도 열 이름을 대조해 읽는다.

### Added

- **전량 대조**(`collection-completeness`) — 목록 화면의 전체 건수·마지막 쪽과 게시물 번호로 받은 쪽이 빈틈없는지 본다. 쪽마다 전체 건수가 다르거나
  번호가 이어지지 않거나 같은 게시물이 두 쪽에 있으면 받는 사이 목록이 밀린 것으로 보고 **전 쪽을 다시** 받는다(두 번까지, 그래도 어긋나면 `partial: drift`).
  1쪽 0건은 `partial: empty`, 번호를 숫자로 못 읽으면 대조 없이 성공하지 않는다, 쪽 크기가 바뀌면 `partial: structure`, 다른 쪽 화면이면 `partial: mismatch`.
- **재시도 상한** — 빠진 쪽·실패 자리(`{"error":…}`)·HTTP 오류·본문 절단은 같은 파일을 세 번까지(`-r2`·`-r3` 이름, 덮어쓰지 않음). 나쁜 파일을 회차 상태에 남겨 회전을 넘어 센다.
  계획을 받지 않고 `collect` 하면 `not_fetched` — 시도로 세지 않는다.
- **첨부 받기·검사** — 빈 파일·HTML 오류 화면·형식 불일치·잘림(PDF `%%EOF`·ZIP 계열 끝·OLE 는 FAT 가 쓰는 마지막 섹터까지·JPEG/PNG 끝 표지)을 `failed`,
  규칙 없는 확장자를 `unverified_format` 으로 가른다. 요청은 https·정확한 호스트·첨부 경로 허용 목록 안에서만, 리다이렉트를 따라가지 않는다.
  금감원은 첨부 링크가 목록에 있어 바로 받는다(크기 표시가 없어 크기 대조는 없다).
- `--save-dir` 가 Windows 호스트 경로(`C:\…`·`C:/…`·`\\서버\…`)를 받는다 — Cowork 는 리눅스에서 스크립트를 돌려 `Path.is_absolute` 가 이것을 상대 경로로 봤다.
- 재동기화 회전(전 쪽 다시 받기)이 새 기준이 된다 — 그 회전에서 빠진 쪽은 앞 회전 파일로 물러서지 않고 다시 받고, 실패 계수도 새로 센다.
  쪽들을 서로 다른 회전에서 받았으면(한 쪽만 다시 받은 경우) 전 쪽을 한 회전에 다시 받아 시점을 맞춘다(재동기화 상한을 다 쓰면 `warnings`).
- 계획의 파일이 하나도 없는 `not_fetched` 가 같은 회전에서 세 번째면 `partial: not_received` 로 끝난다(끝없이 되풀이되지 않게).
- 첨부 검사: FAT 섹터가 109개를 넘는 큰 OLE 는 끝 검사를 못 해 `unverified_format`(옛 초판은 ok 였다). 첨부를 받을 계획이면 `attach_files`·
  `attach_bytes_known`·`attach_size_unknown` 을 싣는다.
  첨부 칸에 무엇이든 있는데 읽은 첨부가 0 이면 구조 변경으로 멈춘다(아이콘 class 이름에 기대지 않는다).
- 한 쪽이라도 실패하면 그 쪽만이 아니라 전 쪽을 한 회전에 다시 계획한다(재동기화 상한 안에서) — 그 쪽만 받았다가 회전이 섞여 또 전 쪽을 받던 왕복을 없앴다.
- `not_fetched` 출력에 그 회전의 `batch_args`·`single_calls` 를 다시 싣는다(계획을 낸 출력을 잃어도 다시 부를 수 있게). 첨부 단계에서 끝내 파일이 안 온
  회전은 `partial` 로 끝내되 이미 난 판정을 `results` 에 함께 낸다(안 온 파일은 `failed`).
- 허용 경로는 `/` 로 끝나지 않으면 경로 전체가 같아야 한다(`…/fileDown.doX`·`;jsessionid` 거절).
- `--from` 이 받은 범위보다 이르거나 키워드가 받은 쪽 안에서만 찾은 것이면 `warnings` 로 알린다(기간이 받은 범위 안에 온전히 들면 알리지 않는다).
- hyve 층 판독은 공용 `shared/hyve_input.py`. Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 stdout·stderr 를 UTF-8 로 재설정한다(cp949 에 없는 `—` 가 든 실제 판정 출력으로 테스트). `references/netbridge.md` 동봉.
- 공통부 `scripts/board_common.py`(계획·대조·첨부 검사)는 customs-notice·fss-docs 에 같은 사본으로 있다 — 저장소 `scripts/tests/test_board_common_copies.py` 가 바이트 동일을 지킨다.
- 실측 픽스처 — 2026-09-30 itda-hyve 로 받은 원본을 `tests/trim_fixture.py` 로 판독 블록만 남겨 잘랐다. 테스트용 HWP 는 실제 파일(작성자 메타데이터가 있을 수 있다) 대신 최소 OLE 를 만들어 쓴다.

### Removed

- `scripts/fss_api.py`(네트워크 호출 모듈)과 그 테스트, 옛 픽스처 `list_page.html`.
## [0.1.2] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.1.1] - 2026-07-27

### Changed
- GUIDE.md 에 실측 검증 섹션 추가 — 검증한 지침(자연어 요청·실행 명령)과 실제 응답 결과(2026-07-27 라이브) 명시

## [0.1.0] - 2026-07-27

### Added
- 최초 릴리즈 (IGM 클로드 과정 7기 배포, #1309)
- 목록 수집 CLI: 최근 N건(기본 10)·키워드·날짜 범위 필터, 페이지 상한(기본 1)
- 마크다운 표 / JSON 출력, `--xlsx` 저장
- 실패 시 원인 메시지 + 사이트 개편 안내 (조용한 침묵 금지)
