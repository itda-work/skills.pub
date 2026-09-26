---
name: mmaa-welfare
description: >
  군인공제회 복지포털 스냅샷 Q&A — 복지부조(신규가입·출산 축하금, 재해위로금, 축하기념품)·
  회원콘도 이용안내·유익한 정보(취업·창업·시니어)를 출처 URL·수집일과 함께 답합니다.
  "출산축하금 얼마?", "군인공제회 콘도 이용 조건", "재해위로금 대상" 같은 군인공제회 복지
  질문이거나 사용자가 이 스킬을 지명하면 사용합니다. 제휴복지·특별할인·콘도 예약은 회원
  로그인 영역이라 URL 안내까지만 합니다.
license: Apache-2.0
compatibility: "Python 3.10+"
allowed-tools: Bash, Read, mcp__workspace__bash
user-invocable: true
argument-hint: "[질문] [--refresh]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  status: "active"
  version: "0.3.1"
  created_at: "2026-07-27"
  updated_at: "2026-09-25"
  tags: "MMAA, welfare, benefits, condo, snapshot, QnA"
---

# mmaa-welfare

군인공제회 복지포털(`https://www.mmaa.or.kr/web/contents/welfaremain.do`)의 공개
콘텐츠를 수집·구조화한 스냅샷(`data/pages.jsonl`)을 근거로 복지 관련 질문에
답합니다. 사이트 재방문 없이 즉답하되, **출처 URL 과 스냅샷 수집일을 항상 함께**
제시합니다.

## Prerequisites

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/mmaa-welfare}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/mmaa-welfare' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

Windows(PowerShell):

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\mmaa-welfare"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

검색만 할 때는 표준 라이브러리만 사용하므로 설치가 필요 없습니다.
재수집(`--refresh`) 시에만 의존성을 설치합니다:

```bash
# macOS/Linux (재수집 시에만) — 정문
python3 "$SKILL_DIR/scripts/install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

```powershell
# Windows (재수집 시에만) — 정문
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

## 사용법 — 질문 답변 (기본)

1. 사용자 질문에서 핵심 키워드를 뽑아 스냅샷을 검색한다:

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/search.py" "출산축하금 금액" --top 5

# Windows
py -3 "$env:SKILL_DIR\scripts\search.py" "출산축하금 금액" --top 5
```

2. 상위 결과 중 관련 페이지를 `--full` 로 본문 전체를 받아 근거로 답한다:

```bash
python3 "$SKILL_DIR/scripts/search.py" "출산축하금" --top 2 --full
```

3. 답변 계약 (필수):
   - **모든 정보 항목에 출처 URL 을 명시**한다 — 여러 페이지를 근거로 하면
     항목별로 해당 URL 을 붙인다. 답변 끝에 **스냅샷 수집일**(`snapshot_date`)을
     명시한다. 예: `출처: https://www.mmaa.or.kr/... (2026-09-04 수집 기준)`
   - **스냅샷 한계를 설명**한다: 이 스킬에 패키징된 데이터는 수집 시점의 박제라
     스킬 스스로 갱신할 수 없으며, 금액·기간·할인율 등은 현재 변경됐을 수 있다.
     최신 확인이 필요하면 "최신화 요청"이 가능함을 알린다(아래 절).
   - 결과에 `auth_required: true` 페이지만 있으면(신청·조회·예약 등 로그인 영역)
     "회원 로그인이 필요한 영역"임을 알리고, 해당 URL 을 안내한다 — 본문을
     추측으로 채우지 않는다.
   - 검색 결과가 없으면 "스냅샷에 없는 내용"이라고 명시하고, 원하면 라이브
     확인이 가능함을 안내한다(무단 라이브 조회로 조용히 대체하지 않는다).

## 사용법 — 최신화 요청 (라이브 조회)

사용자가 "지금 기준으로", "최신 정보로", "요즘도 그래?" 등 **최신화를 요청**하면:

1. 스냅샷 검색으로 해당 정보의 **출처 URL** 을 찾는다.
2. 사용 가능한 실브라우저 도구로 그 URL 을 라이브 조회한다 — 우선순위:
   - Claude in Chrome(`claude-in-chrome` 도구)이 있으면 해당 페이지를 열어 판독
   - aside 브라우저(`itda-web:aside-browser-mcp`)가 연결돼 있으면 해당 페이지를 열어 판독
   - 둘 다 없으면 라이브 확인이 불가함을 알리고 URL 직접 방문을 안내
3. 라이브 결과를 스냅샷과 **비교해 차이를 명시**하며 전달한다.
   예: "스냅샷(2026-09-04)에는 30만원이었는데, 현재 사이트 기준으로 변경되었습니다."
4. **한계 고지**: 스킬에 패키징된 스냅샷 파일은 변경할 수 없으므로, 라이브로
   확인한 최신 정보는 이번 대화의 답변에만 반영되고 이후 질문에는 다시 스냅샷
   기준으로 답하게 됨을 설명한다. 영구 반영은 스냅샷 재수집 후 스킬 새 버전
   릴리즈로만 가능하다.

제휴복지(카테고리·무신사·메가스터디·특별할인소식)·콘도 예약·희망플러스·법률상담처럼
**회원 로그인 영역**(아래 한계 참조)은 라이브로도 본문을 볼 수 없다 — 로그인 필요
안내와 URL 제공까지만 하고, 라이브 조회를 시도하지 않는다.

## 사용법 — 스냅샷 재수집 (개발·로컬용)

패키징된 `data/` 는 읽기 전용이다. 로컬 사본을 새로 만들려면:

```bash
# macOS/Linux — 재수집 (약 1~2분, 저속 순차)
python3 "$SKILL_DIR/scripts/collect.py" --output-dir ./mmaa-welfare-data
python3 "$SKILL_DIR/scripts/search.py" "질문" --data-dir ./mmaa-welfare-data

# Windows
py -3 "$env:SKILL_DIR\scripts\collect.py" --output-dir .\mmaa-welfare-data
```

- 수집은 요청 간 0.7초 지연의 저속 순차만 지원한다(병렬·고빈도 수집 금지).
- 로그인 필요 페이지는 URL·제목만 기록하고 본문을 수집하지 않는다.

## 데이터 구조

```
data/
├── meta.json      # generated_at(수집일)·페이지 수·로그인영역 수
└── pages.jsonl    # 페이지별 {url, breadcrumb, title, kind, auth_required, text, fetched_at}
```

`kind`: `page`(안내 페이지) · `partner`(제휴복지 상세) · `board`(특별할인소식 게시글).

## 범위와 한계

- **범위**: 복지포털 섹션 한정. 공개 본문이 실제로 있는 곳은 **복지부조 안내 5종**
  (퇴직급여 신규가입축하금·출산축하금·재해위로금·축하기념품·연금식 분할급여
  가입축하금), **회원콘도 이용안내**(대상·요금·예약안내), **제휴복지 제안**,
  **유익한 정보 6종**(취업·창업·여가/건강·금융/경제·지식정보·시니어)이다.
  저축·대여·주택 등 타 섹션은 범위 밖이다.
- **회원 로그인 영역**(2026-09-04 실측, 41페이지 중 25페이지): 신청·조회·예약뿐
  아니라 **콘도 예약 페이지(대명·한화), 제휴복지 전체(카테고리·더케이몰·건강검진·
  무신사·플러스앤·메가스터디·특별할인소식), 기타복지 전체(재무설계·희망플러스론·
  개인회생·법률상담·헤이웰)** 가 로그인 뒤에 있다. 정적 HTML 이 본문 대신
  `webLogin.do` 리다이렉트 스크립트만 싣고, 브라우저로 열어도 로그인 페이지로
  넘어간다. 사용자가 물으면 로그인 필요 안내와 URL 제공까지만 한다.
  - 오판 이력: 구 스냅샷(2026-07-27)은 이 22페이지의 GNB 메뉴 문자열(37자)을
    본문으로 세어 "본문 34페이지"라 했고, 특별할인소식·제휴업체 상세를 "WAF 경유
    JS 렌더라 미수집"으로 설명했다. 둘 다 틀렸다 — 실체는 로그인 영역이다(#1643).
    라이브 조회로 뚫리는 것이 아니므로 그 경로로 안내하지 않는다.
- 스냅샷은 수집 시점의 박제이며 **스킬 스스로 갱신할 수 없다** — 이벤트·할인은
  종료됐을 수 있다. 수집일 명시·한계 고지 계약을 지킨다.

## 데이터 경로 정책

- 스냅샷 정본: 스킬 동봉 `data/` (배포 시 포함)
- 재수집 산출: 기본은 동봉 `data/` 갱신, 쓰기 불가 환경은 `--output-dir` 지정
- `.itda-skills/` 내부에는 최종 결과를 저장하지 않습니다
