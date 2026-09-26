---
name: eatery-trend
description: >
  여행지·동네의 '지금 뜨는' 맛집과 음식 트렌드를 검색량 surge로 탐지하는 스킬입니다.
  "제주 요즘 뜨는 맛집", "성수에서 트렌디한 국밥", "지금 핫한 디저트 뭐야"처럼 말하면 됩니다.
  평점(레벨)이 아니라 관심의 급증(velocity)으로 유행을 판별하고, 협찬 거품은 검색량으로 거릅니다.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, Glob, Grep, mcp__workspace__bash
argument-hint: "[지역/테마] 또는 [동네 주제]"
metadata:
  author: "Chinseok"
  version: "0.1.3"
  category: "data-fetching"
  status: "experimental"
  created_at: "2026-06-01"
  updated_at: "2026-07-26"
  tags: "restaurant, food-trend, hotplace, search-volume, surge, naver-datalab, searchad, eatery-trend"
---

# eatery-trend

여행지·동네의 **지금 뜨는 맛집·음식 트렌드**를 탐지합니다. 핵심 가설:
**유행 = 평점(레벨)이 아니라 관심의 미분(검색량 velocity)**. 네이버 데이터랩
검색트렌드의 surge를 측정해 *지금 떠오르는지*를 판별하고, 블로그/검색 비율로
협찬 거품을 거릅니다. 장소는 네이버 공식 지역검색 API로 해결합니다(스크래핑 0).
사용자용 가이드는 GUIDE.md 참조.

## 두 모드

- **모드 B — 핫키워드 탐지(주 파이프라인)**: `지역/테마 seed`(예: 제주) →
  뜨는 음식·디저트·테마 키워드 Top-N + surge 근거 + 매핑 가게.
- **모드 A — 검색 보강**: `동네 + 주제`(예: 성수 국밥) → 가게목록 + 주제 surge 맥락.

## 실행

먼저 스킬 디렉토리를 확정합니다(이후 모든 실행이 이 기준).

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/eatery-trend}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/eatery-trend' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\eatery-trend"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/main.py" --mode B --seed 제주              # 핫키워드 탐지
python3 "$SKILL_DIR/scripts/main.py" --mode B --seed 제주 --emit-candidates   # 발굴+relevance만(LLM 판정 전)
python3 "$SKILL_DIR/scripts/main.py" --mode B --seed 제주 --judge-file verdicts.json  # LLM 판정 반영
python3 "$SKILL_DIR/scripts/main.py" --mode A --region 성수 --topic 국밥  # 동네×주제

# Windows
py -3 "$env:SKILL_DIR\scripts\main.py" --mode B --seed 제주
```

옵션: `--top-n N`(기본 10) · `--json` · `--no-cache` · `--throttle 초`.

## Claude 라우팅 가이드

Claude가 이 스킬을 실행할 때 반드시 따르는 행동 규칙입니다. (전 사용자 공유
행동 규칙의 single source of truth는 본 섹션)

**규칙 1 — 모드 판별**
"요즘 뜨는 맛집", "제주 핫플", "지금 뭐가 떠?"처럼 *지역/테마*만 있으면 모드 B
(`--mode B --seed <지역>`). "성수 국밥", "이 동네 트렌디한 곳"처럼 *동네+주제*면
모드 A(`--mode A --region <동네> --topic <주제>`).

**규칙 2 — LLM 음식 판정 (REQ-015, 필수)**
출력에 `🤔 LLM 음식 판정 필요` 목록이 나오면 Claude가 직접 판정합니다. 이 단계는
스킬의 정확도 핵심입니다(휴리스틱 사전 재현율 ~56%, 44% 놓침). 절차:
1. `--emit-candidates`로 후보를 먼저 받거나, 일반 실행의 needs_llm 목록을 확인.
2. 각 후보를 **음식/먹거리(true) vs 관광·교통·쇼핑·체험(false)**으로 판정.
   - 먹거리 시장(동문시장·올레시장·오일장)·트렌드 먹거리(마음샌드)·요리명(텐동·조개구이) = **true**.
   - 관광지(섭지코지·만장굴·비자림)·공항·기념품·액티비티(카트) = **false**.
3. `{"키워드": true/false}` JSON을 저장하고 `--judge-file`로 재실행.
   판정된 음식 후보가 velocity 검증 파이프라인에 진입합니다.

**규칙 3 — 레벨 vs 속도 구분 (REQ-006)**
출력의 "레벨(월검색량)"과 "속도(surge/상대YoY)"를 혼동해 설명하지 않습니다.
유명한데 안 뜨는 집(높은 레벨·평탄 속도)은 *클래식이지 유행이 아님*을 명시합니다.

**규칙 4 — 3레인 분리 표기 (REQ-017)**
🆕 신규출현 / 🔥 검증상승 / 📺 미디어스파이크를 구분해 전달합니다. 미디어스파이크
(성시경·흑백요리사 효과)는 **지속성이 약할 수 있음**을 함께 안내합니다(막주 모멘텀).

**규칙 5 — 거품·노이즈 강등 사유 전달 (REQ-007)**
"협찬 거품 강등"(블로그 폭발·검색 미달)과 단순 노이즈를 구분해 사유를 전달합니다.

**규칙 6 — fail-loud (REQ-008)**
출력에 `🚨 소스 상태`가 있으면 일부 데이터 소스 도달 실패를 의미합니다. 빈 결과를
"뜨는 곳 없음"으로 단정하지 말고 소스 실패를 사용자에게 알립니다.

**규칙 7 — 출력 한국어 고정**, 모드 A는 모든 가게에 surge를 붙이지 않습니다(평범한
가게가 평탄한 건 정상 — REQ-020).

## 사전 준비 (자격증명)

네이버 OpenAPI(데이터랩·검색)와 검색광고 API 키가 필요합니다.

> **⚠️ NAVER API HUB 이관 고지 (2026-07 약관 변경)**: 네이버 OpenAPI(검색·데이터랩)는 네이버클라우드(NCP) **NAVER API HUB**로 이관된다. 2026-07-30 이후 개발자센터 신규 이용 신청 불가 — 신규 사용자는 NAVER API HUB에서 발급하도록 안내한다. 기존 키는 **2027-06-30까지** 현행대로 동작한다. 검색광고 API는 별개 서비스로 무관.

**권장 (비개발자 포함 모든 사용자) — 작업 폴더 `.env`에 키 등록:**

작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트) 루트에 `.env` 파일을 만들고 아래 다섯 줄을 넣어 두면 스킬이 자동으로 찾아 읽습니다. 파일명 별칭 `.env.txt`·`env.txt`·`환경변수.txt` 도 동일하게 탐색된다. `.env` 대신 셸 환경변수나 `~/.claude/settings.json` 의 `env` 로 설정해 두어도 로더가 자동으로 찾습니다.

```dotenv
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
NAVER_SEARCHAD_ACCESS_KEY=...
NAVER_SEARCHAD_SECRET_KEY=...
NAVER_SEARCHAD_CUSTOMER_ID=...
```

> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find` 등으로 **사전 점검하지 않는다** — 스크립트가 `.env`·`.env.txt`·`env.txt`·`환경변수.txt` 를 스스로 탐색하므로 **우선 실행**한다(셸 glob·검색 패턴은 별칭을 놓쳐 오탐한다: `.env*`→env.txt 누락, `*env*`→환경변수.txt 누락). 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수가 선언돼 있는 경우 그 값을 환경변수로 전달해 재시도한다 — 예: `NAVER_CLIENT_ID=<...> ... python3 "$SKILL_DIR/scripts/main.py" ...`. 지침에도 없으면 해당 소스가 fail-loud로 사유를 표시한다. 수동 확인이 꼭 필요하면 파일명 4종(`.env`·`.env.txt`·`env.txt`·`환경변수.txt`)을 그대로 나열해 확인한다.

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수.txt 의 NAVER_CLIENT_ID 를 사용했습니다") — 사용자가 어느 설정파일이 쓰였는지 인지하게 하는 계약이다. 값은 어디에도 표시하지 않는다.

**개발자 (선택) — 환경변수 / `.env`:** 셸 환경변수, `~/.claude/settings.json`의 env, 실행 위치(cwd) 또는 `$HOME`의 `.env` 파일도 사용할 수 있습니다.
> 키 조회 우선순위(REQ-008): **셸 환경변수 > `~/.claude/settings.json`의 env(Claude 주입 포함) >
> 실행 위치(cwd) 또는 `$HOME`의 `.env` 파일**. 임의 디렉토리에서 실행하면서 키가
> 이 위치들에 없으면 해당 소스는 fail-loud로 사유를 표시합니다(크래시 아님).
> 자동완성은 무인증이라 키 없이도 동작합니다.

## 제약 (Exclusions)

- **인스타그램 직접 스크래핑 영구 비목표** — 검색량 surge가 인스타 유행의 다운스트림 그림자.
- 예약/결제(캐치테이블 영역) · 실시간 분 단위(데이터랩 일/주 lag 수용) 미지원.
- v1 wedge = 여행지/테마. 전국 cold 신상 발굴은 콘텐츠(유튜브) 발굴축 도입 후(로드맵).
- 지역검색 쿼리당 5건 cap · 0매칭(팝업/미등록)은 웹 폴백 권장 · 동음 다수는 리뷰수 tiebreak(OQ-3 잔여).
- surge 절대값은 작을 수 있음(1.2~2.2) · 카테고리 상대 YoY로 macro 보정하나 데이터랩 범위 제약.
