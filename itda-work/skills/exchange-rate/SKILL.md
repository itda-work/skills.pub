---
name: exchange-rate
description: >
  원화 기준 일별·월 평균 기준 환율을 조회하는 스킬입니다.
  "오늘 달러 환율 알려줘", "이번 달 엔화 평균 환율 보여줘", "EUR 환율 조회해줘"처럼 말하면 됩니다.
  공휴일에는 자동으로 직전 영업일 환율로 폴백합니다.
license: Apache-2.0
compatibility: Claude Code & Cowork
user-invocable: true
argument-hint: "[YYYY-MM-DD|YYYY-MM] [currency] - Date/month and optional currency code (default: USD)"
allowed-tools: Read, WebFetch, Bash(python3:*), Bash(date:*), mcp__workspace__bash, mcp__workspace__web_fetch
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.10.7"
  created_at: "2026-03-18"
  updated_at: "2026-07-26"
  tags: "exchange-rate, currency, forex, korea"
---

# Exchange Rate (매매기준율 조회)

## Instructions for Claude

When this skill is invoked, follow these steps exactly.

### Step 1: Determine the Skill Directory

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/exchange-rate}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/exchange-rate' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

### Step 2: Parse the Argument

The argument (if any) is in `$ARGUMENTS`. Parse it to extract:
- **Date or month**: `YYYY-MM-DD`, `YYYY.MM.DD`, or `YYYY-MM`
- **Currency code or alias**: e.g., `USD`, `JPY`, `달러`, `엔`

If no date/month is provided, use today's date: run `date +%Y-%m-%d`.

If no currency is provided, default to `USD`.

| Input format | Example | Mode |
|---|---|---|
| YYYY-MM-DD | `2025-01-03` | Daily rate |
| YYYY.MM.DD | `2025.01.03` | Daily rate |
| YYYY-MM | `2025-01` | Monthly average |

### Step 3: Run the Exchange Rate Script

```bash
python3 "$SKILL_DIR/scripts/exchange_rate.py" [--date DATE | --month MONTH] [--currency CODE]
```

Examples:
- `python3 "$SKILL_DIR/scripts/exchange_rate.py" --date 2025-01-05 --currency USD`
- `python3 "$SKILL_DIR/scripts/exchange_rate.py" --date 2025.01.05 --currency JPY`
- `python3 "$SKILL_DIR/scripts/exchange_rate.py" --month 2025-01 --currency EUR`
- `python3 "$SKILL_DIR/scripts/exchange_rate.py" --month 2025-01`
- `python3 "$SKILL_DIR/scripts/exchange_rate.py" --date 2025-01-05`

### Step 4: Display the Output

Display the script output directly to the user without modification.

### Error Handling

If the script exits with an error, display the error message from the script output.
The script outputs Korean error messages for user-facing errors.
