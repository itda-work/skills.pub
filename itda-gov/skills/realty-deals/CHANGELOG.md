# Changelog — itda-realty/realty-deals

## [0.12.1] — 2026-09-27

### Changed

- `references/netbridge.md` 사본 동기화 — 설치 판정을 서버 이름 기준으로 — 도구 목록에 이름에 `itda-hyve__` 가 든 도구(Cowork `mcp__remote-devices__itda-hyve__*`, Claude Code `mcp__itda-hyve__*`)가 없을 때만 설치·업데이트 안내. 앞 문구는 Cowork 접두어만 조건으로 삼아 Claude Code 에 연결한 사용자에게도 재설치를 안내하게 했다(12.0.0 공개 전 리뷰 M1). 금지는 "다른 서버의 도구·내장 fetch" 로 한정.
- 옛 서버 이름 안내 제거 — compatibility 의 옛 이름 병기를 빼고 `references/netbridge.md` 사본을 정본과 동기화(옛 판 분기를 "itda-hyve 도구가 없으면 0.9.0 이상 설치·업데이트 안내" 한 갈래로).

## [0.12.0] — 2026-09-25 (itda-work/itda-hyve#6)

> **릴리스**: skills **11.0.0**(`skills-v11.0.0`, 첫 공개 저장소 `itda-work/skills.pub`)에 싣는다.
> 요구: **itda-hyve 0.9.0 이상** — 받는 곳 https://github.com/itda-work/itda-hyve.pub/releases/latest
> 도구 이름 접두어가 `mcp__remote-devices__itda-butler__*` → `…itda-hyve__*` 로 바뀌어, 0.8.x(itda-butler) 서버와 이 버전은 서로 동작하지 않는다.
> 모델이 막을 수 있는 경계가 아니라 배포 순서로 보장한다 — 위 주소에 itda-hyve 0.9.0 설치본이 올라온 것을 확인한 뒤에 `skills-v11.0.0` 태그를 단다.

### Changed

- MCP 서버 이름 `itda-butler` → `itda-hyve`(0.9.0). `allowed-tools`·본문 도구 지목·스크립트 안내문을 itda-hyve 로. `references/netbridge.md` 사본 동기화. compatibility 에 itda-hyve 0.9.0 이상, `save_dir` 거부 범위(홈 자체·`AppData`·`~/Library`)를 정본대로.
- GUIDE 「처음 설정하기」에 itda-hyve 받는 곳 링크. `references/netbridge.md` 사본 동기화 — itda-hyve 받는 곳 한 줄.

## [0.11.0] — 2026-09-23 (이슈 #1707)

### Changed (BREAKING — 사용 경로)

- **itda-butler 단일 네트워크 경로.** SKILL.md 가 `http_request` 를 직접 지시한다(정확한 URL·`params` 의 `serviceKey: {{secret:KO_DATA_API_KEY}}`·`LAWD_CD`·`DEAL_YMD`·`pageNo` 예시·`save_as`·`save_dir`). 저장은 **`save_dir` 에 Cowork 연결 폴더의 호스트 경로**를 넣고 샌드박스는 `$HOME/mnt/<폴더 이름>/<saved_path>` 로 읽는다(파일 `find` 절차 제거). 같은 이름 파일은 덮어쓰지 않으므로 페이지·월마다 이름을 달리 짓는다. `allowed-tools` 에 `mcp__remote-devices__itda-butler__http_request` 전체 이름을 적었다. `.env`·환경변수 키 해석 서술은 SKILL.md·GUIDE.md 에서 제거 — 키는 butler GUI 시크릿 탭에 **Decoding 키**로 등록한다.
- **`deals_cli.py` 는 파일 입력 전용이 됐다.** `collect --input <xml…>` 로 butler 가 `save_as` 한 응답을 읽어 정규화·요약한다. 네트워크 호출(`collect_deals_range`·`fetch_xml`)과 키 해석(`resolve_api_key`)을 제거했고, 정적 가드(`TestNoNetworkInScript`)가 재유입을 막는다. `--start-month`·`--end-month`·`--api-key` 인자는 사라졌다(월 범위는 butler 호출 쪽이 정한다).

### Added

- **전량 수집 대조를 산출에 싣는다** — `sources[]`(파일별 month·totalCount·page·item_count)·`months[]`(월별 totalCount ↔ collected)·`warnings[]`. 모자라면 `status: "incomplete"` 로 내린다(성공으로 말하지 않는다).
- `data_go_client.parse_response_xml()` — 저장된 응답 XML 을 읽는 공개 진입점(기존 `_parse_xml` 노출, 동작 동일).

## [0.10.0] — 2026-09-22 (이슈 #1707)

### Added

- **netbridge 경로 (#1707 파일럿)** — 네트워크가 막힌 환경(Cowork 샌드박스)에서 itda-netbridge `http_request` 로 직접 호출하는 절차를 SKILL.md 에 명시: `{{secret:KO_DATA_API_KEY}}` 자리표시자(`params` 전용), 12유형 서비스명 표, XML 성공 판정(`resultCode` 000 · 게이트웨이 `<OpenAPI_ServiceResponse>` 오류를 0건으로 접지 않음), 월×페이지 전량 순회와 `totalCount` 대조, 정규화 키 대응표, 호출 예산 안내.
- `references/netbridge.md` 동봉 — 정본 `skills/shared/netbridge.md` 사본(동기화 가드 `shared/tests/test_netbridge_doc_sync.py`).

## [0.9.8] — 2026-07-26 (이슈 #1284)

### Fixed

- 저장소 직접 실행용 PYTHONPATH 개발 부연 추가(배포본은 주입으로 불필요).

## [0.9.7] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.9.6] — 2026-07-26 (이슈 #1281·#1282)

### Changed

- 사전 요구사항의 `curl | sh`(astral.sh) uv 설치 블록 삭제 — 이 스킬은 표준 라이브러리만 쓰므로 설치 지시 자체가 불필요.
- `.env` 안내를 "Cowork에 연결한 작업 폴더" → "작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트)" 로 교체하고, 셸 환경변수·`~/.claude/settings.json` 의 `env` 경로를 병기.

## [0.9.5] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.9.4] — 2026-07-26 (이슈 #1275)

### Changed

- `deals_collector.py` 를 스킬 scripts/ 에서 플러그인 `itda-realty/shared/` 로 승격 (#1275) — 형제 스킬(jeonse-gap·price-stats)이 publish 주입으로 도달 가능해짐. 동작·공개 API 불변.

## [0.9.3] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.9.2] — 2026-05-21

### Changed

- `env_vars` frontmatter 블록 폐기 → SKILL.md body `## 환경 변수` 표로 이전. itda-setup·check_env_vars.py 의존성 제거.

## [0.9.1] — 2026-05-21

### Improvements

- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.
