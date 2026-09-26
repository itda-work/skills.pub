---
name: weather-here
description: >
  현재 위치 또는 지정 지역의 날씨를 한국어로 빠르게 조회하는 스킬입니다.
  "날씨 알려줘", "지금 여기 날씨 어때", "부산 날씨 알려줘"처럼 말하면 됩니다.
  위치 미지정 시 IP 지오로케이션으로 자동 탐지하고, 기본은 한 줄 요약, 상세는 --detail 옵션입니다.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, Glob, Grep, mcp__workspace__bash
argument-hint: "[지역명(선택)]"
metadata:
  author: "Chinseok"
  version: "0.12.5"
  category: "data-fetching"
  status: "experimental"
  created_at: "2026-05-19"
  updated_at: "2026-07-26"
  tags: "open-meteo, weather, location, openmeteo, keyless"
---

# weather-here

현재 위치 또는 지정 지역의 날씨를 한국어로 빠르게 조회합니다. 데이터는
Open-Meteo Forecast(무키), 위치 정확성은 기상청 권위 좌표표(260점,
시청 <1km 검증)로 보장. **사전 준비 불요(인증키·신청 없음).**
사용자용 가이드는 GUIDE.md 참조.

## 실행

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/weather-here}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/weather-here' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용

python3 "$SKILL_DIR/scripts/weather_here.py"            # 위치 자동탐지(되묻지 않음)
python3 "$SKILL_DIR/scripts/weather_here.py" 부산        # 지역 지정
python3 "$SKILL_DIR/scripts/weather_here.py" 부산 --detail   # 상세 수치
```

```powershell
# Windows
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\weather-here"  # 미설정이면 SKILL.md 위치 절대경로 사용
py -3 "$env:SKILL_DIR\scripts\weather_here.py" [지역]
```

출력 예: `부산광역시 · 오늘 구름 조금, 강수확률 2% — 비 올 가능성 낮아요`
(`--detail`은 기온·습도·강수량·풍속+강수확률 블록)

## Claude 라우팅 가이드

Claude가 이 스킬을 실행할 때 반드시 따라야 하는 행동 규칙입니다.
(전 사용자 공유 행동 규칙의 single source of truth는 본 섹션)

**규칙 1 — 위치 되묻기 금지 (REQ-007)**
"날씨 알려줘", "지금 날씨", "지금 여기 날씨" 처럼 위치를 명시하지 않으면
"어느 지역인가요?" 등으로 되묻지 말고 즉시 `python3 "$SKILL_DIR/scripts/weather_here.py"`
를 실행하여 IP 자동탐지로 진행합니다.

**규칙 2 — 지역명 우선 (REQ-003)**
"부산 날씨", "수원 날씨 알려줘" 처럼 지역명(한국어 또는 주요 영문 별칭)이
발화에 있으면 IP를 무시하고 `python3 "$SKILL_DIR/scripts/weather_here.py" 부산` 형태로
지역명을 인자로 전달합니다.

**규칙 3 — IP 실패 안내 (REQ-008)**
스크립트가 "현재 위치를 자동으로 파악할 수 없습니다"를 반환하면
사용자에게 지역명을 1회 안내합니다(비대화형, 대화 차단 금지).

**규칙 4 — 조회 실패 안내 (REQ-013)**
"날씨 정보를 가져오는 데 실패했습니다" 안내가 나오면 네트워크 일시
오류이므로 잠시 후 재시도를 1회 안내합니다(되묻기 금지).

**규칙 5 — 출력 한국어 고정**
모든 출력은 한국어이며 첫 줄에 어느 지역 기준인지 표기됩니다. 해외
위치는 "(해외·대략·미검증)" 라벨이 붙습니다.

## 제약 (Exclusions)

현재값+오늘 gist만(다일·주간 예보 없음) · 캐싱 없음 · 시·도+시군구(일반구
포함)까지(읍면동 미지원) · 외부 지오코더 미사용 · 해외는 best-effort+
"(해외·대략·미검증)" 라벨 · 대기질/자외선/일출몰/특보 미지원 · 출력 한국어
고정(입력은 한·영 주요 별칭).
