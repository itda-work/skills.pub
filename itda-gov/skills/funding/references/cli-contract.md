# funding CLI 계약 (v3.0.0)

이 문서는 `funding` 스킬의 스크립트 표면을 **고정**한다. SKILL.md·GUIDE·테스트·문서는
전부 이 파일을 단일 참조로 삼는다 — 여기 없는 인자·exit code·필드를 다른 문서가 주장하면
그쪽이 틀린 것이다.

- 스크립트는 **네트워크를 하지 않는다**(itda-work/skills#45, 규칙 `cowork-network-via-hyve`). 요청은 itda-hyve 의
  `batch`(`plan_file`)·`http_request` 가 보내고 `save_as` 로 회차 폴더에 저장한다. 스크립트는 **계획 파일을 쓰고**(`plan`)
  **저장된 파일을 판정한다**(`collect`).
- 대상 스크립트: `scripts/survey_crawl.py`(계획·판정), `scripts/survey_diff.py`(회차 비교).
- `survey_crawl.py` 는 결과와 오류를 **stdout JSON 한 덩어리**로 낸다(모델이 필드로 읽는다). stderr 에는 `run_manifest.json`
  손상·잔존 run 경고 같은 진단 한 줄만 나온다(`run_manifest.update_manifest`) — 판정은 stdout 필드로 한다.
- API 키가 없다 — 공개 공고 페이지만 받는다. 2.x 의 K-Startup 공공데이터 API 경로는 3.0.0 에서 지웠다(CHANGELOG).

---

## 0. 회차 폴더와 저장 이름 (식별 계약)

한 조사 = 한 회차 폴더(`<BASE>/<YYYYMMDD-HHMM>/`). 스크립트에는 스크립트가 보는 경로(`--run-dir`), itda-hyve 에는
같은 폴더의 **호스트 절대 경로**(`--save-dir` → 계획 파일의 `save_dir`)를 준다. 모든 `save_as` 는 그 폴더 기준 상대 경로이고 한글이 없다.

| 파일 | 쓰는 쪽 | 뜻 |
|---|---|---|
| `raw/list/<source>-p<NNN>.html` | itda-hyve | 목록 쪽. 같은 쪽을 다시 받으면 `-r2`·`-r3` — 판정은 가장 큰 번호를 쓴다 |
| `raw/detail/<source>-<id>.html` | itda-hyve | 상세 페이지(다시 받으면 `-r2`). `<id>` 의 영숫자·`_`·`-` 밖 글자는 `_` |
| `raw/detail/kocca-<intcNo>-pop1.html` | itda-hyve | KOCCA 첨부 목록 팝업 |
| `raw/att/<source>-<id>-<NN>.<ext>` | itda-hyve | 첨부. `<ext>` 는 상세 페이지가 준 파일 이름의 확장자(없으면 `bin`) |
| `plan-list-<n>[a-z].json`·`plan-detail-<n>[a-z].json` | 스크립트 | batch `plan_file`(`{calls, save_dir, timeout_sec: 50}`) |
| `funding-list.json`·`funding-detail.json` | 스크립트 | 계획 상태(소스·기준일·상한·대상) — 손대지 않는다 |
| `survey.jsonl`·`run_manifest.json`·`details/` | 스크립트 | 결과 |

- `raw/list/`·`raw/detail/`·`raw/att/` 에 이름 규칙 밖 파일이 있으면 `error: input`(조용히 건너뛰지 않는다).
- 실패한 호출 자리에는 모델이 `{"error": {"code", "message"}}` 를 **스크립트가 보는 경로(`R`) 기준으로** 쓴다(itda-hyve 실패는 파일을
  쓰지 않으므로). 스크립트는 입력 세 형태(본문 그대로·응답 JSON 전체·실패 자리)를 모두 읽는다(공용 `shared/hyve_input.py`).
- **없는 파일의 상한** — `collect` 는 회차 폴더의 계획 파일 전부(모양이 `{calls, save_dir}` 인 JSON — 이름을 바꿔 줘도 센다)에서
  저장 이름이 몇 번 **시도**됐는지 센다. 시도는 그 계획 파일의 저장 이름 중 파일(응답·실패 자리)이 하나라도 있는 계획만이다 — 아무것도
  남기지 않은 계획 파일은 batch 로 부르지 않은 것으로 본다(계획 파일을 다 받기 전에 `collect` 를 불러도 받아 본 적 없는 쪽이 확정되지 않게).
  그래서 **`batch_args` 를 전부 부른 뒤에** `collect` 한다. 같은 이름을 **3번** 시도했는데 파일이 없으면 그 호출은 "받지 못함"(`hyve:missing`)으로
  확정한다 — 시도 흔적이 없는 한 호출짜리 계획이 되풀이되면 회전 상한(목록)·대상별 8회전(상세)이 끝을 낸다 —
  목록 쪽은 `bad`(다시 받지 않음), 상세는 `fail`, 첨부는 `failed`. 읽을 수 없는 `plan-*.json` 은 `error: input`.
- 계획 파일은 호출 **40개**, 같은 호스트 **20개**까지 담는다(호스트를 번갈아). 넘치면 `a`·`b`… 로 나눈다(26개 상한).
- 호출 한 칸: `{"id", "tool": "http_request", "args": {"url", "follow_redirects": false, "timeout_sec": 30|45, "save_as"}}`.
  쿼리는 `url` 에 사이트가 만드는 순서 그대로(`params` 는 이름순으로 다시 짠다). `headers`(User-Agent·Cookie)를 싣지 않는다.

## 1. `plan list` — 목록 1쪽 계획

```
python3 survey_crawl.py plan list <source…|all> --run-dir R --save-dir S [--max-pages N] [--smoke] [--write FILE]
```

| 인자 | 설명 |
|---|---|
| `source` | `kstartup` · `bizinfo` · `nipa` · `smtech` · `kocca` · `all`(다섯 모두). `kocca` 는 요청하지 않고 `inactive` 로만 기록 |
| `--run-dir` | 회차 폴더(없으면 만든다). 이미 목록 계획(`funding-list.json`)이 있으면 `error: args` |
| `--save-dir` | 같은 폴더의 호스트 절대 경로(`/…`·`C:\…`·`C:/…`·`\\서버\…` — 스크립트가 도는 OS 가 아니라 호스트 기준) — 상대 경로면 `error: args` |
| `--max-pages` | 소스당 쪽 상한(기본 150, smtech 30). 분모가 넘으면 `collect` 가 받기 전에 `will_truncate` |
| `--smoke` | 1쪽만. 커버리지 판정 없이 `stop_reason: smoke`·`coverage: window` |
| `--write` | 계획 파일 경로(기본 `plan-list-<n>.json`, 회차 폴더 바로 아래여야 한다) |

출력: `{"status": "ok", "sources", "inactive"?, "estimate": {"typical_calls", "total_calls", "note"}, "plan_files", "batch_args", "call_count", "calls_preview"}`.
`estimate` 는 2026-09-30 실측 쪽 수 + 1쪽 괄호 2호출(kstartup 14·bizinfo 107·nipa 38·smtech 6)이며 받기 전에 사용자에게 알리는 값이다.

## 2. `collect list` — 목록 전량 대조

```
python3 survey_crawl.py collect list --run-dir R [--next-plan [FILE]]
```

`--next-plan` 을 값 없이 주면 `plan-list-<n>.json` 을 자동으로 짓는다. 주지 않으면 다음 호출을 `next_calls` 로 싣는데, 이것은
**미리보기 전용**이다(`preview_only: true`) — 계획 파일이 남지 않으면 없는 파일 상한·재동기화 횟수·회전 상한·1쪽 판 대조가 동작하지
않는다. 받을 때는 늘 `--next-plan` 을 준다(`collect detail` 도 같다).

### 쪽 판정

| 판정 | 조건 | 처리 |
|---|---|---|
| `ok` | 목록 행이 있고, 본문의 현재 쪽 표시가 이름의 쪽 번호와 같다 | 쓴다 |
| `empty` | 행이 없고 "등록된/검색된 … 없습니다" 표시 | 마지막 쪽 너머 |
| `blocked` | 앞부분에 차단·CAPTCHA 표지 | 소스 `manual`(exit 3) — 우회하지 않는다 |
| `bad` | hyve 실패 자리·HTTP 오류·잘림·3xx 본문·구조 없음·현재 쪽 표시 없음·쪽 번호 불일치·1쪽이 쪽당 행 수를 채웠는데 마지막 쪽 표시 없음·(bizinfo·nipa) 행 번호를 못 읽은 행 | `-r2`·`-r3` 로 다시 받고, 그래도면 소스 `partial` |
| (받지 못함) | 같은 저장 이름을 **3번 시도**했는데 파일이 없다(시도 = 그 계획 파일의 저장 이름 중 파일·실패 자리가 하나라도 온 계획) | 다시 받지 않고 `bad`(`hyve:missing`) — 1쪽이면 `stop_reason: fetch-failure` |

### 분모와 전량 대조 (2026-09-30 실측)

| 소스 | 목록 | 분모 | 대조 |
|---|---|---|---|
| kstartup | 모집중만, 쪽당 15 | 1쪽의 마지막 쪽 링크 | 고유 id = 15×(마지막−1)+끝 쪽 행 수(가운데 쪽 15 미만·쪽 사이 중복이면 어긋남). 쪽들이 한 회전에 모여야 한다(행 번호가 없어 늦게 받은 쪽이 변화를 숨긴다) |
| bizinfo | 모집중만, 쪽당 15 | 1쪽 첫 행 번호 = 총건수(`reported_total`) | 행 번호(오래된 것부터 1)가 1..최대까지 빠짐없이 한 번씩, 쪽 사이 같은 id 없음(빈 번호·같은 번호의 다른 공고·중복 id 는 어긋남) |
| nipa | 이력 전체, 쪽당 10 | 1쪽 첫 행 번호 | bizinfo 와 같다. 마감 행은 싣지 않는다 |
| smtech | 이력 전체, 쪽당 15 | 마지막 쪽 링크 | 5쪽씩 받고, 받은 앞 구간 끝의 "모집중 0 인 쪽"이 3개 이어지면 멈춘다(`closed-streak`, `coverage: window` — 받지 못한 쪽은 연속을 끊는다). 쪽 p 의 행 번호는 15(p−1)+1…(최신부터 1)이고 마지막 쪽이 아니면 정확히 15행. 쪽 사이 같은 id 는 밀림. 받은 구간의 마감일이 내림차순이 아니면 경고 |
| kocca | — | — | robots `Disallow:/kocca/*/list.do` — 받지 않는다(`inactive`, `stop_reason: robots-disallowed`, `coverage: none`) |

**다시 받기 규칙**(재리뷰 N1·N2 — 회전 하나 = 계획 파일 한 벌(`plan-list-<n>a/b…`)을 전부 받고 `collect` 한 번):

- **1쪽 괄호** — kstartup·bizinfo·nipa 는 마지막 쪽이 2 이상이면 2회전 계획의 **맨 앞과 맨 끝**에 1쪽을 넣는다(`-r2`·`-r3`). 계획 파일이
  나뉘면 앞 1쪽은 첫 파일, 끝 1쪽은 마지막 파일에 들어가 **파일 사이에서는** 그 회전을 감싼다 — 한 파일 안의 호출 순서는 batch 가
  보장하지 않는다(동시 8칸 — kstartup 처럼 한 파일이면 앞뒤 1쪽은 같은 1~2초 안의 두 시점이다). 앞 1쪽으로 1회전과 2회전 사이의 변화(특히 **제거** — 중복도 모자란 쪽도 만들지
  않는다)를 막고, 앞뒤 1쪽이 다르면 그 회전 동안 목록이 바뀐 것이다(맨 위 추가 + 경계 부근 제거가 겹치면 행 번호가 빈틈없이 맞아 한 건이
  빠지는데 — 시뮬레이터 실측 — 이 비교가 잡는다). 괄호의 한쪽만 왔으면(실패 자리·파일 없음) 남은 판을 쓰고 1쪽 **한 호출**을 더 계획해
  대조한다 — 같으면 통과, 다르면 아래 재동기화. 나머지 쪽만 오고 1쪽 다시 받기가 계획된 적이 없으면 그것을 계획한다.
- **1쪽 판 대조**(3차 리뷰 P2·P3) — 쓰인 쪽들(2쪽 이상)이 받힌 회전이 [a, b] 면, a 회전의 앞 1쪽(없으면 그 전 회전의 마지막 1쪽)부터
  b 회전의 끝 1쪽(또는 그 뒤에 받은 1쪽)까지의 1쪽 판들이 모두 같아야 한다. 쪽 하나를 늦게 따로 받아 여러 회전에 걸쳐도 그 사이의
  "맨 위 추가 + 상쇄하는 제거" 가 여기서 보인다. 끝 쪽 확인이 없으면 1쪽 한 호출을 더 받는다.
- **이상한 쪽**은 그 쪽만 다시 받는다(쪽마다 나쁜 판 3개까지) — 행 번호가 있는 bizinfo·nipa 는 늦게 받은 쪽도 번호로 대조된다.
  kstartup 은 2회전 뒤에 **어떤 쪽이든** 다시 받게 되면 받은 쪽 전부를 한 회전에 다시 받는다(재동기화를 다 썼으면 그 쪽만).
- **받는 사이 목록이 바뀐 흔적**(위 대조의 어긋남·앞뒤 1쪽 다름·kstartup 쪽들이 여러 회전에 걸침)이 보이면 쪽을 골라 받지 않고
  **받은 쪽 전부**(분모까지, 괄호 포함)를 한 회전에 다시 받는다 — 두 번까지(재동기화 회전은 호출 id 의 `resync-` 표식으로 알아보고,
  시도된 회전만 센다 — itda-hyve 계획 파일은 모르는 키를 거부해 파일 최상위에 표식을 둘 수 없다). 그래도 어긋나면 `partial`. 받지 못한 쪽이 있으면 빈 번호는
  그 탓이므로 다시 받지 않는다. (쪽을 골라 받으면 옛 판과 새 판의 경계가 회전마다 한 쪽씩 옮겨 bizinfo 가 12~52회전을 돌았다.)
- **회전 상한** — 소스마다 계획 회전이 "필요한 회전(kstartup·bizinfo·nipa 2, smtech 1+⌈(상한−1)/5⌉) + 6" 에 닿으면 더 계획하지 않고
  그때까지 받은 것으로 `partial`(`stop_reason: round-cap`, `coverage: window`, 받지 못한 쪽은 `errors`).
- **1쪽 다시 받기만 실패**하면(2회전 뒤) 1회전 1쪽으로 분모를 잡고 받은 쪽을 실어 `partial` — `errors` 에 "받는 사이의 변화를 대조하지
  못했다".
- **1쪽을 끝내 못 받거나 못 읽으면**(분모가 없다) `partial`·`coverage: none`·0건(`stop_reason: fetch-failure`·`parse-failure`).

**1쪽이 "없습니다"(0건)면 네 소스 모두 `partial`**(`stop_reason: empty`, `coverage: none`, exit 2) — 모집중이 수백 건인 소스에서 1쪽 0건은
점검·조회 조건 변경·오류 화면일 가능성이 훨씬 크다. 2.x 의 `--min-expected` 하한을 이 규칙과 분모 대조가 대신한다.

**읽지 못한 행**(링크·구조를 못 읽은 행 — `dropped.no_link` 등)이 하나라도 있으면 그 소스는 `partial` 이다. 정상 계수(마감 행·IRIS 행)는
`counted` 로 따로 싣는다.

모집중 판정(이력형 목록): SMTECH 상태 표시(접수중·접수예정 = 모집중, 접수완료·마감 = 아님) → 없으면 마감일 ≥ 계획 기준일 →
마감일을 못 읽으면 모집중(보수적).

### 출력

모자라면 exit 1:

```json
{"status": "incomplete", "error": "incomplete", "detail": "…", "sources": {"<source>": {"status": "incomplete", "pages_fetched", "last_page", "reported_total"?, "pending_calls"}},
 "next_call_count", "will_truncate"?, "need_pages"?, "plan_files", "batch_args", "call_count", "next_calls_preview"}
```

다 모이면 `survey.jsonl`(수집 0건이면 쓰지 않는다)·`run_manifest.json` 을 쓰고:

```json
{"status": "ok|partial|blocked", "collected", "survey", "manifest",
 "sources": {"<source>": {"status", "pages_fetched", "last_page"?, "reported_total"?, "collected", "stop_reason", "coverage", "counted"?, "dropped"?, "errors"?}},
 "warnings"?}
```

## 3. `plan detail` — 상세 계획

```
python3 survey_crawl.py plan detail <대상…> --run-dir R [--save-dir S] [--write FILE]
```

대상 한 개는 `<source>:<id>`(`survey.jsonl` 에서 url·제목을 찾는다 — K-Startup id 는 `pbancSn`), 상세 URL, 또는 K-Startup 공고번호(숫자).
`--save-dir` 를 빼면 `plan list` 때 값을 쓴다. 같은 대상을 다시 주면 건너뛴다(`funding-detail.json` 에 누적).

**요청하지 않는 대상**(`refused[]` 에 사유, 전부 거부면 `error: args`): 목록에 없는 `<source>:<id>` · IRIS 행(`detail: "iris"`) ·
다섯 소스의 정확한 호스트가 아닌 URL(서브도메인 포함) · URL 에서 공고 id 를 못 읽음 · robots 불허 경로 · 소스의 상세 화면 경로가 아님
(허용: kstartup `/web/contents/bizpbanc-ongoing.do` · bizinfo `/sii/siia/selectSIIA200Detail.do` · nipa `/home/2-2/<숫자>` ·
smtech `/front/ifg/no/notice02_detail.do` · kocca `/kocca/pims/view.do` — 글자 그대로, `..`·인코딩 없이).

## 4. `collect detail` — 상세·첨부 판정

```
python3 survey_crawl.py collect detail --run-dir R [--next-plan [FILE]]
```

1. 상세 페이지를 읽는다. 차단 표지면 `manual`. 소스별 **본문 컨테이너**(kstartup `content_wrap`·bizinfo `view_cont`/`print_area`·nipa
   `tbWrap gonggo`/`hwp_editor_board_content`·smtech `#subcontent`·kocca `#contents_body`)가 없으면 공고 화면이 아니다(`unexpected_response` —
   없는 공고번호의 셸·3xx 본문·오류 화면). 그 공고인지 대조한다 — 목록 레코드의 제목(글자·숫자만 남긴 앞 15자)이 본문에
   있어야 하고, 레코드가 없으면 bizinfo `pblancId`·smtech `ancmId`·KOCCA 사업번호(`3-26-D00011-111` → `326D00011111`). kstartup·nipa
   URL·공고번호는 본문에 식별자가 없어 대조하지 못한다 — 결과는 `ok` 가 아니라 `partial`. 컨테이너 없음·대조 실패·hyve 실패·HTTP 오류는
   `-r2` 로 한 번 다시 받고, 그래도면 `fail`.
2. 첨부 링크를 거른다 — 받을 것만 `raw/att/` 계획에 넣고, 나머지는 `download_status` 를 붙여 링크로 남긴다:
   `skipped_robots`(robots 불허 — K-Startup `/afile` 전부, bizinfo `/uploads`) · `skipped_unverified`(허용 호스트 밖·KOCCA 팝업2 pms.kocca.kr) ·
   `failed`(KOCCA 팝업1 을 읽지 못함 — 첨부 유무 불명). KOCCA 는 팝업1(`noticeFilePop.do`)을 먼저 받는다.
3. 받은 첨부를 **바이트로** 검사한다(`attach_download.verify_attachment`): 빈 파일·50MiB 이상(itda-hyve 상한 — 잘림)·
   HTML 시작(오류·차단 페이지)·확장자와 매직 바이트 불일치(PDF·OLE(hwp/doc/xls/ppt)·ZIP(hwpx/docx/xlsx/pptx/zip)·이미지)·
   잘림(PDF `%%EOF` 없음·ZIP 중앙 디렉터리 끝 없음·OLE 는 머리의 섹터 크기·DIFAT 가 가리키는 FAT 섹터를 읽어 FAT 가 쓰는 마지막 섹터가
   파일 밖·JPEG `FFD9`·PNG `IEND`·GIF `3B` 없음)은 `failed`, 통과는 `ok` + `sha256`·`size`. 검사 규칙이 없는 확장자(`bin`·`txt` 등)는
   `unverified_format` — v3 을 찍지 않는다.
4. 본문을 추출해 해시하고 `details/<source>-<id>.txt` 를 쓴다(첫 줄 URL, `CONTENT_HASH:`·`HASH_VERSION:`·`ATTACHMENTS:` 머리). 목록 레코드가
   있으면 `survey.jsonl` 에 병합한다(원자적 교체) — 못 찾으면 `fail`. 레코드가 없는 대상은 `merged: false`(경고).

모자라면 exit 1 `{"status": "incomplete", "pending": {"<source>:<id>": n}, "next_call_count", "plan_files", …}`.
다 모이면 `{"status": "ok|partial|blocked", "results": [{"target", "status", "details"?, "hash_version"?, "attachments"?: {download_status: 개수}, "merged"?, "reason"?, "warnings"?}]}`.

결과 `status`: `ok`(첨부 전부 `ok` — 첨부가 있으면 hash v3, 없으면 v2) · `partial`(첨부 일부 미검증·형식 미확인 — v2, `attachments_complete: false`,
또는 목록 레코드가 없어 본문이 그 공고인지 대조하지 못함) · `fail`(본문 컨테이너 없음·그 공고가 아님·다시 받아도 오류·받지 못함·회전 상한) · `manual`.

## 5. exit 계약

| code | 뜻 |
|---|---|
| **0** | 전부 끝났고 요청한 것을 다 했다(목록: 모든 소스 `ok`/`inactive`, 상세: 모든 대상 `ok`) |
| **1** | 더 받을 것이 있다(`incomplete`) — 또는 인자·입력 오류(`status: error`, `error: args|input`) |
| **2** | partial — 커버리지 불완전(목록: 1쪽 0건·1쪽을 받지 못함·쪽 상한·회전 상한·받지 못한 쪽·다시 받아도 어긋남·읽지 못한 행·구조 변경 / 상세: 첨부 미검증·형식 미확인·레코드 없이 대조 못 함·상세 실패) |
| **3** | 차단 — 우회하지 않고 수동 확인으로 전환 |

**호출자 규율**: exit 2 를 성공으로 취급하지 않는다. 보고서에는 반드시 커버리지 한계를 고지한다.

## 6. jsonl 레코드 스키마

한 줄 = 공고 1건(JSON). `survey_diff.py` 가 두 형태를 정규화한다.

### bizinfo · nipa · smtech

| 필드 | 설명 |
|---|---|
| `source`, `id` | 소스와 소스 내 식별자(`PBLN_…` · 숫자 · smtech `ancmId-dtlAncmSn` · IRIS 행 `iris-<해시 12자>`) |
| `title`, `field`, `org` | 공고명 · 지원분야(smtech 는 사업명) · 소관/수행기관 |
| `apply_start`, `apply_end`, `reg_date` | `YYYY-MM-DD`(파싱 불가 시 원문) |
| `url` | 상세 URL(smtech 는 목록이 준 쿼리 전체, IRIS 행은 IRIS 홈페이지) |
| `system`, `recruit_status` | smtech 만 — `SMTECH`·`IRIS`, 목록의 상태 표시(접수중 등) |
| `detail` | IRIS 행만 `"iris"` — 상세를 받지 않는다 |

### kstartup

`pbancSn`(원본 키) · `source`="kstartup" · `id`(=`pbancSn`) · `category` · `dday` · `title` · `program` · `org` · `agency_type` · `start` · `deadline` ·
`apply_start`·`apply_end`(별칭) · `url`.

### `collect detail` 이 병합하는 필드

| 필드 | 설명 |
|---|---|
| `content_hash`, `hash_version` | `2` = 본문만, `3` = 본문 + 정렬된 첨부 sha256(첨부 전부 `ok` 일 때만) |
| `attachments` | `[{url, filename, download_status, download_reason?, local_path?, sha256?, size?}]` — `local_path` 는 회차 폴더 기준 `raw/att/…` |
| `attachments_complete` | 첨부 전부 `ok`(첨부 없음 포함) |

`download_status`: `ok` · `failed` · `unverified_format` · `skipped_robots` · `skipped_unverified`. (2.x 의 `blocked_redirect` 는 3.0.0 이 내지 않는다.)

## 7. `run_manifest.json` (schema v1)

목록 판정이 끝날 때 `survey.jsonl` 과 같은 폴더에 원자적으로 쓴다. 커버리지 판정은 이 파일을 읽는다. 같은 소스의 기존 run 은
새 run 으로 교체된다. 다른 소스 run 은 그 소스의 데이터가 방금 쓴 jsonl 에 실재할 때만 보존된다(0건이라 jsonl 을 쓰지 않은 런은 대조하지 않는다).

```json
{"manifest_schema_version": 1, "generated_at": "2026-09-30T16:50:00+09:00",
 "runs": [{"source": "kstartup", "status": "ok", "exit_code": 0, "pages_fetched": 12, "collected": 176,
           "stop_reason": "last-page", "cutoff": null, "errors": [], "duplicates": 0,
           "coverage": "exhaustive", "last_page": 12}]}
```

- `status` ∈ `ok`·`partial`·`manual`·`inactive`. `ok`·`inactive` 는 `exit_code` 0, `partial` 2, `manual` 3(모순 시 작성 거부).
- `stop_reason`: `last-page` · `closed-streak` · `page-cap` · `round-cap`(회전 상한 — partial) · `blocked` · `empty`(1쪽 0건 — partial) · `smoke` · `parse-failure`(1쪽을 못 읽음) · `fetch-failure`(1쪽을 받지 못함) · `robots-disallowed`.
- `coverage`: `exhaustive`(분모까지 다 받음) · `window`(최근 구간 — SMTECH 멈춤·쪽 상한·회전 상한·smoke) · `none`(KOCCA·1쪽 0건·1쪽을 못 받거나 못 읽음·차단).
- `reported_total`(bizinfo·nipa 1쪽 첫 행 번호) · `duplicates`(쪽 사이 같은 id) · `counted`(정상 계수 — `closed_rows`·`iris_rows`) ·
  `dropped`(결손 — `no_link`·`parse_skip`, 있으면 그 run 은 partial) — 있을 때만.
- **개인정보·검색어·공고 본문은 들어가지 않는다** — 카운트·상태·사유만.
- 손상되거나 스키마 버전이 다른 매니페스트는 `run_manifest.json.corrupt-<ts>` 로 보존한 뒤 새로 시작한다(`recovered_from_corrupt`).

## 8. `survey_diff.py` — 회차 비교

```
python3 survey_diff.py <old_dir> <new_dir> [--out FILE] [--old-profile P --new-profile P] [--assume-complete]
```

분류: `new` · `changed` · `gone` · `needs_rehash` · `unchanged`. 비교 필드는 `title` · `apply_start` · `apply_end` · `status` · `content_hash`.
GONE(소멸)은 `--out` 이 아니라 같은 폴더의 `gone_<out 파일명>` 에 쓴다.
**GONE 은 현재 회차가 그 소스를 `status=ok`·`exit_code=0`·`coverage=exhaustive` 로 받았을 때만** 판정한다 — partial·window 회차에서
사라진 것처럼 보이는 항목은 억제된다. 2.x 회차의 SMTECH 레코드(`id` 가 `ancmId` 뿐)는 url 의 `dtlAncmSn` 으로 새 식별자에 맞춘다.
