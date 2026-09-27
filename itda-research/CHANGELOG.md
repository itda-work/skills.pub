# Changelog — itda-audit

## [1.0.2] - 2026-09-27

### Changed

- `market-scan` 0.2.4 — 시장 주제별 전문 스킬 라우팅에서 공개 배포에 없는 주식 스킬 추천을 뺐다. 상장사·업종 재무는 `itda-gov:dart`, 금리·환율 등 거시 지표는 `itda-gov:ecos` 로 안내한다(설치할 수 없는 스킬을 데이터 소스 보기에 올리지 않는다).

## [1.0.1] - 2026-09-25

### Changed

- **hyve 안내 정리 (itda-work/itda-hyve#6)** — `market-scan` 0.2.3(빠진 naver-place 라우팅 삭제), `brain-audit` 0.3.4·`brain-ingest` 0.2.4(hyve 연계 예정 문구 삭제), `meeting-reliability` 0.1.4(빠진 `itda-egg:stt` 상류 지목 삭제), README 에서 이미 없는 pptx-diff 행(첫 줄 “문서 버전” 포함)과 hyve 저장소 SPEC 경로 정리.

## [1.0.0] - 2026-09-20

### Changed

- 팩 개명 `itda-evidence-verify` → **`itda-research`** (#1703).
- `itda-knowledge-build` 흡수 — brain-* 5종(업무DB).
- `pptx-diff`·`pdf-context-refinery` 는 `itda-doc` 으로 이관.

## [0.2.0] - 2026-09-06

### Changed

- **플러그인 재정비 2·3단계 (#1648)** — 구 `itda-audit` 개명(#1648 2단계). ground-check·investigate·market-scan(구 itda-work)·pptx-diff(구 itda-hyve) 편입. 에이전트 deep-researcher·ground-verifier 이동. 폐기 이름은 별칭 없이 제거(마스터 결정 2026-09-05). 게이트: check_plugin_registry · check_plugin_refs(신설) · 카탈로그 · publish dry-run.

## [Unreleased]



### Fixed

- **문서-코드 drift 일괄 정합 (#1284)** — 95스킬 감사 부수 발견분. 세부는 각 스킬 CHANGELOG 참조.
### Changed

- **플랫폼 문서 정비 4축 일괄 (#1280·#1281·#1282·#1283)** — ① compatibility 라벨을 실태 정합(`Claude Code & Cowork` 표준, 역방향 라벨 교정) ② 설치 지시에서 `uv pip install --system`·`curl|sh` 제거(`python3 -m pip` 정본, 스크립트 안내 문자열·README 포함) ③ `.env` 안내를 양 플랫폼 병기(SKILL.md+GUIDE.md, 셸 env·`~/.claude/settings.json` env 명시) ④ `allowed-tools` 의 표준명 `Bash`/`WebFetch` 에 Cowork 실명(`mcp__workspace__bash`/`mcp__workspace__web_fetch`) 병기(73스킬) + brain `Task`→`Agent`, MCP 소비 4스킬은 필드 삭제(전체 상속). 세부 버전은 각 스킬 CHANGELOG 참조.
### Changed

- **실행 경로 SKILL_DIR 규약 표준화 (#1279)** — SKILL.md 실행 명령을 SKILL_DIR 확정 블록(Code=`$CLAUDE_PLUGIN_ROOT/skills/<skill>` / Cowork=세션 마운트 find) 기준으로 통일. cwd 상대경로·저장소 경로·플레이스홀더 표기 제거. 대상: meeting-reliability 0.1.1 (+ 워커 정의 경로 후보에 $CLAUDE_PLUGIN_ROOT 1순위 추가).

### New Agent
- **meeting-reliability-worker** 신설 (#1139) — meeting-reliability 스킬이 명시 디스패치하는 격리 추출·검수 작업자. 회의 녹취 전문을 본 대화에 들이지 않고 격리 컨텍스트에서 검수 표를 추출한 뒤, 스킬의 코드 게이트(`selfcheck.py`, `MAX_REWRITES=3`)를 워커 내부에서 실측 실행해 통과시키고, 지정 출력 디렉토리에 `result.json` + 자족 HTML 을 생성한다. 반환은 표 전문이 아니라 'HTML 경로 · 게이트 PASS/FAIL · 행 수 · 사람 검토 필요 여부'(파일 릴레이). tools 미지정(전체 상속 — 표준명 함정 회피), 필수 3섹션(입력/출력/에러 계약) 구비, 3회 초과 FAIL 시 추정 채움 없이 사람 검토 handoff. meeting-reliability SKILL.md 에 위임 절 추가(워커 부재 환경은 본 컨텍스트 폴백, 게이트·산출 계약 불변).
  - Codex 리뷰 R2 보완 (#1139): deep 모드 실행 분기 추가(basic PASS 후 원 스킬 deep 계약 — 다관점 비판·over-hedge 교정·숨은 리스크 의존·조건부 확정 재검증 승계, result.json 갱신 시 게이트 재실행·재작성 카운트 basic 과 합산 3회 상한), evidence 표현 정정('배열 길이 ≥1, 인덱스 0-base — 0 허용'), Cowork 마운트 탐색 정밀화(`find -path '*meeting-reliability/scripts/selfcheck.py'` + 3종 동거 검증으로 동명 오매치 배제).

## [0.1.0] — 2026-06-21 (신규 플러그인, SPEC-AUDIT-RELIABILITY-001 #547)

### New Plugin
- **itda-audit** 신설 — 감사(경영진단·감사 조직) 신뢰성 검수 스킬팩. IGM 5기(삼성SDS 감사 조직) 교육에서 파생.
- 기존 루트 `STATUS-AUDIT.md`(하드코딩 audit 인프라, 횡단형)와 **동음이의** — 본 그룹 상태는 `STATUS-AUDIT-RELIABILITY.md`로 분리.

### New Skill
- **meeting-reliability v0.1.0** (alpha): 회의 raw 녹취 → 신뢰성 검수 표. 코어 5규칙을 결정론 verifier로 코드 강제 + 근거 tooltip HTML 출력. 골든 회귀(부록 A, pytest 32 GREEN).

---

## 흡수 이력 — itda-knowledge-build

> #1703 재편으로 이 팩이 흡수되었다. 아래는 흡수 시점까지의 itda-knowledge-build 변경 이력이다.

## Changelog — itda-brain

## [0.7.0] - 2026-09-06

### Changed

- **플러그인 재정비 2·3단계 (#1648)** — 구 `itda-brain` 개명(#1648 2단계). pdf-context-refinery(구 itda-work) 편입. 폐기 이름은 별칭 없이 제거(마스터 결정 2026-09-05). 게이트: check_plugin_registry · check_plugin_refs(신설) · 카탈로그 · publish dry-run.

## 2026-09-01 (이슈 #1621) — v0.6.2

### Changed

- **`agents/brain-auditor.md` AUDIT_SCHEMA 정합** — 검수 4각도·`검수리포트.md` 파일 릴레이는 그대로 두고 최종 텍스트를 공통 감사자 JSON(`verdict`·`findings`·`recomputed`·`unverifiable`)으로 고정. tools 에서 `Skill` 제거(감사자 허용목록 밖), 셸 쓰기 금지 [HARD] 명시. `brain-build` v0.3.4 관문7 이 `verdict` 필드를 읽도록 정합.

## 2026-07-26 (이슈 #1280·#1281·#1282·#1283)

### Changed

- **플랫폼 문서 정비 4축 일괄 (#1280·#1281·#1282·#1283)** — ① compatibility 라벨을 실태 정합(`Claude Code & Cowork` 표준, 역방향 라벨 교정) ② 설치 지시에서 `uv pip install --system`·`curl|sh` 제거(`python3 -m pip` 정본, 스크립트 안내 문자열·README 포함) ③ `.env` 안내를 양 플랫폼 병기(SKILL.md+GUIDE.md, 셸 env·`~/.claude/settings.json` env 명시) ④ `allowed-tools` 의 표준명 `Bash`/`WebFetch` 에 Cowork 실명(`mcp__workspace__bash`/`mcp__workspace__web_fetch`) 병기(73스킬) + brain `Task`→`Agent`, MCP 소비 4스킬은 필드 삭제(전체 상속). 세부 버전은 각 스킬 CHANGELOG 참조.

## 2026-07-26 (이슈 #1279)

### Changed

- **실행 경로 SKILL_DIR 규약 표준화 (#1279)** — SKILL.md 실행 명령을 SKILL_DIR 확정 블록(Code=`$CLAUDE_PLUGIN_ROOT/skills/<skill>` / Cowork=세션 마운트 find) 기준으로 통일. cwd 상대경로·저장소 경로·플레이스홀더 표기 제거. 대상: brain-audit 0.3.1 · brain-build 0.3.1 · brain-fixture 0.3.1 · brain-ingest 0.2.1.

## [0.6.1] — 2026-07-24 (구두 주장 규율 하드닝 — 실기기 리허설 실측 이탈 차단, #1241)

### Fixed
- **CLAUDE-template 구두 주장 처리 규칙 하드닝**: Cowork 실기기 리허설(#1241, Sonnet 5·중간)에서 관측된 모델 자연 본능 이탈 3종을 부정 지시로 차단 — ① 미검증 주장을 위키 정본 페이지에 "⚠️ 미확인" 딱지로 기록(사실 세탁 경로 — S2 실측) → **기록처는 오직 검증대기.md** 명시 ② 등록을 사용자 답변 뒤로 미룸(세션 단절 시 증발 리스크) → **근거를 묻기 전에 먼저 등록** ③ 구두확인서 승인 시 "CLAUDE.md 에 조항 추가" 제안(뇌 1차 기록화 — S4 실측) → **승인의 실체는 소스 폴더 이동까지, 반영은 정상 적재 경로** 명시.
- 리허설 성과: **EXC-3 양성 실측**(상위 폴더 세션이 하위 업무DB CLAUDE.md 를 지침으로 자동 로드 — 2세션 연속) + **AC-C1 충족**(스킬 미설치·규율만으로 감지→등록→요구→미검증 안내 루프 재현, S4 는 원장·초안 게이트 모범 준수 + S2 건 소급 등록). 리허설 킷·판정 기록은 `skills/docs/testbeds/brain-claim-rehearsal/`·#1241.

## [0.6.0] — 2026-07-19 (주장→근거 파이프라인 + 검색 사각 표면화, #1222·#1223)

### Added — 구두 주장 검증 적재 (배우는 뇌, SPEC-BRAIN-CLAIM-001, #1222)
- **CLAUDE-template "구두 주장 처리 규칙" 절 신설**: 질답 중 사용자가 업무DB에 없는 사실·판단 기준을 구두로 말하면("재계약해서 21,000원이 맞아") 조용히 흘리지도 그대로 적재하지도 않는다 — **채팅 발언 = 지식이 아니라 적재 요구 신호(주장)**. `검증대기.md` 등록 → 근거 요구 3갈래(ⓐ 사내 실물을 소스 폴더에 요청 ⓑ 외부 수집 후 `외부/` 격리 ⓒ 구두확인서 초안 `초안/` → 사람 비준 → 소스 폴더 원본화) → 도착 실물 ↔ 주장 대조(일치=적재+졸업, 불일치=모순 보존) → 통과 실물만 기존 적재 경로. 뇌는 어떤 경우에도 1차 기록이 되지 않는다(순수 암묵지도 비준된 구두확인서 원본 경유 — "2차 정리본" 불변 보존, 환각 세탁 경로 차단). 검증대기 중 주장은 정본 답변에 불사용, "미검증 구두 주장 있음" 안내 전용. 자동 감지는 **폴더 스코프**(업무DB 폴더를 연 세션의 CLAUDE.md 규율)만 — 전역 감시는 영구 비범위(스킬 pull 메커니즘·뇌 라우팅·대화 오염). 검증대기는 데이터 후보 대기열로 온보딩 "상태 비저장"(사람 이해 축)과 직교함을 명문화.
- **brain-ingest v0.2.0**: 적재원 3분류(주장 해소 근거) + 관문1.5 대조 게이트 + 검증대기 졸업(해소일·근거 경로) + **뇌 밖 명시 접수**("이 얘기 뇌에 반영해줘" — 대상 뇌 확인 후 검증대기 등록부터, 위키 직접 기록 금지).
- **brain-audit v0.3.0**: 관문1.5 미결 주장 집계(건수·최장 경과일, 원장 부재=0건 정상) — 신선도(제5각) 옆 결정론 표면화, 오래된 미결은 근거 확보 재촉을 조치 권고로.

### Added — 내용 검색 불가 표면화 (검색 사각, #1223 · SPEC-BRAIN-VERTICAL-001 REQ-022 개정)
- **brain-build v0.3.0**: 스캔 PDF(텍스트 레이어 부재)·이미지 위주 문서를 `문제파일.md`에 **"내용 검색 불가"** 분류로 기록(판독·적재 여부와 별개 — 텍스트 검색의 사각 표시). 적재 집계에 검색 불가 S 추가.
- **CLAUDE-template 질의 응답 규칙**: 검색 빈손 시 "없음" 단정 금지 — "내용 검색 불가 N건은 이 검색에 포함되지 않음"을 함께 고지(검색 사각의 거짓 안심 차단, `no-silent-fallback` 의 검색판). 유지보수 절에 숨김 파일(`.brain-manifest.json`) 조회는 경로 직접 지정 명시(ripgrep 기본값이 숨김 파일 제외).
- **brain-audit**: `문제파일.md` 내용 검색 불가 건수를 리포트에 상시 노출.

## [0.5.0] — 2026-07-18 (brain-fixture v0.2 — 인사이트 축 + 원장 보강, #1203·#1202)

### Added
- **brain-fixture v0.2.0 — 인사이트 축(합성해야만 보이는 것, REQ-050)**: 원장을 3축으로 완성 — 함정(잘못된 것)·미끼(잘못 아닌 것)에 **인사이트(여러 문서를 종합해야만 보이는 것)** 를 더했다.
  - **원장 `insights[]`**: `id`·`type`(negotiation-leverage·threshold·trend·concentration·margin·deadline)·`conclusion`·`derivation`(op+operands 도출식)·`evidence`(서로 다른 문서 ≥2)·`surface_question`·`tier`(1~3). 스키마 검증이 evidence 상이성(≥2)·피연산자 문서 바인딩(from ∈ evidence)·피연산자 다문서 분산(합성 강제)을 강제.
  - **verify 제5축 "합성 강제"**: insights 선언 시 실행(없으면 SKIP, 하위호환). ① evidence 문서 실재·상이성 ② 피연산자 값이 선언 출처 문서에 실재 ③ derivation 재계산(diff/sum/product/ratio 수치 일치, compare/threshold 부등호 성립) ④ **스포일러 금지** — 파생 결과값이 어느 단일 문서에 직접 렌더되면 FAIL(우연 충돌 포함, 원장 수치 조정 지시). "데이터를 종합해야만 알 수 있다"의 기계 보장.
  - **answer_sheet 인사이트 절**: "## 인사이트(합성해야만 보이는 것 — 3계단 질답 모범답안)" tier별 질문→기대 결론→도출식(피연산자+근거 경로). 함정·미끼 절과 동급 위상.
  - **헬스케어 원장 v1.1**: 인사이트 5종 추가(협상카드·안전재고 미달·전년비 성장률·채널 집중도·렌탈 회수기간 — B2 미끼의 양성 반전) + #1202 보강 4건: 직원명부 22명 전원(조직도 정합)·회사소개서 렌탈가 39,000 시점 정합(1/20 발행)·손상 파일 페이로드를 고정 시드 의사난수로(ASCII 마커 제거, 결정론 유지)·재고 실사 메모 실사일 명시(T8 시점 역행 검출력 강화). 37→38 문서.
  - **테스트**: 인사이트 왕복·스포일러/evidence/derivation/operand mutation·하위호환 회귀 추가(45→53).

### Hardened (Codex 2R 적대 리뷰 재현 수용 — 게이트 무결성 직격 9건, 미릴리즈)
- **G1 소수 스포일러**: 파생값이 정수 인코딩("137")뿐 아니라 **소수 표기("13.7"·"13.70")로 직접 렌더돼도 FAIL**(재파싱 텍스트 이중 검사).
- **G2 op↔결론 미바인딩**: 인사이트에 구조화 **`result`(kind numeric+value | relation)** 필수화 — 수치 결론을 relation op(compare)으로 위장해 스포일러를 우회하던 경로 차단(kind=numeric ⟹ 수치 산출 op + value 재계산 일치 + 스포일러 대상). derivation 의 `expected` 는 `result.value` 로 이관.
- **G3 합성 강제 실검사**: 선언 `from` 상이만 보던 것 → **어느 단일 정상 문서도 피연산자 전체를 공존 보유하면 FAIL**(그 문서만으로 도출 가능 = 합성 아님, 재파싱 값 기준).
- **G4 NaN·bool 차단**: JSON 로드 시 `parse_constant` 로 NaN/Infinity 거부, 수치(operand·result.value·expected·tier) 검증을 유한·비-bool 로 통일.
- **G5 falsy insights**: `insights: {}`·`false`·`0` 를 SKIP 으로 오인하던 것 → 키 존재 시 list 강제(위반 명시 에러), 빈 배열 `[]` 은 "0건 PASS"(SKIP 은 키 부재만). consistency·traps·baits 도 동일 가드.
- **G6 EOCD postcondition**: 손상 파일 의사난수 페이로드의 우연 `PK\x05\x06`(EOCD) 대비 — 페이로드 내 `PK` 결정론 치환 + 생성 직후 `is_zipfile==False` postcondition(위반 시 명시 에러).
- **L1 실존 상호 개명**: 실검색으로 실존 확인된 "웰라이프메디"·"웰니스마켓" 등을 전면 가상명(온제릭스·큐리페어·두레케어라운지·하란테크소재 등)으로 교체. 두 상호를 **회귀 금지 목록**으로 테스트에 고정(원장 등장 시 FAIL).
- **L2 I5 결론 정정**: "13.7개월이면 판매가를 넘는다" → "손익분기 약 13.7개월, 월 납부 14회차(490,000원)부터 렌탈 누계가 판매가 초과".
- **F8 테스트**: 소수 스포일러·compare 위장·피연산자 공존·NaN/bool·insights:{}·실존 상호 회귀 + **헬스케어 원장 전체 왕복(generate→verify 5축)을 정식 pytest** 로 추가(53→62).

### Added — REQ-060 질답 E2E 도구 (v0.3, #1206, 미릴리즈)
- **`scripts/qa_sheet.py`**: insights[] 에서 **질문지·채점지 분리 산출** — `qa-questions.md`(응답자용, tier 오름차순·번호·질문만)와 `qa-key.json`(채점자용, 기대 conclusion·result·evidence·derivation 요약). **정답 미누출 자체검증** — 질문 문구(surface_question)에 result 수치(정수 인코딩+소수 표기)·evidence 경로가 있으면 exit 2 명시 에러(누출 insight id·토큰 명시). insights 미선언/빈 배열은 "질답 대상 없음" 명시 에러(스포일러 금지의 질답판).
- **`references/qa-protocol.md`**: 응답자 계약(업무DB 폴더만 연 zero-context 에이전트 — 원장·정답지·검수리포트·qa-key 접근 금지, CLAUDE.md 질의응답 규율, 답마다 근거 경로)·실행 절차(질문지 순서→`qa-answers.md`)·채점 기준(결론 포함·근거 evidence 포괄·창작0)·tier별 합격선(tier1·2 전건, tier3 방향 일치 부분 인정)·채점표 양식.
- **테스트**: qa_sheet 산출·스키마·질문지 미누출 기계 검증·질문 문구 누출 검출(수치/경로)·insights 부재 에러(62→70). SKILL.md 관문6(선택 질답 실사격) 절·metadata.version 0.3.0.

## [0.4.0] — 2026-07-18 (brain-fixture 신설, #1201)

### Added
- **brain-fixture v0.1.0** (신규 스킬, SPEC-BRAIN-FIXTURE-001): brain-build 검증·데모·강의용 **함정 데이터셋 포지**. 한빛오피스 37파일 fixture 수작업 저작 경험을 **원장(ledger) 분리 + 선언적 함정 + 자기 검증 게이트**로 일반화했다.
  - **원장 SSoT · 창의/결정론 분리**: 에이전트는 세계관·수치 대장·함정을 `ledger.json` 으로 저작(창의 구간), 문서 렌더·검증·정답지는 Python 이 결정론 수행(기계 구간). "생성 후 재검증"(마스터 지시)을 프로세스가 아니라 구조로 보장.
  - **`scripts/generate.py`** — 원장 documents[] 전건을 유형별 렌더(python-docx·openpyxl·python-pptx·reportlab 텍스트 레이어 PDF·txt·csv + 손상/잠금 파일), `os.utime` 으로 mtime=내부 날짜. 비어있지 않은 출력 폴더는 exit 2 거부(비파괴), 스키마 위반은 명시 에러(어느 필드가 왜).
  - **`scripts/verify.py`** — 자기 검증 게이트(thesis). 생성물을 독립 재파싱해 원장과 4축 재대조: ①수치 정합(선언값 전수) ②연계성(전건 실재·consistency 파생 재계산·정본 문서 바인딩) ③mtime=내부 날짜 ④함정 실재(선언 traps/baits 마커 렌더 확인). exit 0/2 + 한국어 findings(no-silent-fallback).
  - **`scripts/answer_sheet.py`** — 원장 traps/baits/consistency 에서 강사용 정답지(세계관·함정 표·정본 숫자·기대 검수 결과·오탐 경계) md 생성.
  - **함정 유형 카탈로그 v1** (8종): contradiction·version-hell·stale-rule·time-warp·decision-drift·broken-file·lock-file·untitled + 오탐 미끼 3종(direction·scope·duplicate).
  - **개인형 프리셋 3종**: `freelancer`(프리랜서 정산)·`household`(가계 아카이브)·`club`(동호회 운영) — 동작하는 씨앗 원장 + 확장 가이드.
  - **헬스케어판 v1** (`examples/healthcare-ledger.json`): 가상 헬스케어 기기 업체 '온제릭스(주)'(실존 상호·인명 금지 — 초안명이 실존 상호로 판명되어 L1 하드닝에서 개명) 문서 무더기·함정 8종(도메인 고유 인증규정 이중화 포함)·오탐 미끼 3종(렌탈 vs 일시불 단가 포함). generate→verify PASS·정답지 생성 라이브 실증.
  - **테스트**: pytest 45건(generate→verify 왕복·mutation 검증(값 변조·함정 미렌더·mtime·파일 삭제 시 FAIL)·스키마 위반 명시 에러·배포형 subprocess CLI·예시/프리셋 가드·보안 가드 회귀).
  - **Codex 적대 리뷰 하드닝** (재현 실측 기반 수용 3건): ① 경로 탈출 차단 — `documents[].path` 절대경로·`..` 거부 + 전 파일 접근 `safe_join` containment(출력 폴더 밖 덮어쓰기 실증 → 명시 에러) ② 유령 함정 차단 — traps/baits 에 검증 가능 marker ≥1 스키마 강제 + verify 축④ 방어 심층(렌더 안 된 함정이 정답지에 실리는 결함) ③ 정규화 중복 경로 거부. 유보 1건(부호 반전 미검출 — 게이트 목적이 렌더러 결함 검출이지 변조 방어가 아님, v1 한계로 ledger-schema·SKILL 명시)·기각 1건(손상 페이로드 치환 — "읽기 불가"가 계약) 은 트리아지 기록.

## [0.3.0] — 2026-07-15 (사람↔뇌 온보딩/인수인계 규약, #1153)

### Added
- **신규 열람자 온보딩(인수인계) 규칙** — Layer 3 정본 `references/CLAUDE-template.md` 에 규약 절 추가(brain-build 가 업무DB 의 `CLAUDE.md` 로 자동 심음). 기존 검수(brain-audit/brain-auditor)가 보는 **뇌↔원본**(데이터 충실도)과 직교하는 **사람↔뇌**(인간 이해 충실도) 축을 다룬다: 이 뇌를 처음 받는 사람(신입·후임·담당자 교체)이 폴더를 열면 `INDEX.md`·위키 근거로 뇌 지도와 **판단 필요 지점**(`검수리포트.md` 모순·`문제파일.md`·신선도 낡음)을 브리핑받고, 원하면 근거로 채점 가능한 **판단 문항**(회상 트리비아 아님)으로 이해를 확인한다. 책임 경계(사람이 확인·결정할 것)를 명시하고, **이해 상태는 뇌에 비저장**(개인 귀속 — 뇌는 *데이터*의 정본, 온보딩은 매 세션 행동일 뿐 상태 미축적). 새 스킬·에이전트 없이 "질답은 `CLAUDE.md` 가 담당" 메커니즘 재사용(스프롤 0). brain-build 관문5·완료보고·README 시나리오 반영.

## [0.2.0] — 2026-07-14 (실사용 리뷰 하드닝, #1122)

### Fixed
- **brain-auditor Cowork tools 함정 교정** (#1130 후속): Cowork 워커의 셸은 표준명 `Bash` 가 아닌 `mcp__workspace__bash` 로 존재하고 frontmatter `tools:` 는 미매칭 이름을 조용히 소실시키는 필터라(스모크 13종 실측, `skills/docs/cowork-capability-map.md`), 기존 정의로는 Cowork 에서 셸 없이 구동되어 수치 재대조 검수가 무력화(또는 실행 서술·환각)될 수 있었다. `mcp__workspace__bash` 를 병기해 양 플랫폼에서 셸을 보존하고, 원본 불가침 계약 문구를 셸 도구 중립으로 정합.
- **freshness.py 조용한 폴백 2종 제거** (실사용 엣지 실측): ① `update-baseline` 이 manifest 부재 시 빈 기준선을 조용히 생성하던 것 → `manifest 없음` 명시 에러(exit 2 — 오타 시 정본 기준선이 1엔트리로 대체되는 사고 차단). ② 손상(비JSON·빈) manifest 가 원시 traceback 을 뱉던 것 → `manifest 손상` 한국어 명시 에러(exit 2, 부재=unknown 과 구분). scan 소스 폴더 부재도 traceback 대신 명시 에러. 회귀 테스트 5건 추가(21→26).
- **brain-build 관문 6↔7 순서 교체**: manifest 저장을 검수 디스패치보다 먼저 — 검수관이 참조하는 기계 기준선이 검수 시점에 항상 부재하던 순서 결함(실사용 검수관 피드백 실측). manifest 저장은 `.tmp && mv` 패턴으로 통일(scan 실패 시 깨진 기준선 잔존 차단). 관문 번호 참조 오기 3곳 정정.
- **경로 계약 명문화**: `CLAUDE.md` 머리말 `sources:` 는 **절대경로**(brain-audit 가 이 값만으로 소스를 찾음 — 상대경로는 실행 위치 의존), CLAUDE-template 경로는 플러그인 루트 `references/` 기준임을 명시.

### Changed
- **v1 단일 소스 명문화** (마스터 결정 2026-07-14, A안): 뇌 하나 = 소스 폴더 하나. brain-build 가 2개 이상 요청을 명시 거부하고 분리 빌드를 제안 — manifest·근거 상대경로가 단일 루트 전제라 다중 소스는 신선도 레이어가 조용히 틀린 답을 냄. 다중 소스는 실수요 시 manifest 포맷 확장으로 후속.
- **brain-auditor 지시서 보강** (실사용 검수관 피드백 5건): 커버리지 분모 정본 = freshness scan 출력(OS 잡음 제외 명문화) · 심각도 4단계 경계 정의 · 조건부 모순(세금/단위 기준이 한쪽만 명시된 금액 대조 = 시나리오 병기 + 심각도 하향) · 경미 결함 기재 위치 규칙(각도 절=근거, 조치 권고=실행 항목만) · 소규모(≤약 20개) 시 무작위→전수 대조 승격.
- **brain-build 관문7 검수 2차 경로**: `itda-brain:brain-auditor` 타입 부재 환경(소스 저장소 등)에서 general-purpose 서브에이전트에 `agents/brain-auditor.md` 지시서를 주입해 디스패치 — 격리 검수 동등 성립(실측 검증). fail-visible 배너는 서브에이전트 디스패치 자체가 불가할 때로 한정.

### New
- **`evals/` 골든 시나리오** (skill-creator 외부 검증 권고): 함정 6종(단가 모순·거래방향 미끼·파일명 함정·잠금 임시파일·빈 문서·시계열 미끼) fixture + assertions A1~A10. 실사용 E2E 에서 판별력 실증(심은 모순 검출·오탐 0·우발 결함까지 검출)된 시나리오를 검수관 검출력 회귀 가드로 승격.
- **brain-build 관문3 위키 페이지 실물 예시** 추가(머리말+인라인 근거+모순 병존 — 형식 해석 편차 제거).

## [0.1.0] — 2026-07-14 (신규 vertical 플러그인, #1122)

### New Features
- **itda-brain v1** (신규 플러그인, SPEC-BRAIN-VERTICAL-001): 비정형 문서 무더기 → 근거 추적 업무DB(뇌) vertical. `itda-data`(정형 데이터)와 나란히 서는 비정형 문서의 근거 추적.
- **brain-build v0.1.0**: 폴더 무더기 → 3-Layer(Raw→Wiki→Schema) 업무DB 빌드. 원본 전수 열람(원본 불가침) → 주제별 위키 + `INDEX.md`(적재이력) + `CLAUDE.md`(Layer 3 스키마·뇌 메타 자기서술) + `문제파일.md`. 규약 역공학(폴더-지도·명명-규칙·양식). 빌드 끝에 `brain-auditor` 1회 자동 호출.
- **brain-auditor** (신규 에이전트): 검수 전담 서브에이전트(읽기 전용 + 리포트 쓰기만). 빌드 기억과 격리된 컨텍스트에서 원본 재열람 → 검수 4각도(전수성·수치 재대조·근거 추적·교차 모순) → `검수리포트.md`. 심각도순 모순 목록 + 오탐 방지 정합 목록. #1121 `agents` WHITELIST 로 skills.pub 배송.
- **brain-audit v0.1.0**: 독립 재검수 진입점(정기잡·수시 점검). `brain-auditor` 디스패치 + **신선도 점검**(제5각) — `scripts/freshness.py`(stdlib, 결정론 mtime 스캔)로 소스 폴더 재스캔 → 커버리지 표의 빌드 시점 수정시각과 대조 → 신규/변경/삭제 파일 표면화.

### Scaffold (후속 버전 구현)
- **brain-ingest** *(v1.1 스텁)*: 증분 적재 + 외부 스킬 산출물 어댑터(`외부/` 격리) + 신규 유형 학습 루프. orchestration outline 제공.
- **brain-scribe** *(v1.5 스텁)*: 규약 준수 문서 생성 + `초안/` 승인 게이트 + 근거 사이드카. orchestration outline 제공.

### Design
- **연계 대비 3원칙** (hyve 셸 "두 번째 뇌" 후속 연계 대비, 스키마만 선매설): ① 뇌의 정본은 폴더 그 자체(스키마 정본 = `references/CLAUDE-template.md` 한 곳) ② 자기서술 폴더(`CLAUDE.md` 머리말 뇌 메타 — 이름·소스폴더·최종갱신·원본 수) ③ 관측 가능 필드 선매설(검수리포트 커버리지 표에 원본 수정시각, `INDEX.md` 적재이력). hyve 는 향후 읽기만.
- **검증**: IGM "클로드 활용 2026 업무혁명 과정" 업무DB 실습키트 3차 리허설(2026-07-13) 실측 설계 — 원본 37개 전수 커버·수치 오류 0·함정 7종 100% 검출·오탐 0(약 33분).
