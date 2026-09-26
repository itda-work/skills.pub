---
name: taxlaw
description: >
  국세법령정보시스템(taxlaw.nts.go.kr)에서 세법 법령·세법해석례(예규)·판례/결정례·상담사례를
  검색하고 전문(全文)을 조회하는 스킬입니다. "양도소득세 예규 찾아줘", "부가가치세 판례 검색해줘",
  "국세기본법 제18조 보여줘", "서면-2019-법령해석재산-1234 문서 찾아줘", "세법 해석사례 조사해줘",
  "국세청 상담사례 검색해줘"처럼 말하면 됩니다. 브라우저 없이 순수 HTTP 로 동작하며
  문서번호 검색·페이지네이션·정렬·전문 조회를 지원합니다.
  [책임 경계] 본 스킬은 국세법령정보시스템 세법 조회(법령·예규·판례) 전담 — 위하고·홈택스 등 세무 포털 자동화·장부 수집은 범위 밖(현재 지원 스킬 없음)이며, 세법 밖 일반 법령은 다루지 않습니다.
license: Apache-2.0
compatibility: "Claude Code & Cowork. Python 3.10+"
allowed-tools: Bash, Read, Write, mcp__workspace__bash
user-invocable: true
argument-hint: "\"검색어\" [--domain law|interpretation|precedent|counsel|form|library|all] [--limit N] [--page N] [--sort accuracy|registered|produced] [--docno] [--format table|json|md]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  status: "active"
  version: "0.1.3"
  created_at: "2026-09-01"
  updated_at: "2026-09-25"
  tags: "tax law, NTS, statute, tax ruling, precedent, tax tribunal, Korea tax"
---

# taxlaw

국세법령정보시스템(국세청, <https://taxlaw.nts.go.kr>)을 검색합니다.
세무 리서치에 필요한 4개 축 — **법령 조문 · 세법해석례(예규/질의회신) · 판례/결정례 · 국세상담센터 상담사례** — 를
한 번의 명령으로 훑고, 개별 문서의 **전문**(판결문·회신문·조문 본문)까지 가져옵니다.

> Python 표준 라이브러리만 사용 — API 키 불요, 브라우저 불요, 추가 의존성 없음.
>
> ⚠️ 법제처 **국가법령정보센터(law.go.kr)와 다른 시스템**입니다. 이 스킬의 대상은
> 국세청 국세법령정보시스템(taxlaw.nts.go.kr)입니다.

## Prerequisites

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/taxlaw}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/taxlaw' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

## 검색

```bash
python3 "$SKILL_DIR/scripts/search_taxlaw.py" "가상자산 양도소득"
```

기본은 핵심 4개 도메인(법령·세법해석례·판례/결정례·상담사례)을 도메인당 10건씩 조회하고,
**도메인별 전체 건수(분모)** 와 각 결과의 `id`·원문 URL 을 함께 출력합니다.

| 옵션 | 의미 |
|---|---|
| `--domain` | `law`(법령) `interpretation`(세법해석례) `precedent`(판례·결정례) `counsel`(상담사례) `form`(별표·서식) `library`(전자도서관) — 쉼표로 복수, `all`=전부, 기본 `core`=핵심 4개 |
| `--limit N` / `--page N` | 도메인당 건수(기본 10) / 페이지(1-base) |
| `--sort` | `accuracy`(정확도, 기본) · `registered`(등록일) · `produced`(생산일) |
| `--docno` | **문서번호 검색** — `"부가가치세과-1196"`, `"서면-2014-부가-22035"`, `"서울고등법원-2025-누-7641"` 등 |
| `--include 단어` / `--exclude 단어` | 결과 내 포함어/제외어 (반복 지정 가능) |
| `--synonym` | 동의어 확장 |
| `--format` | `table`(기본) · `json` · `md` |

## 전문 조회

검색 결과의 `id` 를 그대로 넘깁니다.

```bash
# 판례 전문 (판결문 전체)
python3 "$SKILL_DIR/scripts/search_taxlaw.py" detail --domain precedent --id 200000000000009799

# 세법해석례 전문 (질의·회신·관련 법령)
python3 "$SKILL_DIR/scripts/search_taxlaw.py" detail --domain interpretation --id 010000000000152433

# 법령 — 법 한 벌의 전 조문 (특정 조만: --article 제18조)
python3 "$SKILL_DIR/scripts/search_taxlaw.py" detail --domain law --id "<id>" --article 제18조

# 상담사례 답변 전문
python3 "$SKILL_DIR/scripts/search_taxlaw.py" detail --domain counsel --id 1387
```

`--format json` 을 주면 구조화 JSON(제목·문서번호·요지·회신·전문·관련법령)으로 받습니다.

## 결과 활용 지침 (Claude 실행 규칙)

- 조사 보고에는 **문서번호·생산일자·원문 URL 을 반드시 함께 인용**한다 — 세무 판단의 근거는
  문서 식별자가 전부다.
- 도메인별 `총 N건` 분모를 사용자에게 전달한다. limit 만큼만 표시했음을 밝히고, 더 필요하면
  `--page` 로 이어간다.
- 법령 검색 결과는 **특정 시행일자 기준 조문**이다(`시행 YYYY.MM.DD` 표기 확인). 개정 연혁
  비교가 필요하면 원문 URL 로 안내한다.
- 사이트 안내문 그대로: 검색 결과는 참고자료이며 개별 사안에는 전문가 확인이 필요함을
  세무 판단 성격의 답변에 덧붙인다.

## 오류·한계

- `오류: API status=...` / `기대와 다른 응답 형식` — 사이트 내부 API 계약이 변경된 신호.
  `references/taxlaw-api.md` 의 재실측 절차를 따라 계약을 갱신한다(조용한 우회 금지).
- 별표·서식(`form`)·전자도서관(`library`)은 검색·메타데이터까지 지원(첨부 파일 다운로드 비지원).
- 법령 전문 조회(`detail --domain law`)는 종류가 **법령**(국세법령 조문)인 결과만 지원한다.
  기본통칙·세법집행기준·훈령·고시·조세조약은 검색 결과에 `id` 없이 원문 URL 만 붙는다 —
  그 URL 로 안내한다.
- 세법해석례 중 `정비`(실효 사례) 문서는 상세 조회가 비어 있을 수 있다.
- 대량 수집 용도가 아니다 — 조사·리서치 목적의 조회에만 사용한다.

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 위하고·홈택스 로그인·장부·분개장 수집 | 세무 포털 자동화는 현재 지원 스킬 없음 |
| 세법 밖 일반 법령·판례 | 미지원(국세법령정보시스템 범위 밖) |
| 대량 수집·크롤링 | 미지원 — 조사 목적 조회만 |
| 답변 근거의 출처 검증 | itda-research:ground-check |

## 부록: Claude Code 확장 (선택)

이 절은 Claude Code 세션에만 적용된다. Cowork 는 본문 절차 그대로 진행한다(부록 미적용이 결함이 아니다).

### 병렬 처리

서로 다른 검색어·도메인 조사는 독립이다. 여러 주제를 동시에 조사할 때는 한 메시지에 복수
Agent 호출로 팬아웃하고, 산출은 파일로 회수한다. 같은 주제의 검색→전문 조회는 순차 유지.
