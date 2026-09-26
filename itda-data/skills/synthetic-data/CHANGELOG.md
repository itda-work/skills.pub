# Changelog — synthetic-data

## 0.1.1 (2026-09-06)

- **Windows cp949 stdout 크래시 수정 (#1647)** — Parallels Windows 11 + Python 3.13 실측에서 `show`·`validate`·`generate` 가 파이프·파일 리다이렉트 시 `UnicodeEncodeError: 'cp949' codec can't encode '\u2014'` 로 rc=1(산출물은 만들어진 뒤라 비개발자에게 실패로 보였다). `synth.py` 가 stdout/stderr 를 UTF-8(`errors=replace`)로 고정 — `-X utf8` 없이 `py -3` 만으로 전 명령 rc=0. 회귀 `test_stdio_is_utf8_even_when_locale_is_cp949`(`PYTHONIOENCODING=cp949` 로 OS 무관 재현, 뮤테이션 RED 실측).
- **GUIDE.md 실측 재작성** — 8종 프리셋(요양병원·노인장기요양)의 실제 산출 예시를 `<details>` 폴딩으로 담아, 데이터·개인정보 등급·검증 규칙을 평소엔 접어 두고 펼쳐 본다. 안전성 실측 수치(주민번호 검증식 통과 0/50·동명이인·연락처 대역) 포함. GUIDE 셸 금지 lint 통과.
- 사람 실측 픽스처 `tests/fixtures/live/`(빈 입퇴원 대장 xlsx · 괄호 항목 상담 기록지 hwpx — 개인정보 0, 배포 제외) + Windows 한글·공백 경로 종단 실측(원본 양식 sha 불변·placeholder 10/10·양식 시트 보존).

## 0.1.0 (2026-09-05)

- **신설 (#1647)** — 인터뷰 기반 가상 데이터 생성. 프리셋 8종(요양병원 4 · 노인장기요양 4), 프리셋 검증기(스키마·규칙 참조·등급·고지 변조 RED), 공통 식별자 생성기(가상 성명+동명이인 의도 삽입 · 검증자리 고의 불일치 주민번호 · 예약 대역 연락처 · 가상 지명), 규칙 검증 리포트, 항목 정의표(등급·reid_keys·근거 조문), xlsx 양식 채우기(헤더 자동 탐지·다른 시트 보존·「안내」 시트) · hwpx 양식 채우기(1건 1장, placeholder 치환·mimetype 보존), 자유텍스트 `fill-text`. 한계 고지 2종 + "프리셋 그대로 생성" 고지. 뮤테이션 4종(등급 검사 제거·검증자리 정답·동명이인 제거·규칙 참조 검사 제거) RED 실측.
- **Codex 적대 리뷰 반영** (`skills/docs/reviews/synthetic-data-codex-review-2026-09-05.md`) — `--confirm-fake` 없이는 생성 거부(첫 질문 강제) · 예시 행·자유텍스트의 실제 데이터 형식 탐지(검증식 통과 주민번호·부여 가능 휴대전화) · hwpx 원본이 산출 경로와 겹치면 쓰기 전 거부(P1-1 원본 절단) · `render` 명령(fill-text 뒤 xlsx·hwpx 재렌더, 행 재생성 없음) · 0행 생성·검증 RED · schema_version 검사 · sum 파생 int 보존 · xlsx 헤더 아래 기존 내용은 덮지 않고 아래로 밀기 · hwpx 한계 고지 미기입 경고 · 인정번호 `LX` 접두 · 연락처 문구 정정.
