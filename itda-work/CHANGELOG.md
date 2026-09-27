# Changelog

이 플러그인의 주요 변경 사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/), 버전은 [SemVer](https://semver.org/)를 따릅니다.

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
