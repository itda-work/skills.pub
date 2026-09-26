---
name: fss-docs
description: >
  금융감독원 공통업무자료 게시판을 수집해 마크다운 표로 정리하는 스킬입니다.
  "금감원 업무자료 확인해줘", "금융감독원 공통업무자료 이번 주 것만 보여줘", "금감원에서 사모펀드 자료 찾아줘"처럼 말하면 됩니다.
  로그인·API 키 없이 공개 페이지만 수집하며, 첨부파일명·담당부서와 키워드·날짜 필터, xlsx 저장을 지원합니다.
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
  tags: "FSS, financial supervisory, work materials, board scraping, korea government"
---

# fss-docs

금융감독원 공통업무자료 게시판(<https://www.fss.or.kr>)을 수집해
`날짜 | 제목 | 담당부서 | 첨부 | 링크` 마크다운 표로 정리합니다.
사모펀드 현황·주채무계열·외국집합투자기구 등록현황 등 감독 실무 자료가 올라오는 게시판입니다.

## Prerequisites

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/fss-docs}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/fss-docs' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
python3 "$SKILL_DIR/scripts/install_skill_deps.py"          # 정문
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

Windows(PowerShell):

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\fss-docs"  # 미설정이면 SKILL.md 위치 절대경로 사용
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

## 사용법

```bash
# macOS/Linux — 최근 10건 (기본)
python3 "$SKILL_DIR/scripts/collect_fss.py"

# 키워드·날짜 필터
python3 "$SKILL_DIR/scripts/collect_fss.py" --keyword "사모" --limit 5
python3 "$SKILL_DIR/scripts/collect_fss.py" --from 2026-07-01 --to 2026-07-27

# xlsx 저장 / JSON 출력 / 페이지 확장
python3 "$SKILL_DIR/scripts/collect_fss.py" --xlsx 금감원자료.xlsx
python3 "$SKILL_DIR/scripts/collect_fss.py" --format json
python3 "$SKILL_DIR/scripts/collect_fss.py" --pages 3 --limit 30

# Windows
py -3 "$env:SKILL_DIR\scripts\collect_fss.py" --limit 5
```

## CLI 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--limit` | 최근 N건 | 10 |
| `--pages` | 조회 페이지 수 상한 (페이지당 10건) | 1 |
| `--keyword` | 제목 키워드 필터 | — |
| `--from` / `--to` | 날짜 범위 (YYYY-MM-DD) | — |
| `--format` | `table`(마크다운 표) / `json` | `table` |
| `--xlsx` | xlsx 저장 경로 (첨부파일명 포함) | — |

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 (0건 매칭 포함 — 안내 메시지 출력) |
| 1 | 수집 실패 (네트워크 오류, 사이트 개편으로 인한 파싱 실패) |
| 2 | 인자 오류 |

실패 시 stderr 에 원인이 출력됩니다. "사이트 개편 시 스킬 업데이트가 필요할 수 있습니다" 안내가 나오면 게시판 마크업이 바뀐 것이니 스킬 업데이트를 요청하세요.

## 트리거 키워드

금감원, 금융감독원, 공통업무자료, 업무자료, 감독자료, 사모펀드 현황, 주채무계열,
FSS, financial supervisory service, work materials

## 파일 구조

```
fss-docs/
  SKILL.md
  GUIDE.md
  CHANGELOG.md
  requirements.txt
  scripts/
    fss_api.py       # 목록 페이지 요청·파싱
    collect_fss.py   # 수집 CLI
  tests/
```
