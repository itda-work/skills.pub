# Changelog — imagegen

> 2026-06-16: `itda-egg/codex-image` → `itda-media/imagegen` 졸업 마이그레이션(SPEC-IMAGEGEN-002 P2). 이하 0.7.1까지는 codex-image 시절 이력.

## 1.0.0 (2026-09-29) — itda-hyve#8·#16

itda-hyve 에서 제거됐던 imagegen 을 **itda-doc/imagegen** 으로 되살린다. 생성 경로는 itda-hyve 의 에이전트 작업 도구(`accounts_list`·`agent_run`·`job_status`, recipe `codex.imagegen`)다.
codex 는 itda-hyve 가 설치·검증한 관리형 codex 만 쓴다(itda-hyve#16) — 사용자가 따로 설치한 codex 는 쓰지 않고, 설치·로그인은 itda-hyve 창의 에이전트 탭에서 한다(터미널 없음).

**배포 순서**: itda-hyve 0.10.0 설치본을 공개한 뒤에 배포한다 — 0.9.0 에는 `agent_run` 도 에이전트 탭도 없다. 옛 판 사용자는 `accounts_list` 의 `server_version` 으로 가려 업데이트를 안내한다.

### Changed

- 생성 경로를 `image.generate` 에서 `agent_run` + `job_status` 비동기 작업으로 바꾼다. 여러 장은 한꺼번에 넣고(계정당 3개 동시·나머지 대기열) `request_key` 로 재시도를 묶는다.
- `allowed-tools` 를 itda-hyve 도구 3개 + Read 로 되살린다(Cowork 전체 이름).
- 사전 점검에 `server_version`(0.10.0 미만이면 업데이트 안내)과 `accounts_list` 의 `agents[].logged_in` 을 넣는다 — `false` 면 생성 전에 GUI 로그인을 안내하고, 로그인이 풀린 채 부르면 작업이 `not_logged_in` 으로 곧바로 끝난다(모델 호출 없음).
- 참조 이미지는 `agent_run` 의 `inputs` 로 보내고 확인 단계(`needs_confirmation`)를 거친다.
- 카드 템플릿의 옛 codex 지시(“파일 경로만 한 줄로 보고”·`{출력파일}` 슬롯)를 걷어낸다.
- GUIDE.md 를 itda-hyve 에이전트 탭 기준으로 다시 쓴다(셸 명령 없음) — codex 설치 → 계정 추가 → 로그인(브라우저) 순서.
- codex 가 없으면(`accounts_list` 의 `available: false` 설치 사유 · `agent_run` 의 `not_found` "codex 가 설치되지 않음" · 작업의 `not_installed`) 에이전트 탭의 **codex 설치** 를 안내한다. `npm`·`brew` 설치는 안내하지 않는다.
- 트러블슈팅: `codex_exit` 중 설정 거부(`unknown configuration field`·`Error loading config`·`Unknown feature flag`)는 다시 해도 같으므로 되풀이하지 않고 itda-hyve 업데이트를 안내한다. `unknown_recipe`·작업 단계 `invalid_input`(프롬프트 64KB)·같은 `request_key` 다른 인자·`rate_limited`(`job_status` 만)·`io_error` 의 itda-hyve 작업 폴더 사유·`timeout` 상한(codex 4분, 작업 전체 약 9분)을 더한다. 확인 토큰이 묶이는 인자를 정확히 적는다.
- `references/netbridge.md` 를 공용 정본(에이전트 작업 도구 절 포함)과 맞춘다.

### Measured

- codex-cli 0.157.0 · itda-hyve 개발판으로 5종(blog-hero·slide-visual·video-illust·photoreal-portrait·poster) 1장씩 실측, 마스터 판정 통과. 카드마다 r 라운드와 썸네일을 더했다.
- poster 의 한글 제목 행사 변형(A)을 verified 로 올린다 — "봄꽃 축제"·"4월 5일 – 4월 7일" 철자 0오류.
- video-illust: 세로는 1024×1536(2:3)으로 나온다 — 9:16 은 잘라 쓴다. 인물 국적을 적지 않으면 서양인으로 나온다.

## 0.8.2 (2026-07-26) — 이슈 #1280·#1281·#1282·#1283

### Changed

- `allowed-tools` 필드 삭제 (#1283) — hyve image.generate MCP 소비 스킬인데 필터에 MCP 도구가 없어 강제 경로에서 호출이 소실될 수 있었다. 서버 등록명이 클라이언트마다 달라 실명 병기가 불가하므로 생략(전체 상속)으로 전환.

## 0.8.1 (2026-07-06)

- **MCP 온보딩 정본화 (hyve#921)** — 전제의 등록 안내를 폐지된 전체 `/mcp`+Bearer 에서 **hyve 설정 > MCP 탭의 문서(office) 프리셋 등록**(image 도메인 소속 프리셋, hyve#852·#887)으로 교체. stdio `hyve mcp` 는 개발·검증 전용 명시. itda-media README 동반 갱신.

## 0.8.0 (2026-06-16)

- **itda-media/imagegen 으로 졸업** — codex 직접 호출에서 **hyve `image.generate` MCP 소비**로 전환(길 X). SKILL.md 재작성, GUIDE.md MCP화(no-shell), 카드 템플릿의 codex 저장지시 라인 제거, _SCHEMA 작성지침 중립화.
- codex 전용 메커니즘 제거: `scripts/codex_imagegen_batch.sh`(병렬 배치) 삭제 — N장은 MCP N회 호출(병렬은 hyve/클라이언트 책임).
- 케이스 카드 9종·5층 공식·실사 우선·취향 프로필·실측 썸네일 보존(자산 폐기 아님). 측정 history(codex-cli 버전·병렬 기록)는 이력으로 유지.

## 0.7.1 (2026-06-13)

- **poster 텍스트 베이킹 한계 검증** (#343): 난이도 점증 5종 실측 — 한글 4줄 정보
  블록(콜론·숫자·괄호)·영문 3줄 단락까지 철자 0오류, 깨짐 임계 미발견. r1 잔여 가설
  "긴 카피·한글 장문 깨짐" 사실상 폐기
- 경로 A/B 분기 기준 개정: **길이가 아니라 통제 필요도**(폰트·오차0 계약·다버전 → B).
  _PATTERNS.md §5 / SKILL.md 글자 정책 동기화

## 0.7.0 (2026-06-13)

- **poster 스타일 자동 제안 레이어** (#337): 4축 의도 신호(장르·톤·청중·행동목표) →
  7 스타일 군집 매핑표 + 제안 프로토콜. 스타일 미지정 주제 5종 추론 검증 — 군집 5/5 별개,
  전부 의도 적합(캠페인=플랫그래픽/클래식=엘레강스/인디록=그런지/채용=스위스/호러=시네마틱)
- **저장소 스타일 정렬**: GUIDE.md 신설(형제 스킬 컨벤션), itda-egg README 입주 스킬 표 등록.
  PR #336 머지로 itda-egg 인큐베이션 정착 완료(`~/.claude/skills` symlink)

## 0.6.0 (2026-06-13)

- **poster 카드 신설 + 텍스트 렌더링 가설 검증 완료** (#329): codex image_generation 이
  영문(`THE LAST SIGNAL`)·한글(`서울 재즈 페스티벌`)·타이포(`FORM`) 짧은 1줄을 철자 0오류로
  렌더 — 구 "글자 거의 깨짐" 가정 폐기
- SKILL.md **글자 정책 재정의**: no-text 는 "불가능"이 아니라 *원치 않는* 글자 차단용
  기본값. 글자 필요 시 따옴표 명시 + "perfectly spelled" / 긴 카피는 존 비우기 후가공(B)
- 포스터 경로 분기: A(텍스트 베이킹, 짧은 1줄) / B(타이틀 존 비우기, 후가공) — 5/5 통과
- 트렌드 §6 의 Bollywood/movie 포스터 바이럴 대응 — 총 9케이스

## 0.5.0 (2026-06-13)

- 마스터 "일단 OK" 판정 → blog-hero·slide-visual·video-illust(실사 A)·photoreal-portrait
  **verified 승격** (첫 verified 4종) (#329)
- product-catalog 구체화 (r2, 5장 병렬): 멀티앵글 세트(C)·실존 제품 참조(D) 템플릿 +
  유리 재질 확장 검증
- **참조 이미지 입력 가설 검증 완료**: `codex exec -i` + image_generation 으로 첨부 제품의
  재질·구성 충실 재현(실루엣 일부 변형, 비정형 해상도 가능) — 앵커 컷 방식 권장
- 실패 변형 누적: 텍스트 명세만의 멀티앵글 세트는 실루엣 비례 드리프트
- 비율 통계 확정: 방향 12/12 정확, 정사각 6/9 (드리프트 시 1254, 비율 유지)

## 0.4.0 (2026-06-13)

- r2 마스터 판정 반영: **실사 우선 원칙** 명문화 (일러스트/렌더는 "컴퓨터 그래픽 느낌
  = 효용 낮음" — 명시 요청 시만), 과장 표정 금지 안티프롬프트 (#329)
- blog-hero·slide-visual·video-illust 템플릿을 실사 기본(A)/일러스트 대안(B) 구조로 전환
- _PATTERNS.md §4.5 마스터 취향 프로필 신설 (판정 누적 갱신 체계)
- product-catalog 카드 신설 + 첫 실측 통과 (재질 명명 기법 검증) — 총 8케이스
- 실측 라운드 3: 실사 전환 4종 + 카탈로그 1종 전부 Claude 1차 통과 —
  "not exaggerated" 표정 교정 검증, 표정 슬롯 변형 검증(portrait r2),
  세로 비율 3연속 정확, 정사각 드리프트 통계 3/6 확정

## 0.3.0 (2026-06-13)

- Threads 수집 패턴 종합 `cases/_PATTERNS.md` 신설: 5층 공식(주제+스타일+세부묘사+
  조명/분위기+기술스펙)·렌즈 명시 팁·스타일 군집 완성형·역프롬프팅 메타 기법 (#329)
- r1 품질 미달(마스터 판정) 원인 = 4·5층 누락 → 공통 체크리스트 C6(조명·깊이감) 신설,
  전 카드 템플릿에 조명/렌더 층 주입
- 실측 라운드 2 (r1 과 동일 주제 통제 비교): 5케이스 전부 체감 품질 급상승 —
  클립아트풍→매거진/렌더급. "clean waist-up framing" 으로 r1 부속물 아티팩트 해소.
  정사각 픽셀 간헐 드리프트(1254) 발견 — 비율은 유지, 방향 지정은 7/7 정확
- 신규 케이스 2종 첫 실측 통과: figurine(상품화 피규어)·photoreal-portrait(실사 인물,
  렌즈 팁 + natural skin texture 문구 검증)

## 0.2.0 (2026-06-13)

- `~/.claude/skills/codex-image`(전역·untracked)에서 itda-egg 인큐베이션으로 승격 (#329)
- 케이스 카드 체계 신설: `cases/_SCHEMA.md`(스키마·draft→verified 라이프사이클) + 카드 5종
  (blog-hero · slide-visual · icon-logo · character-illust · video-illust, 전부 draft)
- SKILL.md 에 작업 순서(케이스 분류→카드 읽기→생성→검증)·공통 품질 하한·라우팅 표 추가
- 기존 병렬 메커니즘(5장 동시·배치 스크립트·실측 시간표)·트러블슈팅 보존
- 실측 라운드 1 (codex-cli 0.137.0): 5케이스 5장 병렬 생성, Claude 1차 체크리스트 전부
  통과 수준 — 요청 비율 5/5 일치(세로 1024×1536 포함, "해상도 강제 어려움" 구 기록 폐기),
  글자 아티팩트 0. 카드별 교훈·썸네일(`cases/measurements/`) 기록. 마스터 최종 판정 대기

## 0.1.0 (2026-05-30)

- 초기 전역 스킬: codex exec 병렬 이미지 생성 메커니즘 (5장 동시 실측 2.84×)
