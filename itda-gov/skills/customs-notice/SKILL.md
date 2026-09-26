---
name: customs-notice
description: >
  관세청 공지사항 게시판을 수집해 마크다운 표로 정리하는 스킬입니다.
  "관세청 공지 확인해줘", "관세청 공지사항 최근 10건 보여줘", "관세청에서 원산지 관련 공지 찾아줘"처럼 말하면 됩니다.
  로그인·API 키 없이 공개 페이지만 수집하며, 키워드·날짜 필터와 xlsx 저장을 지원합니다.
license: Apache-2.0
compatibility: "Claude Code & Cowork. Python 3.10+"
allowed-tools: Bash, Read, Write, mcp__workspace__bash
user-invocable: true
argument-hint: "[--limit 10] [--keyword 키워드] [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--xlsx 경로]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  status: "active"
  recommended: true
  version: "0.1.1"
  created_at: "2026-07-27"
  updated_at: "2026-07-27"
  tags: "customs, KCS, public notice, board scraping, korea government"
---

# customs-notice

관세청 공지사항 게시판(<https://www.customs.go.kr>)을 수집해 `날짜 | 제목 | 작성자 | 링크` 마크다운 표로 정리합니다.

> 관세청은 브라우저가 아닌 요청에 빈 안내 페이지("시스템안내")를 돌려줍니다.
> 이 스킬은 Chrome UA 로 요청해 실제 게시판을 받아옵니다 — 일반 WebFetch 로는 수집이 안 되는 소스입니다.

## Prerequisites

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/customs-notice}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/customs-notice' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
python3 "$SKILL_DIR/scripts/install_skill_deps.py"          # 정문
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

Windows(PowerShell):

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\customs-notice"  # 미설정이면 SKILL.md 위치 절대경로 사용
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

## 사용법

```bash
# macOS/Linux — 최근 10건 (기본)
python3 "$SKILL_DIR/scripts/collect_customs.py"

# 키워드·날짜 필터
python3 "$SKILL_DIR/scripts/collect_customs.py" --keyword "원산지" --limit 5
python3 "$SKILL_DIR/scripts/collect_customs.py" --from 2026-07-01 --to 2026-07-27

# xlsx 저장 / JSON 출력 / 페이지 확장
python3 "$SKILL_DIR/scripts/collect_customs.py" --xlsx 관세청공지.xlsx
python3 "$SKILL_DIR/scripts/collect_customs.py" --format json
python3 "$SKILL_DIR/scripts/collect_customs.py" --pages 3 --limit 30

# Windows
py -3 "$env:SKILL_DIR\scripts\collect_customs.py" --limit 5
```

## CLI 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--limit` | 최근 N건 | 10 |
| `--pages` | 조회 페이지 수 상한 (페이지당 10건) | 1 |
| `--keyword` | 제목 키워드 필터 | — |
| `--from` / `--to` | 날짜 범위 (YYYY-MM-DD) | — |
| `--format` | `table`(마크다운 표) / `json` | `table` |
| `--xlsx` | xlsx 저장 경로 | — |

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 (0건 매칭 포함 — 안내 메시지 출력) |
| 1 | 수집 실패 (네트워크 오류, 사이트 개편으로 인한 파싱 실패) |
| 2 | 인자 오류 |

실패 시 stderr 에 원인이 출력됩니다. "사이트 개편 시 스킬 업데이트가 필요할 수 있습니다" 안내가 나오면 게시판 마크업이 바뀐 것이니 스킬 업데이트를 요청하세요.

## 트리거 키워드

관세청, 공지사항, 통관, 관세, 세관, KCS, 관세청 공지, 관세 공지,
customs, KCS notice, customs notice, tariff

## 파일 구조

```
customs-notice/
  SKILL.md
  GUIDE.md
  CHANGELOG.md
  requirements.txt
  scripts/
    customs_api.py       # 목록 페이지 요청·파싱
    collect_customs.py   # 수집 CLI
  tests/
```
