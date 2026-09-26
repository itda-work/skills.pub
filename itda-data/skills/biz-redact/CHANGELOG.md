# Changelog — biz-redact

## 0.2.1 (2026-09-05)

- **itda-work → itda-privacy-gate 이관 (#1648 1단계)** — 스크립트·테스트·용어집 형식 불변. 참조 표기 `itda-privacy-gate:biz-redact`. description 에 `[책임 경계]` 슬롯 추가(pii-redact·synthetic-data 지목). 강의(요양병원 1교시) 교재로서 synthetic-data 산출물이 실습 입력이 된다.

## [0.2.0] — 2026-07-26 (이슈 #1285)

### Added

- "부록: Claude Code 확장 (선택)" 절 신설 — code-extension-appendix 규약 파일럿. 본문(Cowork 기준) 불변.

## [0.1.2] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.1.1] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.1.0] — 2026-07-16 (이슈 #1171, itda-work 신규 스킬)

### New Skill

- **biz-redact v0.1.0**: 업무 문서의 영업기밀을 외부 AI에 넣기 전 로컬에서 결정론적으로 마스킹하고, AI 산출물을 원값으로 되돌리는 **왕복 게이트** 스킬. `itda-work` 신설. pii-redact(무상태 PII 마스킹)가 구현한 "마스킹 절반"에 대응하는 **나머지 절반 — 복원·거버넌스**의 실현이다(ml-absa 기획서 §6.5 "복원 키 분리 저장").
  - **결정론 마스킹 게이트**(`scripts/biz_redact.py mask`): 사용자 용어집(`glossary.json`) 기반 치환. 매칭은 길이 내림차순·정의 순서 우선 순차 치환(겹침 결정론) + 이미 치환된 토큰 영역 격리. 토큰 `⟦{category}_{n}⟧`(카테고리 내 정의 순번) — 용어집이 순번의 진실 소스라 문서 간 일관 토큰. 치환 직후 자체 잔존 검증 자동 실행(잔존 > 0 = exit 1), 산출 원자성(게이트 통과 시에만 `os.replace` 승격). stdlib(`re`·`json`·`argparse`·`hashlib`·`datetime`·`pathlib`)만.
  - **잔존 검증**(`verify`): 용어집 전 표면형 재스캔 — "마스킹했다"가 아니라 "잔존 0 검증됨" 리포트. 매처 비의존 golden oracle 대조로 검출력 자체를 테스트.
  - **왕복 복원 + 변형 감지**(`restore`): map.json(복원키) 기준 토큰 → 대표값 치환. 환각·공백삽입 토큰·복원 후 `⟦⟧` 잔존은 exit 1(조용히 틀리지 않는 안전 실패). map schema 무결성 선검증.
  - **감사 로그**(`audit.jsonl`): mask/restore가 시각·단계·결과·doc_id·카테고리별 건수·이상 건수를 append(기밀값 미포함).
  - `references/`(glossary-format.md·glossary-template.json) + SKILL.md + GUIDE.md.

### 설계 의도

- **AI 밖 게이트**(pain P3): 마스킹은 정의상 AI 접촉 전 로컬 코드가 해야 경계가 성립한다. 에이전트에게 "가려줘"라고 원문을 주는 순간 원문이 이미 클라우드 모델에 들어간다 → SKILL.md [HARD] 1(평문 기밀 4종 — 원문·glossary.json·map.json·restored.txt — 에이전트 Read 금지, 신뢰 산출물은 masked.txt·report.json·리포트·audit.jsonl로 한정).
- **PII와 영업기밀의 구조적 차이**: CS 분석에서 전화번호는 판정에 무관해 영구 마스킹으로 충분했다(pii-redact에 복원이 없는 이유). 그러나 검토 업무에서 단가·금액은 **AI가 검토해야 할 대상 그 자체**일 수 있다 → 왕복 복원이 이 스킬에만 필수인 이유. 마스킹 범위 ↔ AI 수행력 트레이드오프를 SKILL.md 오케스트레이션 지시서에 명시(기본 권장: 식별자는 가리고 검토 대상 수치는 남김).
- **소속 = itda-work 신설**: pii-redact 확장이 아니다(원문 미유출·무상태와 정면충돌 + CS 스코프 밖). 복원 선례(human-tone `lock_preserved.py`)가 이미 itda-work에 거주.

### 설계 결정 (정본 계약 C1~C8)

- 용어집이 토큰 순번의 진실 소스(문서 간 일관 토큰) · 토큰 `⟦{category}_{n}⟧` · category는 비기밀 라벨(value/alias 포함 시 로드 에러) · 표면형 최소 길이 2 · 2~3자 한국어 표면형 WARN(차단 안 함) · 원값 평문은 map.json에만 존재 · doc_id 기본값 = 원문 SHA256 앞 12 hex(파일명 비의존).

### 보안 하드닝 (R1·R2·R3·R4 리뷰 반영 — v0.1.0 계약)

- **토큰 격리는 발행 가능 토큰 집합에 한정** — 잔존 스캔이 TOKEN_RE 문법에 맞는 모든 `⟦…⟧`을 격리하던 것을, 현 용어집/맵이 발행 가능한 토큰만 격리하도록 좁혔다. 기밀을 토큰 문법으로 감싼 변조 문서(`⟦현대엘리베이터_1⟧`)가 잔존 0을 통과하던 회피를 차단.
- **표면형 부분문자열·중복·상한 가드** — ① 생성 토큰의 부분문자열이 되는 표면형(예 `_1`)은 로드 거부(토큰 내부 은닉 차단) ② 중복 검사를 casefold로(ASCII IGNORECASE 매칭 정합 — `HDEL`·`hdel` 이중 등재 거부) ③ 카테고리당 entry 상한 9999(토큰 번호 4자리) ④ `name`도 category와 동일한 비기밀 라벨 제약(리포트·감사로그 노출).
- **NFC 정규화(안전 우선)** — mask/verify/restore가 입력 텍스트·표면형을 NFC로 정규화. NFD(분해형) 문서에서 등재 기밀이 조용히 안 가려지던(위음성) 것을 차단. 원문 NFD면 리포트 `normalized: true`. 바이트 왕복 무손실은 NFC 문서 기준.
- **restore 변형 감지·평문유출 스캔 강화** — 변형 괄호 판정을 치환 후가 아닌 **치환 전 원본 산출물** 기준으로(중첩 `⟦⟦거래처_1⟧_1⟧`이 정상 토큰으로 위장되는 것 차단). 평문유출 스캔에 entry value·전체 alias를 항상 포함(map이 전체 alias 보유 — alias-only 마스킹 후 AI가 대표값을 평문 재생산해도 감지). map.entries.matched_surfaces 필수화(누락 시 스캔 생략 방지) + 짧은 순수 숫자/기호 표면형 WARN 확장.
- **검증 파이프라인 정규화 통일(R2)** — R1이 매처(mask/verify/restore)만 NFC+casefold로 바꾸고 `validate_glossary`의 비교 사이트는 원철자였던 불일치를 해소. 정규화 헬퍼 `_norm_key(s)=_nfc(s).casefold()`로 **모든 비교 사이트**(표면형 min-length[NFC 길이]·중복[NFC+casefold 키]·category/name 비기밀[NFC+casefold]·겹침·토큰 부분문자열)와 `_build_surfaces`의 category 토큰 생성(NFC)을 매처와 동일 기준으로 통일. 차단한 회피: category `HDEL`+value `hdel`가 검사를 통과해 `⟦HDEL_1⟧`로 기밀 case-variant 노출(P1), NFD 표면형 min-length 우회(NFD "가"=2코드포인트), NFC/NFD 이중등재, NFD category ↔ NFC value 겹침 우회.
- **validate_map 완결(R2)** — `created_at` 필수화 + `doc_id`·`glossary_name`·`glossary_sha256`·`created_at` 문자열 타입 검증. 잘린·변조 map(created_at 누락, doc_id=int, sha256=dict)이 성공 처리되지 않고 exit 2.
- **restore 산출 원자성(R3)** — cmd_restore가 이상 게이트(환각·변형 exit 1) 판정 **전에** restored.txt를 무조건 쓰던 것을, mask와 동일하게 **restored=True(이상 0)일 때만 `os.replace` 승격**하도록 수정. 실패 복원본이 정상처럼 남거나 기존 정상본을 덮어쓰지 않는다.
- **에러 메시지 기밀 미노출 완결(R3)** — validate_map 토큰 형식오류·중복 메시지가 tok 원문을 삽입하던 것을 인덱스·고정 안전 메시지로 교체(변조 토큰 속 기밀의 stderr 평문 노출 차단, 자기계약 준수). 비 UTF-8 입력은 traceback 대신 명시 UsageError(exit 2).
- **by_category occurrence 통일(R3)** — mask report의 `by_category`를 entry 수에서 **치환 출현 건수(occurrence)**로 통일(restore·matched_surfaces와 동일 의미, 감사 정확성). `tokens_total`은 고유 토큰 수로 유지.
- **라벨 겹침 방향 인지형 정책(R3)** — category/name ↔ 기밀 겹침의 casefold bidirectional 과차단을 3단계로 조정: 동일·기밀⊆라벨·라벨이 기밀에 **원문(대소문자 구분) 부분문자열** = BLOCK, casefold로만 걸리는 우연 겹침(`IT`⊂`digital…`) = WARN. 실증 공격(HDEL/hdel·라벨 경유 완전 유출)은 전부 차단 유지, 짧은 ASCII 라벨(IT·PO·PJ) 사용성 복원. 3단계 정책은 glossary-format.md에 문서화.
- **평문 기밀 산출물 0600(R4)** — `_write_atomic(secret=True)`로 map.json·restored.txt를 **0600**(owner rw only)으로 생성해 group/other 가독 차단(POSIX; masked.txt·report.json·audit.jsonl은 비기밀이라 기본 umask 유지). rename이 tmp의 mode를 승격하므로 최종 파일도 0600.
- **라이브러리 진입점 가드(R4)** — 공개 함수 `mask()`/`verify()`가 CLI 미경유 직접 호출에서도 `validate_glossary`를 내부 강제(restore는 이미 validate_map 호출). category=기밀 등 위반이 라이브러리 경로로 새지 않는다(WARN은 중복 억제).
- **_norm_key casefold 매처 정합(R4)** — 검증 dedup의 casefold를 **ASCII 한정**(`n.casefold() if n.isascii() else n`)으로 좁혀 매처(ASCII만 IGNORECASE)와 1:1 정합. `straße`/`strasse`(비ASCII ß)는 매처가 별개로 보므로 dedup도 별개 취급, `HDEL`/`hdel`(ASCII) 차단은 유지. 라벨 겹침·토큰 부분문자열 등 **보안 검사**는 보수적 full casefold(라벨)·interior casefold(토큰)로 유지해 case-variant 유출을 계속 차단.
- **[HARD] 경계의 정직 명시 + 도구 축소(R4)** — SKILL.md allowed-tools에서 미사용 `Grep` 제거, [HARD] 1에 "이 경계는 도구 권한으로 완전 차단되지 않는 **지시-강제(instruction-enforced)** 경계"임을 명시(`Read`가 신뢰 산출물 열람에 필요해 원문·map.json 열람을 기술적으로 막지 못함을 정직 표기).
- **비목표(v1)**: 신종 기밀 자동 검출(NER 없음 — 용어집 등재는 사람 몫) · "무엇이 기밀인가" 정책 판단 · 이미지·스캔 속 기밀 · PII 패턴(pii-redact 소관) · 타 스킬 핸드오프 광고 없음(역할 차이만 표로 설명).

### 참조 구현 (사상 계승, 코드 복제 아님)

- human-tone `scripts/lock_preserved.py` — mask/restore/audit + PreserveMap 왕복(split 격리 방식).
- pii-redact `scripts/redact.py`·`validate_output.py` — 결정론 검출·일관 가명화·잔존 검증·리포트 키 화이트리스트(기밀 미유출) 사상.
- ml-absa 기획서 §6.5 — 복원키 분리 저장·보존/파기/감사·실데이터 커밋 금지 거버넌스.

> 정식 SPEC은 운영 졸업 시점에 생성 예정. 현재 명세 기준은 GitHub 이슈 #1171 및 `.context/orchestrate/feat-biz-redact-1171/plan.md`.
