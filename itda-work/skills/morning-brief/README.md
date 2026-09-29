# morning-brief — 개발자 노트

사용자용 실행 계약은 `SKILL.md` 다. 이 문서는 **차용 출처와 갈라진 지점**을
기록한다(`upstream-fork-evidence-sync`).

## 차용 출처

| 항목 | 값 |
|---|---|
| 상류 | Claude 기본 스킬 `morning` |
| 상류 판 | **2026-09 판** (2026-09-03 마스터 제공본) |
| 원문 보존 | GitHub Issue itda-skills/hyve **#1638 첫 코멘트** (SKILL.md 전문) |
| 차용 범위 | Gather → Write → Build → Verify 흐름, Voice, Ground rules, 버튼 정확 문구 게이트와 seed 규율. 두 목록 구조·지형 한 획 + 세 마디는 0.5.0 에서 걷어냈다(D16) |
| 복제 여부 | **없음** — 계약을 우리 문장(한국어 존댓말)으로 다시 썼다 |

상류는 **디자인 스킬**이라 `empirical-validation` 류 반증 기록이 없다. 즉 상류
규칙의 판별력이 대조 코퍼스로 측정된 적이 없으므로, 우리는 상류 규칙을 옮길 때
"무조건" 을 그대로 받지 않고 **코드가 집행할 수 있는 축만** 게이트로 올렸다
(`verify.py`). 나머지는 SKILL.md 의 문서 규율로 남긴다.

## 의도적 divergence

| # | 상류 | 우리 | 왜 |
|---|---|---|---|
| D1 | LLM 이 HTML 을 직접 그린다 | **결정론 3종**(`gather.py`·`render.py`·`verify.py`), LLM 은 Sort·문장만 | 이스케이프 누락·링크 스킴·요일 오기·버튼 인코딩이 매 회차 흔들린다. 공통 뿌리를 코드로 닫는다 |
| D2 | 커넥터 카탈로그(Google Calendar·Gmail·Slack·M365) | **itda-hyve**(로컬 MCP 서버)의 메일·캘린더 도구 — LLM 이 부르고 응답을 폴더에 저장, `gather.py --input` 이 판정 | 한국 사용자의 네이버·아이클라우드·다음·CalDAV 에는 커넥터가 없다. 상류는 연결 제안 카드만 띄우고 끝난다. 0.2.0 까지는 형제 스킬 스크립트를 subprocess 로 돌려 `.env` 비밀번호로 직접 붙었다 — #18 에서 걷어냈다(아래 정정 이력) |
| D3 | 역할 4종(calendar·email·chat·other) | **2종**(calendar·email) | chat·task 소스가 우리에게 없다. 없는 역할을 이름만 남기지 않는다 |
| D4 | 미연결 역할에 커넥터 제안 카드 | 카드 없음, 조용히 skip | 우리에겐 제안할 커넥터가 없고, 카드는 브리핑이 아니다 |
| D5 | 버튼 게이트를 LLM 이 판정 | `gather --include-buttons` 가 `controls.buttons` 에 **고정**, render·verify 는 그 값만 본다 | 제3자 데이터를 읽은 뒤의 LLM 판단은 권위가 아니다. 후보를 읽기 전에 확정한다 |
| D6 | Fraunces woff2 를 base64 로 임베드 | **폰트 임베드 폐기**, 시스템 스택만 | 한글 헤드라인에 Fraunces 는 Latin 전용이라 무효다. Cowork 샌드박스에 Noto CJK 15 패밀리가 있고(실측), HTML 은 사용자 OS 에서 열린다 |
| D7 | playwright 스크린샷으로 Verify | **정적 검증이 정본**, 시각 축은 `INCONCLUSIVE` | Cowork 에 playwright·chromium·`/opt/pw-browsers` 가 없다(Phase 0 실측 확정). 상류 Build 의 렌더 체크 절은 통째로 미채택 |
| D8 | 팔레트 wash `#F9F9F7` / clay `#C6613F` | **스타일 4종의 색 토큰**(라이트·다크 한 벌씩, 인쇄는 늘 라이트) — 기본 타임라인은 청록 accent `#0F766E` | 0.10.0 까지는 먹·한지 톤(`#FBF8F1`·`#22201C`) + 단청 주홍 `#B3492D` 한 벌이었다. #42 에서 사용자가 고른 시안(C·A·B·E)의 색으로 바꾸고 다크 모드를 더했다(D18) |
| D9 | "오늘 마감"·"사라진 겹침"·비주최자 prep·spare 검색 | 없음 | 소스가 없거나(마감·회차 간 상태) 앵커가 약하다. 지어내느니 뺀다 |
| D10 | Sections 는 연결된 아무 도구나, **요청한 것만** | allowlist **2종**(날씨·환율), argv 확정. **날씨는 기본 적용**(`Sections: none` 으로 제외) | 교차 플러그인 자유 호출은 계약이 없다. 날씨는 아침에 가장 먼저 궁금한 것이라 매번 요청하게 두지 않는다(마스터 결정 2026-09-03 — v4 "Sections 없음=0" 반전). 시드·수집 실패 시엔 다른 데서 끌어오지 않고 경고만 남긴다. 날씨 위치는 itda-hyve `location`(batch 안), 예보는 weather-here 가 샌드박스에서 직접(실패 때만 `http_request` 한 번 — #40, 아래 Sections 판단) |
| D11 | 인용 축자 요구가 문서 규율 | `verify.py` 가 앵커 1:1 + 인용 **바이트 대조**로 집행 | "축자로 쓰라"는 지킬 수 없다 — 지켰는지 재는 것이 답이다 |
| D12 | 예약 작업을 스킬이 만든다 | **템플릿 제공까지** | 예약 자동 생성은 이 판의 범위 밖. 무인 판별 신호가 없어 프롬프트 명시가 유일 |
| D13 | RTL 지원 | 없음 | 한국어 전용 |
| D14 | 페이지 하단에 아무것도 두지 않는다(footer 금지) | 접이식 **「출처」 절** — 수집 요약(역할·프로바이더·계정 주소)·원본 목록·항목↔원본 링크·미표시 후보 표기 | 상류는 브리핑의 여백을 지키려 footer 를 금지하지만, 우리 데이터는 **연결된 커넥터가 아니라 사용자 개인 계정**에서 온다 — 무엇을 어느 계정에서 읽었고 무엇을 안 보여줬는지 말할 수 있어야 신뢰가 선다. 기본 닫힘이라 여백은 지켜지고, 공유 시엔 `--no-sources` 로 뺀다. candidates.json 만으로 코드가 만들어 LLM 무접촉 |
| D15 | 소스가 없으면 커넥터 제안 카드 | **샘플 모드** — 명시 요청(`샘플 브리핑`)에만 지어낸 시나리오로 같은 페이지를 그리고, 최상단 상시 띠·출처 계정란 「샘플 · 에이전트 생성 시나리오」·앵커 `provider:"sample"` 로 샘플임을 못 지우게 박는다 | 상류는 미연결 역할에 연결 제안 카드를 띄우지만 우리에겐 제안할 커넥터가 없다(D4). 그래도 "이 스킬이 뭘 주는지" 는 보여줄 수 있어야 도입 판단이 선다 — 카드 대신 **완성된 형식 한 장**으로 답한다. 계정 부재 시 자동 대체는 금지(no-silent-fallback): 계정 0 페이지는 안내 한 줄만 두고, 전환은 사용자의 명시 요청으로만 |
| D16 | 하루의 모양(지형 한 획 + 세 마디)과 두 목록(「지금 당신이 필요한 일」·「정리된 일」)을 LLM 이 고르고 쓴다 | **오늘 일정 전체 → 일정별 관련 메일 → 일정과 무관한 미회신(제목·보낸 사람·요약)** 세 목록을 **코드가** 고르고 그린다. LLM 은 셋째 목록의 요약 문장만. 내일 일정·prep·취소 목록·재회신 목록·관련 사람 정보 없음 | 사용자 피드백(2026-09-28, itda-work/skills#38) — "하루를 세 마디로" 는 러프했고 원하는 것은 일정과 그 일정에 걸린 메일을 한눈에 보는 것이었다. 고르기를 코드로 옮기자 목록↔버킷 대조(구 ② 버킷 축)·acts 개수 축이 필요 없어졌다. 관련 사람 정보는 사용자 결정으로 넣지 않는다 |
| D17 | (상류 해당 없음 — 수집 방식) | **batch 한 번**: `accounts_list`·`location`·`calendar_events`/`imap_search` INBOX(`include_snippet: 300`)/`imap_search` `\Sent` 를 `account: "*"`(파일 이름 `{n}`)로 한 계획 파일에. **`location` 은 정밀(OS) 그대로 같은 batch** — `ip_only`·따로 부르기 둘 다 택하지 않았다. 예보는 batch 밖(weather-here 직접) | batch 는 가장 느린 호출을 기다린다. `location` 의 긴 대기(권한 창 25초 + 위치 8초)는 **위치 권한을 아직 정하지 않았을 때만**, itda-hyve 프로세스당 한 번 생긴다(`location/os_darwin.go` 판독 — 두 번째부터는 창 없이 바로 IP). 권한이 정해진 뒤에는 10분 안의 OS 위치면 즉시, 아니면 8초 상한, 결과는 10분 캐시 — 메일 수집(첫 로그인 최대 6.5초, itda-hyve#21 실측)과 겹친다. **따로 부르면** 매일 바퀴 하나가 늘어 모델 대기(0.6.0 실측 72초·33초)가 돌아오고, **`ip_only` 로 바꾸면** 매일 시·도부터 틀릴 수 있다(#37 — 대전 KT 회선이 성남). 첫 회차 30초 남짓은 사용자가 권한 창에 답하는 시간이기도 하다. 예보는 좌표가 `location` 결과에 달려 한 batch 에 못 넣는다 — weather-here 의 기본(샌드박스 직접, 2026-09-28 Cowork 실측 성공)으로 받고 막히면 `http_request` 한 번. 본문은 snippet(200·500자 시간이 같아 300자)으로 쓰고 snippet 이 없는 메일만 예외 바퀴의 `imap_fetch` |
| D18 | 한 모양(두 밴드·640px 한 단) | **보고서 스타일 4종**(`render.py --style`): `timeline`(기본 — 세로 시간축, 길이 비례 블록, 1시간 이상 빈 시간, 관련 메일은 일정 옆) · `memo`(결재 메모) · `desk`(지표 띠·표) · `print`(A4 두 단). ② 일정별 관련 메일은 따로 절이 아니라 **그 일정 곁**에 붙는다. 시안 D(카드형)는 넣지 않았다 | 사용자 결정(2026-09-29, itda-work/skills#42) — 시안 5종 중 C 를 기본, A·B·E 를 옵션으로. 모양은 사용자 발화에서 **후보를 읽기 전에** 고른다. 네 스타일은 같은 조각 함수(일정 제목·관련 메일 목록·미회신 항목·대량 발송·출처)를 다른 자리에 놓을 뿐이라 `data-mb-*` 표지와 내용이 같고, verify 는 스타일과 무관하게 같은 검사를 한다(`style-declared` 만 추가). 웹 폰트는 여전히 싣지 않는다(D6) |

## 상류 반증 대조

| 회차 | 상류 리비전·판 | 대조한 것 | 결과 |
|---|---|---|---|
| 2026-09-03 | 2026-09 판(#1638 첫 코멘트) | 최초 차용 — 전 절 대조 | 위 D1~D13 으로 갈랐다. 상류에 반증 기록(empirical validation) **없음** |
| 2026-09-28 | (상류 대조 아님) | 사용자 피드백으로 구성 변경 | D16 — 상류의 지형·세 마디·두 목록을 걷어냈다. 상류 판 대조는 하지 않았다 |

상류가 개정되면 이 표에 줄을 더한다. **상류 문구가 우리와 다르다는 이유만으로
되돌리지 않는다** — divergence 표의 사유가 무너졌는지를 먼저 본다.

## 정정 이력

- **2026-09-29 · 옛 itda-hyve 멈춤·미리보기(#43, 0.12.0)** — 판단:
  - **페이지 한 줄 안내(0.10.0)를 버리고 그리지 않는다** — 옛 판으로 그린 브리핑은 받은 메일이 비어 쓸모가 없고, 사용자는 업데이트 뒤 한 번 더 만든다.
    멈춤은 gather(exit 4, candidates 미작성)가 정본이고 render 거부는 옛 gather 가 남긴 candidates 를 막는 2차 선이다.
  - **판이 1차, 거부가 2차** — `accounts_list` 최상위 `server_version` 은 0.9.5 도 주므로(itda-hyve#26 계약) 판으로 먼저 가른다. `X.Y.Z` 로
    시작하지 않으면 판으로는 판정하지 않고 거부(`snippet_for`)로만 가른다 — 모르는 것을 옛 판으로 단정하면 새 서버가 멈춘다.
  - **브라우저로 열기는 기능 목록으로** — `server_features` 에 `open_file` 이 있을 때만(0.10.1+). 판 번호로 추측하지 않는다. 그 정보는
    `gather --out` 의 상태 줄로 모델에 준다 — candidates 에 실으면 골든·verify 가 서버 판에 묶인다.
  - **show_widget 은 쓰지 않는다** — verify 가 본 파일과 다른 것을 보여 줄 수 있다. 미리보기는 파일 공유(present_files) 하나로, 그것이 안 되면 사용자 동의 뒤 브라우저.
- **2026-09-29 · 보고서 스타일 4종(#42, 0.11.0)** — 기본 모양을 세로 시간축(시안 C)으로 바꾸고 보고서(A)·표(B)·인쇄용(E)을 `--style` 로 더했다. 판단:
  - **「일정별 관련 메일」 절을 없앴다** — 네 시안 모두 관련 메일을 일정 곁(옆·아래·하위 행)에 둔다. 절이 따로 있으면 같은 일정 이름을 두 번 읽는다.
    verify 는 원래 관련 메일 수·빈 줄(`data-mb-empty="related"`)만 봤으므로 계약이 그대로 선다(빈 줄은 일정 절 안으로 옮겼다).
  - **순서는 candidates 그대로** — 타임라인이 시각순으로 다시 정렬하면 계정 배지 순서(verify ①-account-badges)가 스타일마다 갈린다. gather 가 이미
    종일 먼저·시작 시각순으로 정렬하므로 다시 정렬하지 않는다.
  - **취소된 일정은 시간을 차지하지 않는다** — 빈 시간은 가장 늦게 끝난 일정부터 잰다(겹친 일정 포함). 취소 일정 앞뒤로 나눠 보여 주되
    빈 시간을 줄이지 않는다(골든: 13:00 빈 2시간 → 15:00 취소 → 15:00 빈 1시간 → 16:00).
  - **스타일은 content 와 무관** — 요약은 한 번 쓰고 모양만 바꿔 다시 그린다. 스타일마다 다른 문장을 쓰게 하면 verify ② 의 1:1 이 스타일 수만큼 는다.
  - **폰 너비** — 표 스타일은 가로 스크롤 상자 대신 좁은 화면에서 행을 블록으로 접는다(시안 B 는 `min-width: 620px` 표를 좌우로 밀었다). 400px 이상 고정 폭 0 을 테스트가 고정한다.
    aside 로 1100px·400px·다크(`data-theme="dark"`)를 네 스타일 모두 눈으로 확인했다(Cowork 는 여전히 `INCONCLUSIVE`).

- **2026-09-29 · 미리보기는 사람 메일에만(itda-work/itda-hyve#22, 0.10.0)** — 0.9.5 Cowork 실측에서 batch 9.6초 중 Gmail 받은편지함 45통 + snippet 이 7.6초였고
  그 대부분이 대량 발송이었다. itda-hyve 0.9.6 `snippet_for: "non_bulk"` 로 서버가 `bulk` 표지·noreply 류 발신 메일의 본문을 받지 않는다. 판단 셋:
  - **서버 판정이 정본** — 건너뛴 메일(`snippet_skipped`)은 스킬이 무조건 대량 발송으로 둔다. 서버 noreply 는 보낸 사람 **중 하나**를 보고 스킬 규칙은 첫 주소만 본다 —
    규칙을 맞춰도 표본 하나(두 주소 From)에서 갈린다. 두 규칙을 같게 유지하는 것보다 "건너뛰었으면 후보 아님" 한 줄이 구조적으로 닫힌다. 모르는 사유도 같다.
    itda-hyve 보고서는 스킬 규칙을 `NOREPLY_LOCALPARTS`(전체 일치)로 적었지만 0.7.0 부터 부분 문자열(`NOREPLY_TOKENS`)이라 서버 쪽이 부분집합이다
    (`test_server_noreply_rule_is_inside_the_skill_rule`).
  - **옛 서버는 업데이트 안내, 대체 경로 없음** — 0.9.5 는 모르는 인자를 호출 단위 `invalid_input` 으로 거부한다(`batchtool.Adapt` 의 `DisallowUnknownFields`).
    인자를 빼고 다시 부르면 동작은 하지만 느린 경로가 조용히 굳는다. 거부를 `hyve_outdated` 로 읽어 페이지가 할 일을 말한다.
  - batch 스키마로 0.9.5·0.9.6 을 가를 수 없어(`snippet_for` 는 `imap_search` 인자) 보장은 배포 순서다 — 플러그인 CHANGELOG 의 요구 판을 0.9.6 으로 올렸다.

- **2026-09-29 · 대량 발송 메일을 메일 계정별로(#41, 0.9.0)** — 사용자 요청: 업무용·개인용 메일 계정이 섞여 있어 한 목록으로는 어느 계정의 메일인지
  모른다. 판단 셋:
  - **계정 소절은 메일 계정이 둘 이상일 때만** — 기준은 대량 메일이 있는 계정 수가 아니라 `roles.email.accounts` 수다. 두 계정 중 한쪽에만 대량 메일이
    있어도 소절 머리를 둬야 "그 계정 것" 임을 안다. 하나면 머리는 소음이라 예전 모양 그대로(샘플도 하나).
  - **발신자 상한은 계정마다** — 한 계정의 뉴스레터가 다른 계정 발신자를 밀어내지 않는다. 같은 발신자(같은 뉴스레터를 두 계정으로 구독)도 계정마다 따로 선다.
  - **②·③ 에 계정 배지** — 같은 사람이 보냈어도 어느 계정으로 왔는지가 답장할 계정을 정한다. 이름만(앵커의 `account`) 싣고 주소는 출처 절에 맡긴다.
    계정 소절의 주소도 `--no-sources` 에서는 뺀다 — 그 모드는 공유용 노출 축소이고 본문 `@` 0 이 계약이다(`test_no_people_section`).
  - candidates `email.bulk.groups`(0.7.0)는 `email.bulk.accounts[].groups` 로 옮겼다. 전체 `count`·`kinds` 는 계정 값의 합이고 verify 가 대조한다.

- **2026-09-29 · 수집을 batch 한 번으로(#40 할 일 1, 0.8.0)** — itda-hyve 0.9.5(itda-work/itda-hyve#21)의 batch `account: "*"`(계정마다 펼침, `save_as`
  의 `{n}`)와 `imap_search` `include_snippet` 으로 0.6.0 의 batch 세 번(① 계정·위치 ② 일정·메일·예보 ③ 미회신 본문)을 한 번으로 줄였다. 0.6.0 Cowork 실측의
  바퀴 사이 모델 대기 72초·33초와 첫 not_found 재시도가 이 구조에서 나왔다. 판단은 D17:
  - `location` 을 같은 batch 에 정밀(OS) 그대로 넣었다 — 긴 대기는 권한 미결정 첫 회차뿐이다(itda-hyve 보고서의 "34초" 는 번들이 아닌 테스트 바이너리라
    권한이 늘 미결정이었던 경우다). `ip_only`(정확도 손실 매일)·따로 부르기(바퀴 하나 매일)보다 싸다.
  - 예보는 batch 밖으로 — 좌표 의존이라 한 batch 에 넣을 수 없다. #38 에서 "샌드박스 네트워크에 기대지 않는다" 로 둘째 바퀴에 넣었던 것을 뒤집는다.
    근거는 weather-here 의 2026-09-28 Cowork 실측(Open-Meteo 응답)과 실패 시 `http_request` 한 번의 대체 경로다. `shared/netbridge.md` 의 "샌드박스는 무인증 API 도
    막힌다" 서술과 어긋나므로 **Cowork 재실측 항목**이다 — 막히면 매 회차 도구 호출이 하나 느는 것이지 날씨가 틀리는 것은 아니다.
  - 요약 재료를 1000자 본문에서 300자 snippet 으로 줄였다(itda-hyve 실측: 200·500자 시간이 같다 — 비용은 통당 왕복). snippet 이 없는 메일만 예외 `imap_fetch`.
    `snippet_truncated` 는 흔하다(google 50/50) — 그것으로 본문을 받으면 예외가 기본이 된다. 후보에 `body_partial` 로 남기고 모델은 앞부분으로 알 수 있는 것만 쓴다.
  - `{n}` 은 `accounts_list` 순번(건너뛴 계정도 번호를 차지)이라 `accounts.json` 순번과 같다 — 파일 이름 계약(`inbox-<n>.json`)을 바꾸지 않았고,
    순서가 어긋나면 파일 안 `account` 대조(`account_mismatch`)가 잡는다. 캘린더 미지원 계정의 `skipped` 는 실패가 아니다(SKILL 1-2).

- **2026-09-29 · 자동 발송 판정 보강·대량 발송 메일 절·계획 파일 확정 쓰기(#40, 0.7.0)** — 0.9.4 + 0.6.0 Cowork 실측(4분 36초)에서
  bulk 표지 메일 35통은 빠졌지만 **표지 없는 자동 메일**이 「미회신」 에 남았다: Firebase `firebase-noreply@`, NHN KCP(표시 이름 「발신전용」,
  `pgadmcust@`), 쿠팡 결제 `easypay_noreturn@`, Apple `no_reply@`, Replicate `billing@`, AliExpress `@notice.aliexpress.com`.
  - 0.6.0 의 noreply 규칙은 **로컬파트 전체가** 목록과 같을 때만 걸렸다 — `firebase-noreply`·`easypay_noreturn` 은 앞뒤에 다른 말이 붙어
    빠졌다. 이제 구분자를 지운 로컬파트 **어디에든** `noreply`·`noreturn`·`donotreply`·`mailerdaemon` 이 있으면 잡는다.
  - 국내 PG·카드사는 로컬파트가 사람 이름 같은 코드다(`pgadmcust`) — **표시 이름**(「발신전용」·「회신불가」·no-reply)을 본다.
  - 역할 주소·발송 서브도메인은 **약한 표지**다: 사람도 `billing@`·`@mail.회사` 로 쓴다. 그래서 **아는 상대**(최근 30일 보낸편지함의 받는 사람·
    참조, 계정 무관)면 사람 메일로 둔다(사용자 결정 — 「미회신」 은 사람 메일만, 처음 보는 자동 발신은 대량 발송 절로). 강한 표지(광고 표지·
    대량 발송 헤더·noreply 류·「발신전용」)는 아는 상대여도 덮지 않는다 — 답장할 수 없는 주소다.
  - 역할 목록에서 support·info·help·contact·sales·team·admin 은 **뺐다**. 사람이 받아 답하는 공용 창구라 그리로 온 메일은 답을 기다리는 메일일
    수 있다(지우는 쪽 오류는 사용자가 못 알아챈다 — `upstream-fork-evidence-sync` 의 판별법과 같은 결).
  - 발송 서브도메인은 도메인이 **세 마디 이상**일 때만 본다 — `@email.com`·`@mail.net` 같은 두 마디 도메인은 일반 메일 서비스다.
  - **대량 발송 메일 절**(사용자 결정): 「뉴스레터·알림 N통」 한 줄을 종류(뉴스레터·자동 알림·결제·청구·광고) → 발신자 → 제목 목록으로 바꿨다.
    모델 요약은 없다 — 스크립트가 candidates `email.bulk.groups`(0.9.0 부터 `email.bulk.accounts[].groups`)로 만들고 render 가 그린다. 발신자마다 종류 **하나**(다수 종류)다 — 메일마다
    가르면 같은 콘솔의 로그인 알림과 「결제 계정」 알림이 두 줄로 쪼개진다. 「발신전용」 처럼 누군지 말하지 않는 이름은 도메인을 곁들인다.
  - **첫 not_found**: 실측 첫 batch 가 `not_found` 로 한 바퀴(약 100초 중 일부)를 날렸다. 원인은 로그에서 확정하지 못했다 — 계획 파일이 호스트에
    보이기 전에 부른 것, 또는 `HOST_IN` 이 입력 폴더와 다른 곳을 가리킨 것 두 후보를 함께 닫는다: `write_plan` 이 임시 이름 → fsync → 이름 바꾸기
    → 폴더 fsync → 다시 읽어 대조한 뒤에만 경로를 내고, `--input` 과 `--save-dir` 의 마지막 이름이 다르면 `save_dir_mismatch` 로 멈춘다(NFC 로
    맞춰 비교 — macOS 는 「클로드 실습」 같은 한글 이름을 NFD 로 돌려줄 때가 있다). 격리 가드는 `os` 를 fsync·open·close·O_RDONLY 로만 허용한다.

- **2026-09-29 · 계획 파일(plan_file)·대량 메일 표지(#39, 0.6.0)** — 0.5.0 Cowork 재실측(itda-hyve 0.9.3)이 전체 약 2분 40초였다.
  도구 시간은 8초로 줄었는데 ① 1→2바퀴 사이 84초 — 모델이 `--plan` 의 호출 9개를 batch 인자로 **다시 출력**했다 ② 정리 45초 — 무관 미회신
  12통 대부분이 뉴스레터·결제 알림·프로모션이라 그 요약을 쓰는 데 시간이 갔다. itda-hyve 0.9.4(itda-work/itda-hyve#17)의 두 기능으로 닫는다.
  - `--plan` 은 batch 인자를 입력 폴더의 `plan-<k>.json` 으로 쓰고 **`{"plan_file": <호스트 경로>}` 한 줄만** 낸다. 모델은 그것을 batch 에
    그대로 준다 — 출력은 호출 수와 무관하게 경로 하나다. 파일은 입력 폴더 안·숨김이 아닌 이름(itda-hyve 는 숨김 이름·심볼릭 링크를 거부),
    내용은 batch 인자와 같은 JSON(`calls`·`save_dir`·`overwrite`·`timeout_sec` — itda-hyve 가 모르는 필드를 거부하므로 그 밖을 싣지 않는다).
  - `imap_search` 의 `bulk`·`bulk_reason` 으로 대량 메일을 ③·요약에서 빼고 「뉴스레터·알림 N통」 한 줄(종류별 수)로 센다. 종류는
    `Auto-Submitted` → 자동 알림, List-Id·List-Unsubscribe·Precedence → 뉴스레터. 헤더가 없는 것은 보낸 사람(noreply 류 — 이 판에서
    `notification(s)`·`notify`·`newsletter`·`mailer-daemon` 을 더했다)과 제목 첫머리 「(광고)」(정보통신망법 제50조 ④ 의 법정 표지 — 헤더 없는
    네이버 발 광고도 이것은 단다)로 보완한다. 0.5.0 의 "List-Id·Precedence 가 없어 대량 메일은 noreply 주소로만"(아래 0.3.0 약점 ②)이 풀렸다.
  - **② 에서 대량 메일은 주소로 이어질 때만 붙는다**(판단). 참석자·주최자가 메일링 리스트로 보낸 안내는 그 자리의 준비일 가능성이 크지만,
    제목 키워드만 맞는 뉴스레터("이번 주 계약서 작성 팁" ↔ "계약서 초안 검토 회의")는 우연이다. 붙은 대량 메일은 회신 판정 대신
    "단체 발송" 으로 보인다(리스트 공지에 「미회신」 을 달면 답장을 재촉하는 셈이다). 0.5.0 은 noreply 메일을 ② 에서 통째로 뺐다.
  - 대량 메일은 `exclusion` 에서 `not_addressed` 보다 **먼저** 판정한다 — 리스트 주소로 온 뉴스레터가 「참조 수신」 경고 수에 섞이지 않는다.
  - `bulk` 필드가 없는 응답(0.9.3 이하)은 헤더 판정 없이 보낸 사람·제목 규칙만 쓴다(하위 호환). 다만 `plan_file` 이 없는 판에서는 수집 자체가
    멈추므로 최소 요구는 **0.9.4** 다 — batch 입력 스키마에 `plan_file` 이 있는지로 가른다(도구 이름은 같다).

- **2026-09-28 · 새 구성과 batch 수집(#38, 0.5.0)** — Cowork 0.9.2 실측에서 도구 호출 23회가 연결을 거치며 하나씩 처리돼
  (수집 약 35초 + 바퀴 사이 모델 대기) 느렸고, 브리핑이 러프했다. itda-hyve 0.9.3 의 `batch`(읽기 호출을 서버 안에서 동시에, 결과는
  호출마다 `save_as`)와 `imap_fetch` `uids`(같은 메일함 여러 통을 한 호출)로 수집을 **batch 2~3번**으로 바꿨다(실계정 묶음 22.7초 → 2.0초,
  itda-work/itda-hyve#15). 구성은 D16. 되돌리지 마라 — 되돌리면 호출 수가 다시 계정 수에 비례한다.
  - candidates·content 계약을 **schema_version 2** 로 올렸다(옛 판 candidates 는 `render.py` 가 `candidates_schema_version` 으로 거부).
  - 일정–메일 잇기: `calendar_events` 의 `organizer`·`attendees`(0.9.3)를 쓴다. 0.4.0 까지 "itda-hyve 는 주최자를 주지 않는다" 는
    한계로 prep 을 "참석자 없는 내 일정" 으로 좁혔는데, 이 판에서는 prep 자체가 없어졌다. 옛 서버(참석자 목록 없음)는 `attendees_missing` 결손.
  - 날씨: 위치를 IP 서비스 한 곳(`http_request` ipapi.co)에서 itda-hyve `location`(OS 위치 → IP 합의, #37)으로, 예보도 batch 둘째 바퀴의
    `http_request` 로 받아 샌드박스 네트워크에 기대지 않는다. 요청은 weather-here `build_params` 와 같다(테스트가 대조).
  - batch `timeout_sec` 50 — Cowork 가 도구 호출 하나를 60초에서 끊기 전에 batch 가 돌려주게.

- **2026-09-28 · 수집 경로를 itda-hyve 로(#18, 0.3.0)** — 0.2.0 의 `gather.py` 는 형제 스킬
  스크립트(calendar `check_env.py`·`list_events.py`, email `check_env.py`·`thread_status.py`)를
  subprocess 로 돌렸고, 그 스크립트들은 환경변수·`.env` 의 계정 비밀번호로 IMAP·CalDAV 에 **직접**
  붙었다. itda-hyve 원칙(키는 itda-hyve 볼트에만, Claude 는 값을 못 본다)과 어긋나고, calendar 역할은
  매 대화 `caldav`·`icalendar` 설치가 먼저여야 했다. 파이썬은 MCP 도구를 부를 수 없으므로 dart 의
  `--input` 패턴으로 갈랐다 — **수집은 LLM 이 itda-hyve 도구로, 판정은 스크립트가**.
  - 판정 규칙은 옛 `thread_status.py` 를 itda-hyve 요약 필드 위에 다시 썼다(창 2일·발신함 30일,
    union-find 스레드, fail-closed). 요약에 없는 필드 때문에 **세 곳이 약해졌다**: ① 참조(CC)가 없어
    받는 사람(To)에 내가 있는 메일만 모집단 ② List-Id·Precedence 가 없어 대량 메일은 noreply 주소로만(0.6.0 에서 풀림 — 위)
    ③ 그룹 판정은 받는 사람 수로만. 약해진 쪽은 **후보를 덜 올리는 방향**이고, 참조 수신은 경고로 센다.
  - itda-hyve `calendar_events` 는 주최자를 주지 않는다 — `prep` 을 "주최자 = 내 계정" 에서
    "주최자를 알면 그것, 모르면 **참석자가 없는** 내 일정" 으로 바꿨다. 참석자가 있는 회의는 남이 연
    자리와 가를 수 없어 올리지 않는다(D9 — 약한 앵커는 뺀다). itda-hyve 가 주최자를 주는 판이 오면
    코드가 자동으로 그쪽을 쓴다.
  - 네이버는 반복 일정을 펼치지 않는다(마스터 + `rrule`). 옛 경로는 calendar 스크립트의 icalendar
    전개에 기댔다 — stdlib 로 DAILY·WEEKLY·MONTHLY·YEARLY 부분집합을 펼치고, 못 읽는 규칙은
    `recurrence_unsupported` 로 표면화한다. EXDATE 는 응답에 없어 반영 못 한다.
  - `sibling_deps_missing` 처방·`--siblings-dir`·동봉 `siblings/` 경로·subprocess 예산·프로세스 그룹
    정리를 걷어냈다. 되돌리지 마라 — 되돌리면 `.env` 비밀번호 경로가 살아난다.

- **2026-09-03 · T1 실계약 반영(#1638)** — 초판 `gather.py` 는 세 곳이 계약과 달랐다.
  ① 에러 봉투 키를 `code` 로 알고 `status:"error"` 본문을 통과시켰다(실제 키는 `error`).
  ② `--account` 를 `default` 가 아닐 때만 붙였다 — 다계정에서 그 호출은 **exit 2** 다.
  ③ `thread_status` 의 `warnings` 를 전부 `severity: "warning"` 으로 접어
  `sent_folder_not_found`(회신 판정 전건 실패 → 후보 0)가 **조용한 빈 목록**이 됐다.
  ③ 때문에 `severity` 에 `degraded` 를 신설하고 render·verify 가 그것도 한 줄로
  말하게 했다. 되돌리지 마라 — 후보 0 과 "판정을 못 해 0" 은 다르다.

규칙을 강등·조건부화·삭제할 때는 여기에 **무엇이 왜 틀렸는지**를 남긴다.
조용히 고치면 다음 사람이 상류 원문을 보고 되돌린다.

## 동기화 절차

1. 상류 `morning` SKILL.md 의 현재 판을 구해 #1638 첫 코멘트의 보존본과 diff 한다.
2. 바뀐 절이 위 divergence 표의 어느 줄에 걸리는지 본다.
   - 걸리지 않는 새 규칙 → 우리 문장으로 채택 검토.
   - 걸리는데 상류가 근거를 새로 댔다면(반증·실측) → 우리 D 항목의 사유가 아직
     성립하는지 재확인하고, 무너졌으면 **정정 이력**과 함께 바꾼다.
3. 상류 판 날짜와 대조 결과를 위 **상류 반증 대조** 표에 한 줄 추가한다.
4. `verify.py` 가 집행하는 축을 바꿨다면 뮤테이션으로 RED 를 실측한다.

## 구조

```
scripts/gather.py    --plan: batch 계획 파일(plan-<k>.json) + plan_file 한 줄 / --input: 저장된 응답 폴더 → candidates.json(v2)
scripts/render.py    candidates.json(목록) + content.json(요약 문장) → 단일 파일 HTML(`--style` timeline·memo·desk·print)
scripts/verify.py    ①~⑨ 정적 검증. exit 0/1, 판정 JSON
tests/               itda-hyve 응답 형태 픽스처로만 돈다(네트워크·실계정 0)
tests/fixtures/hyve_input/  도구 응답 픽스처(`@sample.example.com` 만)
tests/fixtures/golden/      종단 골든 3종(candidates·content·brief.html) — hyve_input 에서 만든다. 스타일 스냅숏 brief-{memo,desk,print}.html
tests/fixtures/golden-empty-day/  일정 0건 날 골든 — hyve_input + hyve_input_empty_day 덮어쓰기
tests/fixtures/golden-sample/     샘플 시드 골든
```

외부 의존 없음(stdlib only) — `requirements.txt`·`deps.json` 을 두지 않는다. `gather.py` 는
`subprocess`·네트워크 모듈을 들여오지 않고, `os` 는 계획 파일 fsync(`fsync`·`open`·`close`·`O_RDONLY`)에만 쓴다(테스트가 AST 로 고정, #40).

### 입력 폴더 계약 (`--plan` 이 이름을 정한다)

파일은 **itda-hyve 가 직접 쓴다** — `--plan --save-dir <입력 폴더의 호스트 경로>` 가 바퀴마다 batch 인자(40개씩 나눔)를 입력 폴더의
`plan-1.json`(`plan-2.json` …)으로 쓰고 stdout 에는 `{"status": "pending", "batch": [{"plan_file": "<호스트 경로>/plan-1.json"}]}` 한 줄만 낸다
(끝났으면 `{"status": "complete", "batch": []}` 이고 계획 파일을 쓰지 않는다). 계획 파일은 batch 수준 `save_dir`·`overwrite: true`·
`timeout_sec: 50`, 호출마다 `save_as` 를 싣는다. 모델은 `batch({"plan_file": …})` 로 부르고 호출별 요약만 받는다(itda-hyve 0.9.4,
itda-work/itda-hyve#17). 계정별 호출은 `account: "*"` + `save_as`·`id` 의 `{n}` 으로 itda-hyve 가 계정마다 펼친다(0.9.5, itda-work/itda-hyve#21) —
`{n}` 은 `accounts_list` 순번이라 아래 `<n>` 과 같다. 저장 파일은 **저장하지 않고 받은 응답과 같은 구조·같은 바이트**다(itda-work/itda-hyve#10). 호출 `id` 는 `save_as` 에서
`.json` 을 뺀 것이라 실패 기록(`$IN/<id>.json`)의 이름이 된다. `--save-dir` 가 없으면 `save_dir_required`, `--input` 이 묶음 파일이면 `plan_needs_folder`.

계정은 이름 대신 `accounts.json` 의 **순번**(1부터)으로 가리킨다. 파일 안의 `account` 가 그 순번의 계정 이름과 다르면 `account_mismatch`.

바퀴: **한 번** — `accounts_list`·`location`·`calendar_events` `"*"`·`imap_search` INBOX `"*"`(snippet)·`imap_search` `\Sent` `"*"`(#40). 예외 바퀴: 빠진 계정별 파일(계정 이름으로),
③ 목록 중 snippet 이 없는 메일의 `imap_fetch` `uids`.

| 파일 | 도구 · 인자 | 쓰는 필드 |
|---|---|---|
| `accounts.json` | `accounts_list` | `accounts[].name`·`email`·`calendar.supported` |
| `location.json` | `location`(날씨 절이 있고 `--weather-place` 가 없을 때) | `source`·`lat`·`lon`(0.05° 격자) — 판정은 weather-here `--geo-input` |
| `weather-forecast.json` | (예외) 샌드박스에서 Open-Meteo 가 실패했을 때만 모델이 `http_request` 한 번(weather-here `--weather-request` 인자) | weather-here `--weather-input` |
| `calendar-<n>.json` | `calendar_events` 오늘 00:00 ~ 내일 00:00(+09:00), `expand: true`, `limit: 1000` | `events[]`(`uid`·`calendar`·`summary`·`start`·`end`·`all_day`·`status`·`location`·`rrule`·`recurrence_id`·`has_attendees`·`organizer{email}`·`attendees[{email}]`·`attendees_truncated`)·`errors[]`·`truncated` |
| `inbox-<n>.json` | `imap_search` INBOX, `since` = 오늘 −2일, `limit: 200`, `include_snippet: 300` | `messages[]`(`uid`·`date`·`from`·`to`·`subject`·`message_id`·`in_reply_to`·`bulk`·`bulk_reason`·`snippet`·`snippet_truncated`)·`total_matched` |
| `sent-<n>.json` | `imap_search` `mailbox: "\Sent"`, `since` = 오늘 −30일, `limit: 200` | 같음 + `special_use` |
| `bodies-<n>.json` | (예외) `imap_fetch` INBOX `uids`(③ 목록 중 snippet 이 없는 메일만, 계정당 한 호출), `max_body_chars: 1000` | `messages[].uid`·`text`, `errors[]` — 있으면 snippet 보다 먼저 |
| `section-날씨.txt`·`section-환율.txt` | 형제 스킬 `weather-here`(`--geo-input location.json`, 실패 때 `--weather-input weather-forecast.json` 또는 지역명)·`exchange-rate` 출력 | 평문 |

도구 실패는 같은 이름에 `{"error": {"code","message"}}`(batch `results[].error` 를 모델이 쓴다). 파일이 아예 없으면 `input_missing`.
`--input` 은 폴더 대신 `{"<파일 이름>": <내용>}` 묶음 JSON 한 개도 받는다.

### 일정–메일 잇기 규칙 (#38)

- **주소가 먼저** — 받은 메일의 보낸 사람·받는 사람·참조(있으면)에서 내 주소를 뺀 것과, 일정의 주최자·참석자(내 주소 제외)가 겹치면
  `organizer`/`attendee`. 주소는 `mailto:` 제거·소문자·`+태그` 제거로 정규화한다(itda-hyve 는 대소문자를 서버 원문 그대로 준다).
- **다음으로 제목 키워드** — 일정 제목의 두 글자 이상 단어(숫자만·흔한 말 제외)가 메일 제목에 있으면, 세 글자 이상 하나 또는 두 글자 이상
  둘일 때만 `keyword`. 두 글자 한 단어("설계")로 이으면 무관한 메일이 딸려 와서다. 흔한 말 목록은 `gather.KEYWORD_STOPWORDS`.
- 대량 메일(`gather.bulk_kind` — `bulk: true`·제목 「(광고)」·noreply 류 보낸 사람)은 **주소로 이어질 때만** 잇고(키워드로는 잇지 않는다)
  판정을 `bulk`("단체 발송")로 싣는다. 내가 보낸 메일(받은편지함의 내 메일)은 잇지 않는다.
- 한 스레드가 어느 일정에 이어지면 그 스레드는 ③ 에 오지 않는다. 같은 메일이 두 일정에 걸리면 두 곳에 다 보이고 출처는 하나다.

### 보낸편지함 창·References 결정 (#34)

- **`include_references` 를 끈다.** 판정은 `message_id`·`in_reply_to` 로 한다(itda-work/itda-hyve#9 결정). 그 이슈의 실계정 표본에서
  References 가 있는 메일은 naver 0/50·google 0/50·icloud 3/50·daum 5/36 이었고 시간 차이는 오차 범위였다. 끄면 잃는 것은 중간 메일이
  수집 집합 밖인 스레드의 연결뿐이다(그때 오류는 이미 답한 스레드가 「지금 필요한 일」로 오는 한 방향).
- **보낸편지함 30일·200통을 유지한다.** save_as 로 응답이 모델 맥락에 들어오지 않아 창 크기는 토큰 비용이 아니다. 남는 비용은
  서버 시간인데 그것은 창이 아니라 `limit` 이 상한이다(네이버 ENVELOPE 약 45ms/통 → 200통 약 9초, 전송 경로 60초 안). 창을
  줄이면 오래전에 답한 스레드의 새 회신이 `replied_then_new` 대신 `unreplied` 로 뒤집히고, References 를 끈 지금은 직계 부모가
  수집 집합에 있어야 스레드가 이어지므로 보낸편지함까지 줄이지 않는다. 200통을 넘으면 `sent_truncated` 경고가 남는다.
- 재측정 항목: Cowork 재실측에서 ② 바퀴의 소요(특히 네이버 보낸편지함 200통)를 잰다 — 전송 경로 60초에 가까우면 limit 을 다시 정한다.

### Sections 판단 (#18 → #33·#34 → #38)

| 절 | 외부 API | 키 | 판단 |
|---|---|---|---|
| 날씨 | Open-Meteo Forecast(`api.open-meteo.com`) + itda-hyve `location` | 없음 | 위치는 batch 안의 `location`(OS 위치 → IP 합의, #37 — IP 한 곳은 대전 KT 회선을 성남으로 잡았다). 예보는 **weather-here 가 샌드박스에서 직접**(#40 — 좌표가 location 결과에 달려 batch 한 번에 못 넣는다. #38 의 "둘째 바퀴 `http_request`" 는 바퀴를 하나 더 만들었다), 실패하면 `http_request` 한 번. 지역명을 말한 경우도 같은 순서 |
| 환율 | 서울외국환중개 매매기준율(`www.smbs.biz`) | 없음 | 현행 유지 |

#18 의 기준("키가 필요하면 itda-hyve 경로로, 아니면 현행 유지")대로 둘 다 현행을 유지했다. 달라진 것은
**누가 부르는가**다 — `gather.py` 가 subprocess 로 부르던 것을, LLM 이 형제 스킬 스크립트로 받아
`section-*.txt` 로 남긴다(`gather.py` 는 스크립트를 실행하지 않는다). ⚠️ `shared/netbridge.md` 는
"Cowork 샌드박스는 인증이 필요 없는 API 도 막힌다" 고 적고 있고 capability map §3.6·§3.8 은 PyPI·npm
도달을 기록한다 — 샌드박스에서 이 두 호스트가 닿는지는 **Cowork 실측 항목**이다. 막히면 그 절은
`section_missing` 경고로 빠지고(지어내지 않는다), 그때 itda-hyve `http_request` 경로를 검토한다.
