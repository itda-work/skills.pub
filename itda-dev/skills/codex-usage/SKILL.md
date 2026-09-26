---
name: codex-usage
description: >
  이 머신에 로그인된 Codex CLI(ChatGPT 계정)의 사용량(5시간·주간 창 사용률, 리셋 시각, 플랜)을
  ~/.codex/auth.json 토큰으로 직접 조회한다(codex 실행 불요, Windows 동일). "codex 사용량 얼마나
  남았어", "코덱스 한도 확인해줘", "codex 리셋 언제야", "지금 codex 돌려도 돼?" 같은 요청과 codex 를
  많이 쓰는 작업 앞 "N% 이하일 때만" 게이트(--max)에 사용한다. OpenAI API 키 과금은 대상이 아니다.
  [책임 경계] 본 스킬은 Codex CLI 구독 사용량 전담 — itda-dev:claude-usage 는 Claude Code 사용량.
license: MIT
compatibility: Claude Code · Cowork (Python 3.9+, 네트워크 필요, codex login 선행)
user-invocable: true
argument-hint: "[--max <percent>] [--window session|weekly] [--home <설정홈>]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.2.0"
  status: "experimental"
  created_at: "2026-09-11"
  updated_at: "2026-09-20"
  tags: "codex, openai, chatgpt, usage, quota, rate-limit, subscription, devtools, gate"
---

# codex-usage

Codex CLI 가 로그인하며 남긴 자격증명으로 **구독 사용량**을 읽어 JSON 으로 돌려준다. 이 스킬은
로그인·토큰 갱신을 하지 않는다 — 토큰이 만료돼 있으면 `codex` 를 한 번 실행하라고 안내한다.

## 실행

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/codex-usage}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/codex-usage' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃·~/.claude/skills 링크 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용

python3 "$SKILL_DIR/scripts/usage.py"                       # 조회
python3 "$SKILL_DIR/scripts/usage.py" --max 20              # 5시간 창 20% 이하일 때만 exit 0
python3 "$SKILL_DIR/scripts/usage.py" --window weekly --max 80
python3 "$SKILL_DIR/scripts/usage.py" --home ~/.codex-alt    # 두 번째 계정 프로필
```

**두 계정을 한 번에 물으면** `--home` 으로 프로필마다 한 번씩 돌려 에이전트가 합쳐 말한다.
한 호출이 여러 계정을 합쳐 내지는 않는다(계정마다 플랜·창 구성이 달라 섞으면 오해를 만든다).

출력은 **JSON 한 건**뿐이다. 사람에게는 에이전트가 읽어 서술한다 — 최소한 창별 `label`·`percent`·
`resets_at_local` 과 `plan` 을 한 줄로 말하고, 80% 이상 창이 있으면 먼저 말한다.

```json
{"ok": true, "provider": "codex", "config_dir": "/Users/me/.codex", "plan": "Plus", "email": "…",
 "windows": [
   {"key": "primary_window", "kind": "session", "label": "5시간", "percent": 66.0,
    "window_seconds": 18000, "resets_at": 1789106353.0, "resets_in_seconds": 10705,
    "resets_at_local": "2026-09-11 14:59"},
   {"key": "secondary_window", "kind": "weekly", "label": "7일", "percent": 27.0, "…": "…"}
 ],
 "fetched_at": "2026-09-11T12:00:47+0900",
 "gate": {"passed": false, "window": "5시간", "percent": 66.0, "max": 20.0}}
```

| exit | 뜻 |
|---|---|
| 0 | 조회 성공 (`--max` 가 있으면 임계 이하) |
| 1 | `--max` 초과 — 게이트 중단 |
| 2 | 조회 실패 — `{"ok": false, "error": …, "message": …}`. **게이트를 통과시키지 않는다** |

`error` 값: `no_credential`(로그인 안 함) · `bad_credential`(auth.json 형식) · `token_expired`
(401/403 — `codex` 한 번 실행) · `bad_response`(응답 형식 변경) · `network` · `http_<코드>`.

## 어디서 읽는가 (sheriff 실측 계약, 2026-09-11)

- **자격증명** — `<설정홈>/auth.json` 의 `tokens.access_token` + `tokens.account_id`. 키체인 없음.
  설정 홈은 **`--home` > `CODEX_HOME` > `~/.codex`** 순으로 정해지고, 출력의 `config_dir` 이
  실제로 읽은 홈이다. `CODEX_HOME` 은 codex 가 보는 것과 같은 변수라, 그 변수로 두 번째 계정을
  띄우는 구성(`cod-alt` 같은 래퍼)에서는 **인자 없이도 그 세션의 계정**을 읽는다 (#1700).
- **요청** — `GET https://chatgpt.com/backend-api/wham/usage` + `ChatGPT-Account-Id` 헤더.
  `codex doctor`·`codex exec --json` 에는 이 값이 **없다**(실측 2026-09-11). 구 `skills/scripts/
  codex_usage.py` 는 `codex app-server` 의 `account/rateLimits/read` 를 썼는데, 바이너리 기동이
  필요하고 Windows 에서 갈려 이 HTTP 경로로 통합했다(#1683).
- **응답** — `rate_limit.primary_window`·`secondary_window`. **어느 자리가 5시간인지는 계약이
  아니다** — `limit_window_seconds`(초)로 세션(≤24h)·주간을 가른다(테스트가 자리를 뒤집어 고정).
- 이 계약의 원본은 `~/Apps/itda-skills/sheriff` 의 `Core/UsageStatus.swift` 다.

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| Claude Code 사용량 | itda-dev:claude-usage |
| OpenAI API 키 과금(platform.openai.com) | 해당 없음 — 대시보드에서 직접 |
| 메뉴 막대 상시 표시·80/100% 알림 | sheriff 앱 (같은 계약의 상주판) |

## 금지선

- 토큰 값을 출력·로그·이슈 코멘트에 싣지 않는다(테스트가 고정).
- 자격증명을 갱신·재발급하지 않는다. 만료는 안내만 한다.
