---
name: web-scout
description: >
  정보원 정찰 스킬 — "이 정보가 어느 사이트 어디에 있고 어떻게 꺼내야 싸게 되는가"를 실측해 기억합니다. 발견 프로브(robots·sitemap·RSS·llms.txt) → 정적 fetch → 익명 API → 브라우저 순 사다리로 A/B/C/D 등급과 플레이북을 남기고 프롬프트 팩·competitor-watch targets.yaml·등급표로 내보냅니다. "이 사이트들 뉴스 어디서 어떻게 읽나 정리해줘", "정보원 등급표 만들어줘", "웹 정찰해줘", "web-scout", "플레이북 갱신해줘"처럼 말하면 됩니다. 단건 읽기는 web-reader, 반복 수집·알림은 competitor-watch 담당.
license: Apache-2.0
compatibility: Claude Code & Cowork
allowed-tools: Bash, Read, Write, Agent, WebFetch, WebSearch, mcp__workspace__bash, mcp__workspace__web_fetch
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.2.1"
  created_at: "2026-08-30"
  updated_at: "2026-09-25"
  tags: "web, discovery, sitemap, rss, playbook, grading, provenance, records, browser, ladder, korean, extraction, prompt-pack, competitor-watch"
---

# web-scout

정보가 **어디 있는가**(discovery)·**어떻게 꺼내는가**(access)·**알아낸 결과를 다음에 쓰는가**(memory)를
한 사다리로 다룬다. 비싼 수단(브라우저)은 **탐색 1회**에만 쓰고, 그 산출은 본문이 아니라 **"다음에 브라우저
없이 가는 방법"** 이다. 수집 산출은 요약이 아니라 **추출 레코드**(출처 URL + 원문 발췌 — web-reader
`extract_records`)이며, 판단(선별·요약)은 레코드 위에서만 한다.

3층 분리: 이 스킬의 코드는 **도메인 무관**이다. 도메인 지식은 `playbooks/<도메인>/<host>.yaml`(동봉 시드,
읽기 전용) + 로컬 누적(`itda_path.resolve_data_dir("web-scout")/playbooks/`) 에만 있다. 시드가 없어도 S3 부터 돈다.

## Prerequisites

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/web-scout}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/web-scout' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
python3 "$SKILL_DIR/scripts/install_skill_deps.py"          # 정문(형제 web-reader 몫까지 함께 건다)
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt" -r "$SKILL_DIR/../web-reader/requirements.txt"
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\web-scout"  # 미설정이면 SKILL.md 위치 절대경로 사용
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

형제 스킬 **web-reader 가 같은 플러그인에 있어야 한다**(HTTP·추출 레코드는 그쪽 스크립트를 재사용한다 — 복제 금지).

## 절차 (S1 → S8)

**S1 정규화** — 요구를 `정보 항목 × 정보원(호스트)` 매트릭스로 적는다. 정보원이 없으면 web-search 로 후보를 모은다.

**S2 플레이북 조회** — `python3 "$SKILL_DIR/scripts/playbook.py" resolve --host <host> --domain <도메인> --seed-dir "$SKILL_DIR/playbooks" --local-dir <로컬>`.
hit 이면 **S8 로 직행**(탐색 생략). miss/stale 이면 S3.

**S3 발견 프로브** — `python3 "$SKILL_DIR/scripts/probe_discovery.py" https://<host>/ --budget 12`.
루트 JS 리다이렉트면 최종 URL 을 재시도하고, `install_gate`(보안모듈·공동인증서 설치 안내)면 **그 URL 은 폐쇄**(브라우저로 올리지 않는다 — 설치는 불가·불요). 후보 = 피드·메뉴 링크·sitemap·llms.txt·OpenAPI·JSON-LD.
사이트 고유 경로를 **추측하지 않는다**(`references/transitions.md`).

**S4 접근 사다리** — 후보 위치마다 싼 단부터, 성공하면 정지:
- L1 `web-reader fetch_html` → `extract_records` (봉투 + 행). 진단은 `grade.diagnose` 전이표대로.
- L2 페이지네이션·인코딩·헤더 조건(값은 응답에서 매회 파생 — 쿼리 **값** 박제 금지).
- L3 익명 API **GET** 만(관측된 POST 는 재생하지 않는다). 모든 HTTP 는 web-reader 검증기 경유.
- L4 브라우저 — `references/browser-probe.md` 로 가용성을 **probe 한 뒤** 선택(OS 는 필터일 뿐). 목적 (a) 본문 회수 (b) API 채집(네트워크 요청을 읽을 수 있는 브라우저 도구가 있을 때만). 채집한 API 는 **브라우저 밖 GET 재생으로 대조**(`grade.replayability`)해 `anonymous_replayable / session_bound / browser_only` 를 판정한다 — 관측만으로 박제 금지.
- 예산: 호스트당 ≤40 요청 · 전체 ≤15분 · L4 ≤3회. 초과는 `budget_exceeded` 로 stop.

**S5 판정** — 축 4종(`discovery_path · repeat_access · auth_state · env_availability`) + 기대 shape(Content-Type·필수 키·최소 건수·**최신성**·분모) + 근거(시점·표본 수·브라우저). 등급 A/B/C/D 는 `grade.derive_grade` 로 **파생**한다(`references/grades.md`). 1회 관측은 계약이 아니다 — `samples` 를 정직하게 적는다.

**S6 플레이북 갱신** — `playbook.propose()` 로 **제안 파일**(`*.proposal.yaml`)을 만들고 사용자에게 보여 준 뒤 `playbook.py commit <제안>` 으로 박제한다. 자동 박제 금지. 비밀은 `secret_ref` 이름만.

**S7 내보내기** — `export_prompt.py`(추출/가공 2단 템플릿, A/B 만) · `export_targets.py`(competitor-watch, A + URL 축약 L2 만) · `export_table.py`(등급표 md). 각 `python3 "$SKILL_DIR/scripts/<x>.py" <플레이북.yaml…> --output <파일>`.

**S8 반복 조회 (runner)** — `python3 "$SKILL_DIR/scripts/run_playbook.py" --host <host> --domain <도메인> [--l4-raw <dir>] [--json] [--output <파일>]`.
플레이북 hit → `repeat_access` 단만 재생 → 추출 레코드(봉투 포함)를 `<data>/runs/<도메인>/<host>/<location_id>/<UTC>.json` 에 저장 → 결과 분류 → 이전 회차와 diff → stale 은 `<data>/proposals/<도메인>/<host>.proposal.yaml` 제안(플레이북 불변). C(L4) 위치는 `needs_browser` 로 `l4_sequence` 를 돌려주므로 **에이전트가 브라우저로 실행해 raw HTML 을 `<dir>/<location_id>.html` 로 저장**하고 `--l4-raw <dir>` 로 재호출하면 같은 후처리를 탄다. exit 0 전건 성공 · 2 stale/브라우저 필요/typed 실패 있음.
HTML 에서 목록 구조를 못 찾은 0건은 `no_dated_list` → `schema_drift`(재탐색)이지 `empty_valid` 가 아니다(CEO Brief 거짓 성공 실측).

플레이북 위치의 `repeat_access` 단만 실행(L1~L3 은 discovery·L4 없이, C 는 저장된 `l4_sequence` 를 브라우저 가용 시). 산출 = 추출 레코드. 결과는 `grade.classify_result` 로 `fresh_nonempty / empty_valid`(성공) · `incomplete / schema_drift`(재탐색 → **제안**, 덮어쓰지 않음) · `auth_expired`(typed 종결). 이전 회차 레코드와 `source_url` + `content_hash` 로 diff(신규·변경·소실).

## 에이전트의 MCP/브라우저 호출 (길 X)

Python 은 MCP 를 부르지 않는다. L4 는 **에이전트**가 브라우저(aside `aside repl` / Claude in Chrome)를 호출해 raw(HTML·네트워크 캡처)를 파일로 저장하고, 스크립트는 그 파일을 후처리한다. 브라우저 밖 재생 대조도 에이전트가 `fetch_html` 로 받은 응답 파일을 `grade.replayability` 에 넣는다. 자세한 선택표·probe 명령은 `references/browser-probe.md`.

## 하지 않는 것

- 보안모듈·공동인증서 설치, 사용자에게 설치 안내 — 요구되면 그 경로는 **없는 것**으로 본다(`install_gate`).
- 비-GET 재생 · origin 전환 재생 · 사이트 상태 변경(`collect-only`) · 우리 신원을 싣는 요청(`outbound-identity-leak`).
- 요약만 만들고 레코드를 남기지 않는 것. 최소 건수 단독으로 "깨졌다" 판정.
- 로그인 세션 결정론 반복 수집 · 반복 실행·알림 · 본문 정제(web-reader).

## Script Reference

| 스크립트 | 역할 |
|---|---|
| `probe_discovery.py <root> [--budget N] [--no-follow]` | S3 후보 위치 JSON |
| `grade.py` | 순수 판정 함수(`diagnose`·`transition`·`derive_grade`·`classify_result`·`replayability`·`key_types`) — CLI 없음 |
| `playbook.py validate\|resolve\|commit` | 스키마 검증·시드+로컬 병합·제안 커밋 |
| `export_prompt.py <pb…> --topic` / `export_targets.py` / `export_table.py` | 내보내기 3종 |
| `run_playbook.py --host --domain [--l4-raw] [--budget 40] [--json]` | S8 재생 runner — 재생·레코드 저장·분류·diff·제안 |

## 부록: Claude Code 확장 (선택)

이 절은 Claude Code 세션에만 적용된다. Cowork 는 본문 절차 그대로 진행한다(부록 미적용이 결함이 아니다).

### 병렬 처리
호스트별 S3~S5 는 서로 독립이다. Claude Code 에서는 한 메시지에 복수 Agent 호출로 동시 팬아웃하라(정보원 5개 이상일 때). 산출은 제안 파일로 회수하고 요약만 텍스트로 받는다. 플레이북 commit 은 순차 유지.
