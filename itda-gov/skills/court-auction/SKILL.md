---
name: court-auction
description: >
  대법원 법원경매정보(courtauction.go.kr)의 부동산 매각공고·사건·물건을 조회하는 스킬입니다.
  "오늘 서울중앙지법 경매 공고 보여줘", "2024타경100001 사건 진행상황 알려줘",
  "강남 아파트 5억 이하 유찰 1회 물건 찾아줘"처럼 말하면 됩니다.
  읽기 전용·참고용이며, 입찰 전 반드시 법원 원문을 재확인하세요.
license: Apache-2.0
compatibility: "Python 3.10+ (표준 라이브러리만 사용, 추가 설치 없음)"
user-invocable: true
allowed-tools: Bash, Read, AskUserQuestion, mcp__workspace__bash
argument-hint: "서울중앙지법 오늘 경매 / 2024타경100001 사건 / 강남 아파트 5억 이하 경매"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.1.3"
  status: "experimental"
  created_at: "2026-06-05"
  updated_at: "2026-07-26"
  tags: "court-auction, auction, realestate, courtauction, property, real-estate-auction, foreclosure, court"
---

# court-auction

대법원 **법원경매정보**(`courtauction.go.kr`)의 부동산 매각공고·사건·물건을 조회해
JSON으로 돌려줍니다. itda-realty의 시장 데이터(실거래·전세·공급·가격)와 달리 **경매
매물**을 다룹니다. 사용자용 가이드는 GUIDE.md 참조.

## ⚠️ 시작 전 반드시 확인 (디스클레이머)

- 공식 OPEN API가 없어 **사이트 내부 WebSquare 검색(비공식 XHR)** 을 호출합니다.
  사이트 정책 변경으로 **언제든 동작이 멈출 수 있습니다**.
- 사이트는 **IP 단위 자동화 차단이 공격적**입니다(≈16회/30초면 1시간 차단). 이 스킬은
  호출 간 2초 지연·세션 10회 budget·차단 즉시 중단으로 보수적으로 동작하며,
  **차단되면 같은 IP로 약 1시간 뒤에야 복구**됩니다.
- **읽기 전용·참고용**입니다. 데이터는 공고 시점 기준이며 정정·취하·연기로 바뀔 수
  있으니 **입찰 전 반드시 법원 원문 매각공고를 재확인**하세요.
- **입찰서 자동 작성·제출·결제는 제공하지 않으며**(입찰은 법원에서 사람이 직접),
  매크로(자동 반복 조회·폴링)도 제공하지 않습니다.

## 자격증명

**필요 없습니다.** API 키 없이 동작합니다(사이트 세션 쿠키만 내부적으로 사용).

## 워크플로우 / 서브커맨드

| 서브커맨드 | 용도 |
|---|---|
| `codes courts\|bid-types\|usages\|regions` | 법원사무소코드(동적)·입찰구분·용도·지역 코드표 |
| `notices` | 매각공고 목록(월·법원·입찰구분) |
| `notice-detail` | 공고 펼치기 → 사건/물건(사건번호·용도·주소·감정가·최저가) |
| `case` | 사건번호 직접 조회(진행상태·기일별 결과) |
| `search` | 물건 자유 조건검색(지역·용도·가격·면적·유찰횟수) |

## 실행

> 표준 라이브러리만 사용하므로 추가 설치나 `PYTHONPATH` 설정이 필요 없습니다.
> 모든 옵션은 서브커맨드 **뒤**에 둡니다. 결과는 JSON(stdout)입니다.

먼저 스킬 디렉토리를 확정합니다.

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/court-auction}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/court-auction' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\court-auction"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/main.py" codes courts
python3 "$SKILL_DIR/scripts/main.py" notices --date 2026-04 --court-code B000210 --bid-type date
python3 "$SKILL_DIR/scripts/main.py" case --court-code B000210 --case-number 2024타경100001
python3 "$SKILL_DIR/scripts/main.py" search --sido 서울특별시 --usage-large 건물 --price-max 500000000 --flbd-min 1

# Windows
py -3 "$env:SKILL_DIR\scripts\main.py" codes courts
```

> 저장소 체크아웃에서 개발용으로 실행할 때는 `SKILL_DIR=itda-gov/skills/court-auction` 을 저장소 루트에서 지정하면 위 명령이 그대로 동작합니다.

공고 펼치기(`notice-detail`)는 `notices` 응답 각 row의 `raw.cortOfcCd`·`raw.dspslDxdyYmd`·
`raw.jdbnCd`(재판부 토큰)를 그대로 넘깁니다:

```bash
python3 "$SKILL_DIR/scripts/main.py" notice-detail \
  --court-code B000210 --sale-date 20260427 --jdbn-cd <raw.jdbnCd>
```

## Claude 라우팅 가이드

Claude가 이 스킬을 실행할 때 따르는 행동 규칙입니다.

**규칙 1 — 법원코드 먼저**
`notices`(선택)·`case`(필수)는 법원사무소코드(예: 서울중앙지방법원 `B000210`)를
씁니다. 모르면 `codes courts`로 찾거나 사용자에게 어느 법원인지 묻습니다.

**규칙 2 — 사건번호 형식**
`2024타경100001` 권장(`2024-100001`도 자동 정규화). `case`가 `found:false`면 사건번호·
법원이 맞는지 다시 확인합니다(없다고 단정하지 않음).

**규칙 3 — 공고 펼치기는 raw 토큰 전달**
`notice-detail`은 `notices` 결과의 `raw.jdbnCd`(재판부 암호화 토큰)가 필수입니다.
목록을 먼저 조회해 사용자가 고른 공고의 raw 필드를 넘깁니다.

**규칙 4 — 차단·예산 시 fail-loud (자동 재시도 금지)**
`ok:false` + 차단/budget 사유가 오면 그대로 사용자에게 전달합니다. **자동으로 다시
시도하지 않습니다**(차단 연장 위험). 차단이면 약 1시간 뒤·다른 네트워크를 안내합니다.

**규칙 5 — 정직 고지 (매번)**
결과를 전할 때 ① 참고용이며 **입찰 전 법원 원문 재확인** ② 가격·기일은 **공고 시점
기준**(정정·취하·연기 가능)임을 함께 알립니다.

**규칙 6 — read-only·매크로 금지**
입찰서 작성·제출·결제는 하지 않습니다. 반복 조회 루프를 만들지 않고 1회성으로만
실행합니다. 연속 조회가 필요하면 2초 간격·10회 budget 안에서만, 차단 위험을 알립니다.

**규칙 7 — budget 안내**
여러 번 조회했으면 남은 호출 여지(세션 10회)를 사용자에게 알려 추가 조회를 판단하게
합니다. 같은 클라이언트 세션은 warmup 쿠키를 재사용합니다.

## 출력 / 에러

- 성공: `{"ok": true, ...정규화 결과}` (count·items 등). Claude가 천단위 콤마 + 억/만
  환산으로 한국어 요약해 전달합니다.
- 실패: `{"ok": false, "error": "<한국어 사유>"}` + 종료코드 4. 차단·예산초과·세션만료·
  네트워크 오류를 사유로 구분합니다.

## 제약 (Exclusions)

- **입찰서 자동 작성·제출·결제** — 영구 비목표(입찰은 법원에서 사람이 직접).
- **매크로/반복 폴링** — 영구 비목표.
- **동산(자동차·중기) 경매** — v1 범위 밖.
- **매각물건명세서·현황조사서·감정평가서 PDF·물건 사진** — 후속 증분 후보.
- **물건 자유검색(search)** 은 라이브에서 raw 호출로 정상 동작을 확인했으나(warmup 쿠키
  확보 시), 사이트 WAF 정책상 빈번·연속 조회 때 HTTP 400/차단이 날 수 있습니다(조건을
  줄이거나 잠시 후 재시도). Playwright 폴백은 현재 불필요하여 미구현입니다.
- 사이트 변경 시 동작이 멈출 수 있으며, 결과의 정확성·최신성은 법원경매정보 데이터에 의존합니다.
