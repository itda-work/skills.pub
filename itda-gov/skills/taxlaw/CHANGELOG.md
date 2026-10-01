# Changelog — taxlaw

## [0.2.0] — 2026-10-01 (itda-work/skills#46)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다.
> 0.10.4 는 기본 User-Agent 도 범용 `Mozilla/5.0` 으로 바꾼다 — 이 스킬의 호출은 UA 헤더를 싣지 않으므로, 그 전 판에서는 국세법령정보시스템 서버 로그에 제품명이 남는다.

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 `plan`·`parse` 가공만** (itda-work/skills#45·#46, 규칙 `cowork-network-via-hyve`). `search_taxlaw.py`·`taxlaw_api.py` 는 사이트를 직접 부르지 않는다(`urllib.request` 제거).
  - 옛 `search_taxlaw.py "검색어" …` → `plan search "검색어" …` → itda-hyve `http_request` POST(save_as) → `parse search "검색어" … --input <search-….json>`.
  - 옛 `search_taxlaw.py detail --domain D --id X` → `plan detail --domain D --id X` → POST → `parse detail --domain D --id X --input <…>`. 법령은 호출 2개(`law-…`·`lawlist-…`), `--input` 두 개.
  - 식별은 두 층이다 — 저장 이름 `taxlaw/<종류>-<요청 본문 지문 12자>-<받은 날>.json` 을 인자로 다시 만든 본문의 지문과 대조하고, **응답이 되비친 요청 값**(검색 `schVcb`·`collection`·`startCount`·`viewCount`·`sortField`·`searchType`·`icldVcbCtl`·`exclVcbCtl`, 문서 `dcmDVO.ntstDcmId`, 상담 `reqStdId`, 법령 MR03 `ntstBscId`·`ntstBrkdId`·`ntstPmgNo`·MR01 `ntstSysClCd`·`ntstTlawClCd`)을 계획과 대조한다(다르면 `mismatch`, 되비침이 없으면 `site`). 이름은 plan 이 지었다는 것만 증명하고, 모델이 POST 본문을 옮겨 적다 바뀐 것은 되비침이 잡는다(W11 리뷰 M1 — 초판은 "응답에 검색어가 되비치지 않는다" 고 잘못 적고 이름만 봤다).
- **BREAKING — 법령 id 가 다섯 칸** — `<기본ID>:<내역ID>:<공포번호>:<체계구분>:<세법구분>`(검색 결과의 `SYS_CL_CD`·`TLAW_CL_CD` 를 더했다). 옛 세 칸 id 는 `args` 로 거부한다(검색을 다시 하면 새 id). 체계·세법구분 없는 행은 id 를 비운다.
- **BREAKING — 법령 목록 호출(MR01)을 사이트 모양으로** — 옛 `{"ntstBscId","ntstSysClCd"}` 를 법령 상세 화면(`Biz.doSearch`)이 보내는 `{"ntstSysClCd","ntstTlawClCd"}` 로(2026-10-01 aside 판독). 응답은 그 체계의 목록 전체이고(세법 `01/101` 31행, 세법구분 `ZZZ`(국세법 밖 일반 법령) 시행령 `02/ZZZ` 4,775행·4MB) 같은 `ntstBscId` 행에서 법령명을 읽는다. 법령명을 못 찾으면 비우고 `warnings` 로 알린다(옛판은 URL 까지 비웠다 — 이제 URL 은 id 의 구분코드로 늘 만든다).
- **BREAKING — 실패 출력** — 옛판은 stderr `오류: …` + exit 1(인자 오류 2)이었다. 이제 stdout 에 `{"status":"error","error":<종류>,"detail":…}`, exit 1(`args` 는 exit 2). 종류: `args`·`input`·`incomplete`·`mismatch`·`not_found`·`site`·`truncated`·`hyve`(`hyve_code` 동봉)·`http`.
- **BREAKING — 성공 JSON** — `--format json` 출력 첫 필드에 `status: "ok"`, 검색·법령 전문에 `warnings` 목록. 검색의 `missing` 블록은 그대로이고 `warnings` 에도 한 줄 싣는다.
- 요청 본문을 사이트 jQuery 와 **글자까지 같게** — `JSON.stringify`(공백 없음) + `encodeURIComponent`·공백 `+`. 옛판은 파이썬 기본 `json.dumps`(`", "`·`": "`)라 글자가 달랐다(2026-10-01 aside 에서 사이트 `Req.doAction` 의 XHR 본문을 캡처해 골든으로 고정).
- Referer 를 **그 XHR 을 보내는 화면**으로 — 옛판은 모든 호출에 검색 화면(`/is/USEISA001M.do`)을 실었다. 해석례·판례는 상세 팝업(`…?ntstDcmId=<id>&wnKey=`), 상담사례는 `/is/USEISA004P.do?reqStdId=<id>`, 법령은 버전 고정 상세 주소. 검색은 그대로.
- 브라우저 User-Agent 헤더를 싣지 않는다(itda-hyve 0.10.4 기본 `Mozilla/5.0` — 2026-10-01 범용 UA 로 10회 전부 200). 헤더는 `Content-Type`·`Accept`·`X-Requested-With`·`Referer` 넷.
- `--limit` 상한 100(대량 수집 용도가 아니다), 같은 도메인 두 번·빈 검색어는 `args`. 법령 id 는 다섯 칸 모두 있어야 한다(공포번호 포함 — 사이트는 늘 싣는다).
- **깊은 쪽 상한** — 검색엔진은 5,000번째 결과까지만 준다(2026-10-01 실측: "세법" 해석례 42,410건, startCount 1,001·2,001·3,001·4,001 은 10건씩, 5,001·9,901 은 0건 — 4,011~5,000 은 재지 않아 경계는 추정). `page × limit` 이 넘으면 `plan` 이 받기 전에 `args`, 분모 안인데 0건이면 `incomplete` 에 "다시 받아도 같습니다"(W11 리뷰 M2).
- 응답 목록 원소가 객체가 아니거나 문자열 칸에 다른 값이 오면 traceback 이 아니라 `site` JSON(판독 함수가 못 막은 형태도 마지막 그물이 `site` 로 — W11 리뷰 m1). `dcmDVO` 가 비면 `not_found`(m2).

### Added

- **전량 대조** — 도메인마다 기대 건수 `min(limit, 전체 − 시작 + 1)` 와 `resultCount`·받은 목록 길이를 대조해 다르면 `incomplete`(collection-completeness ①②). 요청하지 않은 컬렉션이 섞이면 `mismatch`, 마지막 쪽 너머는 0건 + `warnings`.
- **응답 식별 대조** — 해석례·판례 `dcmDVO.ntstDcmId`, 상담사례 `reqStdId`, 법령 MR03 `ntstBrkdId`·MR01 체계구분·세법구분이 요청과 다르면 `mismatch`. 문서 없음(SUCCESS 인 채 null)은 `not_found`.
- hyve 층 판독은 공용 `shared/hyve_input.py`(본문 그대로·응답 JSON 전체·실패 자리). 본문 JSON 이 도중에 끊기면 `truncated`, HTML 이면 `site`.
- Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 stdout·stderr 를 UTF-8 로 재설정(테스트로 고정). `references/netbridge.md` 동봉.
- 실측 픽스처 `law_list_sys01_101.json`(2026-10-01 itda-hyve — 세법 체계 법령 목록 31행).
- `references/taxlaw-api.md` — 전송 계약에 본문 인코딩·헤더·호출별 Referer 표, robots 재확인(2026-10-01 같은 내용), 재실측 절차를 robots 허용 화면 기준으로 고쳤다(검색 화면은 Disallow — 다시 떠야 하면 사용자 결정).

### Removed

- `tests/test_taxlaw_api.py`(urlopen 모킹) — `tests/test_parse_search.py`(판독)·`tests/test_taxlaw_flow.py`(계획·판독 흐름·골든)로 바꿨다.
## [0.1.4] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다.

## [0.1.3] - 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- `[책임 경계]`·“쓰지 않을 때” 표에서 세무 포털 자동화 행을 `itda-org-taxhero:web-automation` 대신 “현재 지원 스킬 없음” 으로 — 그 스킬은 hyve 앱 폐기로 실행 경로가 없다.

## [0.1.1] - 2026-09-01 (이슈 #1617)

### Changed

- **플러그인 이관 `itda-gov` → `itda-tax`** (마스터 결정). 스킬 내용·CLI·`SKILL_DIR` 규약은
  불변(플러그인 상대 경로 `skills/taxlaw`). stdout JSON compact 규율은 itda-gov 횡단 가드 밖으로
  나가므로 스킬 자체 가드(`tests/test_response_compact_guard.py`)로 유지.

## [0.1.0] - 2026-09-01 (이슈 #1616)

### Added

- 최초 릴리즈 — 국세법령정보시스템(taxlaw.nts.go.kr) 통합검색·전문 조회.
  - 통합검색(`ASEISA001MR01`): 법령·세법해석례·판례/결정례·상담사례·별표서식·전자도서관,
    문서번호 검색(`--docno`)·페이지네이션·정렬(정확도/등록일/생산일)·포함어/제외어·동의어.
  - 전문 조회: 세법해석례·판례(`ASIQTB002PR01` — 판결문·회신 전문 + 관련 법령),
    법령 조문(`ASISTA002MR03` — 조·항 단위), 상담사례(`ASEISA004MR01`).
  - 계약 근거는 2026-09-01 라이브 실측(`references/taxlaw-api.md` 박제). 쿠키·세션·키 불요,
    Python 표준 라이브러리만 사용.
- (릴리즈 전 적대 리뷰 R1 반영 — gpt-5.6-sol) stdout JSON compact 전환(#438 가드 정합) ·
  리터럴 `<개정 …>`·`<YYYY.MM.DD>` 표기 보존(태그 제거를 ASCII 시작 태그로 한정) ·
  요청 도메인 미수신 시 missing 명시 · `--article` 비대상 도메인 usage 에러 ·
  itda-gov justfile 테스트 러너 등재 · 픽스처 debugMsg 전 위치 소거(내부 인프라 정보) ·
  응답 close/타임아웃 typed 처리.
- (R2 반영 + 브라우저 10검색어 대조) 법령 제목을 사이트 표기 `법령명【조표시 조제목】` 로 정합 ·
  법령 링크를 사이트 라우팅(법령/통칙/집행/조약/훈령 5갈래)대로 생성 · 법령 전문 조회의 원문
  URL 을 렌더 필수 파라미터(`ntstTlawClCd`) + 버전 고정(`ntstBrkdId`)으로 생성하고 법령명을
  MR01 역해석으로 채움(전에는 빈 화면 URL·빈 법령명) · 텍스트 출력에 원문 URL 누락 수정 ·
  조/항·호/집행/훈령/통칙 실측 픽스처 추가.
- (R2 최종 반영) 공개 픽스처 위생 — 라이브 세션 키(wnKey UUID)·운영자 계정/조직 식별자를
  사이트 자체 익명화 형식으로 소거하고 `test_fixture_hygiene.py` 가드(UUID·debugMsg·내부
  IP·운영자 식별자 0, 뮤테이션 자기검증 포함) 신설 · `<!DOCTYPE>`/조건부 주석 선언 제거 ·
  조제목이 조표시로 시작할 때 제목 중복 방지 · references actionId 표 현행화.
- (R3 CONDITIONAL_LGTM 잔여 P2) 통칙 요약처럼 `&lt;p&gt;` 로 이중 인코딩된 마크업이 화면에
  리터럴 `<p>` 로 남던 것을 unescape 후 ASCII 태그 재제거로 정리(`<개정 …>` 보존 양립).
