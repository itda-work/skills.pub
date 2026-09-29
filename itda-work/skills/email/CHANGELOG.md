# Changelog — itda-email

## [0.38.1] — 2026-09-29 (itda-work/skills#44)

### Changed

- itda-hyve 설치·업데이트 안내의 받는 곳을 `https://itda.work/hyve/` 하나로 바꿨다(GitHub 릴리스 페이지 링크 제거, itda-work/skills#44). SKILL.md·GUIDE.md.
- `references/netbridge.md` 사본을 정본과 동기화 — 받는 곳 한 줄이 `https://itda.work/hyve/` 로 바뀌었다.

## [0.38.0] — 2026-09-28 (#34)

### Added

- 보낸·임시·휴지통·스팸 메일함을 이름 대신 특수 용도(`"\\Sent"`·`"\\Drafts"`·`"\\Trash"`·`"\\Junk"`)로 지목하는 안내(itda-hyve 0.9.2).
  "보낸메일함 보여줘" 에서 `imap_list_mailboxes` 한 번이 줄어든다. 옛 판(`invalid_input`·`not_found`)이면 이름 확인으로 돌아가고 업데이트를 안내한다.
  최소 판은 0.9.0 그대로 — 이 기능 밖의 계약은 바뀌지 않았다.
- `references/netbridge.md` 사본 동기화(읽기 도구 `save_as`·특수 용도 메일함 절).

## [0.37.0] — 2026-09-28 (#20)

### Removed

- 남아 있던 옛 IMAP 직접 접속 읽기 스크립트 9개(`check_env`·`check_connection`·`read_email`·`list_folders`·`reply_context`·`email_providers`·`email_state`·`email_imap_utf7`·`diagnose_smtp`) — `.env`·환경변수의 계정 비밀번호로 메일 서버에 직접 붙던 경로다. 마지막 사용처였던 `inbox-triager` 에이전트를 itda-hyve 메일 읽기 도구로 옮겨 실행 경로가 0이 됐다. 이 스킬 폴더에 `scripts/` 가 없다.
- 그 스크립트의 테스트 23개 파일(435건)·`imap_mock.py`·`fixtures/*.eml` 3개, email 안의 `env_loader` 사본 테스트(`test_env_loader.py` — 정본은 `shared/tests` 가 지킨다).
- 삭제 전 참조 조사: https://github.com/itda-work/skills/issues/20#issuecomment-5863481713

### Added

- `tests/test_inbox_triager_agent.py` — `inbox-triager` 의 `tools` 가 itda-hyve 메일 읽기 도구 4개(Cowork·Claude Code 이름)+`ToolSearch` 와 정확히 같고(셸·파일 읽기·`smtp_send`·`imap_save_attachment` 없음), 본문이 옛 스크립트·`.env`·환경변수를 실행 경로로 지목하지 않으며, 이 스킬에 `scripts/` 가 없음을 고정한다.

## [0.36.0] — 2026-09-28 (#19)

### Removed

- 옛 IMAP/SMTP 직접 접속 스크립트 17개 — 발송·초안·폴더 조작 계열(`send_email`·`send_outbox`·`send_draft`·`save_draft`·`read_draft`·`list_drafts`·`delete_draft`·`_draft_imap`·`email_compose`·`attachment_validator`·`flag_email`·`mark_spam`·`move_email`·`trash_email`·`manage_folder`·`_imap_common`)과 `thread_status`(morning-brief 0.3.0 이 itda-hyve 로 옮겨 사용처 없음). 이 스킬 본문은 itda-hyve 도구만 쓰고, 저장소 어디에서도 실행 경로가 아니었다. 관련 테스트 21개 파일 삭제, 섞인 4개 파일은 해당 케이스만 걷어냈다(738 → 435건).
- 삭제 전 참조 조사: https://github.com/itda-work/skills/issues/19#issuecomment-5863283032

### Kept

- 읽기 경로 9개(`check_env`·`check_connection`·`read_email`·`list_folders`·`reply_context` + import 폐포 `email_providers`·`email_state`·`email_imap_utf7`, 그리고 `check_connection` 오류 안내가 가리키는 `diagnose_smtp`) — 플러그인 에이전트 `inbox-triager` 가 아직 이 스크립트를 실행한다. 에이전트를 itda-hyve 로 옮기면 함께 지운다(후속).

## [0.35.2] — 2026-09-27 (#12)

### Changed

- 첨부 읽기 안내를 문서 스킬 계약과 맞췄다 — HWP·HWPX 는 `itda-doc:hwpx` 읽기 경로(병합·중첩 표·글상자 보존, 바이너리 `.hwp` 포함),
  스캔 쪽이 있는 PDF 는 `itda-doc:pdf-context-refinery` 쪽별 판정. 그 스킬이 없거나 못 읽은 쪽이 있으면 요약에 그 사실을 적는다(읽은 척 금지).

## [0.35.1] — 2026-09-27

### Changed

- 설치 판정을 서버 이름 기준으로 — 도구 목록에 이름에 `itda-hyve__` 가 든 도구(Cowork `mcp__remote-devices__itda-hyve__*`, Claude Code `mcp__itda-hyve__*`)가 없을 때만 설치·업데이트 안내. 앞 문구는 Cowork 접두어만 조건으로 삼아 Claude Code 에 연결한 사용자에게도 재설치를 안내하게 했다(12.0.0 공개 전 리뷰 M1). 금지는 "다른 서버의 도구·내장 fetch" 로 한정. 도구 표 머리에 Claude Code 이름 병기.
- 옛 서버 이름 안내 제거 — 개명 전 이름의 도구를 지목하던 분기를 "도구 목록에 itda-hyve 도구가 없으면(미설치·미연결·0.9.0 보다 옛 판) 0.9.0 이상 설치·업데이트와 연결을 안내하고 멈춘다" 로 합쳤다. compatibility 의 옛 이름 병기도 뺐다. `references/netbridge.md` 사본 동기화.

## [0.35.0] — 2026-09-25 (itda-work/itda-hyve#6)

> **릴리스**: skills **11.0.0**(`skills-v11.0.0`, 첫 공개 저장소 `itda-work/skills.pub`)에 싣는다.
> 요구: **itda-hyve 0.9.0 이상** — 받는 곳 https://github.com/itda-work/itda-hyve.pub/releases/latest
> 도구 이름 접두어가 `mcp__remote-devices__itda-butler__*` → `…itda-hyve__*` 로 바뀌어, 0.8.x(itda-butler) 서버와 이 버전은 서로 동작하지 않는다.
> 모델이 막을 수 있는 경계가 아니라 배포 순서로 보장한다 — 위 주소에 itda-hyve 0.9.0 설치본이 올라온 것을 확인한 뒤에 `skills-v11.0.0` 태그를 단다.

### Changed

- MCP 서버 이름 `itda-butler` → `itda-hyve`(0.9.0). `allowed-tools`·도구 지목을 `mcp__remote-devices__itda-hyve__*` 로, 안내 문구를 itda-hyve 로 바꾸고 compatibility 에 0.9.0 이상을 적었다. `references/netbridge.md` 사본 동기화.
- 개명 전 이름 도구만 보일 때 업데이트 안내 분기, 첨부 거부 조건(숨김 이름·심볼릭 링크·특수 파일)·확인 토큰 무효 조건(`attachments_dir` 변경·미리보기 뒤 파일 수정), 저장 폴더 거부 범위를 정본대로. GUIDE 의 기본 저장 폴더 안내(옮겨 온 사용자는 예전 폴더)·“계정이 없다” 원인(계정은 바로 반영됨)을 고침.
- `imap_save_attachment.save_as` 를 비웠을 때 같은 이름 파일이 있으면 서버가 ` (1)` 식 번호를 붙인다는 것을 인자 표에 적음.
- itda-hyve 가 없을 때의 설치 안내에 받는 곳(https://github.com/itda-work/itda-hyve.pub/releases/latest)을 SKILL·GUIDE 에 적었다. `references/netbridge.md` 사본 동기화(정본에 받는 곳 한 줄).

## [0.34.0] — 2026-09-25 (이슈 #1709)

### Added

- **받은 첨부 저장·읽기 — itda-butler `imap_save_attachment`(butler 0.7.1).** `allowed-tools`·도구 표에 추가하고 「계약 3 — 첨부는 파일로 받아 연다」 절을 신설했다. `save_dir` 에 연결 폴더의 호스트 경로를 넣고, `parts` 를 비우면 모든 첨부, 응답의 `saved[].saved_path` 를 샌드박스의 `$HOME/mnt/<폴더 이름>/<saved_path>` 로 열어 읽는다. 인자·응답은 butler `internal/tools/mailtool/save.go` 판독 기준.
- **요청 해석 규칙** — 「첨부를 받아서 (내용을) 요약/정리/분석」 의 대상은 **첨부 파일의 내용**이며 메일 본문 요약으로 대신하지 않는다. butler Cowork 실측(`docs/FIELD-TEST-cowork-attachment-2026-09-25.md`)에서 이 문장에 모델이 파일을 저장만 하고 메일 본문을 요약했고, 도구 응답의 `note` 로는 고쳐지지 않았다(1·3차 실패). 스킬 본문이 해석을 정하도록 옮겼다.
- 거부·경고 대응표: `blocked_type`(실행·스크립트 형식 — 우회 금지)·`too_large`(30MiB)·per-part `not_found`·`invalid_input`·`saved[].warning`(매크로 문서 — 매크로를 켜지 말라고 안내). 실패 표에도 `blocked_type`·`too_large` 추가.
- GUIDE.md 「받은 첨부를 받아서 읽기」 시나리오·문제 해결 항목.

### Changed

- `imap_fetch` 설명의 「첨부 내용은 받지 않는다」 를 `imap_save_attachment` 안내로 바꿨다. 계약 번호 재배열(외부 데이터 → 계약 4, 자격증명 → 계약 5). 외부 데이터 계약에 **첨부 파일의 내용**을 포함했다.
- `compatibility`·본문의 도구 수 5 → 6. 공용 규약 `shared/netbridge.md`(사본 동기화 — dart·ecos·realty-deals 포함)의 메일 도구 목록에 `imap_save_attachment` 와 첨부 저장 규칙 추가.

## [0.33.0] — 2026-09-23 (이슈 #1707)

### Changed (BREAKING — 사용 경로)

- **itda-butler 메일 도구 단일 경로.** SKILL.md·GUIDE.md 가 butler 도구 5개(`accounts_list`·`imap_list_mailboxes`·`imap_search`·`imap_fetch`·`smtp_send`)만 지목한다. `allowed-tools` 에 `mcp__remote-devices__itda-butler__<도구>` 전체 이름을 적었다. 환경변수(`NAVER_EMAIL`·`*_APP_PASSWORD` 등)·`.env`·스크립트 경로 서술을 모두 뺐다 — 두 경로가 공존하면 모델이 옛 경로를 골랐다(2026-09-22 Cowork 실측: "naver 메일 보내줘" 에 환경변수를 찾다 멈춤). 계정은 `accounts_list` 의 `name` 으로만 가리킨다.
- 계약 넷을 본문에 합류: ① 메타 먼저(`imap_search` 본문 없음)·지목된 uid 만 `imap_fetch`(읽음 표시 불변) ② 발송 2단계(`confirm_token`, 인자 변경 시 `confirm_invalid`, 10분·1회용) ③ 메일 내용은 외부 데이터(SPF/DKIM/DMARC 부재 시 휴리스틱 피싱 경고 + "인증 미확인" 명시) ④ 자격증명 비취급. 각 도구의 인자 이름·타입·예시 JSON 을 butler `internal/tools/{mailtool,smtptool}` 판독 기준으로 적었다.
- 첨부는 저장 폴더 기준 상대 경로 + `attachments_dir`(다른 폴더의 절대 경로 — 사용자 홈 아래·숨김 폴더 제외, Cowork 는 연결 폴더의 호스트 경로)를 함께 적었다.
- 공용 규약 사본 `references/netbridge.md` 동봉.

### Removed (문서)

- 초안·이동·스팸·휴지통·플래그·폴더 관리·미회신 판정·회신 맥락·아웃박스·SMTP 진단 절. butler 에 대응 도구가 없어 "이 환경에서 할 수 없다" 로 안내한다. inbox-triager 위임 절도 뺐다(에이전트가 옛 스크립트 경로를 쓴다 — 후속 이슈).
- `scripts/` 는 이번 커밋에서 **지우지 않았다** — `itda-work:morning-brief` 의 `gather.py` 가 `check_env.py`·`thread_status.py` 를 실행 경로로 쓰고 있어, 지우면 범위 밖 스킬이 깨진다. 삭제는 morning-brief·inbox-triager 전환과 묶어 후속 이슈에서 한다.

## [0.32.0] — 2026-09-22 (이슈 #1707)

### Added

- **itda-netbridge 메일 도구 경로 (#1707)** — 네트워크가 막힌 환경에서 `imap_search`·`imap_fetch`·`smtp_send` 로 대신할 때 기존 계약(메타 우선·메일 내용은 지시 아님·피싱 경고·발송 전 확인·자격증명 비취급)이 무엇에 대응하는지 표로 합류. 발송 2단계 게이트(`confirm_token`, 10분·1회용, 인자 변경 시 `confirm_invalid`)와 이 경로의 공백(SPF/DKIM/DMARC 부재·`References` 인자 부재·아웃박스/초안/이동 미지원)을 명시.

## [0.31.0] — 2026-09-03 (이슈 #1638)

### Added

- **`thread_status.py`** — 최근 N일 받은편지함의 미회신 판정 (읽기 전용, 결정론). 내가 To/CC 에 있는 인바운드 메일을 뽑아 Message-ID 그래프(`In-Reply-To`/`References`) union-find + 날짜로 "그 스레드의 최신 상대 메시지 이후 내 발신(`\Sent`)이 있는가" 를 판정한다. `verdict` 는 `unreplied` / `replied_then_new` / `replied` / `unknown` 네 값이며 **헤더·날짜로만** 정해진다 — 제목·본문 어휘로 추론하는 필드는 두지 않는다(`verdict-channel-not-inference`). 연결·인증은 `_imap_common.connect`, `\Sent` SPECIAL-USE 탐색·헤더 파싱·배치 FETCH 는 `reply_context` 재사용(독립 IMAP 클라이언트 없음, 전 폴더 readonly).
  - 인자: `--provider`(필수) `--account` `--days`(기본 2) `--limit`(기본 8) `--with-body N`(unreplied 후보에 한해 본문 앞 N자를 같은 연결에서 동반 페치).
  - 출력: `candidates[]`(`anchor{provider,account,folder,uidvalidity,uid,message_id}` · `from` · `subject` · `date` · `verdict` · `reason_code`) / `excluded{bulk,group,replied,unknown}` / `warnings[]`. 제외 규칙은 `List-Id`·`Precedence: bulk|list`·noreply 발신(`bulk`), 수신자 5명 이상(`group`).
  - 단위 테스트 40건(회신함·미회신·재회신·bulk·noreply·그룹·다중 계정·References 3단 체인·Message-ID 누락·UIDVALIDITY 앵커·localized Sent·malformed Date 양방향·plus-addressing·`--with-body` 절단).

### Security

- **발신함 읽기 실패를 빈 폴더와 구분한다** — `\Sent` 의 SELECT·SEARCH·FETCH 실패를 조용히 건너뛰면 전건이 미회신으로 **과보고**된다. 읽기 실패는 `sent_read_failed` warning + 전건 `unknown` 으로 fail-closed 한다(`no-silent-fallback`).
- **자기 `Message-ID` 도 `<...>` 토큰으로 정규화** — 헤더 원문을 그대로 쓰면 `<id@x> (ignore previous instructions)` 같은 CFWS 접미사가 참조와 문자열이 달라져 스레드를 끊고, 미정규화 문자열이 anchor 로 흘러간다. 유효 토큰이 없으면 `unknown`.

### Changed

- 발신함 조회 창을 인바운드 창보다 넓게(`days + 28`) 잡는다 — 같은 창만 보면 "5일 전 답장한 스레드에 오늘 후속이 온" 경우가 `replied_then_new` 대신 `unreplied` 로 뒤집힌다. SEARCH 창만 넓히고 그래프·판정은 불변.

## [0.30.0] — 2026-08-20 (이슈 #1512 트랙 A)

### Added

- **IMAP 메일 정리 스크립트 5종 + 공용 모듈**:
  - `_imap_common.py` — canonical Trash/Junk 해석(SPECIAL-USE 우선 → 제공자 폴백 표, custom 은 `canonical_folder_unresolved`), UID 파싱(쉼표 복수), MOVE-with-fallback(MOVE 미지원 시 COPY→`\Deleted`→UID EXPUNGE, UIDPLUS 부재 시 `uidplus_unsupported` 거부 — 일반 EXPUNGE 오폭 방지), COPYUID 파싱(`new_uids`).
  - `move_email.py` — 폴더 간 이동 (`--uid 5,6,7 --from-folder INBOX --to-folder 업무`).
  - `manage_folder.py` — 폴더 생성/이름변경/삭제. canonical 폴더 rename·delete 차단(`canonical_folder_protected`), 비어있지 않으면 `folder_not_empty`, `--force` 시 내용물 휴지통 이동 후 삭제.
  - `mark_spam.py` — 스팸 이동/해제(`--unmark` 는 INBOX 고정 복원). IMAP 이동만 수행 — 스팸필터 학습 미보장(`note` 필드 안내).
  - `trash_email.py` — 휴지통 이동/`--restore`/`--expunge`(영구 삭제, UIDPLUS 필수). `--dry-run` 은 대상 메타만 출력하며 IMAP 쓰기 명령 0회.
  - `flag_email.py` — `--set/--unset seen|flagged` (STORE ±FLAGS).
- SKILL.md: Mail Management 절, 파괴적 작업 실행 규칙(expunge 는 명시 요청 + dry-run 확인 후), Gmail 라벨 모델 한계, Trigger Keywords 확장.
- **CAPABILITY 판정을 살아있는 post-auth 명령으로** (라이브 실측 결함 2호 수정): imaplib 의 `.capabilities` 속성은 접속 시점(pre-auth) 캐시라 iCloud·Gmail 처럼 로그인 후에만 MOVE/UIDPLUS 를 광고하는 서버에서 빈 값 → `uidplus_unsupported` 오폭으로 이동 전체가 거부됐다. `capabilities()` 가 로그인 후 `CAPABILITY` 명령을 직접 발행해 판정하고 연결당 1회 캐시한다(명령 실패 시에만 속성 캐시 폴백).
- **미존재 UID 성공 위조 방지** (라이브 실측 결함 수정): 모든 조작 경로(move/spam/trash/restore/expunge/dry-run/flag)가 쓰기 명령 발행 전에 대상 UID 실재를 FETCH 로 검증하고, 하나라도 없으면 `uid_not_found`(detail 에 missing UID + 선택 폴더명)로 전체 거부한다. `fetch_meta` 는 실재 확인된 UID 만 반환(빈 메타 행 생성 금지) — 미존재 UID 에 대한 no-op STORE/EXPUNGE 가 `status:ok` 로 위조되던 결함을 차단.
- 단위 테스트 83건 추가(인코딩 왕복·MOVE 폴백·COPYUID 파싱·canonical 보호·folder_not_empty/--force·dry-run 무변경·UIDPLUS 거부·exit code) — 트랙 B(Go) 와 공유하는 계약(폴백 표·에러 키·응답 필드) 고정.

## [0.29.2] — 2026-07-26 (이슈 #1280·#1282)

### Changed

- `compatibility` 라벨을 `Claude Code & Cowork` 로 교체 (#1280).
- `.env` 위치 안내를 "작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트)" 로 일반화하고 셸 환경변수·`~/.claude/settings.json` 의 `env` 경로를 명시 (#1282).

## [0.29.1] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.28.0] — 2026-07-10 (이슈 #1018)

### Bug Fixes

- **`read_email.py` 기본 경로 UID SEARCH/FETCH 통일 — UID-only IMAP 서버(ecount) 호환**: `--since-last-run` 없는 기본 경로가 시퀀스 번호 `imap.search()`/`imap.fetch()`를 썼는데, ecount(wmbox3.ecount.com)처럼 UID 검색만 지원하는 서버는 이를 `NO [CANNOT] Search command must send messages with UID`로 거부한다. 모든 경로를 `UID SEARCH`/`UID FETCH`로 통일했다(스킬 내 다른 스크립트와 동일 패턴, 외부 사용자 실측으로 UID SEARCH 정상 동작 확인).
- **SEARCH/FETCH 실패 응답 오파싱 차단**: 응답 `typ`을 확인하지 않아 서버 `NO` 에러 텍스트(`b'must'`, `b'send'`, `b'UID'` …)가 메시지 ID로 파싱되고 후속 FETCH가 `Invalid parameter: U`로 깨졌다. 3곳 SEARCH + FETCH 전부 `typ='OK'` 검증(`_ensure_ok`) + SEARCH 결과 토큰 자릿수 검증을 추가해 실패를 에러 JSON으로 표면화한다(no-silent-fallback — 다른 검색으로 재시도하지 않음).

### BREAKING

- **`id` 필드가 sequence number → UID**: 기본 경로도 UID로 동작하므로 `id`는 `uid`와 동일한 값이 된다. sequence number는 세션 한정·휘발이라 재사용 불가였고(#692), 기존 소비자(`reply_context.py`·draft 도구 `--uid`)는 전부 UID 기반이라 실질 영향 없음.

### Tests

- `TestUidSearchHardening` 6종: ecount NO 응답 시나리오(에러 표면화 + FETCH 미호출), 비숫자 토큰 거부(통합·단위), 기본 경로 UID 명령 전용(`imap.search`/`imap.fetch` 미호출) + `id`==`uid`. `scripts/tests` `_FakeIMAP` 도 UID 인터페이스로 정합(시퀀스 `search()`/`seq_search` 제거 — 릴리즈 CI 에서 표면화된 후속). email 누적 610 passed(skip 0, tests/ + scripts/tests/).

## [0.27.0] — 2026-06-30 (이슈 #694)

### Performance

- **`reply_context.collect_related` 배치 FETCH — 순차 N회 왕복 제거**: 관련 메일(상대방 히스토리)을 모을 때 후보 UID를 **1건씩 순차 FETCH**하던 것을, 청크(≤500)당 **단일 `UID FETCH`**로 묶었다. self-target 실측(gmail): FETCH 왕복 **2095회 → 2회**, `reply_context` 소요 **150s+ → ~5s**(단일 연결). 응답은 메시지별로 분리 파싱(`_iter_fetch_messages`, prefix의 UID로 매핑). 의미·스코어링·토큰 0(IMAP IO) 불변.

### Bug Fixes

- **`collect_related` 보낸함 방향 교정 `FROM`→`TO`**: "상대 X와의 왕복"은 받은함=`FROM X`, 보낸함=`TO X`인데 기존엔 보낸함도 `FROM X`였다. 그래서 (a) 외부 X 회신 시 **내가 X에게 보낸 과거 메일이 관련 맥락에 0건**이었고, (b) self-target일 때 보낸함 전체가 잡혀 블로업했다. 실측: gmail 보낸함 후보 `FROM self` 2014 → `TO self` **168(12× 축소)**, 동시에 내가 보낸 답장이 관련 맥락에 정상 포함된다.

### Tests

- `_batched`·`_iter_fetch_messages`(배치 응답 메시지별 UID 분리·payload 비혼합) + fake-IMAP `collect_related`(폴더별 FROM/TO 방향·폴더당 FETCH 1회·스레드 dedup·target 없음). email 누적 605 passed / 배포형 격리 122 passed.

### Live Verification

- gmail self-target(uid 572470): `collect_related` FETCH 왕복 **2회**·**5.1s**·관련 **191건** 수집(status ok). 구버전 동일 케이스 150s+(#694 배경 실측, FROM self 2014건 순차).

## [0.26.0] — 2026-06-30 (이슈 #692)

### Bug Fixes

- **받은편지함 회신 워크플로 `id`↔`uid` 계약 결손 수정**: `read_email.py` 일반 모드(`--since-last-run` 없음)는 `imap.search()` 결과인 **sequence number**를 `id`로 냈는데, `reply_context.py`/`read_draft.py`/`send_draft.py`/`delete_draft.py`의 `--uid`는 **UID**를 요구한다. `id`를 그대로 `--uid`에 넘기면 UID와 어긋나 `target_not_found`(또는 오매칭) → 스레드 재구성이 끊기고 회신 워크플로가 본문 수동 파싱으로 폴백했다. 네이버처럼 큰 메일함에서 seq≠uid가 항상 성립해 재현됐다.

### New Features

- **`read_email.py` 출력에 `uid` 필드 상시 추가**: FETCH spec을 `(UID BODY.PEEK[...])`로 바꿔 envelope에서 안정 UID를 파싱(`_extract_uid_from_fetch`, 프리픽스만 신뢰 — 본문 `UID ...` 스푸핑 차단), 매 메시지에 노출한다. 회신·초안 조작은 이 `uid`를 쓴다. 기존 `id`(sequence number)는 표시·디버그용으로 유지(**하위호환**). 초안 워크플로(`list_drafts→*_draft`)가 이미 `uid` 필드로 정합이던 것과 동일 계약으로 통일.
- **`save_draft.py --in-reply-to`/`--references` 추가**: 회신을 임시보관함 초안으로 저장할 때도 스레딩 헤더를 주입해, 모바일·웹메일에서 발송 시 같은 대화로 묶인다. `build_mime_message`가 이미 지원하던 파라미터를 CLI·`save_draft()`까지 배관(`send_email.py`와 동일 계약). 미지정 시 헤더 없음(**하위호환**).
- **SKILL.md 회신 워크플로/검색 레시피 정합**: 대상 메일은 `read_email`의 `uid`로 식별(`id` 아님)하고, 받은편지함이 크면 `--search`로 좁히도록 명시. 출력 표에 `uid` 행 추가 + `id`는 `--uid` 비호환 경고. `save_draft` 회신 초안 예시 추가.

### Docs

- **GUIDE.md에 "받은 메일에 답장하기" 시나리오 신설**: 사용자용 가이드에 답장 워크플로가 통째로 빠져 있던 갭을 메움 — 답장 시 대화 맥락·관련 메일을 자동 수집하고, 임시보관함에 저장한 **회신 초안이 원래 대화에 묶인 채** 저장됨을 자연어로 설명(빠른 시작에 "이 메일에 답장해줘" 추가). 기존 임시보관함 절은 유지. GUIDE 규칙(SPEC-GUIDE-NO-SHELL-001) 준수 — CLI 노출 0(전체 61 GUIDE lint PASS).

### Tests

- `_extract_uid_from_fetch` 단위 4(프리픽스 파싱·부재·페이로드 스푸핑 무시·빈 입력) + 일반 모드 `uid` 노출·FETCH spec UID 요청 통합 2. `save_draft` 스레드 헤더 주입·미지정 하위호환 2. 기존 fetch-spec 정확매칭 2건을 `(UID BODY.PEEK[])`로 갱신(BODY.PEEK invariant 유지). email 누적 600 passed.

### Live Verification

- **naver**: 스레드 A→B→C self 발송 후 `reply_context --uid`가 해당 스레드만 격리 재구성(thread 3·decoy는 thread 제외/related 포함), seq(`id`)를 `--uid`로 오용 시 `target_not_found` 재현(버그 클래스 실증).
- **daum**·**google(gmail)**: `read_email` `uid` 노출 확인(daum 9/9, gmail 20/20, 모두 `id`≠`uid`). daum은 기존 메일로 `reply_context --uid` thread 3 재구성까지 확인.
- **nate**: 빌트인 provider 아님 → `custom` IMAP/SMTP 자격증명 필요(미설정)으로 후속.
- 별개 발견(비-#692): `reply_context.collect_related`가 발신자 `FROM` 히스토리를 1건씩 순차 fetch → 대용량 메일함(gmail Sent 2025건)에서 느림. 후속 이슈 후보.

## [0.25.0] — 2026-06-29

### New Features

- **`send_email.py --from-name` — From 헤더 발신자 표시 이름(display name)**: `--from-name "현우테크 김민수"` 지정 시 From 헤더가 `현우테크 김민수 <addr>` 형태(RFC 5322 `email.utils.formataddr`)로 발송돼, 수신자 메일함에 이메일 주소 대신 발신자 이름이 표시된다. 한국어 이름은 RFC 2047로 자동 인코딩(수신측 디코딩 복원). 미지정 시 기존처럼 계정 이메일 주소만 — **하위호환**(기존 동작·테스트 회귀 0). `send_email.py` 단독 적용(`email_compose`·`save_draft` 경로는 비목표). (#678)

### Tests

- 신규 단위 3개 (`test_send_email.py`): `--from-name` ASCII display name / 한국어 display name RFC 2047 복원 / 미지정 시 주소-only 하위호환. email 스킬 누적 117 passed / 0 failed.

## [0.24.1] — 2026-06-18

### Docs

- **GUIDE 빠른 시작 예시 교정 — 수신자에 실제 주소 명시**: 스킬은 이름→주소 해석(주소록 조회)이 없고 `send_email.py --to`가 실제 이메일 주소를 요구하므로, 이름만 적은 예시(`김아무 과장님에게 보내줘`)는 자기완결적이지 않았다. 자연어 맥락을 살리면서 실행 가능하도록 `김 과장(kim@example.com)에게 메일 보내줘` 형태로 교정(첨부 예시의 `김대리`도 동일 적용).
- **시간범위 예시 추가**: "새로 온 메일"(증분 — `--since-last-run` UID 커서, 지난 확인 이후)과 별개로, 고정 시간창 의도를 위한 `최근 24시간 안에 온 메일만 보여줘` 예시를 추가(IMAP `SINCE` 검색 근거). 기존 증분 예시는 더 정밀하므로 유지.

## [0.24.0] — 2026-06-02 (SPEC-EMAIL-REPLY-CONTEXT-001)

### New Features

- **`reply_context.py` 신규 — 회신용 컨텍스트 결정론 수집**: 대상 메일 1건(UID)을 주면 코드가 스레드 재구성(References 정/역참조, INBOX+Sent 교차) + 발신자 히스토리(FROM) + 결정론 스코어링·시간순·budget을 수행해 회신용 컨텍스트 묶음 JSON을 반환. **중복 내용 판단은 LLM 책임**(코드는 수집만). 영속 저장 없음, stdlib only.
  - 탐색(IMAP IO)은 토큰 0, Claude가 읽는 출력만 `--max-chars-total` budget으로 제한
  - HTML 본문은 `_strip_tags` 평문화로 토큰 절감 (raw HTML 태그가 budget 잠식 방지)
  - 출력: `target` / `thread`(시간순·평문 본문) / `related`(스코어·사유) / `reply_headers`(In-Reply-To·References) / `budget` / `stats`
- **`read_email.py` 스레딩 헤더 노출**: 출력에 `message_id`/`in_reply_to`/`references` 추가(메타조회·본문 모두). `_HEADER_FIELDS`에 MESSAGE-ID/IN-REPLY-TO/REFERENCES 페치 편입
- **`send_email.py` 회신 스레드 헤더**: `--in-reply-to`/`--references` 플래그 — 받는 클라이언트가 같은 대화로 묶도록 헤더 세팅(reply_context 출력 `reply_headers`와 연결). `email_compose.build_mime_message`도 동일 파라미터 지원(하위호환)

### Phase 0 라이브 검증 (네이버·iCloud 실계정)

- 스레드 역참조 `HEADER REFERENCES`/`IN-REPLY-TO` SEARCH: iCloud OK(hits 4/1), 네이버 문법 OK → **채택**
- 비ASCII(한국어) SUBJECT SEARCH: 양 서버 `BAD`(parse error) → 제목 IMAP 검색 폐기, 후보 내 로컬 계산
- FROM 발신자 히스토리: 양 서버 OK(hits 6/82) → 관련메일 주력
- Sent 폴더: `\Sent` SPECIAL-USE 플래그로 탐지(이름 추측 대신)

### Tests

- 신규 단위 25개 (`test_reply_context.py` 23: 정규화·스코어링·budget·정렬 / `test_email_compose.py` 2: 회신 헤더)
- 라이브: iCloud 실제 스레드(안미현 DART 대화 8건) INBOX+Sent 교차 재구성·평문화·`reply_headers` RFC 정합 확인
- 누적: 564 → 589 passed / 0 failed / 0 skipped

### Behavior Contracts

- `reply_context.py`는 영속 파일을 만들지 않는다 (수집 → stdout → 종료)
- 코드는 중복 dedup을 하지 않는다 — 시간순 묶음을 LLM에 넘겨 중복 판단 위임 (HTML·interleaved·편집된 인용은 코드 휴리스틱의 천장)
- read_email/send_email 변경은 하위호환 (신규 키·플래그 추가, 회귀 0)

## [0.23.0] — 2026-05-27 (SPEC-EMAIL-MULTIPART-001)

### Bug Fixes

- **multipart MIME 파싱 결함 4건 일괄 수정** (`read_email.py`): SPEC-EMAIL-ICLOUD-001 라이브 검증서 적발된 결함을 단일 SPEC으로 묶어 해결. iCloud/naver/google 3 provider 라이브 매트릭스로 종단 확인.
  - D-1 `_get_raw_body_text`: `Content-Disposition: attachment` 파트를 본문 후보에서 제외 — 첨부 텍스트가 `body`로 누출되던 결함 차단
  - D-2 entry build: `to`/`cc`/`bcc` 헤더 `email.utils.getaddresses` + `decode_header`로 파싱 — 기존엔 호출 자체 부재
  - D-3 `_extract_attachments` 신규 헬퍼: `attachments[]` 메타 빌드 (filename·content_type·size_bytes·content_id, RFC 2047 filename 디코딩)
  - D-4 multipart/alternative: HTML 본문 우선 정책 (`--prefer-text`로 text/plain 우선 opt-out)

### New Features

- **출력 스키마 확장**: `to`/`cc`/`bcc` = `[{"name","addr"}]` dict list, `attachments` = `[{...}]` (want_body 무관 항상 반환), `body_format` = 평탄한 top-level 키 (`"html"`/`"text"`/`""`)
- **`--prefer-text` 플래그**: multipart/alternative 메일에서 text/plain 우선 (기본은 HTML 우선)

### Tests

- 신규 단위 테스트 21개 (`test_multipart.py`): 합성 fixture(F-1 multipart/mixed, F-2 alternative, F-3 한글 헤더, F-4 한글 filename, F-5 inline+content_id, F-6 첨부만)로 AC-001~010 전수 검증
- 라이브 매트릭스 (AC-007): naver/google/icloud 3 provider × send(HTML+CC+첨부) → read 종단 통과, `to/cc/attachments/body_format/<h2> 마커` 모두 정상
- 누적: 452 → 473 passed / 0 failed / 0 skipped

### Behavior Contracts

- `attachments[]` 는 `--body` 무관 항상 반환 (메타라 토큰 비용 작음)
- multipart/alternative 본문 우선순위 = HTML > text/plain (변경 가능 `--prefer-text`)
- 단순 text 메일 (`is_multipart()=False`) 경로는 회귀 0 — 기존 동작 보장

## [0.22.0] — 2026-05-27 (SPEC-EMAIL-ICLOUD-001)

### New Features

- **iCloud Mail 프로바이더 추가 (`icloud`)**: Apple iCloud Mail 을
  `--provider icloud` 단축 경로로 송·수신. `imap.mail.me.com:993 SSL` +
  `smtp.mail.me.com:587 STARTTLS`. `@icloud.com`·`@me.com`·`@mac.com` 도메인 동일 처리.
- **환경변수**: `ICLOUD_EMAIL` / `ICLOUD_APP_PASSWORD`. 멀티 계정 suffix
  지원 (`ICLOUD_EMAIL_WORK` 등 기존 패턴 그대로). 앱 전용 비밀번호 필수
  (appleid.apple.com 2단계 인증 활성 상태에서 발급).
- **GUIDE.md "처음 설정하기"**: iCloud 앱 전용 비밀번호 발급 절차 추가.

### Behavior Contracts

- iCloud SMTP 는 처음부터 587 STARTTLS 직행 (465 시도 안 함). 응답
  `transport` 필드로 식별 가능 (`starttls_587`).

### Tests

- 신규 단위 테스트 35개: PROVIDERS 등록·`detect_providers` icloud 보고·멀티 계정
  suffix·잘못된 자격증명 시 `credentials_missing` 반환. 네트워크 mock
  강제(실 IMAP/SMTP 호출 0). 기존 406 + 신규 35 = 441 passed / 0 failed.

## [0.21.2] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.21.1] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.

## [0.21.0] — 2026-05-18 (SPEC-EMAIL-004 개정)

### Breaking Changes

- **`read_email.py` 기본 동작이 메타조회로 전환.** 이전: 기본으로 본문(1500자)까지 페치. 이후: `--body` 미지정 시 메타데이터(from/subject/date/reply-to/피싱신호)만 반환. 본문은 `--body` 또는 `--max-chars N`을 명시할 때만 페치. CLI 직접 소비자는 없고(개발자 테스트 전용) 스킬은 SKILL.md 라우팅으로 의도에 맞게 호출하므로 사용자 워크플로우 영향 없음.
- **메타조회 시 `body`/`total_chars`/`truncated` 키 자체를 생략.** 이전 `--headers-only`는 `body`에 빈 봉투(`===EMAIL_CONTENT_START===\n\n===END===`)+`total_chars=0`을 출력했으나, 본문을 안 받았으면 키가 없는 게 정직하고 메시지당 토큰도 절감. 키 부재 = "본문 미페치" 신호.

### Removed

- **`body_preview` 필드 완전 제거.** SPEC-EMAIL-004 §4.4에서 v0.13.0+ 제거 예정으로 deprecated된 필드(`body`의 500자 캡 중복본). 외부 소비자 0 확인 후 전 모드에서 삭제. 관련 내부 상수 `_BODY_PREVIEW_SANITIZE_LIMIT` 제거, `BODY_PREVIEW_LIMIT`→`HEADER_FIELD_LIMIT`(헤더 필드 sanitize 캡으로 의미 정정).

### New Features

- **`--body` 플래그 신설**: 메시지 본문 opt-in. `--max-chars N`은 `--body`를 함의(이 옵션만 줘도 본문 조회). 메타조회만 하면 5건 기준 약 **86% 토큰 절감** — 목록 brief·새 메일 확인·피싱 스캔의 기본 경로가 비용 최소 경로로 정렬됨.
- **SKILL.md Claude 라우팅 가이드 신설**: 의도(메타조회/본문읽기/전체본문)→플래그 매핑 표 + 모호 트리거 2단계(progressive disclosure) 패턴 명문화. 동작 규칙을 전 사용자 공유 SKILL.md에 고정.

### Improvements

- **SKILL.md 런타임 계약으로 순수화 (776→383줄, -50.6% / 33KB→19KB).** Setup(provider별 앱 비밀번호 발급 단계)·Migration·Troubleshooting 워크스루를 사용자용 GUIDE.md로 이전. SKILL.md엔 자격증명 변수명 표 + "누락 시 GUIDE 안내" 런타임 규칙만 잔존(온보딩 progressive disclosure). 모든 `vX.Y.Z` 버전스탬프 제거 — CHANGELOG가 변경이력 유일 정본. 진단 코드표는 `diagnose_smtp.py` 출력 해석용으로 압축 보존. 동작·계약 변경 0(문서 재배치).
- **GUIDE.md 보강**: "처음 설정하기"(provider별 온보딩, 사용자 톤)·"안 될 때"(증상별 해결) 추가.

### Deprecations

- **`--headers-only`**: 메타조회가 기본이 되어 no-op. 하위호환용으로만 수용하며, `--body`/`--max-chars`와 함께 와도 메타데이터-only를 강제(우선순위 보장).

## [0.20.0] — 2026-05-13 (SPEC-EMAIL-DRAFTS-001)

### New Features

- **IMAP Drafts 흐름 (REQ-DRAFTS-001~009)**: 사용자가 명시적으로 작성한 메일을 IMAP `Drafts` 폴더에 저장·검토·발송하는 워크플로우 추가. 네이버 메일·Gmail 모바일 앱·웹메일의 "임시보관함"과 자동 동기화됨.
- **`save_draft.py` 신규**: MIME 조립 후 IMAP `APPEND` to Drafts + `\Draft` 플래그 + `INTERNALDATE` 명시. APPENDUID(RFC 4315)로 UID 발급, 미지원 서버는 폴더 SELECT/SEARCH로 fallback. 첨부 파일은 기존 `attachment_validator`로 검증 후 `multipart/mixed`, HTML 본문은 `multipart/alternative`로 조립.
- **`list_drafts.py` 신규**: Drafts 폴더 SELECT 후 최근 N개(기본 20, `--limit`) 메시지의 UID·Subject·From·To·Date·Size를 INTERNALDATE 내림차순 JSON 배열로 출력. `--since YYYY-MM-DD` 필터 지원.
- **`read_draft.py` 신규**: UID로 본문(text/plain, text/html, 첨부 메타데이터) 조회. JSON 응답에 body_text, body_html, attachments 포함.
- **`send_draft.py` 신규**: UID FETCH → MIME 파싱 → SMTP 발송 → 성공 시 `UID STORE +FLAGS (\Deleted)` + `UID EXPUNGE`(UIDPLUS, 미지원 시 일반 EXPUNGE fallback). `--keep`(EXPUNGE 스킵), `--dry-run`(SMTP 호출 없이 파싱 결과만 출력) 옵션. Sent 폴더 처리는 기존 `send_email.py` 패턴 위임.
- **`delete_draft.py` 신규**: UID에 `\Deleted` 플래그 + EXPUNGE. exit 0 시 `{"status": "deleted", "uid": N, "expunged": true}`.
- **`send_email.py --save-as-draft` 플래그**: 기존 발송 흐름에서 SMTP 단계를 건너뛰고 Drafts에 저장. outbox 큐 fallback 비활성화. 응답에 UID 포함.
- **`email_compose.py` 신규 헬퍼**: MIME 조립 로직(EmailMessage 생성, 첨부 인코딩, 한글 헤더 UTF-8 처리)을 모듈화. `save_draft.py`와 `send_email.py`에서 공유.

### Behavior Contracts

- IMAP `APPEND`/`FETCH`/`STORE` 실패 시 **outbox fallback 없음** — drafts는 outbox와 의도가 다른 흐름. stderr에 분류 키(`auth_failed`/`network_error`/`server_rejected`/`quota_exceeded`/`unknown`) + 상세 메시지 + exit code 1.
- UID 미존재 시(`send_draft.py --uid 99999`) stderr `uid_not_found`, exit code 1.
- IMAP 연결은 try/finally 또는 contextmanager로 LOGOUT 보장.
- 모든 신규 스크립트는 `--provider naver|google|gmail|daum` 받음 (gmail은 google의 alias, `resolve_provider_name`이 정규화).
- 인증은 기존 `email_providers.PROVIDERS[name]['email_env']` / `['password_env']` + `env_loader.merged_env()` 패턴 그대로. CLI 인자·stdout·stderr에 자격증명 노출 금지.

### Tests

- 신규 84개 unit test 추가 (`test_save_draft.py`, `test_list_drafts.py`, `test_read_draft.py`, `test_send_draft.py`, `test_delete_draft.py`, `test_send_email_save_as_draft.py`, `test_email_compose.py`). `imaplib.IMAP4_SSL`/`smtplib.SMTP_SSL` 전부 mock.
- 전체 402 테스트 통과 (기존 318 + 신규 84).
- 신규 스크립트 라인 커버리지 평균 **85%** (`email_compose.py` 100%, `read_draft.py` 85%, `list_drafts.py` 83%, `send_draft.py` 83%, `delete_draft.py` 82%, `save_draft.py` 81%).

### Out of Scope (향후 SPEC에서 다룸)

- 로컬 파일시스템 초안 저장(`.eml`/`.html`/`.json`), Windows 탐색기 가시화·HTML 미리보기.
- IMAP Drafts ↔ 로컬 파일 양방향 동기화.
- `update_draft.py` (수정은 `delete_draft.py` → `save_draft.py` 흐름으로 대체).
- 초안 검색 기능.

## [0.19.1] — 2026-05-13

### Removed

- SKILL.md에서 `claude config set env.*` 안내 제거. Claude Code 전용 명령어로 Claude Cowork에서 동작하지 않음. CLAUDE.md 또는 `.env` 파일 사용을 권장하는 두 가지 방법만 남김 (Naver/Google/Daum 3개 섹션).

## [0.19.0] — 2026-05-13 (SPEC-EMAIL-RESILIENCE-001)

### New Features

- **TCP probe 사전 탐색 (REQ-004)**: SMTP 연결 전 `socket.create_connection`으로 465/587 포트 개방 여부를 3초 타임아웃으로 탐색. 양쪽 모두 차단된 경우 80초+ 대기 없이 즉시 아웃박스로 저장.
- **아웃박스 패턴 (REQ-004)**: SMTP 포트 차단 또는 양쪽 포트 모두 실패 시 RFC 822 EML + JSON 메타데이터를 `.itda-skills/email/outbox/` 에 저장. 응답 `{"status": "queued", "outbox_path": "...", "reason": "probe_blocked|send_failed_all_attempts"}`. 비밀번호 미포함(REQ-007).
- **`send_outbox.py` 신규 스크립트 (REQ-005)**: 아웃박스 큐 일괄 발송. `--dry-run`, `--limit N`, `--purge-on-success` 옵션. 성공한 메일은 `outbox/sent/`로 이동 또는 삭제. 자격증명은 `get_provider()`로 재로드(메타데이터에서 읽지 않음).
- **포트별 지수 백오프 (REQ-002)**: 각 포트 최대 2회 시도, 실패 후 1초·4초 대기(`_BACKOFF_SEQ = (1, 4)`). 마지막 시도 후에도 대기 적용(포트 전환 전 쿨다운 포함). 인증 에러는 재시도 제외.
- **복수 수신자 (REQ-003)**: `--to "a@x.com,b@x.com"` 쉼표 구분 지원. 빈 토큰 자동 제거. `msg["To"]` 헤더에는 원본 문자열 보존.
- **TLS 컨텍스트 명시적 전달 (REQ-001)**: `ssl.create_default_context()`를 `SMTP_SSL` 및 `starttls()` 양쪽에 명시적으로 전달.
- **`--skip-probe` 플래그**: TCP probe를 건너뛰고 바로 SMTP 시도. 이미 포트 개방이 확인된 환경에서 사용.

### Breaking Changes

- **양쪽 포트 실패 시 동작 변경**: 구 동작(`exit 1`, `error: "send_failed_both_ports"`) → 신 동작(`exit 0`, `status: "queued"`, `reason: "send_failed_all_attempts"`). 이메일이 유실되지 않고 아웃박스에 보존됨. `send_outbox.py`로 재전송 가능.

### Tests

- 신규 14개 unit test (`test_send_email_resilience.py`): probe 차단→아웃박스 / probe 1포트 개방→SMTP 진행 / --skip-probe / 아웃박스 메타데이터 비밀번호 미포함 / 디스크 쓰기 실패 graceful / --force-587 probe 스킵 / 465 retry backoff [1,4] / 양쪽 실패→아웃박스 / auth 에러 재시도 없음 / 다중 수신자 헤더 보존 / 빈 토큰 제거 / TLS context 465/587.
- 신규 5개 unit test (`test_send_outbox.py`): 빈 디렉토리 / dry-run / 성공→sent/ 이동 / 실패→파일 유지 / purge-on-success.
- `test_send_email_fallback.py` 업데이트: `test_both_ports_fail_returns_combined_detail` → `test_both_ports_fail_routes_to_outbox` (새 동작 반영). `_run()` 헬퍼에 `socket.create_connection` mock + `time.sleep` mock 추가.
- 전체 318 테스트 통과 (기존 283 + 신규 35).

### Verification

- `python3 -m pytest itda-work/skills/email/scripts/tests/ -v`: 318/318 passed
- `python3 -m py_compile send_email.py send_outbox.py`: OK
- outbox JSON 비밀번호 미포함: `test_outbox_metadata_no_password` 통과

## [0.18.0] — 2026-05-01

### New Features

- **`diagnose_smtp.py` 신규 스크립트**: SMTP 연결 실패의 root cause를 레이어별로 진단. DNS → TCP → SSL → SMTP banner → EHLO → AUTH 단계를 분리 측정하여 `dns_failure` / `egress_block_465` / `ssl_intercept_or_break` / `server_disconnect` / `credentials_invalid` 등 8개 진단 코드로 분류. baseline 비교 (google.com:443) 포함.
- **`send_email.py` 자동 fallback**: 465 SMTPS 연결이 network-level 에러(`SMTPServerDisconnected`, `ConnectionError`, `TimeoutError`, `OSError`)로 실패하면 자동으로 587 STARTTLS로 재시도. 응답 JSON에 `transport: "smtps_465" | "starttls_587_fallback"` 필드 추가. 인증 에러는 fallback 대상에서 제외 (587에서도 동일 실패).
- **에러 응답 hint 필드**: 연결 실패 시 응답 JSON에 `hint` 필드 추가하여 사용자에게 `diagnose_smtp.py` 실행을 안내.
- **`--force-587` 플래그**: 465를 건너뛰고 처음부터 587 STARTTLS 사용. 465가 항상 차단되는 환경(특정 corp/sandbox)에서 fallback 대기 시간(timeout 20초) 절약. 응답 `transport: "starttls_587_forced"`.

### Tests

- 신규 16개 unit test (`test_send_email_fallback.py`): default 465 success / 465→587 fallback (4개 트리거 케이스: SMTPServerDisconnected, ConnectionError, TimeoutError, OSError) / auth/recipient 에러는 fallback 대상 제외 / both ports fail 시 detail_465+detail_587 반환 / `--force-587` 정상/auth 실패/network 실패 / transport 필드 값 검증 / 정상 경로 stderr 무소음.

### Improvements

- **SKILL.md Troubleshooting 섹션 신설**: 8개 진단 코드별 해결 가이드 표 + FAQ 패턴 (Connection unexpectedly closed, Cowork 환경에서만 실패).

### Bug Fixes

- (없음 — 동작 변경 없는 추가 기능)

### Verification

- 정상 발송: `transport: "smtps_465"`
- 465 실패 시뮬: 자동 587 fallback 성공, `transport: "starttls_587_fallback"`
- 양쪽 실패: `error: "send_failed_both_ports"` + `detail_465`/`detail_587`/`hint` 동시 반환
- 단위 테스트 283/283 통과

---

## [0.17.0] — 2026-05-01

### Token Optimization (read_email.py)

`read_email.py` 응답 크기를 대폭 축소하기 위한 3가지 변경. 실제 NAVER 메일 5건 기준 측정.

#### Breaking Changes

- **`--max-chars` 기본값 변경**: `5000` → `1500`. 대부분의 메일은 1500자 이내에 핵심이 있고, 5000자는 토큰 낭비가 큼. 전체 본문이 필요하면 `--max-chars -1`.

#### New Features

- **`--headers-only` 플래그**: body fetch를 완전히 스킵하고 from/subject/date/reply-to/auth 헤더만 수신. 5건 기준 응답 19,717 B → 2,665 B (**-86%**). 메일 목록 brief, 피싱 경고 스캔, 새 메일 도착 확인에 적합.
- **FETCH 명령 변경**: `RFC822` → `BODY.PEEK[]` (전체) / `BODY.PEEK[HEADER.FIELDS (...)]` (`--headers-only`). 부가 효과로 **`\Seen` 플래그를 마킹하지 않음** — 이전에는 read_email 호출 시 메일이 자동 "읽음" 처리되던 부작용 제거.

#### Token Savings (실측)

| 모드 | 5건 응답 크기 | v0.16 대비 |
|------|---:|---:|
| v0.17 default (1500자 + BODY.PEEK) | 14,898 B | -24% |
| `--headers-only` | 2,665 B | -86% |
| `--headers-only --since-last-run` (재호출, 0건) | 140 B | **-99.3%** |

#### Migration

기존 5000자 본문이 필요하면 `--max-chars 5000` 명시. 변경 없이 사용하면 default 1500자가 적용됨.

---

## [0.16.0] — 2026-04-14 (SPEC-EMAIL-008)

### Breaking Changes

- `detect_providers()` return structure changed: each provider entry now includes
  an `accounts` array instead of flat `capabilities`/`email`/`missing` fields.
  External scripts that parse `check_env.py` output must be updated.
- PROVIDERS dict no longer has a top-level `"gmail"` key.
  Use `"google"` (canonical) or `PROVIDER_ALIASES["gmail"] == "google"`.

### New Features

- **Multi-account support**: All providers now support multiple accounts via
  `_{SUFFIX}` postfix on environment variables (e.g. `NAVER_EMAIL_1`, `NAVER_EMAIL_WORK`).
- **`--account` flag**: `send_email.py`, `read_email.py`, `list_folders.py`,
  `check_connection.py` now accept `--account {id}` to select a specific account.
- **Google naming (FR-01)**: `GOOGLE_EMAIL` / `GOOGLE_APP_PASSWORD` are now the
  primary environment variables for Gmail. `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD`
  remain as deprecated fallbacks (removed in v0.18.0).
- **`--provider google`**: New canonical provider name. `--provider gmail` continues
  to work as an alias.
- **`get_provider()` `account` parameter (FR-06)**: New `account=` keyword argument
  for explicit suffix selection. Returns `account_id` field in the result dict.
- **`detect_providers()` new schema (FR-08)**: Each entry now has `aliases`, `status`
  (aggregated), and `accounts` array.
- **Incomplete account detection (FR-11)**: Accounts with email but no password (or
  vice versa) are registered as `status: "incomplete"` with a `missing` list, without
  blocking other complete accounts.
- **state.json migration (FR-12)**: `load_state()` automatically migrates `gmail:`
  keys to `google:` in-memory; persisted on the next `save_state()` call.

### Deprecated

- `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` — use `GOOGLE_EMAIL` / `GOOGLE_APP_PASSWORD`.
  Deprecation warning is printed to stderr once per process.

### Fixed

- `check_env.py` output now consistently includes `accounts: []` for unconfigured providers.

---

## [0.15.0] — 2026-04-14 (SPEC-EMAIL-007)

- Incremental fetch with `--since-last-run` (IMAP UID cursor in `state.json`)
- `--reset-state` flag to drop incremental cursor
- Naver `LIST "" *` fix (imaplib RFC-compliant form)
- Korean folder Modified UTF-7 encoding fix

## [0.14.0]

- `list_folders.py` — IMAP LIST with message counts

## [0.13.0]

- Phishing signal detection (SPF/DKIM/DMARC, Reply-To mismatch)

## [0.12.0]

- Daum/Kakao provider support

## [0.11.0]

- Attachment support with RFC 2231 Korean filename encoding
