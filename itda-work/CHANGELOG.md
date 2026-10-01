# Changelog

이 플러그인의 주요 변경 사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/), 버전은 [SemVer](https://semver.org/)를 따릅니다.

## [4.0.0] - 2026-10-01

> 요구: **itda-hyve 0.10.4 이상**(exchange-rate·weather-here·morning-brief). itda-hyve 0.10.4 를 먼저 설치·업데이트한 뒤 이 판을 설치한다 — 0.10.3 이하는 응답 `final_url` 등에 시크릿이 되비치고 기본 User-Agent 에 제품명이 실린다.

### BREAKING

- **`exchange-rate` 0.11.0 — 요청은 itda-hyve, 스크립트는 `plan`·`show` 가공만** (itda-work/skills#46). 키 없는 서울외국환중개 조회를 itda-hyve 가 받는다. 휴일 폴백은 요청 날짜 앞 14일 창 한 번으로 스크립트가 정하고, 월평균은 요청한 달만 받는다. 실패는 stdout JSON(`status: "error"`)이다. 통화 목록을 사이트와 맞춰 58종으로, `위안`·`인민폐` 는 CNH 로.
- **`weather-here` 0.15.0 — 날씨도 itda-hyve** (itda-work/skills#46). 스크립트의 Open-Meteo 직접 호출과 직접 IP 조회를 지웠다. 위치는 itda-hyve `location`, 날씨는 itda-hyve `http_request` 로 받고 스크립트는 판독만 한다. `location` 이 실패하면 IP 서비스를 따로 부르지 않고 지역명을 묻는다. `--detail` 풍속이 km/h 를 m/s 로 표시하던 결함도 고쳤다.
- **`morning-brief` 0.12.4 — 요구 판 itda-hyve 0.10.4** — 0.10.1~0.10.3 은 `hyve_outdated` 로 멈춘다. 환율 절을 새 exchange-rate 흐름으로(옛 인자 호출이 없어져 환율 절이 늘 비던 결함), 날씨 예보를 늘 itda-hyve 로 받는다.

### Changed

- `calendar` 0.7.3 · `email` 0.38.3 · `time-audit` 0.3.3 — 공개된 적 없는 itda-hyve 판 표기(0.9.1~0.10.0)를 공개판 0.10.1 로 맞췄고 `references/netbridge.md` 사본을 정본과 동기화했다(`secret_missing` 은 그 소스 하나에 대한 멈춤, itda-work/skills#46).
- `work-plan` 0.14.1 — 스킬 카탈로그를 현재 공개 스킬로 다시 만들었다(제거한 스킬과 배포 보류한 `itda-web:web-reader` 가 빠졌다).

### Fixed

- **SKILL_DIR 확정 블록**(itda-work/skills#47) — 새 Cowork 배치(`/root/.claude/plugins/synced/…`, `CLAUDE_PLUGIN_ROOT` 없음)에서 빈 값을 내던 옛 블록을 바꿨다. 스킬을 불러올 때 받은 base directory 를 먼저 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾으며, 후보가 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다(PowerShell 블록도 같은 계약). `exchange-rate` · `morning-brief` · `stakeholder-map` 0.1.5 · `task-brief` 0.2.4 · `time-audit` · `weather-here` · `work-redesign` 0.3.2.

## [3.0.1] - 2026-09-29

### Changed

- itda-hyve 설치·업데이트 안내의 받는 곳을 `https://itda.work/hyve/` 하나로 바꿨다(GitHub 릴리스 페이지 링크 제거, itda-work/skills#44) — `calendar` 0.7.1 · `email` 0.38.1 · `morning-brief` 0.12.2(`gather.py` 의 `update_url` 포함) · `time-audit` 0.3.1 · `weather-here` 0.14.1 · `inbox-triager` 에이전트. 동작은 그대로다.

## [3.0.0] - 2026-09-28

> **릴리스**: skills **13.0.0**(`skills-v13.0.0`)에 싣는다.
> 요구: **itda-hyve 0.9.6 이상** — 받는 곳 https://github.com/itda-work/itda-hyve.pub/releases/latest (0.9.1~0.9.5 는 공개하지 않고 0.9.6 에 #9·#10·#12·#15·#17·#21·#22 를 함께 싣는다)
> morning-brief 는 0.9.6 의 `imap_search` `snippet_for`, 0.9.5 의 batch `account: "*"`·`imap_search` `include_snippet`, 0.9.4 의 batch `plan_file`·`imap_search` `bulk` 와 0.9.3 의 `batch`·`imap_fetch` `uids`·일정 참석자·`location` 을, time-audit 는 0.9.2 의 읽기 도구 `save_as`(응답을 연결 폴더에 직접 저장)를, inbox-triager 는 `\Sent` 와 0.9.1 의 `imap_search` 스레드 헤더(`message_id`·`in_reply_to`)를 쓴다.
> `save_as`·`batch`·`plan_file` 은 도구 입력 스키마·도구 목록에 드러나 스킬이 호출 전에 가를 수 있다(없으면 업데이트 안내하고 멈춘다). 그래도 배포 순서로 보장한다 — 위 주소에 itda-hyve 0.9.6 설치본이 올라온 것을 확인한 뒤에 `skills-v13.0.0` 태그를 단다.

### BREAKING

- **메일·일정 계정을 `.env`·환경변수로 읽던 경로가 없어졌다.** morning-brief(0.2.x 까지 형제 스크립트로 IMAP·CalDAV 직접 접속)·time-audit(calendar 스크립트 실행)·`inbox-triager` 에이전트(email 읽기 스크립트)가 itda-hyve 도구로 옮겨 갔고, calendar·email 의 옛 직접 접속 스크립트는 삭제됐다. 계정은 itda-hyve 설정 창의 "계정" 화면에 등록한다. itda-hyve 없이 `.env` 만으로 쓰던 사용자는 itda-hyve 0.9.6 이상을 설치해야 한다.
- **morning-brief·time-audit(itda-hyve 캘린더 소스)는 Cowork 에서 연결 폴더가 필요하다** — itda-hyve 가 응답을 그 폴더에 쓴다. `gather.py --plan`·`collect_events.py --plan` 은 `--save-dir <입력 폴더의 호스트 경로>` 없이는 `save_dir_required` 로 멈춘다(#34).

### Changed

- `morning-brief` 0.3.0 — 수집을 itda-hyve 경로로(`gather.py --plan`/`--input`). 형제 스크립트 subprocess·`.env` 자격증명·caldav 설치를 걷어냈고 candidates.json 계약·render·verify 는 그대로다. 미회신 판정은 itda-hyve 스레드 헤더(옛 판이면 `thread_headers_missing` 결손으로 페이지가 업데이트를 안내). 서버가 펼치지 않은 반복 일정을 회차로 전개한다(#18).
- `morning-brief` 0.4.0 — **itda-hyve 가 응답을 입력 폴더에 직접 쓴다**: `--plan` 이 모든 호출에 `save_dir`(새 인자 `--save-dir`)·`save_as`·`overwrite` 를 싣고 SKILL.md 의 "응답을 그대로 Write" 지시를 없앴다(Cowork 실측의 가장 큰 병목). 보낸편지함을 `mailbox: "\\Sent"` 로 받아 라운드 4 → 3(`imap_list_mailboxes` 바퀴 제거), `include_references` 끔(보낸편지함 30일·200통 유지 — 근거는 스킬 README). 날씨 위치를 itda-hyve `http_request` 로 받아 `weather_here.py --geo-input` 에 넘긴다(#33 방식). 최소 itda-hyve 0.9.2(#34).
- `calendar` 0.7.0 — 옛 CalDAV 직접 접속 `scripts/`·`requirements.txt`(caldav·icalendar)·`deps.json`·`tests/` 삭제. 설치할 파이썬 패키지가 없어졌다(#19).
- `email` 0.36.0 — 사용처 없는 옛 IMAP/SMTP 스크립트 17개(발송·초안·폴더 조작·`thread_status`)와 테스트 삭제. `inbox-triager` 에이전트가 실행하는 읽기 스크립트 9개는 남겼다(#19).
- `inbox-triager` 에이전트 — 받은편지함 트리아지를 itda-hyve `accounts_list`·`imap_list_mailboxes`·`imap_search`·`imap_fetch` 로 옮겼다. `tools` 를 그 4개와 `ToolSearch` 로 좁혀 셸·파일 읽기·발송·첨부 저장 도구가 없다 — 환경변수·`.env` 자격증명과 email 스크립트를 더는 쓰지 않는다. 분류 표·권장 액션만 반환하는 계약은 그대로다. 피싱은 보이는 신호로만 판정하고 "발신 인증 미확인" 을 붙이며, 답장 여부는 요청받았을 때 보낸 메일함의 `in_reply_to` 로 대조한다(#20).
- `email` 0.37.0 — 옛 IMAP 직접 접속 읽기 스크립트 9개와 테스트 삭제(#20). 스킬 폴더에 `scripts/` 가 없다.
- `time-audit` 0.2.0 — 네이버·아이클라우드·CalDAV 소스를 itda-hyve `calendar_events` 로 옮겼다(`scripts/collect_events.py`, `--plan`/`--input`). calendar 스킬의 옛 직접 접속 스크립트를 더는 부르지 않는다. 수집이 불완전하면 초안을 쓰지 않는다(#19).
- `time-audit` 0.3.0 — `calendar_events` 응답을 itda-hyve 가 입력 폴더에 직접 쓴다(`collect_events.py --plan --save-dir`, `save_as`). 최소 itda-hyve 0.9.2(#34).
- `email` 0.38.0 — 보낸·임시·휴지통·스팸 메일함을 특수 용도 이름(`"\\Sent"` 등, itda-hyve 0.9.2)으로 바로 지목하는 안내. 최소 판은 0.9.0 그대로(#34).
- `inbox-triager` 에이전트 — 스레드 맥락의 보낸 메일함을 `"\\Sent"` 로 받는다(메일함 목록 조회 생략). 최소 itda-hyve 0.9.2(#34).
- `weather-here` 0.13.0 — Cowork 에서 현재 위치를 itda-hyve `http_request`(ipapi.co·ipwho.is)로 받는다. 스크립트가 Cowork 작업 공간에서 돌면 직접 IP 조회(클라우드 IP — 샌프란시스코 실측)를 하지 않고 exit 3 으로 멈춘다. `--lat`/`--lon`·`--geo-input`·`--weather-request`/`--weather-input` 추가, 로컬 실행은 그대로(#33).
- `weather-here` 0.14.0 — 현재 위치를 itda-hyve 0.9.3 의 `location` 도구(OS 위치 서비스 → IP 서비스 6곳 합의)로 받는다. IP 한 곳(ipapi.co)은 대전 KT 회선을 성남으로 잡았다. 날씨 줄 첫머리가 출처를 드러낸다 — OS 위치는 "대전광역시 중구", IP 합의는 "(시·도 기준)", 합의 실패·IP 한 곳은 "(대략·IP 기준)". location 이 없는 0.9.0~0.9.2 는 `http_request` 경로 그대로(#37).
- `morning-brief` 0.5.0 — **새 구성**: 오늘 일정 전체(시간·장소·참석 인원) → 일정별 관련 메일(참석자·주최자 주소, 다음으로 제목 키워드 — 제목·보낸 사람·날짜·회신 여부) → 일정과 무관한 미회신 메일(제목·보낸 사람·요약). 목록·매칭·정렬은 `gather.py`, 모델은 요약 문장만(content·candidates schema 2). 지형·세 마디·두 목록·내일 일정·관련 사람 정보를 뺐다. 수집은 itda-hyve 0.9.3 `batch` 두세 번(①계정·위치 ②일정·받은/보낸 메일·날씨 예보 ③미회신 본문 `uids`), 날씨 위치는 `location`. 최소 itda-hyve 0.9.3(#38).
- `morning-brief` 0.6.0 — `gather.py --plan` 이 batch 인자를 입력 폴더의 `plan-<k>.json` 으로 쓰고 `{"plan_file": …}` 한 줄만 낸다. 모델은 그대로 batch 에 준다(호출 목록을 다시 출력하던 바퀴 사이 84초 제거). 대량 메일(itda-hyve 0.9.4 `imap_search` `bulk`·`bulk_reason`, 헤더 없는 것은 noreply 류 보낸 사람·제목 「(광고)」)을 미회신·요약에서 빼고 「뉴스레터·알림 N통」 한 줄(뉴스레터·자동 알림·광고 수)로 센다. 관련 메일에는 참석자·주최자 주소로 이어질 때만 붙고 "단체 발송" 으로 보인다. `bulk` 가 없는 응답은 보낸 사람·제목 규칙만(하위 호환). 최소 itda-hyve 0.9.4 — batch 스키마에 `plan_file` 이 없으면 업데이트 안내(#39).
- `morning-brief` 0.7.0 — **「미회신」 은 사람 메일만**: 표지 없는 자동 메일(로컬파트 어디에든 noreply·noreturn 류, 표시 이름 「발신전용」·「회신불가」)을 대량 발송으로 보고, 역할 주소(billing·receipt·order·alert·notice 등 — support·info·help 제외)·발송 서브도메인(notice.·email.·mail.·news. 등)은 최근 30일 보낸편지함에 없는 상대일 때만 대량 발송으로 본다. 미회신 뒤에 **「대량 발송 메일」 절**(종류 → 발신자 → 제목 목록, 모델 요약 없음 — candidates `email.bulk.groups`, 종류에 `billing` 추가). `--plan` 은 계획 파일을 fsync·재확인한 뒤에만 경로를 내고, `--input`·`--save-dir` 의 마지막 이름이 다르면 `save_dir_mismatch`(NFC 비교 — NFD 한글 폴더 대응)(#40).
- `morning-brief` 0.8.0 — **수집이 batch 한 번**: 계정 목록·위치·모든 계정의 오늘 일정·받은 메일(본문 앞부분 300자, `include_snippet`)·보낸 메일을 `account: "*"`(파일 이름 `{n}`)로 한꺼번에 받는다. 미회신 요약은 snippet 으로 쓰고 본문 바퀴를 없앴다(snippet 이 없는 메일만 예외로 `imap_fetch` `uids`). `location` 은 같은 batch 에 정밀(OS) 그대로 — 긴 대기는 위치 권한을 정하지 않은 첫 회차뿐이다(README D17). 날씨 예보는 weather-here 가 샌드박스에서 직접 받고 실패하면 `http_request` 한 번. 최소 itda-hyve 0.9.5(#40).
- `morning-brief` 0.9.0 — **대량 발송 메일을 메일 계정별로**: 「대량 발송 메일」 절이 계정(이름·주소·통수) 소절 → 종류 → 발신자 → 제목이다(발신자 상한은 계정마다, 메일 계정이 하나면 소절 머리 없이 예전 모양). 메일 계정이 둘 이상이면 관련 메일·미회신 줄에 계정 이름 배지. candidates `email.bulk` 가 `accounts[]` 로 바뀌었다(최상위 `groups` 제거) — verify 가 계정 합·계정 소절·배지를 대조한다(#41).
- `morning-brief` 0.10.0 — 받은 메일 본문 앞부분을 **사람 메일에만** 받는다(`imap_search` `snippet_for: "non_bulk"`, itda-hyve 0.9.6 — 대량 발송·noreply 메일은 건너뛴다). 서버가 건너뛴 메일(`snippet_skipped`)은 미회신 후보가 되지 않는다. 0.9.5 가 이 인자를 거부하면 페이지가 "0.9.6 이상으로 업데이트" 를 말한다. 최소 itda-hyve 0.9.6(itda-work/itda-hyve#22).
- `morning-brief` 0.11.0 — **보고서 스타일 4종**: 기본은 세로 시간축(`timeline` — 일정 길이에 비례한 블록, 1시간 이상 빈 시간, 관련 메일은 일정 옆), "보고서 형식으로"·"표로"·"인쇄용으로" 하면 `memo`(결재 메모)·`desk`(지표 띠·표)·`print`(A4 두 단)(`render.py --style`). 네 스타일은 내용이 같고 verify 를 모두 통과한다. 「일정별 관련 메일」 은 따로 절이 아니라 각 일정 곁에 붙는다. 라이트·다크·폰 너비·인쇄 CSS, 웹 폰트 없음(#42).
- `references/netbridge.md` 사본(email·calendar·morning-brief·time-audit·weather-here) — 정본에 읽기 도구 `save_as` 절과 특수 용도 메일함을 더했다(#34). `location` 절(#37), `batch`·`imap_fetch` `uids`·일정 참석자 절(#38), batch `plan_file`·`imap_search` `bulk` 절(#39).
- `email` 0.35.2 — 첨부 HWP·HWPX·스캔 PDF 읽기 안내를 문서 스킬(`itda-doc:hwpx`·`itda-doc:pdf-context-refinery`) 계약과 맞췄다. 못 읽은 쪽이 있으면 요약에 그 사실을 적는다(#12).
- `work-plan` 0.14.0 — 메일·캘린더 계정을 환경변수로 안내하지 않는다. ground check 가 `NAVER_EMAIL`·`NAVER_APP_PASSWORD`·`GOOGLE_*`·`DAUM_*` 를 허용 목록에서 빼고 "itda-hyve 계정 화면에 등록" 경고로 내려보내며, 메모 틀·GUIDE 예시를 계정 등록 절차로 바꿨다(#23).

## [2.0.2] - 2026-09-27

### Changed

- `work-plan` 0.13.4 — 발급 안내 표와 알려진 환경변수 목록에서 공개 팩 스킬이 쓰지 않는 증권사 키 3종(`KIS_APP_KEY`·`KIS_APP_SECRET`·`KIS_ACCOUNT_NO`)을 뺐다. 계획에 넣으면 이제 "알려진 목록에 없음" 으로 확인을 요청한다.

## [2.0.1] - 2026-09-27

### Changed

- `work-plan` 0.13.3 — 스킬 카탈로그에 공개 팩 스킬만 싣는다(비공개 `itda-egg`·`itda-stocks` 17행 제외, 97 → 80). 설치할 수 없는 스킬을 추천하지 않는다(12.0.0 리뷰 참고 항목).
- **itda-hyve 설치 판정을 서버 이름 기준으로** — `email`·`calendar` 본문과 `references/netbridge.md`: 이름에 `itda-hyve__` 가 든 도구(Cowork `mcp__remote-devices__itda-hyve__*`, Claude Code `mcp__itda-hyve__*`)가 없을 때만 설치 안내. Claude Code 에 연결한 사용자에게 재설치를 안내하던 문구를 바로잡았다(12.0.0 공개 전 리뷰 M1).
- `calendar` 0.6.2 — `calendar_delete` 가 `not_found` 면 이미 지워진 것으로 보고 다시 지우지 않고 사용자에게 알린다(Cowork 실측 2026-09-26, 이미 지운 일정 재삭제 시도).
- `weather-here` 0.12.6 — 외부로 나가는 User-Agent 에서 우리 신원(저장소 URL·조직·스킬 이름)을 뺐다(outbound-identity-leak) — `Mozilla/5.0 (compatible; weather-here-skill; +itda-skills)` → `Mozilla/5.0`.
- **옛 서버 이름 안내 제거** — `email` 0.35.1·`calendar` 0.6.1: 개명 전 이름의 도구를 지목하던 분기를 "itda-hyve 도구가 없으면(미설치·미연결·0.9.0 보다 옛 판) 0.9.0 이상 설치·업데이트 안내" 한 갈래로 합치고, compatibility·GUIDE 의 옛 이름 병기를 뺐다. `references/netbridge.md` 사본 동기화.
- `work-plan` 0.13.2 — 스킬 카탈로그 재생성(itda-org-taxhero `web-automation`·itda-doc 디자인 스킬 4종 제거 반영). 인수 테스트의 신세대 스킬 표본을 pptx-shrink 로 바꾸고, 제거한 스킬이 카탈로그·디렉토리에 없음을 단언하는 회귀를 더했다.

## [2.0.0] - 2026-09-25

> **릴리스**: skills **11.0.0**(`skills-v11.0.0`, 첫 공개 저장소 `itda-work/skills.pub`)에 싣는다.
> 요구: **itda-hyve 0.9.0 이상** — 받는 곳 https://github.com/itda-work/itda-hyve.pub/releases/latest
> 도구 이름 접두어가 `mcp__remote-devices__itda-butler__*` → `…itda-hyve__*` 로 바뀌어, 0.8.x(itda-butler) 서버와 이 버전은 서로 동작하지 않는다.
> 모델이 막을 수 있는 경계가 아니라 배포 순서로 보장한다 — 위 주소에 itda-hyve 0.9.0 설치본이 올라온 것을 확인한 뒤에 `skills-v11.0.0` 태그를 단다.

### BREAKING

- MCP 서버 이름 `itda-butler` → `itda-hyve` 로 도구 전체 이름이 바뀌었다(`mcp__remote-devices__itda-hyve__*`). email·calendar 는 itda-hyve 0.9.0 이상에서만 동작하고, itda-butler 0.8.x 사용자는 서버를 올려야 한다.

### Changed

- **MCP 서버 이름 `itda-butler` → `itda-hyve`(0.9.0, itda-work/itda-hyve#6)** — `email` 0.35.0·`calendar` 0.6.0: 도구 전체 이름 `mcp__remote-devices__itda-hyve__*`, 요구 버전 itda-hyve 0.9.0 이상, `references/netbridge.md` 사본 동기화.
- `work-find` 0.15.2 — 브라우저 자동화 예시에서 hyve `web_browse` 를 aside 로 (itda-work/itda-hyve#6).
- `work-plan` 0.13.1 — 스킬 카탈로그(`references/skill-catalog.md`) 재생성(빠진 스킬 8종 제외, itda-hyve 이름).
- itda-hyve 받는 곳(공개 내려받기 주소)을 email·calendar 의 SKILL·GUIDE 와 공용 규약 사본에 적었다.

## [1.0.0] - 2026-09-20

### Changed

- 팩 개명 `itda-work-coach` → **`itda-work`** (#1703).
- `itda-day-organize` 흡수 — calendar·email·morning-brief·exchange-rate·weather-here.

## [0.4.0] - 2026-09-06

### Changed

- **플러그인 재정비 2·3단계 (#1648)** — 구 `itda-coach` 개명(#1648 2단계). work-find·task-brief·work-proposal·work-pilot(구 itda-work) 편입 — 여정 ①~④가 한 팩에. 폐기 이름은 별칭 없이 제거(마스터 결정 2026-09-05). 게이트: check_plugin_registry · check_plugin_refs(신설) · 카탈로그 · publish dry-run.

## 2026-08-18 (이슈 #1511) — v0.3.0

### Removed
- `work-find` → **itda-work 팩으로 이동** (마스터 결정 2026-08-18 — 코치 팩 중 사용성이 높은 스킬을 주력 팩으로, #1319 편입의 원복). 여정 ①(탐색·구체화)은 크로스팩 연계로 유지 — README·GUIDE 표기 갱신.

## 2026-07-28 (이슈 #1319) — AI 활용 여정 코칭 팩으로 재편

### Added
- **itda-workmap 팩 흡수**: `work-redesign`·`time-audit`·`stakeholder-map` 편입 (workmap 팩 소멸 — 설치 사용자 0 시점 재편).
- **itda-work에서 편입**: `work-find`(탐색), `work-plan`(실행 계획) — 여정(탐색→구조화→계획→조각→굳히기)이 한 팩에 완결.
- `work-find` v0.15.0 — 모드 C(문제 구체화) 신설: 구 `problem-guide` 워크플로우(역질문 5축→재정의→Cowork/Code 두 갈래 가이드)를 흡수, 상세는 `references/problem-mode.md`.

### Removed
- `problem-guide` — work-find 모드 C로 병합 폐기.
- `analysis-guide` — itda-data `data-compass`와 pain 중복으로 폐기(공개·성숙 측 존치). 여정 핸드오프는 data-compass로 연결.

## 2026-07-26 (이슈 #1280·#1281·#1282·#1283)

### Changed

- **플랫폼 문서 정비 4축 일괄 (#1280·#1281·#1282·#1283)** — ① compatibility 라벨을 실태 정합(`Claude Code & Cowork` 표준, 역방향 라벨 교정) ② 설치 지시에서 `uv pip install --system`·`curl|sh` 제거(`python3 -m pip` 정본, 스크립트 안내 문자열·README 포함) ③ `.env` 안내를 양 플랫폼 병기(SKILL.md+GUIDE.md, 셸 env·`~/.claude/settings.json` env 명시) ④ `allowed-tools` 의 표준명 `Bash`/`WebFetch` 에 Cowork 실명(`mcp__workspace__bash`/`mcp__workspace__web_fetch`) 병기(73스킬) + brain `Task`→`Agent`, MCP 소비 4스킬은 필드 삭제(전체 상속). 세부 버전은 각 스킬 CHANGELOG 참조.

## [0.1.0] - 2026-06-21

### Added
- 플러그인 부트스트랩 (#558) — `itda-coach` 강의·온보딩 facilitation 스킬팩 신설.
- `problem-guide` — 막연한 문제 한 줄 → 역질문 5축 구체화 + Cowork/Code 2-track 해결 가이드. (강의 `문제해결-가이드` 승격, name 영문화)
- `analysis-guide` — 데이터 앞 라이브 분석 길잡이(5국면 루프). '다음엔 혼자 시작하는 법'을 남김. (강의 `분석-길잡이` 승격, name 영문화)
- `hour-slice` — 구체화된 문제를 ~1시간 내 가시적 결과가 나오는 한 조각으로 자르는 게이트(**신규**). 1시간 실현가능성 채점 + "오늘의 한 조각" 명세 + out-of-scope 출력.
- `miniskill-forge` — 직군 반복 작업을 재사용 미니스킬로 Cowork에서 도출(**신규**). 직군 예시 뱅크(`references/examples/` 9종) 동봉 — 강의 미니스킬 9 인스턴스를 파라메트릭 1종 + 예시로 접음.
- `GUIDE.md`(플러그인 시작 가이드, **신규**) — 비개발자 온보딩 1장: 복붙 첫 문장 + 상황별 예문 + 꼭 아는 용어 3개 풀이 + 안심형 보안 안내.

### Notes
- 강의 funnel: `problem-guide`(구체화) → `hour-slice`(1시간 조각) → `analysis-guide`(라이브 실행) / `miniskill-forge`(굳히기).
- itda-work의 `find-work`(주 단위 발굴)와 역할 분리 — 강의 입도(1시간)는 `hour-slice`가 담당.
- skill-creator 외부 적대 검수 반영(#558): PG↔AG 트리거 경계 명시, find-work funnel 핸드셰이크(itda-coach→find-work 역포인터), `miniskill-forge` 가짜 트리거 교체·"대상 특정 후" 전제 명시, 사무 공통 예시(`meeting-notes-summary`) 추가.
- 비개발자 3-페르소나 리뷰(마케터·감사/보안·입문자) 반영(#558): `GUIDE.md` 신설, README 평이화(encode/funnel/2-track 순화 + 한국어 별명), 보안 안내 안심형 전환(워크스페이스=내 폴더 정의·마스킹 체크리스트·BigQuery=사외 클라우드 경고), `analysis-guide` 마케팅 예시 추가, 감사 흐름 `pii-scan-mask` 선행 안내, Track B "몰라도 됨" 명시.

---

## 흡수 이력 — itda-day-organize

> #1703 재편으로 이 팩이 흡수되었다. 아래는 흡수 시점까지의 itda-day-organize 변경 이력이다.

## Changelog — itda-day-organize

## [0.1.0] - 2026-09-05

- **팩 신설 (#1648 2단계)** — 하루의 일정·메일·환경 신호(날씨·환율)를 조회·조작하고 morning-brief 가 한 장으로 조립한다. morning-brief 는 형제 스킬 스크립트를 부모 경로에서 직접 실행하므로 5종은 분리 불가.
- 포함 스킬: calendar, email, exchange-rate, morning-brief, weather-here.
