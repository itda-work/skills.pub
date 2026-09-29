# CHANGELOG — morning-brief

이 파일이 변경 이력의 유일 정본이다.

## 0.12.1 (2026-09-29)

- **GUIDE.md 를 사이트 독자 눈높이로** (website#207) — 0.12.0 활용법을 다듬어 「모양 고르기」 절·필요한 itda-hyve 판 표·브라우저로 열기(「파일·링크 열기」 끌 수 있음) 소절을 두고, 설치·업데이트 안내의 GitHub 링크를 뺐다(itda-hyve 는 강의에서 안내받은 곳에서 받는다). 스크립트·페이지는 그대로다.

## 0.12.0 (2026-09-29)

- **옛 itda-hyve 면 렌더 전에 멈춘다** (#43, Cowork 실측 13.0.0-test.7 + itda-hyve 0.9.5 — 받은 메일이 빈 브리핑이 끝까지 만들어져 업데이트 뒤
  두 번 만들었다). `gather.py` 가 `--plan`·수집 모두에서 옛 판을 보면 **exit 4** 와 안내 한 줄(`status: "hyve_outdated"`·`required`·`found`·
  `evidence`·`rejected_accounts`·`update_url`·`steps` 3단계)만 내고, 계획 파일·candidates 를 쓰지 않는다(지난 회차 `--out` 파일은 지운다).
  근거는 둘 — ① 1차: `accounts_list` 최상위 `server_version`(0.9.5 도 준다, itda-work/itda-hyve#26 계약)이 0.9.6 미만(형식을 못 읽으면 판정하지 않는다)
  ② 2차: 받은편지함이 `snippet_for` 거부(판 필드가 없거나 못 읽을 때의 근거). 한 계정만 거부돼도 멈춘다.
  `render.py` 는 `hyve_outdated` 경고가 있는 candidates 를 `hyve_outdated`(exit 2)로 거부한다 — 페이지 한 줄 안내(0.10.0)는 없어졌다.
- **미리보기를 매 회차 띄운다** (#43 — 파일 카드가 뜬 회차와 안 뜬 회차가 섞였다). SKILL.md 5절: 첫 브리핑·스타일 재요청 모두 마지막에
  `mcp__cowork__present_files`, 없거나 실패하면 "시스템 브라우저로 열까요?" → 예이고 `server_features` 에 `open_file` 이 있으면 itda-hyve `open_file`(0.10.1+)에
  호스트 경로를, 없거나 에러(`disabled` — 사용자가 끔 · `rate_limited` · `io_error` 등)면 파일 경로 안내. 무인 회차는 묻지 않는다.
  `gather.py --out` 은 성공하면 `{"status":"ok","path",…,"server_version","open_file"}` 한 줄을 낸다(candidates 에는 싣지 않는다 — 골든 불변).
  `allowed-tools` 에 `mcp__cowork__present_files`·`mcp__remote-devices__itda-hyve__open_file`·`mcp__itda-hyve__open_file`. `mcp__visualize__show_widget` 인라인 표시는 검토 뒤 쓰지 않기로 했다.
- **GUIDE.md 활용법 절** — 미리보기·모양 바꿔 다시 보기·인쇄·PDF 저장(⌘P)·브라우저로 열기·itda-hyve 업데이트 3단계·자주 겪는 문제.
- 테스트: 거부 픽스처에서 candidates 미작성·exit 4(전 계정·한 계정), 지난 candidates 삭제, `--plan` 이 계획 파일 없이 멈춤, 서버 판 미만 4종·이상/판독 불가 7종,
  판 비교가 숫자 단위, 초안의 `server.version` 객체는 읽지 않음, render 가 옛 판 candidates 를 파일 없이 거부, `--out` 상태 줄의 `open_file`
  (기능 있음·없음·배열 아님·필드 없음). 입력 픽스처 `accounts.json` 을 0.10.1 모양(최상위 `server_version`·`server_features`)으로 — 골든 3종 바이트 동일.

## 0.11.0 (2026-09-29)

- **보고서 스타일 4종** (#42, 사용자 결정 — 시안 5종 중 C 기본, A·B·E 옵션, D 제외). `render.py --style timeline|memo|desk|print`(기본 `timeline`).
  사용자가 "보고서 형식으로"·"표로"·"인쇄용으로" 처럼 말하면 SKILL.md 가 그 스타일을 고른다(후보를 읽기 전에).
  - `timeline`(기본) — 세로 시간축. 일정 길이에 비례한 블록(1분 0.9px, 52~270px), 1시간 이상 빈 시간 줄(가장 늦게 끝난 일정부터 재고, 취소된 일정은
    시간을 차지하지 않는다), 관련 메일은 일정 옆(720px 이하에서는 아래), 날씨·환율은 머리 오른쪽, 미회신은 카드.
  - `memo` — 결재 메모. 머리에 날짜·캘린더/메일 계정 이름·날씨·환율, 한 줄 요지("오늘은 일정 N건, 답을 기다리는 메일 M통이에요." — 준비된 역할만 센다),
    명조 제목, 관련 메일은 일정 아래 들여쓰기.
  - `desk` — 지표 띠(일정·일정별 관련 메일·일정과 무관한 미회신·대량 발송, 준비 안 된 역할은 `—`)와 표. 관련 메일은 일정 행 아래 하위 행.
    720px 이하에서는 표 행이 블록으로 접힌다(가로 스크롤 없음).
  - `print` — A4 한 장 두 단(왼쪽 일정·오른쪽 미회신과 대량 발송), 검은 머리띠. `@page A4 12mm`, 인쇄에서는 두 단 고정·버튼 숨김·색 유지.
  - **「일정별 관련 메일」 절이 없어졌다** — 관련 메일은 네 스타일 모두 그 일정 곁에 붙는다. 어느 일정에도 없으면 "오늘 일정과 이어지는 메일이 없어요" 한 줄이
    「오늘 일정」 절 안에 나온다.
  - 네 스타일 모두 라이트·다크(OS 설정, `data-theme` 로 고정 가능)·인쇄(늘 라이트) 색 토큰. 웹 폰트 없음(시스템 글꼴). 출처 절·계정 배지·단일 계정 단순형·
    `--no-sources` 주소 0 은 그대로 — 출처 절은 스타일과 무관하게 바이트 동일.
  - 페이지 `<body>` 에 `data-mb-style`. `verify.py` 에 `style-declared`(아는 스타일 하나)·`--style`(렌더 때와 같은가) 검사. 나머지 ①~⑨ 는 스타일과 무관하게 같다.
- 테스트: 네 스타일 × 골든 3종 × 출처 있음/없음 verify PASS, 스타일마다 같은 내용(일정·관련/미회신 제목·보낸 사람·요약·대량 제목·날씨 줄)과 같은 표지 수,
  관련 메일이 제 일정 곁에만, 빈 시간·블록 높이·겹침·60분 경계, 데스크 지표, 메모 요지, A4 인쇄 CSS, 토큰 라이트/다크 키 일치, 400px 이상 고정 폭 0,
  행 누락 뮤테이션 8종 × 스타일 4종 RED. 골든 `brief.html` 3종을 타임라인으로 다시 굳히고 스타일 스냅숏 3종(`brief-{memo,desk,print}.html`)을 더했다.
  렌더·검증 뮤테이션 14종 RED(스냅숏 테스트를 빼고도).

## 0.10.0 (2026-09-29)

- **미리보기는 사람 메일에만** (itda-work/itda-hyve#22, itda-hyve 0.9.6). 받은편지함 `imap_search` 에 `snippet_for: "non_bulk"` — 서버가 `bulk` 표지 메일과
  noreply 류 발신(로컬파트 전체 일치 noreply·donotreply) 메일의 본문 앞부분을 받지 않고 `snippet_skipped`(`bulk`·`noreply`)를 단다. 서버 실측 Gmail 45통
  첫 호출 4.8초 → 2.1초. 대량 메일은 원래 요약하지 않으므로 페이지는 그대로다(골든 3종 바이트 동일).
  - **건너뛴 메일은 미회신 후보가 될 수 없다** — `auto_reason` 이 `snippet_skipped` 를 강한 표지로 읽는다(아는 상대여도, 모르는 사유여도). 서버의 noreply 는 보낸 사람
    **중 하나**를 보고 스킬 규칙은 첫 주소만 봐서, 두 번째 주소가 noreply 인 메일이 미리보기 없이 미회신에 남을 수 있었다. 서버 규칙은 스킬 noreply 규칙(부분 문자열)의
    부분집합이고, `bulk: true` 는 원래 강한 표지다.
  - **최소 itda-hyve 0.9.6.** 0.9.5 는 모르는 인자를 호출 단위 `invalid_input` 으로 거부한다(일정·보낸편지함은 받힌다). 그 거부를 경고 `hyve_outdated`(error)로 읽어
    페이지가 "itda-hyve 가 옛 판이라 받은 메일을 읽지 못했어요 — 0.9.6 이상으로 업데이트해 주세요." 한 줄을 말한다(「계정 확인 실패」 로 뭉뚱그리지 않는다).
    인자를 빼고 다시 부르는 대체 경로는 두지 않는다. batch 스키마로는 0.9.5·0.9.6 을 가를 수 없어 배포 순서(0.9.6 공개 뒤 태그)로 보장한다.
- 테스트: 계획의 `snippet_for`, 건너뛴 메일 3종(두 번째 주소 noreply·`bulk` 누락·모르는 사유 — 아는 상대여도)이 후보·본문 바퀴에 오지 않음, 픽스처의 건너뛴 메일 전부 대량,
  서버 noreply ⊂ 스킬 규칙, 옛 서버 거부 → `hyve_outdated`·다른 `invalid_input` 은 그대로, 페이지 안내 줄. 픽스처 받은편지함을 0.9.6 non_bulk 응답 모양으로(대량 메일은
  `snippet` 대신 `snippet_skipped`). 뮤테이션 5종 RED.
- `references/netbridge.md` 사본 동기화 — 0.9.6 `snippet_for`·`snippet_skipped` 절.

## 0.9.0 (2026-09-29)

- **대량 발송 메일을 메일 계정별로** (#41, 사용자 요청 — 업무용·개인용 계정이 섞여 있다). 「대량 발송 메일」 절이 계정(accounts_list 의 이름·주소·통수)
  소절 → 종류 → 발신자 → 제목 목록이다. 발신자 8곳 상한은 계정마다. 메일 계정이 하나면 소절 머리 없이 예전 모양 그대로. `--no-sources` 에서는
  계정 주소를 빼고 이름만 싣는다(공유용 노출 축소 — 본문에 `@` 0 계약 유지).
  - candidates `email.bulk` 계약: `{count, kinds, accounts: [{account, login, count, kinds, groups}]}` — 최상위 `groups` 를 없앴다. `accounts` 는
    accounts_list 순번 순서, 대량 메일이 있는 계정만. 전체 `count`·`kinds` 는 계정 값의 합.
  - **계정 배지** — 메일 계정이 둘 이상이면 일정별 관련 메일·미회신 줄에 계정 이름을 작은 배지로 단다(앵커의 `account`). 하나면 달지 않는다.
  - 출처 요약 줄에 계정별 대량 메일 수(`naver 14 · google 3`).
  - verify ①: 계정 합 = 전체, 계정마다 수 = 종류 합 = 종류 묶음 합, 계정 소절 수·통수(메일 계정 하나면 소절 0), 계정 배지가 앵커의 계정과 줄마다 일치.
- 테스트: 픽스처 google 계정에 대량 메일 3통(naver 와 같은 발신자 둘 포함 — 계정이 다르면 따로 선다), 골든 3종 갱신, 계정별 상한, 단일 계정 단순형,
  배지·계정 이름 이스케이프, `--no-sources` 주소 제외. 뮤테이션 6종 RED(verify·render 의 계정 판정 무력화, 계정 합 검사 무력화, 0통 계정 소절,
  `--no-sources` 주소 노출, 배지 제거).
- `snippet_for: "non_bulk"`(itda-work/itda-hyve#22) 는 서버 병합 뒤에 싣는다 — 이 판에는 없다(0.10.0 에 실었다).

## 0.8.0 (2026-09-29)

- **수집이 batch 한 번** (#40, itda-hyve 0.9.5 — itda-work/itda-hyve#21). `--plan` 의 첫 바퀴가 `accounts_list`·`location`·`calendar_events`·
  `imap_search` INBOX(`include_snippet: 300`)·`imap_search` `\Sent` 를 `account: "*"`(파일 이름 `{n}` = accounts_list 순번)로 한 계획 파일에 싣는다.
  0.6.0 의 batch 세 번(바퀴 사이 모델 대기 72초·33초 실측)이 한 번이 된다.
  - 미회신 요약 재료는 받은편지함 `snippet`(후보 `body`, 본문이 더 있으면 `body_partial: true`). **본문 바퀴를 없앴다** — snippet 이 없는 메일만 예외 바퀴의
    `imap_fetch` `uids`. 빠진 계정별 파일은 예외 바퀴에서 계정 이름으로 다시 받는다.
  - `location` 은 같은 batch 에 정밀(OS) 그대로 — 긴 대기(권한 창 25초 + 위치 8초)는 위치 권한을 정하지 않은 첫 회차뿐이다(README D17).
  - 날씨 예보를 batch 에서 뺐다 — 좌표가 location 결과에 달려 있다. weather-here 가 샌드박스에서 Open-Meteo 를 직접 받고, 실패하면 `http_request` 한 번.
    `forecast_request`·`location_coords` 를 지웠다(요청 정본은 weather-here `--weather-request`).
  - 최소 itda-hyve **0.9.5** — batch 스키마의 `calls[].args` 설명에 `"*"`(`{account}`·`{n}`)가 없으면 업데이트 안내. `results[]` 의 `skipped`
    (`calendar_unsupported`·`no_accounts`)는 실패가 아니다.
- 테스트: 첫 바퀴 `"*"`·snippet 인자, 예보 없음, snippet 없는 메일만 본문, 빠진 계정 파일 보충, 본문 우선순위(fetch > snippet), 배포형·NFD 종단이
  **batch 한 번**으로 끝남(모사 itda-hyve 가 `"*"`·`{n}` 을 펼친다). 픽스처는 snippet 을 싣고 bodies 파일을 지웠다. 뮤테이션 5종 RED.
- `references/netbridge.md` 사본 동기화 — 0.9.5 `account: "*"`·`include_snippet`·`location` 대기 시간 절.

## 0.7.0 (2026-09-29)

- **「미회신」 은 사람 메일만** (#40, 0.9.4 Cowork 실측). 대량 발송 표지가 없는 자동 메일(Firebase `firebase-noreply@`, NHN KCP 「발신전용」
  `pgadmcust@`, 쿠팡 `easypay_noreturn@`, Apple `no_reply@`, Replicate `billing@`, AliExpress `@notice.…`)이 미회신에 남던 것을 고쳤다.
  - 강한 표지(아는 상대여도 대량 발송): 제목 「(광고)」·`bulk` 헤더·로컬파트 **어디에든** noreply·no_reply·noreturn·donotreply 류·표시 이름
    「발신전용」·「회신불가」·no-reply.
  - 약한 표지(아는 상대면 사람 메일): 역할 주소(billing·receipt·order·account·security·alert·notice·notification·newsletter·marketing 등 —
    support·info·help·contact·sales 는 넣지 않음)·발송 서브도메인(notice.·email.·mail.·news.·em.·mailer. 등, 도메인 세 마디 이상).
    아는 상대 = 최근 30일 보낸편지함의 받는 사람·참조(계정 무관).
- **대량 발송 메일 절** (사용자 결정). 「뉴스레터·알림 N통」 한 줄 대신 종류(뉴스레터·자동 알림·결제·청구·광고) → 발신자(통수 많은 순, 8곳) →
  최신 제목 3개("외 N통")로 묶은 **제목 목록**. 모델 요약 없음 — candidates `email.bulk.groups` 를 render 가 그린다. 종류 `billing` 추가.
  미회신 절 끝에는 "대량 발송 메일 N통은 … 아래에 따로 모았어요" 한 줄. verify ① 에 발신자 줄·제목 줄·전체 수 대조 추가.
- **첫 `not_found` 방지** — `--plan` 이 계획 파일을 fsync·다시 읽어 확인한 뒤에만 경로를 낸다. `--input` 과 `--save-dir` 의 마지막 이름이 다르면
  `save_dir_mismatch`(exit 2 — NFC 로 맞춰 비교, NFD 한글 폴더도 같은 이름). SKILL 에 "연결 폴더 안에 입력 폴더, 호스트 경로 = 연결 폴더의
  호스트 경로 + 상대 경로" 를 명시.
- 테스트: 실측 발신자 6종 픽스처(주소만 sample), 아는 상대의 역할 주소 메일(미회신에 남음), 골든 3종 갱신, NFD·공백 폴더(「클로드 실습」)
  종단(계획 → 저장 → 수집 → 렌더 → 검증), 뮤테이션 11종 RED 확인.

## 0.6.0 (2026-09-29)

- `gather.py --plan` 이 batch 인자를 입력 폴더의 `plan-<k>.json` 으로 쓰고 `{"plan_file": …}` 한 줄만 낸다 — 모델이 호출 목록을 다시 출력하지
  않는다(itda-hyve 0.9.4, #39). 대량 메일(`imap_search` `bulk`·`bulk_reason`, 헤더 없는 것은 noreply 류 보낸 사람·제목 「(광고)」)을 미회신·요약에서
  빼고 「뉴스레터·알림 N통」 한 줄로 셌다. 관련 메일에는 참석자·주최자 주소로 이어질 때만 붙고 "단체 발송" 으로 보인다. 최소 itda-hyve 0.9.4.
  (이 항목은 0.7.0 작업 때 빠져 있던 것을 커밋 96e7cc54 기록에서 옮겨 적었다.)

## 0.5.0 (2026-09-28)

- **새 구성 — 오늘 일정 전체 → 일정별 관련 메일 → 일정과 무관한 미회신(제목·보낸 사람·요약)** (#38, 사용자 피드백).
  "하루를 세 마디로" 요약(지형 한 획 + 세 마디)과 두 목록(「지금 당신이 필요한 일」·「정리된 일」), 내일 일정·prep·재회신 목록을 걷어냈다.
  관련 사람 정보는 넣지 않는다(사용자 결정 — 참석 인원 수만). 날씨 절은 그대로(#37 방식).
  - **목록·매칭·정렬은 스크립트, 요약 문장만 모델.** `gather.py` 가 오늘 일정(종일 먼저·시각순, 취소 표시), 일정마다 관련 메일(참석자·주최자
    주소 → 제목 키워드, 스레드당 최신 1통·5통), 일정과 무관한 미회신(스레드당 최신 1통·계정당 8통)을 정하고, 모델은 content.json 에
    미회신마다 요약 한두 문장만 쓴다(`summaries[{anchor, summary, button?}]`).
  - candidates·content **schema_version 2**. `render.py` 는 옛 판 candidates 를 거부하고, 요약이 후보와 1:1 이 아니면(빠짐·남음·중복·
    관련 메일에 단 요약) exit 2. `verify.py` 축을 새 구성으로 다시 짰다(① 세 목록 수 ② 요약 1:1 … ⑨ 샘플).
  - 날씨·환율 절은 content 를 거치지 않고 candidates 에서 그린다(지어낸 절이 낄 자리가 없다).
- **수집을 batch 두세 번으로** (itda-hyve 0.9.3 `batch`·`imap_fetch` `uids`·일정 `organizer`/`attendees`). `--plan` 이 바퀴마다 `batch` 호출
  하나를 낸다 — ① 계정 목록·현재 위치 ② 오늘 일정·받은 메일·보낸 메일(`\Sent`)·날씨 예보 ③ 일정과 무관한 미회신 본문(계정당 `uids` 한 호출).
  0.9.2 Cowork 실측 23회 호출(수집 약 35초 + 바퀴 사이 대기)이 batch 3번이 된다(itda-hyve 실계정 묶음 22.7초 → 2.0초, itda-work/itda-hyve#15).
  batch `timeout_sec` 50(Cowork 호출 상한 60초 안). 실패한 호출은 모델이 `{"error": …}` 로 기록한다.
- **날씨 위치를 itda-hyve `location` 으로** (#37). IP 서비스 한 곳(ipapi.co·ipwho.is) 호출과 `weather-geo-*.json` 을 없앴다. 예보는 둘째 바퀴의
  `http_request`(weather-here 와 같은 Open-Meteo 요청 — 테스트가 대조)로 받아 `weather_here.py --geo-input location.json --weather-input
  weather-forecast.json` 으로 절을 만든다(샌드박스 네트워크를 쓰지 않는다).
- 본문 발췌 500 → 1000자(요약용). 캘린더 창은 오늘 하루(내일 0시까지).
- 옛 itda-hyve(참석자 목록 없음)는 `attendees_missing` 결손으로 페이지가 업데이트를 안내한다. 최소 itda-hyve **0.9.3** — `batch` 도구가 없으면
  업데이트를 안내하고 멈춘다(도구 목록으로 가른다). allowed-tools 는 `batch`·`http_request`(지역명 날씨의 예보 한 번)만.
- 샘플 시드: `tomorrow` 를 받지 않고(명시 오류) 일정에 `attendees`·`location` 을 받는다. 기본 시나리오를 새 구성에 맞게 고쳤다.
- 테스트: 골든 3종(일정 6건+관련 메일 4통·무관 미회신 2건 / 일정 0건 날 / 샘플), batch 세 번으로 끝나는 종단 테스트, 매칭 규칙·요약 1:1·
  각 검증 축 뮤테이션. 픽스처는 두 계정(naver 캘린더 지원·google 미지원), `@sample.example.com` 만.

## 0.4.0 (2026-09-28)

- **응답을 옮겨 적지 않는다 — itda-hyve 가 입력 폴더에 직접 쓴다** (#34). Cowork 실측에서 가장 큰 비용은 모델이 도구
  응답 JSON(구글 받은편지함 54통 등)을 그대로 다시 출력해 입력 폴더에 쓰는 것이었다. `gather.py --plan` 이 모든 호출
  인자에 `save_dir`(입력 폴더의 호스트 경로 — 새 인자 `--save-dir`)·`save_as`·`overwrite: true` 를 싣고, itda-hyve 0.9.2 가
  응답 전체를 그 파일에 쓴 뒤 모델에게는 `saved_path`·요약만 돌려준다(저장 파일은 저장하지 않은 응답과 같은 바이트 —
  itda-work/itda-hyve#10 실측). SKILL.md 의 "응답을 그대로 Write" 지시를 없앴다. 도구 실패만 `{"error": …}` 한 줄을 쓴다.
  `--save-dir` 없이 `--plan` 을 부르면 `save_dir_required`(exit 2) — 옮겨 적는 길로 돌아가지 않게.
- **라운드 4 → 3** — 보낸편지함 이름을 찾던 `imap_list_mailboxes` 바퀴를 없애고 `imap_search` 의 `mailbox: "\\Sent"` 로
  받는다. 응답의 `special_use` 가 `\Sent` 가 아니면 `sent_mailbox_mismatch` 로 받지 않고, 도구 에러 `special_use_not_found` 는
  `sent_folder_not_found`(보낸편지함 없음)로 읽는다 — 읽기 실패(`sent_read_failed`)와 구별. 입력 폴더에 `mailboxes-<n>.json` 이 없어졌다.
- `include_references` 를 끈다(판정은 `message_id`·`in_reply_to`, itda-work/itda-hyve#9). 보낸편지함 30일·200통은 유지 —
  근거는 README「보낸편지함 창·References 결정」.
- **날씨 위치를 itda-hyve 로** (itda-work/skills#33). 날씨 절이 있으면 첫 바퀴에 `http_request` `https://ipapi.co/json/` 를
  `weather-geo-1.json` 으로 저장하게 하고, 위경도가 없으면 다음 바퀴에 한 번만 `https://ipwho.is/`. 날씨 절은
  `weather_here.py --geo-input` 으로 만든다(Cowork 에서 인자 없이 돌면 weather-here 0.13.0 이 exit 3 으로 멈춰 절이 빠지던 것).
  사용자가 지역을 말했으면 `--plan --weather-place` 로 위치 호출을 내지 않는다.
- 최소 itda-hyve **0.9.2**(0.9.1 은 공개하지 않는다). allowed-tools 에서 `imap_list_mailboxes` 를 빼고 `http_request` 를 넣었다.
  Cowork 는 **연결 폴더가 필요**하다(없으면 연결을 요청하고 멈춘다).
- 테스트: 계획이 모든 호출에 저장 인자를 싣는지, 세 바퀴로 끝나는지, 위치 서비스 폴백이 한 번뿐인지, `\Sent` 응답 검사를
  더했다. 픽스처에서 `mailboxes-1.json`·`references` 를 빼고 `weather-geo-1.json` 을 넣었다(골든 불변). 테스트 249 → 260건.

## 0.3.0 (2026-09-28)

- **수집을 itda-hyve 경로로** (#18). `gather.py` 가 형제 스킬 스크립트(calendar `check_env`·
  `list_events`, email `check_env`·`thread_status`)를 subprocess 로 돌려 `.env` 비밀번호로 IMAP·CalDAV 에
  직접 붙던 경로를 걷어냈다. 이제 LLM 이 itda-hyve 도구(`accounts_list`·`calendar_events`·
  `imap_list_mailboxes`·`imap_search`·`imap_fetch`)를 부르고 응답을 입력 폴더에 저장하며,
  `gather.py --input <폴더>` 가 판정만 한다. **candidates.json 계약은 그대로**다(render·verify 불변).
  - `gather.py --plan` — 아직 부르지 않은 호출(도구·인자·저장 파일)을 낸다. 날짜 창·보낸편지함 이름·
    본문을 받을 uid 를 스크립트가 정해 LLM 이 고르지 않게 했다. `status: complete` 까지 반복.
  - 미회신 판정은 `imap_search` 의 `message_id`·`in_reply_to`·`references` 로 스레드를 잇는다 —
    **itda-hyve 0.9.1 이상** 필요(itda-work/itda-hyve#9). 옛 판이면 `thread_headers_missing` 결손으로
    "업데이트해 달라" 고 페이지가 말한다.
  - 네이버처럼 서버가 펼치지 않은 반복 일정을 stdlib 로 회차 전개(DAILY·WEEKLY·MONTHLY·YEARLY, INTERVAL·
    COUNT·UNTIL·BYDAY·BYMONTHDAY·BYMONTH). 못 읽는 규칙은 `recurrence_unsupported` 결손.
  - `prep` — itda-hyve 가 주최자를 주지 않아 "주최자를 알면 그것, 모르면 참석자가 없는 내 일정" 으로.
  - 새 경고: 결손 `inbox_truncated`·`thread_headers_missing`·`calendar_partial`·`calendar_truncated`·
    `recurrence_unsupported`, 경고 `sent_truncated`·`body_missing`·`not_addressed_skipped`. 모든 결손에
    코드별 한 줄(캘린더 결손이 "메일 일부를…" 로 뭉뚱그려지지 않는다).
  - 제거: `--siblings-dir`·동봉 `siblings/` 해석·`sibling_deps_missing` 처방·`--timeout`/`--call-timeout`.
    GUIDE 의 `.env`·`caldav`/`icalendar` 설치 안내를 itda-hyve 안내로 바꿨다.
  - 날씨·환율 절은 키가 필요 없는 공개 API 라 형제 스킬 그대로(판단 근거는 README). 다만 이제 LLM 이
    받아 `section-*.txt` 로 남기고 `gather.py` 는 실행하지 않는다.
  - 테스트 픽스처를 itda-hyve 응답 형태(`tests/fixtures/hyve_input/`, `@sample.example.com` 만)로 교체하고
    골든을 다시 만들었다. 가짜 형제 스크립트(`fake_skills/`) 삭제. `gather.py` 가 `subprocess`·`os`·
    네트워크 모듈을 들여오지 않음을 AST 로 고정. 테스트 222 → 249건.
- frontmatter `version` 이 0.1.0 에 머물러 0.2.0 을 반영하지 못하던 것을 이 판에서 맞췄다.

## 0.2.0 (2026-09-03)

- **출처 절** (#1638 v5). 페이지 끝에 접이식 「출처」 — 수집 요약(역할·프로바이더·계정
  주소)·원본 목록(메일: 보낸 사람·제목·날짜·판정·본문 발췌 / 일정: 캘린더·제목·시간·
  주최자·상태)·항목↔원본 앵커 링크·미표시 후보 「표시 안 함」. candidates.json 만으로
  코드가 만들며 content 는 읽지 않는다. `render.py --no-sources` 로 뺀다(verify 도 같은
  플래그로 맞춘다). 시각은 ISO 원문이 아니라 한국어 표기(`9월 3일 오전 9:30 – 오전 10시`).
- **샘플 모드** (#1638 v6). `gather.py --sample [시드]` 가 형제 스킬을 한 번도 부르지
  않고 시나리오만으로 같은 형식의 candidates 를 만든다. 동봉 기본 시나리오는 세무사
  사무실 아침(`assets/sample-seed.default.json` — 일정 6·메일 7). 시드 스키마 위반은
  exit≠0 이며 **기본 시나리오로 대체하지 않는다**. 샘플임을 못 지우게: `controls.sample`
  ·역할 상태·앵커 `provider:"sample"`·최상단 상시 띠·출처 계정란·버튼 seed 접두.
  계정이 없다고 스스로 샘플로 바꾸지 않는다 — 계정 0 페이지에 안내 한 줄만.
- 앵커에 `account`·`start` 편입(같은 UID 반복 회차·계정 간 충돌 제거), 시각을 브리핑
  시간대로 변환, 날짜 경계를 걸친 일정을 구간 겹침으로 판정, 캘린더 전 계정 실패를
  `error` 로, 형제 의존성 부재를 `sibling_deps_missing` 으로 갈라 처방까지 안내.
- 한국어 줄바꿈을 어절 단위로(`word-break: keep-all`), calendar `--account` 상시 명시.
- **날씨 섹션 기본 적용**(마스터 결정 — v4 "Sections 없음=0" 반전). `--sections`
  미지정이면 날씨 한 절, `--sections 환율` 이면 환율만, `none` 이면 0개. 샘플도 같은
  규칙이며 시드에 그 절의 문구가 없으면 다른 데서 끌어오지 않고 `section_missing`
  경고만 남긴다. 샘플의 `--sections` 거부(0.2.0 초판)는 철회.
- 라이브(Cowork) 후속: act 를 **정확히 3개**로 조이고(둘만 나오던 회차 — 빈 칸도
  관찰로 쓴다), 샘플 출처 요약의 '샘플' 중복 표기 제거.
- `verify.py` 검사 축 ①~⑦ → **①~⑨**(⑧ 출처, ⑨ 샘플 상호 배타). 테스트 89 → 202건.

## 0.1.0 (2026-09-03)

- 신설 (#1638). Claude 기본 `morning` 스킬(2026-09 판)의 Gather → Sort → Write →
  Build → Verify 계약을 차용하되, 한국 사용자의 CalDAV·IMAP 소스를 itda-work
  `calendar`·`email` 형제 스킬에서 직접 읽도록 갈랐다. 상류 판·의도적 divergence
  13건·동기화 절차는 `README.md`.
- 구조: `gather.py`(형제 스킬 subprocess → `candidates.json`) ·
  `render.py`(`content.json` + `candidates.json` → 단일 파일 HTML) ·
  `verify.py`(①~⑦ 정적 검증, exit 0/1). LLM 은 Sort 와 문장만 쓴다.
- Cowork 에 브라우저가 없어 시각 검증은 `INCONCLUSIVE` — `verify.py` 가 판정 정본.
- 테스트 89건. 가드 18종을 뮤테이션으로 RED 실측.
