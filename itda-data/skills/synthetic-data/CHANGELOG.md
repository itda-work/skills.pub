# Changelog — synthetic-data

## 0.1.4 (2026-09-30) — itda-work/skills#47

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## 0.1.3 (2026-09-28)

- **hwpx 양식 입력 가드 (#27)** — `fill_hwpx` 가 양식을 상한 없이 풀던 것을 `scripts/safe_archive.py`(itda-doc hwpx 와 같은 파일)로 바꿨다.
  엔트리 수(EOCD, 목록 전)·단일/합계 비압축 크기(선언 + 실제 바이트)·압축 방식·크기 위조·경로 탐색 이름·XML DOCTYPE 을 거부한다.
  `generate` 는 data.json 을 쓰기 전에, `render` 는 기존 산출을 덮기 전에 양식을 한 번 끝까지 풀어 보고 exit 2(SpecError)로 멈춘다 —
  부분 산출이 남지 않는다. ZIP 이 아닌 양식도 트레이스백 대신 exit 2. 테스트 10건 · 뮤테이션 5종 RED.

## 0.1.2 (2026-09-27)

- **hwpx 채우기 결함 3종 수정 (#4)** — kordoc 대조(#1)·gpt-6-astra 리뷰에서 재현.
  - 연쇄 치환 제거 — 키를 차례로 `replace` 하던 탓에 넣은 값 안의 다른 placeholder 가 다시 바뀌었다(`{{A}}→{{B}}` 가 `{{B}}` 의 값이 됨). 원문 기준 한 번에(긴 키 우선) 치환한다.
  - 리포트 집계를 항목 단위로 — `(항목명)` 만 세서 `{{항목명}}` 양식은 치환이 돼도 "0건 · placeholder 없음" 경고가 떴다. 두 표기를 합쳐 한 항목으로 센다.
  - 글자 서식이 갈린 run 에 걸친 placeholder 를 리포트에 드러낸다 — 속성이 같은 run 만 합쳐지므로 `{{환자` + `명}}` 은 조용히 0회였다. 문단 글자를 이어 붙여 남은 키를 찾아 ⚠️ 로 알린다.
  - 뮤테이션 3종(연쇄 치환 복원·구 집계 복원·잔존 탐지 제거) RED 실측.

## 0.1.1 (2026-09-06)

- **Windows cp949 stdout 크래시 수정 (#1647)** — Parallels Windows 11 + Python 3.13 실측에서 `show`·`validate`·`generate` 가 파이프·파일 리다이렉트 시 `UnicodeEncodeError: 'cp949' codec can't encode '\u2014'` 로 rc=1(산출물은 만들어진 뒤라 비개발자에게 실패로 보였다). `synth.py` 가 stdout/stderr 를 UTF-8(`errors=replace`)로 고정 — `-X utf8` 없이 `py -3` 만으로 전 명령 rc=0. 회귀 `test_stdio_is_utf8_even_when_locale_is_cp949`(`PYTHONIOENCODING=cp949` 로 OS 무관 재현, 뮤테이션 RED 실측).
- **GUIDE.md 실측 재작성** — 8종 프리셋(요양병원·노인장기요양)의 실제 산출 예시를 `<details>` 폴딩으로 담아, 데이터·개인정보 등급·검증 규칙을 평소엔 접어 두고 펼쳐 본다. 안전성 실측 수치(주민번호 검증식 통과 0/50·동명이인·연락처 대역) 포함. GUIDE 셸 금지 lint 통과.
- 사람 실측 픽스처 `tests/fixtures/live/`(빈 입퇴원 대장 xlsx · 괄호 항목 상담 기록지 hwpx — 개인정보 0, 배포 제외) + Windows 한글·공백 경로 종단 실측(원본 양식 sha 불변·placeholder 10/10·양식 시트 보존).

## 0.1.0 (2026-09-05)

- **신설 (#1647)** — 인터뷰 기반 가상 데이터 생성. 프리셋 8종(요양병원 4 · 노인장기요양 4), 프리셋 검증기(스키마·규칙 참조·등급·고지 변조 RED), 공통 식별자 생성기(가상 성명+동명이인 의도 삽입 · 검증자리 고의 불일치 주민번호 · 예약 대역 연락처 · 가상 지명), 규칙 검증 리포트, 항목 정의표(등급·reid_keys·근거 조문), xlsx 양식 채우기(헤더 자동 탐지·다른 시트 보존·「안내」 시트) · hwpx 양식 채우기(1건 1장, placeholder 치환·mimetype 보존), 자유텍스트 `fill-text`. 한계 고지 2종 + "프리셋 그대로 생성" 고지. 뮤테이션 4종(등급 검사 제거·검증자리 정답·동명이인 제거·규칙 참조 검사 제거) RED 실측.
- **Codex 적대 리뷰 반영** (`skills/docs/reviews/synthetic-data-codex-review-2026-09-05.md`) — `--confirm-fake` 없이는 생성 거부(첫 질문 강제) · 예시 행·자유텍스트의 실제 데이터 형식 탐지(검증식 통과 주민번호·부여 가능 휴대전화) · hwpx 원본이 산출 경로와 겹치면 쓰기 전 거부(P1-1 원본 절단) · `render` 명령(fill-text 뒤 xlsx·hwpx 재렌더, 행 재생성 없음) · 0행 생성·검증 RED · schema_version 검사 · sum 파생 int 보존 · xlsx 헤더 아래 기존 내용은 덮지 않고 아래로 밀기 · hwpx 한계 고지 미기입 경고 · 인정번호 `LX` 접두 · 연락처 문구 정정.
