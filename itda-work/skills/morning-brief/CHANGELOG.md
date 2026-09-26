# CHANGELOG — morning-brief

이 파일이 변경 이력의 유일 정본이다.

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
