---
name: stakeholder-map
description: >
  프로젝트 이해관계자별로 역할·요청할 것·받을 것·소통 방식과, 그 사람이 일을 시작하기
  전에 알아야 할 선행 전달물(톤·형식·분량·필수 문구 같은 제약 조건)을 문서로 굳히는
  스킬입니다. "이해관계자 정리해줘", "협업 지도 만들어줘", "누구한테 뭘 먼저 넘겨야 하지",
  "디자이너한테 뭘 미리 줘야 해?", "요청 순서 정리해줘"처럼 말하면 됩니다. work-redesign
  이 만든 stakeholders 스텁이 있으면 심화하고, "알아서 잘" 같은 모호한 제약은 구조
  게이트가 반려합니다.
license: Apache-2.0
compatibility: Claude Cowork & Code, Python 3.10+
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, AskUserQuestion, mcp__workspace__bash
argument-hint: "[프로젝트명 또는 이해관계자 이름, 비우면 인터뷰]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.1.3"
  category: "productivity"
  status: "experimental"
  created_at: "2026-07-24"
  updated_at: "2026-07-26"
  aliases: "이해관계자맵, 협업지도, 선행전달물, 요청순서"
  tags: "Cowork, stakeholder map, collaboration, upfront constraints, handoff, request sequencing, bottleneck prevention"
---

# stakeholder-map — 내가 병목이 되기 전에, 먼저 넘길 것을 정한다

## 이 스킬이 푸는 문제

> "일이 진행되다 나 때문에 막힌다. 제약 조건(형식·사이즈·톤)을 미리 안 알려주고 맡겨서,
> 다 만든 걸 다시 만들게 한다."

일 잘하는 사람은 자기 일이 100% 끝나기 전에 **상대가 먼저 시작할 수 있는 것**을 미리
넘깁니다 — 내용이 안 정해졌어도 톤·형식·분량·필수 문구는 먼저 갈 수 있습니다. 반대로
테이블 사이즈를 안 알려주고 진열 시안을 받으면, 화려하지만 현실에 안 맞는 결과물
(워크슬롭)이 돌아옵니다. **사람에게든 AI에게든 같은 원리입니다** — 역할을 주고 제약을
선행 전달하지 않으면 짐작으로 만든 것을 받게 됩니다.

이 스킬은 이해관계자별 문서(`stakeholders/<이름>.md`)와 요청 순서를 굳혀, "누구에게
무엇을 언제 먼저 넘길지"를 지도로 만듭니다.

## 발동하지 않는 경우

- 업무 전체를 4분면으로 나누려면 → `work-redesign` (이 스킬은 그 지도의 관계자 축 심화)
- 개별 요청 1건을 다듬어 던지려면 → `task-brief` (선행 전달물은 브리프의 입력이 된다)
- 연락처 관리·메시지 발송은 하지 않습니다(문서화 전용, PII 는 이름·역할 수준만)

## 산출 계약

```
stakeholders/<이름>.md   # 관계자별 문서 (구조 게이트 대상)
project-context.md       # "## 협업 순서" 절 추가 — 누구에게 어떤 순서로 무엇을
```

관계자 문서 형식 (최상위 섹션 `##` 고정 — 게이트 파서 계약):

```markdown
# 이해관계자 — <이름> (<역할>)

## 역할
- <이 프로젝트에서 맡은 것>

## 요청할 것
- <산출물> — 기한: <날짜>

## 받을 것
- <내가 이 사람에게서 받아야 하는 자료·결정·승인>

## 선행 전달물
- <제약 이름>: <값>   ← 톤·형식·분량·사이즈·필수 문구·브랜드 가이드 등

## 소통
- 채널: <슬랙·메일 등>
- 주기: <주간 목요일 등>
```

## 절차

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/stakeholder-map}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/stakeholder-map' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```
```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\stakeholder-map"  # 미설정이면 SKILL.md 위치 절대경로 사용
```


### 0. 스텁 로드

`stakeholders/*.md` 가 이미 있으면(work-redesign 산출 스텁) 읽고 빈 칸을 심화 대상으로
잡습니다. 없으면 프로젝트에 얽힌 사람을 나열하는 것부터 시작합니다(이름·역할만 —
연락처 등 PII 는 받지 않습니다).

### 1. 관계자별 인터뷰 (한 번에 한 명)

관계자마다 순서대로 묻습니다:
1. **역할** — 이 프로젝트에서 이 사람이 맡은 것.
2. **요청할 것** — 내가 이 사람에게 시킬/부탁할 산출물과 기한.
3. **받을 것** — 내가 이 사람에게서 받아야 진행되는 것(자료·결정·승인). 여기가 비면
   대기 병목이 안 보입니다.
4. **선행 전달물(핵심)** — "이 사람이 그 일을 시작하려면, 내용이 확정되기 전에라도
   뭘 먼저 알아야 합니까?" 답이 "없다"면 되묻습니다: 형식은? 분량은? 톤은? 꼭 들어갈
   문구는? 물리적 제약(사이즈·기술 스택)은?
5. **소통** — 채널과 주기.

질문 규율: 한 번에 한 질문(AskUserQuestion 이 있으면 추천 기본값 첫 옵션), 답변 누적
참조, **짐작으로 채우지 않기** — 사용자가 모르는 칸은 비워 두고 게이트가 표면화하게 둡니다.

### 2. 구조 게이트

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/check_stakeholder.py" stakeholders/*.md
# Windows
py -3 "$env:SKILL_DIR\scripts\check_stakeholder.py" stakeholders\김디자.md stakeholders\박리드.md
```

게이트(기계)는 파일마다 C1~C4 를 강제합니다: 필수 섹션(역할·요청·선행 전달물·소통) ·
선행 전달물 ≥2건 전 항목 `키: 값` 제약 구조 · 모호어 0("알아서"·"잘 부탁"·"이쁘게"는
제약이 아니라 짐작 위임) · 미확정 마커 0("확인 필요"·"미정"·"TBD"·"❗" — 모르는 칸을
플레이스홀더로 채워 게이트를 통과시키지 말고, 그 줄을 지워서 FAIL 로 표면화합니다).
W1~W4(받을 것·기한·채널+주기·제목 역할 병기)는 경고입니다.
**FAIL 축은 에이전트가 채우지 말고 1단계로 되돌아가 사용자에게 묻습니다.**

**의미 점검(에이전트)** — 게이트가 못 잡는 것을 채점합니다:
- 선행 전달물이 그 직군에 실제로 필요한 제약인가(디자이너에게 톤·참고 이미지, 개발자에게
  스펙·인증 방식 — 형식만 갖춘 무의미한 키·값이 아닌가).
- 받을 것에 "결정·승인"류가 빠지지 않았는가(자료만 적으면 의사결정 대기가 안 보인다).

### 3. 협업 순서 — project-context.md

관계자 문서가 모이면 요청 순서를 정리해 `project-context.md` 에 `## 협업 순서` 절로
기록합니다: 누구에게 무엇을 **먼저** 넘겨야 그 사람이 병렬로 시작할 수 있는지,
내가 무엇을 받아야 다음 단계가 열리는지. 순서가 애매하면 사용자에게 "A 와 B 중 누가
먼저 시작할 수 있어야 합니까?"로 좁힙니다.

### 4. 활용 핸드오프

- 이 사람에게 실제 요청 1건을 던질 때 → `task-brief` (선행 전달물을 브리프 범위·검증에 복사)
- AI 위임에도 동일 적용 — work-map 증강 항목의 검증·제약 서술에 선행 전달물 원리를 쓴다
- 관계자가 바뀌거나 프로젝트 단계가 넘어가면 이 스킬을 다시 불러 갱신

## 한계

- 게이트는 **형식**만 강제합니다. 제약이 충분한지는 상대에게 실제로 물어봐야 확정됩니다 —
  문서는 그 대화를 빠뜨리지 않게 하는 체크리스트입니다.
- 개인 단위 도구입니다. 조직도·권한 체계 관리가 아닙니다.
- 연락처·개인정보는 다루지 않습니다(이름·역할·채널명 수준).

## 파일 구조

```
stakeholder-map/
├── SKILL.md
├── GUIDE.md
├── CHANGELOG.md
├── scripts/
│   └── check_stakeholder.py   # 구조 게이트 C1~C4 (+W1~W4 경고, 다중 파일)
└── tests/
    ├── conftest.py
    ├── test_check_stakeholder.py
    └── fixtures/
        ├── good_stakeholder.md  # 통과 예시
        └── bad_stakeholder.md   # 실패 예시(모호어·소통 누락·비구조 제약)
```
