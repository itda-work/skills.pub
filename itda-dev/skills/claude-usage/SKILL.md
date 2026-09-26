---
name: claude-usage
description: >
  이 머신에 로그인된 Claude Code 계정의 사용량(5시간·7일 창 사용률, 모델별 주간 한도, 리셋 시각,
  플랜)을 저장된 OAuth 자격증명으로 직접 조회한다. "claude 사용량 얼마나 남았어", "클로드 코드 한도
  확인해줘", "5시간 창 리셋 언제야", "지금 claude 써도 돼?" 같은 요청과 무거운 작업 앞 "N% 이하일
  때만" 게이트(--max)에 사용한다. API 키 과금은 대상이 아니다. [책임 경계] 본 스킬은 Claude Code
  구독 사용량 전담 — itda-dev:codex-usage 는 Codex CLI 사용량.
license: MIT
compatibility: Claude Code · Cowork (Python 3.9+, 네트워크 필요, claude 로그인 선행)
user-invocable: true
argument-hint: "[--max <percent>] [--window session|weekly] [--home <설정홈>]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.2.0"
  status: "experimental"
  created_at: "2026-09-11"
  updated_at: "2026-09-20"
  tags: "claude, claude-code, usage, quota, rate-limit, subscription, devtools, gate"
---

# claude-usage

Claude Code 가 로그인하며 남긴 자격증명으로 **구독 사용량**을 읽어 JSON 으로 돌려준다. 이 스킬은
로그인·토큰 갱신을 하지 않는다 — 토큰이 만료돼 있으면 `claude` 를 한 번 실행하라고 안내한다.

## 실행

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/claude-usage}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/claude-usage' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃·~/.claude/skills 링크 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용

python3 "$SKILL_DIR/scripts/usage.py"                       # 조회
python3 "$SKILL_DIR/scripts/usage.py" --max 20              # 5시간 창 20% 이하일 때만 exit 0
python3 "$SKILL_DIR/scripts/usage.py" --window weekly --max 80
python3 "$SKILL_DIR/scripts/usage.py" --home ~/.claude-alt   # 두 번째 계정 프로필
```

**두 계정을 한 번에 물으면** `--home` 으로 프로필마다 한 번씩 돌려 에이전트가 합쳐 말한다.
한 호출이 여러 계정을 합쳐 내지는 않는다(계정마다 플랜·창 구성이 달라 섞으면 오해를 만든다).

출력은 **JSON 한 건**뿐이다. 사람에게는 에이전트가 읽어 서술한다 — 최소한 창별 `label`·`percent`·
`resets_at_local` 과 `plan` 을 한 줄로 말하고, 80% 이상 창이 있으면 먼저 말한다.

```json
{"ok": true, "provider": "claude", "config_dir": "/Users/me/.claude", "plan": "Max 20x", "email": "…",
 "windows": [
   {"key": "five_hour", "kind": "session", "label": "5시간", "percent": 19.0,
    "resets_at": 1789105200.7, "resets_in_seconds": 9588, "resets_at_local": "2026-09-11 14:40"},
   {"key": "seven_day", "kind": "weekly", "label": "7일", "percent": 80.0, "…": "…"},
   {"key": "weekly_scoped:Fable", "kind": "other", "label": "7일 Fable", "percent": 87.0, "…": "…"}
 ],
 "fetched_at": "2026-09-11T12:00:12+0900",
 "gate": {"passed": true, "window": "5시간", "percent": 19.0, "max": 20.0}}
```

| exit | 뜻 |
|---|---|
| 0 | 조회 성공 (`--max` 가 있으면 임계 이하) |
| 1 | `--max` 초과 — 게이트 중단 |
| 2 | 조회 실패 — `{"ok": false, "error": …, "message": …}`. **게이트를 통과시키지 않는다** |

`error` 값: `no_credential`(로그인 안 함) · `token_expired`(401/403 — `claude` 한 번 실행) ·
`bad_response`(응답 형식 변경 — 스킬 갱신 필요) · `network` · `http_<코드>`.

## 어디서 읽는가 (sheriff 실측 계약, 2026-09-11)

- **자격증명** — macOS 는 키체인 `Claude Code-credentials`(`/usr/bin/security` 로 읽는다 — Claude Code 가
  그 도구로 넣어 ACL 확인 창이 안 뜬다)와 `~/.claude/.credentials.json` **둘 다** 읽어 `expiresAt` 이
  늦은 쪽을 쓴다. 파일에 폐기된 옛 토큰이 남아 있는 것이 실측이다. Windows·Linux 는 파일만.
- **요청** — `GET https://api.anthropic.com/api/oauth/usage` + `anthropic-beta: oauth-2025-04-20`
  (이 헤더가 없으면 401). 이메일은 `/api/oauth/profile` 의 `account.email`(`--no-email` 로 생략).
- **응답** — `five_hour`·`seven_day` 는 상시, `seven_day_opus` 같은 버킷은 있을 때만. 모델별 주간 한도
  (Fable 등)는 상위 버킷이 아니라 `limits[]` 의 `weekly_scoped`(`scope.model.display_name`)로만 온다.
- 이 계약의 원본은 `~/Apps/itda-skills/sheriff` 의 `Core/UsageStatus.swift` 다. 응답이 바뀌어
  `bad_response` 가 나면 그쪽 실측을 먼저 대조한다.

## 프로필 — 계정이 둘 이상일 때 (#1700)

읽을 설정 홈은 **`--home` > `CLAUDE_CONFIG_DIR` > `~/.claude`** 순으로 정해지고, 출력의
`config_dir` 이 실제로 읽은 홈이다. `CLAUDE_CONFIG_DIR` 로 두 번째 계정을 띄우는 구성
(`cc-alt` 같은 래퍼)에서는 그 변수가 이 스크립트까지 내려오므로 **인자 없이도 그 세션의
계정**을 읽는다.

설정 홈이 바뀌면 자격증명 파일만이 아니라 **macOS 키체인 항목명이 함께** 갈린다
(Claude Code 2.1.278 실측):

| 설정 홈 | 키체인 항목 |
|---|---|
| `CLAUDE_CONFIG_DIR` 미설정 | `Claude Code-credentials` |
| 설정(값이 무엇이든) | `Claude Code-credentials-<sha256(설정홈)[0:8]>` |

그래서 **기본 홈이 아닌 프로필은 접미사 없는 항목으로 폴백하지 않는다** — 폴백하면 주 계정
토큰으로 조회해 다른 계정의 사용량을 그 프로필 것인 양 내보낸다(이 스킬이 고친 결함).
기본 홈은 두 항목이 공존할 수 있어 둘 다 후보로 넣고 만료가 늦은 쪽을 쓴다.

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| Codex CLI(ChatGPT) 사용량 | itda-dev:codex-usage |
| Anthropic API 키 과금·조직 콘솔 사용량 | 해당 없음 — console.anthropic.com 에서 직접 |
| 메뉴 막대 상시 표시·80/100% 알림 | sheriff 앱 (같은 계약의 상주판) |

## 금지선

- 토큰 값을 출력·로그·이슈 코멘트에 싣지 않는다. 스크립트도 싣지 않는다(테스트가 고정).
- 자격증명을 갱신·재발급하지 않는다. 만료는 안내만 한다.
