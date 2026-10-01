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
  version: "0.2.0"
  category: "data-fetching"
  status: "experimental"
  created_at: "2026-06-01"
  updated_at: "2026-09-30"
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

**먼저** 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 `SKILL_DIR` 에 넣고 아래 블록을 실행한다 — 블록은 그 값을 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾는다(후보가 여럿이면 멈춘다).

```bash
# SKILL_DIR 확정(skill-dir-resolution) — 스킬을 불러올 때 받은 base directory 를 먼저 SKILL_DIR="그 경로" 로 넣는다(항상)
# 블록은 그 값을 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾는다 — SKILL.md 가 있는 후보가 하나일 때만 받고 아니면 멈춘다
SKILL_DIR=$(sh -c '
S=$1 P=$2 H=${5:-$HOME/.claude}
ok() { d=${1%/}; [ "${d##*/}" = "$S" ] && [ -f "$d/SKILL.md" ] && (cd "$d" && pwd -P); }
[ -n "$3" ] && { ok "$3" && exit; d=${3%/}; [ "${d##*/}" = "$S" ] && echo "SKILL_DIR 무시: $3 에 SKILL.md 가 없다" >&2; }
[ -n "$4" ] && { ok "$4/skills/$S" && exit; echo "CLAUDE_PLUGIN_ROOT 무시: $4/skills/$S 에 SKILL.md 가 없다" >&2; }
c=$(for d in "$H"/plugins/synced/*/"$P"/skills/"$S" "$H"/plugins/synced/*/"$P"~*/skills/"$S" "$H"/plugins/cache/*/"$P"/*/skills/"$S" \
    /root/.claude/plugins/synced/*/"$P"/skills/"$S" /root/.claude/plugins/synced/*/"$P"~*/skills/"$S" \
    /sessions/*/mnt/.remote-plugins/*/skills/"$S" /sessions/*/mnt/.claude/skills/"$S"; do ok "$d"; done | sort -u)
[ "$(printf "%s\n" "$c" | grep -c .)" -gt 1 ] && { printf "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다:\n%s\n" "$c" >&2; exit 1; }
printf "%s\n" "$c"' _ eatery-trend itda-travel "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'eatery-trend'; $P = 'itda-travel'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
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

**키는 환경변수로만 넣는다 — 스킬은 `.env` 같은 파일을 읽지 않는다(itda-work/skills#45):**

| 환경 | 키를 넣는 곳 | 쓰이는 곳 |
|---|---|---|
| Claude Code | 셸 환경변수, 또는 키마다 `claude config set env.NAVER_CLIENT_ID "..."`(`NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET`·`NAVER_SEARCHAD_ACCESS_KEY`·`NAVER_SEARCHAD_SECRET_KEY`·`NAVER_SEARCHAD_CUSTOMER_ID`, 등록 뒤 세션을 다시 시작) | 스크립트가 `os.environ` 에서 읽는다 |

> itda-hyve 시크릿 경로는 이 스킬에 아직 없다 — 스크립트가 API 를 직접 부르므로 itda-hyve 에 등록한 키는 쓰이지 않는다.

> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find`·파일 열람으로 **사전 점검하지 않는다** — 스크립트를 **우선 실행**한다. 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수가 선언돼 있는 경우 그 값을 환경변수로 전달해 재시도한다 — 예: `NAVER_CLIENT_ID=<...> ... python3 "$SKILL_DIR/scripts/main.py" ...`. 지침에도 없으면 해당 소스가 fail-loud로 사유를 표시한다. `.env` 파일을 만들라고 안내하지 않는다(스크립트가 읽지 않는다). 키 값을 대화로 받지 않는다.

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수의 NAVER_CLIENT_ID 를 사용했습니다"). 값은 어디에도 표시하지 않는다.

> 스크립트의 키 소스(REQ-008): `os.environ`(Claude 주입 포함). env 파일·`~/.claude/settings.json` 은 읽지 않는다.
> 키가 없으면 해당 소스는 fail-loud로 사유를 표시합니다(크래시 아님).
> 자동완성은 무인증이라 키 없이도 동작합니다.

## 제약 (Exclusions)

- **인스타그램 직접 스크래핑 영구 비목표** — 검색량 surge가 인스타 유행의 다운스트림 그림자.
- 예약/결제(캐치테이블 영역) · 실시간 분 단위(데이터랩 일/주 lag 수용) 미지원.
- v1 wedge = 여행지/테마. 전국 cold 신상 발굴은 콘텐츠(유튜브) 발굴축 도입 후(로드맵).
- 지역검색 쿼리당 5건 cap · 0매칭(팝업/미등록)은 웹 폴백 권장 · 동음 다수는 리뷰수 tiebreak(OQ-3 잔여).
- surge 절대값은 작을 수 있음(1.2~2.2) · 카테고리 상대 YoY로 macro 보정하나 데이터랩 범위 제약.
