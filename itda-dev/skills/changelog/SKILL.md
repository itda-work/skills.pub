---
name: changelog
description: >
  Orca(onorca.dev)·Claude Code·Codex CLI·herdr 의 최근 릴리즈를 모아 버전별 한국어 요약으로
  만들고 Orca 내장 브라우저 탭으로 연다. "orca 업데이트 뭐 바뀌었어", "claude code 새 버전 뭐가
  달라졌나", "codex cli 최근 릴리즈 요약", "herdr 뭐 바뀌었어", "체인지로그 정리해줘",
  "/changelog" 같은 요청에 사용한다.
  이들 도구는 릴리즈가 잦고 릴리즈당 항목이 많아 사람이 따라갈 수 없으므로, 전량을 보존하면서
  체감 변경만 압축해 보여주는 것이 목적이다. 도구 자체의 사용법 질문(orca-guide·claude-code-guide)이나
  다른 저장소의 릴리즈에는 사용하지 않는다.
license: MIT
compatibility: Claude Code (Orca IDE + gh CLI 필요)
user-invocable: true
argument-hint: "[orca|claude|codex|herdr] [--since 3d|2w|<태그>] [--new] [--all] [--full]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "1.1.0"
  status: "experimental"
  created_at: "2026-08-09"
  updated_at: "2026-09-01"
  tags: "changelog, release, release-notes, update, summary, orca, claude-code, codex, herdr, github, gh, ide, devtools, terminal, multiplexer"
---

# changelog

제품 릴리즈 노트를 **수집(결정론) → 요약(판단) → 렌더 → Orca 탭**으로 잇는다.

**제품을 먼저 정한다** — 사용자가 말한 대상을 그대로 옮긴다:

| 사용자가 말한 것 | `--product` | 릴리즈 소스 | 기본 창 |
|---|---|---|---|
| Orca, 오르카 | `orca` | stablyai/orca | 최근 3일 (하루 1~2회 릴리즈) |
| Claude Code, 클로드 코드 | `claude` | anthropics/claude-code | 최근 3일 (하루 1~3회 릴리즈) |
| Codex, 코덱스 | `codex` | openai/codex | 최근 14일 (정식 릴리즈 주 1회쯤) |
| herdr, 허더 | `herdr` | herdrdev/herdr | 최근 21일 (안정판 1~2주 간격, preview 는 제외) |

대상이 불명하면 묻지 말고 **orca** 로 간다(이 스킬의 원형). 여러 제품을 함께 요청하면
("셋 다", "요즘 도구들 업데이트") 제품별로 아래 전 단계를 반복한다 — 제품마다 탭이 따로 열린다.

## 전제

- `gh` CLI 인증 필요 (`gh auth status`). 비대화형에서도 keyring 으로 동작한다.
- Orca 앱이 실행 중이어야 탭이 열린다. `orca` CLI 가 없는 환경이면 열기 단계는 명시
  에러로 끝난다 — 그 경우 렌더된 HTML 경로를 보고하는 데서 멈춘다(조용한 대체 열기 금지).

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/changelog}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/changelog' 2>/dev/null | head -1)
# 둘 다 아니면(심링크·저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
WORK="${TMPDIR:-/tmp}/changelog"
mkdir -p "$WORK"
P=orca   # 또는 claude | codex | herdr
```

## 1단계 — 수집

```bash
python3 "$SKILL_DIR/scripts/collect.py" --product "$P" --out "$WORK/$P-collect.json"
```

사용자가 범위를 말하면 그대로 옮긴다: `--since 7d` · `--since 2w` · `--since v1.4.170`
· `--since 2026-08-01` · `--new`(마지막으로 본 이후) · `--all` · `--full`(제외 표면 포함).

산출 JSON 의 각 항목은 `{section, kind, scope, title, pr, prs, breaking, revert}` 다.
`window_widened`(기간 내 릴리즈 0 → 최근 1개로 확장)와 `range_truncated`(수집 범위 끝에
닿음)가 true 면 렌더가 알아서 표기하니 따로 손대지 않는다.

**`no_new: true` 면 여기서 멈춘다.** `--new`·`--since <태그>` 구간에 새 릴리즈가 없다는
뜻이다. 요약·렌더·탭 열기를 모두 건너뛰고 "마지막으로 확인한 <태그> 이후 새 릴리즈가
없습니다" 한 줄만 보고한다. 같은 내용을 다시 렌더해 탭을 여는 것은 소음이다.

## 2단계 — 요약 (네가 판단하는 유일한 단계)

`$P-collect.json` 을 읽고 `$WORK/$P-summary.json` 을 쓴다.

```json
{
  "behavior_changes": [{"text": "...", "refs": [12884], "tag": "v1.4.177"}],
  "versions": {"v1.4.177": {"highlights": [{"text": "...", "refs": [13076]}]}}
}
```

**`behavior_changes`** — 전 버전 통합, 최상단에 뜬다. 여기 넣을 것만 넣는다:

- `revert:true` 항목 (되돌림은 "어제 되던 게 오늘 안 되는" 변화다)
- `breaking:true` 항목
- 기본 동작·기본값·설정 항목이 바뀐 것 — 제거된 토글, fail-open→fail-closed, 기본 경로 변경,
  UA·인증처럼 외부에 보이는 동작 변경, 플래그 폐지("`--full-auto` 제거" 류)
- **단순 버그 수정은 넣지 않는다.** "고쳐졌다"는 동작 변경이 아니다.

**`highlights`** — 버전당 **3~7건**. 사용자가 오늘 쓰다가 알아차릴 만한 것만 고른다.
같은 표면의 자잘한 수정이 여러 건이면 한 줄로 묶어라("터미널 안정화 6건 — …").
내부 리팩터·CI·테스트·의존성은 고르지 않는다(전체 목록에는 남아 있다).

**제품별 유의**

- `claude` — 항목에 PR 참조가 거의 없다. `refs: []` 가 정상이며 번호를 지어내지 않는다.
- `codex` — 항목의 `prs` 는 복수일 수 있다. `refs` 에는 그중 대표 1~2개면 충분하다.
  `dump_items`(말미 PR 전량 덤프)는 **highlight 후보가 아니다** — 큐레이션 섹션(items)에서만
  고른다. 덤프는 렌더가 별도 접힘 목록으로 전량 보존한다.
- 정식 릴리즈 간격이 긴 제품(codex)은 한 릴리즈가 크다 — highlights 상한(7건)은 유지하되
  묶음 서술을 적극 쓴다.

**작성 규칙**

- 한국어로, 사용자가 보는 화면 말로 쓴다. 영문 원제를 그대로 옮기지 않는다.
- `refs` 는 반드시 `collect.json` 의 `pr`/`prs` 값에서 가져온다. **번호를 지어내지 않는다.**
  확실한 PR 이 없으면 `refs: []` 로 둔다.
- 원문에 없는 사실을 추론해 넣지 않는다. 제목만으로 효과가 불분명하면 제목을 옮기고 만다.
- 항목이 0건인 릴리즈(`empty:true`)는 요약하지 않는다 — 렌더가 "항목 없음"으로 표기한다.

## 3단계 — 렌더 · 열기

```bash
python3 "$SKILL_DIR/scripts/render.py" \
  --data "$WORK/$P-collect.json" --summary "$WORK/$P-summary.json" \
  --out "$WORK/$P-changelog.html"

python3 "$SKILL_DIR/scripts/open_in_orca.py" \
  --product "$P" --file "$WORK/$P-changelog.html" --tag <가장 최신 태그>
```

`open_in_orca.py` 는 제품별 이전 탭이 살아 있으면 재사용하고, 성공했을 때만 state
(`~/.local/state/itda-changelog/<product>.json` — 스킬 디렉토리 밖, 머신 로컬)를 갱신한다.
실패하면 다음 실행에서 같은 구간이 다시 잡힌다 — 정상 동작이다.

## 4단계 — 대화 보고

**요약 전문을 대화에 반복하지 않는다.** 그것 때문에 탭을 여는 것이다. 3~5줄로:

```
📅 Claude Code · 최근 3일 · 릴리즈 5개 · 47건 → Orca 탭에 열었습니다.
⚠️ 동작 변경 2건 — 게이트웨이 지출 한도 경고 도입, 미신뢰 디렉토리 trust 프롬프트 확대
가장 큰 릴리즈는 v2.1.224(21건, Remote Control·VSCode 집중).
```

`⚠️ 동작 변경` 이 있으면 그중 사용자에게 가장 영향이 큰 1~3건만 대화에도 적는다.

## 출력 구조 (참고)

버전이 1차 축, 각 버전은 3층이다 — **눈에 띄는 변화**(네가 고른 것) / **표면별 집계**(칩:
orca 는 scope, claude·codex·herdr 는 변경 종류) / **전체 N건 펼치기**(`<details>`, 원문 전량;
codex 는 PR 덤프 접힘 목록 추가). 무엇도 버려지지 않는다.

## 제품 추가

`profiles/<product>.json` 을 넣으면 그 이름으로 바로 쓸 수 있다 — 스크립트는 그 디렉터리를
읽어 제품 목록을 만든다(별칭이 필요할 때만 `PRODUCT_ALIASES` 에 한 줄 추가). 파서는 세
가지다: `conventional`(feat(scope): …) · `sections`(`### Added` 류 keep-a-changelog) ·
`prose`. 릴리즈 본문을 먼저 몇 개 열어 보고 고른다.

## 필터에 대해

`profiles/<product>.json` 의 `excluded_scopes`(orca: e2e·ci·test·i18n 등)는 **조연**이다.
실측(2026-08-09, 최근 3일 179건)에서 이 필터가 걸러낸 건 1건뿐이었다. 이 스킬의 가치는
거르기가 아니라 **압축**에 있다 — 178건을 20줄 첫 화면으로 만드는 것.

새 표면을 제외하고 싶다는 요청이 오면 해당 프로파일의 `excluded_scopes` 에 scope 를
추가한다. 표면 한국어 이름은 같은 파일 `scope_labels` 에 있다.
