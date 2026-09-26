---
name: place-finder
description: >
  카카오맵 기준으로 근처 장소를 목적별로 찾아주는 스킬입니다.
  "강남역 근처 술집 찾아줘", "홍대에서 와이파이 되는 카페", "제주공항 근처 숙소"처럼
  위치와 목적을 말하면 됩니다. 맛집·카페·술집·숙박·관광명소·편의점·약국·주유소·
  지하철역·주차장 등 엄선된 카테고리를 거리순으로 정리합니다.
license: MIT
compatibility: "Python 3.10+ (표준 라이브러리만 사용, 추가 설치 없음)"
user-invocable: true
allowed-tools: Bash, Read, AskUserQuestion, mcp__workspace__bash
argument-hint: "강남역 근처 술집 / 홍대 와이파이 카페 / 제주공항 숙소"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.1.3"
  status: "experimental"
  created_at: "2026-06-05"
  updated_at: "2026-07-26"
  tags: "place, kakao, map, nearby, restaurant, cafe, bar, hotel, search, location, travel, place-finder"
---

# place-finder

위치(역명/동네/랜드마크)와 목적을 받아 **카카오맵 기준 근처 장소**를 거리순으로
찾아줍니다. 사용자용 가이드는 GUIDE.md 참조.

## ⚠️ 시작 전 반드시 확인 (디스클레이머)

- **카카오맵 비공식 검색**을 사용합니다. 카카오 이용약관(ToS) 위반 소지가 있으며,
  카카오 측 변경으로 **언제든 동작이 멈출 수 있습니다**.
- **읽기 전용·1회성** 조회만 합니다. 예약·결제·리뷰작성·길찾기는 하지 않습니다.
- **매크로(자동 반복 조회·폴링)는 제공하지 않으며 금지**합니다. 사용자가 다시 요청할
  때 1회만 실행합니다.
- **실시간 영업중 여부·메뉴·영업시간은 제공하지 않습니다.** 그 정보가 필요하면 결과의
  카카오맵 링크를 안내합니다.

## 자격증명

**필요 없습니다.** 카카오 개발자 키 없이 동작합니다.

## 카테고리 프리셋 (4묶음)

| 묶음 | 프리셋 |
|---|---|
| 먹거리 | 맛집 · 카페 · 술집 |
| 여행 | 숙박 · 관광명소 |
| 편의 | 편의점 · 약국 · 은행(ATM) · 주유소 |
| 교통 | 지하철역 · 주차장 |

## 실행

> **실행 전제**: 표준 라이브러리만 사용하므로 추가 설치나 `PYTHONPATH` 설정이
> 필요 없습니다.

먼저 스킬 디렉토리를 확정합니다(이후 모든 실행이 이 기준).

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/place-finder}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/place-finder' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\place-finder"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/main.py" search --near 강남역 --category 술집
python3 "$SKILL_DIR/scripts/main.py" search --near 홍대입구역 --category 카페 --amenity wifi
python3 "$SKILL_DIR/scripts/main.py" search --near 제주공항 --category 숙소 --sort rating --limit 5 --json

# Windows
py -3 "$env:SKILL_DIR\scripts\main.py" search --near 강남역 --category 술집
```

옵션(모두 서브커맨드 `search` **뒤**에 둡니다):
- `--near` (필수): 기준 위치(역명/동네/랜드마크)
- `--category` (필수): 프리셋명(맛집/카페/술집/숙박/관광명소/편의점/약국/은행/주유소/지하철역/주차장), 자연어, 또는 자유 키워드(칼국수·돈까스 등 구체 음식/업종)
- `--amenity`: 편의시설 필터(쉼표) — `parking,wifi,pet,smoking,reservation,delivery,package,disabled`
- `--limit`: 결과 개수(기본 5)
- `--sort`: `distance`(기본 거리순) 또는 `rating`(평점순)
- `--json`: JSON 출력

## Claude 라우팅 가이드

Claude가 이 스킬을 실행할 때 반드시 따르는 행동 규칙입니다.

**규칙 1 — 위치 먼저 확인 (필수)**
위치 정보 없이 바로 검색하지 않습니다. 위치가 없으면 먼저 묻습니다:
`현재 위치나 찾고 싶은 동네를 알려주세요. 강남역/홍대입구/제주공항 같은 역명·동네·
랜드마크면 됩니다.` 위치가 애매하면 가까운 역명·동 이름으로 한 번 더 확인합니다.

**규칙 2 — 카테고리·자유 키워드 매핑**
"혼술"·"한잔" → 술집, "재울 곳"·"잘 데" → 숙박. 프리셋에 없는 구체 음식·업종
("칼국수"·"돈까스"·"파스타")은 `--category`에 그대로 넣으면 자유 키워드로 검색합니다.
"지금 뜨는 맛집"은 eatery-trend로 안내(이 스킬은 위치 기반 검색).

**규칙 3 — 목적 조건을 편의시설 필터로**
"주차되는" → `--amenity parking`, "반려동물 동반" → `pet`, "와이파이"·"카공" →
`wifi`, "흡연 가능" → `smoking`, "예약 되는" → `reservation`. 여러 개면 쉼표로 묶습니다.

**규칙 4 — 정렬 의도 반영**
기본은 거리순입니다. "평점 높은"·"별점순" 요청이면 `--sort rating`.

**규칙 5 — fail-loud (사유 전달)**
"위치를 찾지 못했습니다", "카카오맵 접근 제한" 등 오류는 사유를 그대로 사용자에게
전달합니다. 빈 결과를 "없음"으로 단정하기 전에 위치·카테고리·차단 여부를 점검합니다.

**규칙 6 — 영업상태·메뉴는 링크로 위임**
이 스킬은 실시간 영업중 여부·메뉴·영업시간을 제공하지 않습니다. 사용자가 물으면
결과의 카카오맵 링크에서 확인하도록 안내합니다.

**규칙 7 — 매크로 금지**
취소표 낚기·자동 반복 조회 루프를 만들지 않습니다. 1회성 검색만 수행합니다.

## 제약 (Exclusions)

- **예약·결제·길찾기·경로 안내** — 비목표(위치 검색만).
- **실시간 영업중·메뉴·영업시간** — 비목표(카카오맵 링크 위임). 후속 증분 후보.
- **매크로/반복 폴링** — 영구 비목표.
- **공식 카카오 로컬 API 백엔드** — v1 미구현(어댑터 추상화로 여지만 둠).
- 카카오 측 변경 시 동작이 멈출 수 있으며, 결과의 정확성·최신성은 카카오 데이터에 의존합니다.
