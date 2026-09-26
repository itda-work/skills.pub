# Changelog — itda-web-scout

## [0.2.1] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- L4 브라우저 후보·probe 표에서 hyve `web_browse` 를 지웠다. API 채집은 네트워크 요청을 읽을 수 있는 브라우저 도구가 있을 때만 하고, 없으면 `browser_only` 로 기록한다. `env_availability` 값에서 `hyve` 삭제.

## [0.2.0] — 2026-08-30 (hyve #1600, S8 runner)

### Added

- `scripts/run_playbook.py` — S8 반복 조회 runner(구현 리뷰 P1 "종단 경로" 해소): 플레이북 hit → `repeat_access` 단 재생(L1~L3 은 web-reader fetch, L4 는 `needs_browser`+`--l4-raw` 후처리) → 추출 레코드 저장 → 결과 5분류 → 회차 diff(신규·변경·소실·페이지 hash) → stale 제안 파일(플레이북 불변). 물리 요청 예산, auth 위치 typed 종결, exit 0/2.
- 라이브 종단 실측(2026-08-30, 보험 시드 4호스트): fss·kiri·insnews·kidi 재생 성공, 2회차 diff 0/0/0. **거짓 성공 실측 1건** — 보험연구원 CEO Brief 가 0건 `empty_valid` 로 나옴(제목이 `<p>`, 날짜가 `YYYY-MM`) → HTML 목록 구조 미인식 0건은 `no_dated_list` → `schema_drift` 로 반전, web-reader 에 월 단위 날짜·카드형 컨테이너 폴백 추가 후 10건 `fresh_nonempty`.
- AC5 첫 실측(2026-08-30): `export_targets` → `competitor-watch/profiles/insurance/targets.yaml`(distinct targets 7 · export_eligible pages 8) → runner 6호스트 재생 → `ingest_web_scout.py` 집계 — 대상 7·성공 7·신규 65·실패 0. 공시실 목록이 URL 미확보 9건으로 드러나 kpub 시드에 onclick js_link 패턴 추가(→ 0건).
- 시드: kidi `js_link` 패턴, kpub `js_link`(onclick goDetail), fss 소비자경보 `freshness_days` 추측값 폐기(발행 주기 불규칙 — 판정은 맞았고 시드가 틀렸다).

## [0.1.0] — 2026-08-30 (hyve #1600, 골격)

### Added

- 스킬 신설: 정보원 발견(S3 발견 프로브) → 접근 사다리(L1~L4, 전이표) → 축 4종 판정·파생 등급 → 플레이북(시드 읽기 전용 + 로컬 누적, 제안→확인→박제) → 내보내기 3종(프롬프트 팩·competitor-watch targets.yaml·등급표).
- `scripts/grade.py`(전이·등급·결과 분류·재현성 의미 비교, 순수 함수) · `playbook.py`(스키마 v1·위치 단위 병합·secret_ref 만·원자 갱신) · `probe_discovery.py`(web-reader fetch 재사용, JS 리다이렉트 최종 URL 재시도, install_gate) · `export_{prompt,targets,table}.py`.
- 보험 도메인 시드 플레이북 7종(2026-08-30 AC0 preflight 실측).
- 비목표: 보안모듈·공동인증서 설치(요구되면 그 경로는 없는 것으로), 비-GET 재생, 자동 박제.
- **범위 선언(구현 리뷰 P1 수용)**: 0.1.0 은 T0 + S3 발견 프로브 + 판정/저장/내보내기 **골격**이다. S4 사다리 실행·S8 플레이북 재생·재탐색 제안·회차 diff 를 잇는 runner 는 다음 버전(이슈 #1600 AC1·AC3·AC4·AC6 라이브).
- 구현 리뷰 반영: `empty_valid` 는 200 + 정상 진단일 때만(403/5xx 0건은 `schema_drift`) · `secret_ref` 식별자 문법·URL 쿼리 비밀 키·`headers` 값 전면 거부(`secret_ref:NAME` 만) · 프로브 예산을 물리 요청(trace)로 집계·origin 이탈 시 표준 위치 탐색 중단(`origin_changed`) · 피드 `<link>`/JSON-LD 를 파서로 처리, llms 판정 우선순위 버그 수정 · targets exporter 는 명시 `export_eligible: true` 위치만, queries 있는 C 조직 target 유지(AC5 distinct targets).
