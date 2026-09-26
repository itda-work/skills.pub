---
name: bai-notice
description: >
  감사원 통합공지 게시판을 내부 JSON API로 수집해 마크다운 표로 정리하는 스킬입니다.
  "감사원 공지 확인해줘", "감사원 통합공지 최근 10건 보여줘", "감사원에서 채용 공고 찾아줘"처럼 말하면 됩니다.
  로그인·API 키 없이 공개 API만 사용하며, 서버측 키워드 검색·날짜 범위와 요약(smmTxt), xlsx 저장을 지원합니다.
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
  tags: "BAI, board of audit, public notice, JSON API, korea government"
---

# bai-notice

감사원 통합공지(<https://www.bai.go.kr/bai/notice/notification/tab01>)를 수집해
`날짜 | 제목 | 담당 | 요약 | 링크` 마크다운 표로 정리합니다.

> 감사원 사이트는 SPA(Nuxt)라 HTML 파싱이 불가능합니다.
> 이 스킬은 화면이 실제로 쓰는 내부 JSON API(`/api/boards/notice/list`)를 직접 호출합니다 —
> 키워드 검색과 날짜 범위 필터가 **서버측**에서 처리되어 정확하고 빠릅니다.

## Prerequisites

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/bai-notice}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/bai-notice' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
python3 "$SKILL_DIR/scripts/install_skill_deps.py"          # 정문
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

Windows(PowerShell):

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\bai-notice"  # 미설정이면 SKILL.md 위치 절대경로 사용
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

## 사용법

```bash
# macOS/Linux — 최근 10건 (기본)
python3 "$SKILL_DIR/scripts/collect_bai.py"

# 서버측 키워드 검색·날짜 범위
python3 "$SKILL_DIR/scripts/collect_bai.py" --keyword "채용" --limit 5
python3 "$SKILL_DIR/scripts/collect_bai.py" --from 2026-07-01 --to 2026-07-27

# xlsx 저장 / JSON 출력 / 페이지 확장
python3 "$SKILL_DIR/scripts/collect_bai.py" --xlsx 감사원공지.xlsx
python3 "$SKILL_DIR/scripts/collect_bai.py" --format json
python3 "$SKILL_DIR/scripts/collect_bai.py" --pages 3 --limit 30

# Windows
py -3 "$env:SKILL_DIR\scripts\collect_bai.py" --limit 5
```

## CLI 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--limit` | 최근 N건 (API size 파라미터) | 10 |
| `--pages` | 조회 페이지 수 상한 | 1 |
| `--keyword` | 제목·내용 검색 (서버측) | — |
| `--from` / `--to` | 날짜 범위 YYYY-MM-DD (서버측) | — |
| `--format` | `table`(마크다운 표) / `json` | `table` |
| `--xlsx` | xlsx 저장 경로 | — |

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 (0건 매칭 포함 — 안내 메시지 출력) |
| 1 | 수집 실패 (네트워크 오류, API 스키마 변경) |
| 2 | 인자 오류 |

실패 시 stderr 에 원인이 출력됩니다. "사이트 개편 시 스킬 업데이트가 필요할 수 있습니다" 안내가 나오면 내부 API 가 바뀐 것이니 스킬 업데이트를 요청하세요.

## 트리거 키워드

감사원, 통합공지, 감사원 공지, 감사 공고, 감사원 채용, 감사결과 공개,
BAI, board of audit and inspection, audit notice

## 파일 구조

```
bai-notice/
  SKILL.md
  GUIDE.md
  CHANGELOG.md
  requirements.txt
  scripts/
    bai_api.py       # 내부 JSON API 호출·파싱
    collect_bai.py   # 수집 CLI
  tests/
```
