# Changelog — court-auction

이 스킬의 주요 변경 사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)를 따릅니다.

## [0.2.0] — 2026-10-01 (itda-work/skills#46)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다.
> 0.10.4 는 기본 User-Agent 도 범용 `Mozilla/5.0` 으로 바꾼다 — 이 스킬의 호출은 UA 헤더를 싣지 않으므로, 그 전 판에서는 법원경매 서버 로그에 제품명이 남는다.

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 `plan`·`collect` 가공만** (규칙 `cowork-network-via-hyve`). `main.py` 는 사이트를 직접 부르지 않는다.
  옛 하위 명령(`codes courts`·`notices`·`notice-detail`·`case`·`search`)은 `plan <종류>` → itda-hyve `http_request`(하나씩 — 전부 POST 라 batch 불가) →
  `collect --run-dir R --input <save_as 파일>` 로 바뀌었다. `codes bid-types|usages|regions`(로컬 표)는 그대로다.
- **BREAKING — 회차 폴더** — `plan` 은 `--run-dir`(스크립트가 보는 경로)·`--save-dir`(itda-hyve 가 쓸 호스트 절대 경로 — `/Users/…`·`C:\Users\…`·`\\서버\…`)가 필수다.
  회차 상태 `court-auction-state.json` 에 호출 수·계획한 질의를 적는다. 저장 이름 `court-auction/<종류>-….json` 이 `collect` 의 식별 계약이다.
- **BREAKING — 세션 호출 예산이 회차 단위로** — 옛 `--max-calls`(프로세스당 10)·`--min-delay`(2초 대기)·`--timeout` 을 지웠다. 호출 상한은 회차당 10회
  (첫 `plan` 의 `--max-calls` 로 1~15), 같은 호출을 다시 계획해도 센다(받지 못한 파일을 끝없이 다시 계획하지 않는다). 호출 간격 2초는 SKILL 절차가 지킨다.
  이미 받은 파일이 있으면 `plan` 이 `status: "fetched"` 로 호출 없이 `collect` 를 안내한다. `ipcheck=false` 를 한 번 받으면 그 회차의 `plan` 은 `blocked` 로 거부한다.
- **BREAKING — `notice-detail` 은 `--notice-id`** — 옛 `--court-code`·`--sale-date`·`--jdbn-cd`·`--bid-dvs`·`--bid-bgng`·`--bid-end` 를 지웠다. 같은 회차에서 받은
  목록 파일의 행을 스크립트가 읽어 화면과 같은 본문을 만든다(담당계 전화·법정·매각 시각까지 — 옛 판은 이 칸을 비워 보냈다). `cortAuctnJdbnNm` 은 화면처럼 비워 보낸다
  (옛 판은 목록의 담당계 이름을 실었다).
- **BREAKING — 법원 목록 엔드포인트** — 옛 `/pgj/pgjComm/selectCortOfcCdLst.on` 대신 화면이 지금 부르는 `/pgj/pgj002/selectCortOfcLst.on`(`cortExecrOfcDvsCd=00079B`).
  출력 항목에서 `branchName` 이 빠졌다(응답에 없다).
- **BREAKING — 출력** — 성공 `{"ok": true, "status": "planned"|"fetched"|"ok", …}`, 실패 `{"ok": false, "code": <종류>, "error": …}`(exit 4 — 인자 오류도 JSON,
  옛 argparse exit 2 없음). `code`: `args`·`input`·`budget`·`blocked`·`site`·`http`·`hyve`(`hyve_code`)·`truncated`·`mismatch`·`incomplete`. `case` 의 사이트 status 는
  `status` 가 아니라 `siteStatus` 다. `collect` 출력에 `kind`·`file`·`warnings`·`calls_used`·`calls_remaining` 이 붙는다.
- 요청 헤더를 사이트 화면과 같게 — 2026-10-01 aside 로 뜬 XHR 프로파일(`submissionid`·`SC-Userid`·`SC-Pgmid`·`Accept: application/json`) + 브라우저가 붙이는
  `Origin`·`Referer`. 옛 판의 `X-Requested-With`·jQuery 식 `Accept`·브라우저 UA·warmup GET·쿠키 재사용을 지웠다(쿠키 없이 성립 — itda-hyve 실측).
  POST 는 itda-hyve 가 자동 재시도하지 않게 둔다(`retry_unsafe` 끔 — 차단을 부르지 않게).

### Added

- **응답 대조** (`collect`) — 목록은 행의 법원·입찰구분, 상세는 되비침(`inputData`)의 법원·매각기일·담당계, 사건은 법원·사건번호, 검색은 `pageNo`·`pageSize`·`startRowNo`·행의 법원을
  계획한 질의와 대조한다(다르면 `mismatch`).
- **전량 대조** — 공고 상세는 사건 수(`csCnt`)와 받은 행의 서로 다른 사건 수가 같아야 한다. 검색은 그 쪽에 와야 할 행 수(꽉 찬 쪽은 쪽 크기, 마지막 쪽은 나머지)와
  같아야 한다(둘 다 다르면 `incomplete` — 결과를 내지 않는다). 쪽 넘김 분모는 `groupTotalCount` 가 아니라 `totalCnt` 다(실측: 742·659 에서 70쪽이 꽉 찼다). 목록은 사이트가 총계를 주지 않아
  대조하지 않고 `warnings` 에 그 사실을 싣는다.
- 공고 상세 출력에 `caseCount`·`receivedCaseCount`·`correctionNotices`·`cancellationNotices`, 사건 출력에 `saleItems`(매각 물건별 기일·최저가)·검색 `page.pageCount`·`hasMore`.
- 없는 사건번호는 사이트가 봉투 status 204 로 답한다(2026-10-01 실측 — 1 사건번호 1회차 관측). `collect` 는 사건 조회에서만 204 를 받아 `found: false` 로 내고, 다른 종류의 200 아닌 status 는 `site` 로 거부한다.
- hyve 층 판독은 공용 `shared/hyve_input.py`(본문 그대로·응답 JSON 전체·실패 자리). Windows 콘솔(cp949)에서 한국어·`—` 출력이 죽지 않게 stdout·stderr 를 UTF-8 로 재설정한다(테스트로 고정). `references/netbridge.md` 동봉.
- 실측 픽스처 — 2026-10-01 itda-hyve 응답 7종(목록·상세·사건·없는 사건·검색 1쪽·70쪽·법원 목록)과 aside 요청 프로파일(화면 주소 포함), 소재지 분기 검색 응답·용도 cascade·시도 목록. 상세는 사건 3건만 남겼고, 사건의 이해관계인 이름·집행관 전화를 가렸다.

### Fixed

- **용도 코드표가 사이트와 달랐다** (W12 리뷰 M1) — 옛 표(2026-05-08 캡처라 적힌 대표 7개)의 `공동주택 21200`·`아파트 21201`·`단독주택 21100` 은 사이트에
  없는 코드였다(사이트: 아파트 `20104`, `21100` 은 상업용및업무용). 물건상세검색 화면의 용도 cascade 응답(대 4·중 5·소 66, 75개)을 그대로 옮기고 테스트가 저장한
  응답과 전수 대조한다. 시도는 화면 목록 20개(`전남광주통합특별시 12` 추가). **BREAKING** — 표에 없는 용도·시도는 원문을 통과시키지 않고 `args` 로 거부한다.
  소분류만 주면 대·중분류를 채운다(화면 cascade 와 같다). `codes usages` 출력이 7개 → 75개.
- **물건검색 소재지 분기 본문이 화면과 달랐다** (W12 리뷰 M1) — 2026-10-01 aside 로 소재지 분기를 다시 떠 골든으로 고정했다. 화면처럼 `notifyLoc` `on`(공고중소재지 기본 체크),
  숨은 법원 셀렉트 기본값 `cortOfcCd` `B000210`(서버는 쓰지 않는다 — 부산 조회 3행 전부 `B000412`), 대·중분류, **기간 기본값 오늘 ~ 14일 뒤**(화면은 기간을 비우면
  "기간을 올바르게 입력해주세요." 로 거부한다 — 빈 기간은 화면이 보내는 값이 아니다. 법원 분기도 같다). **BREAKING** — `--sigungu`·`--dong` 은 행정표준코드(해운대구 `26350`)
  또는 사이트 3자리(`350`)를 받아 3자리로 보낸다(옛 판은 5자리를 그대로 보냈다). 법원코드와 지역을 함께 주면·지역 검색에 차량및운송장비·기타 용도를 주면 `args`.
- **검색 행의 조건 되비침 대조** (W12 리뷰 M1) — 행의 `ipchalGbncd`·`srchHjguSidoCd`·`srchHjguSiguCd`·`srchHjguDongCd`·`srchLcls/Mcls/SclsUtilCd` 가 요청과 다르면 `mismatch`,
  대조 키가 없으면 `site`. 소재지 분기에서는 숨은 법원 값을 행의 법원과 대조하지 않는다.
- **검색 마지막 쪽의 행 수** (W12 리뷰 M2) — 쪽마다 와야 할 행 수 `min(크기, 총계 − 앞 쪽들)` 과 받은 수가 다르면 `incomplete`(모자라도 넘쳐도). 출력에 `expected_rows`·`received_rows`.
- **받은 파일 재사용이 옛 질의를 남겼다** (W12 리뷰 M3) — `plan` 이 `fetched` 로 파일을 재사용할 때 회차 상태의 질의를 이번 질의로 갈아 끼운다. (일자로 받은 목록을 월로
  다시 물으면 월 전체, `requestedDate` 도 새 값).
- 둘째 `plan` 의 다른 `--max-calls` 는 말없이 버리지 않고 `args` 로 거부한다(m1). `plan notice-detail` 이 읽은 목록이 차단 응답이면 회차를 멈춘다(m2).
  사건·법원 목록의 `Referer` 를 그 요청을 뜬 화면(경매사건검색 PGJ159M00)으로 — 옛 값은 공고 화면이었다(m5). 같은 조건의 쪽 사이에 총계가 바뀌면 `warnings`(m6).
  공고 상세의 초과본(받은 사건 > `csCnt`)을 "부분본"이라 부르지 않는다(m7).
- 물건검색 기간을 주지 않으면 `collect` 가 실제 기간(화면 기본값 오늘~14일)을 `warnings` 로 되말한다. `--sale-from` 만 주고 그것이 기본 끝보다
  늦으면 오류 문구가 "끝을 주지 않아 기본값을 썼다 — `--sale-to` 도 준다" 를 말한다(W12 재확인 n1·n2).
- 사건 정규화가 현행 응답 키를 읽는다 — 이해관계인 `auctnIntrpsDvsNm`·`intrpsNm`(옛 판은 번호 붙은 키만 읽어 전부 `null`), 기일 `dxdyYmd`·`dxdyHm`·`dxdyPlcNm`·`auctnDxdyRsltCd`(옛 판은 날짜·결과가 `null`).

### Removed

- `scripts/courtauction_adapter.py`(urllib 클라이언트)와 그 테스트, 라이브 테스트 `tests/test_court_auction_live.py` — 스크립트가 네트워크를 하지 않는다. 실측은 itda-hyve 로 한다.
## [0.1.4] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.1.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.1.2] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.1.1] — 2026-06-21

### Fixed

- 라이브 조회(`codes courts` 등)의 warmup GET이 일시적 네트워크/타임아웃(예: 해외 CI 러너→KR 사이트 지연)에 단발 실패하던 문제를 backoff 재시도로 보강 (#492). transient(`URLError`/`TimeoutError`)만 재시도하고 `HTTPError`(서버 응답)는 즉시 반환하며, warmup은 호출 budget을 차감하지 않는다(기본 1회 재시도). 지속 장애는 종전대로 실패해 외부 점검을 유도한다.

## [0.1.0] — 2026-06-05

### Added

- 신규 스킬: 대법원 법원경매정보(courtauction.go.kr) 부동산 매각공고·사건·물건 **read-only 조회**.
- 5개 서브커맨드:
  - `codes` — 법원사무소코드(동적 조회) · 입찰구분 · 용도 · 지역(시도) 코드표.
  - `notices` — 매각공고 목록(월 단위 조회 + 일자 로컬 필터).
  - `notice-detail` — 공고 펼치기(사건번호·용도·주소·감정평가액·최저매각가).
  - `case` — 사건번호 직접 조회(진행상태·기일별 결과·이해관계인).
  - `search` — 물건 자유 조건검색(지역·용도·가격·감정가·면적·유찰횟수).
- WebSquare XHR 어댑터: warmup 세션 쿠키, 호출 간 2초 throttle, 세션 10회 budget,
  `ipcheck=false` 즉시 중단(자동 재시도 없음). 자격증명 불필요(표준 라이브러리만).
- 응답 정규화: raw 한국어/약어 키 → 영문 키, HTML·금액·일자·시각 파싱.
- 정직 고지: 참고용·입찰 전 법원 원문 재확인·IP 차단 위험·공고 시점 기준.

### Notes

- NomaDamas k-skill `court-auction-notice-search`의 컨셉·엔드포인트를 참조해 itda 스타일로
  Python 재작성했습니다. SPEC-COURT-AUCTION-001 (itda-skills/hyve#101).
- 라이브 검증(2026-06-05): codes(60 법원)·notices(서울중앙 5건)·search(서울 건물 2602건) 정상.
  Workflow C 자유검색이 raw HTTP+warmup 쿠키로 작동해 Playwright 폴백은 불필요(미구현).
