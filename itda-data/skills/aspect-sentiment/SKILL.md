---
name: aspect-sentiment
description: >
  한국어 텍스트의 측면별 감정·상태를 Claude가 직접 추출하는 ABSA(측면 기반 감정분석) 스킬입니다.
  "이 리뷰들 측면별 감정 뽑아줘", "상담 로그 측면 분석", "배송·품질 따로 긍부정 분류"처럼 말하면 됩니다.
  무상태 단건 처리로 맥락 오염 0, 고정 JSON 스키마, 화자분리(고객 발화만), closed-set 분류체계로 집계 가능한 출력을 만듭니다.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, Glob, Grep, mcp__workspace__bash
argument-hint: "[텍스트 파일/JSONL 또는 분석 요청]"
metadata:
  author: "Chinseok"
  version: "0.1.6"
  category: "data-analysis"
  status: "experimental"
  created_at: "2026-05-30"
  updated_at: "2026-09-30"
  tags: "absa, sentiment, aspect, korean, stdlib"
---

# aspect-sentiment

> ⚠️ **개념 증명(PoC) 스킬.** 측면 감정분석의 핵심 흐름(무상태 단건·closed-set·화자분리·고정 출력)을 Claude 단독으로 **시연**하는 단계입니다. 정확도 보장·골드셋 평가(F1·IAA)·대량 처리·ML 백엔드는 **아직 없습니다** — 결과는 참고용. 사용법·한계는 `GUIDE.md` 참조.

한국어 텍스트(리뷰 / CS 상담)에서 **측면별 감정·상태**를 추출하는 ABSA 라벨러.
Claude가 직접 수행(LLM 백엔드), 외부 모델·인증키 없음. 단순 긍·부정이 아니라
**무엇에 대한** 감정인지 측면별로 분리합니다.

> 설계 원천: `itda-skills/ml-absa` 기획서(taxonomy 정본 v1.0). 본 스킬은 그 **v1(Claude 직접 추론) 트랙**이며,
> 향후 ML 백엔드(ml-absa)로 교체해도 출력이 같도록 **고정 출력 계약**을 유지합니다.

---

## 핵심 원칙 (반드시 준수)

1. **무상태 단건 처리** — 각 doc(리뷰 1건 / CS 티켓 1건)을 **독립으로** 라벨링한다. 여러 doc을 한 판정에 섞지 않는다(맥락 오염 0). 한 doc 내부의 멀티턴은 통째로 입력한다(intra-doc 맥락은 보존 대상).
2. **closed-set 분류체계** — `aspect`는 `references/taxonomy.ko.yaml`의 확정 라벨만. 매핑 불가 시 `기타`. **라벨에 극성·상태 인코딩 금지**("처리지연불만" → `aspect=대기시간` + `polarity=negative`).
3. **화자분리(CS)** — 측면·극성은 **고객(customer) 발화에서만** 산출. 상담원 정형 응대문구(죄송/불편/양해)는 고객 불만의 evidence가 아니므로 극성 미산입.
4. **미언급 ≠ 중립** — 언급 안 된 측면은 `aspects`에서 제외(빈 배열 가능).
5. **상태 축 분리** — 해결여부·에스컬레이션 등은 감정 극성이 아니라 `process_signals`로 표현.
6. **출력 계약 고정** — `references/output-schema.json`. `evidence`는 원문 인용(추적성). 저신뢰는 `flags.low_confidence=true`.

## Claude 라우팅 가이드 (절차)

사용자가 텍스트를 주면:

1. **분류체계 로드** — `references/taxonomy.ko.yaml`. 사용자가 커스텀 YAML을 주면 그것을 우선(내장은 CS+리뷰 기본).
2. **도메인 판별** — 리뷰면 평면 `text`, CS 상담이면 `turns`(화자 태그). `domain` 게이트로 측면 풀 결정(review 입력에 CS 전용 라벨 출력 금지).
3. **few-shot 적용** — `references/few-shot.md`(한국어 난점: 존댓말 완곡부정·체념 단답·화자귀속·턴간 지시대명사).
4. **doc별 무상태 라벨링** — 각 doc을 독립으로 처리하고 `output-schema.json` 형식 JSON **1개**를 출력. 배치면 doc별로 반복하되 **판정을 섞지 않는다**. `sub_aspect`는 v1에서 항상 `null`.
5. **검증** — 산출 JSON을 `"$SKILL_DIR/scripts/validate_output.py"`(아래 §검증 참조)로 스키마·taxonomy 멤버십·필드 모순 검증.

> 집계·KPI 리포트(측면별 극성 분포·미해결율 등)와 골드셋 평가(F1·IAA)는 **본 스킬 범위 밖**(후속). 여기서는 **라벨링 코어**만 다룬다.

## 출력 예시 (CS 티켓)

```json
{
  "doc_id": "tk_0001",
  "language": "ko",
  "taxonomy_version": "absa-cs-1.0",
  "domain": "cs",
  "overall_sentiment": "negative",
  "aspects": [
    {"aspect": "대기시간", "polarity": "negative", "sub_aspect": null,
     "evidence": "30분째 기다리는데 연결이 안 되네요", "turn_id": 1, "speaker": "customer", "confidence": 0.9}
  ],
  "process_signals": {"resolution": "unresolved", "escalated": false},
  "mentioned_aspects": ["대기시간"],
  "flags": {"sarcasm": false, "euphemistic_negation": false, "low_confidence": false, "critical": false}
}
```

## 검증

**먼저** 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 `SKILL_DIR` 에 넣고 아래 블록을 실행한다 — 블록은 그 값을 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾는다(후보가 여럿이면 멈춘다).

```bash
# SKILL_DIR 확정(skill-dir-resolution) — 스킬을 불러올 때 받은 base directory 를 먼저 SKILL_DIR="그 경로" 로 넣는다(항상)
# 블록은 그 값을 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾는다 — SKILL.md 가 있는 후보가 하나일 때만 받고 아니면 멈춘다
SKILL_DIR=$(sh -c '
S=$1 P=$2 H=${5:-$HOME/.claude}
ok() { d=${1%/}; [ "${d##*/}" = "$S" ] && [ -f "$d/SKILL.md" ] && (cd "$d" && pwd -P); }
[ -n "$3" ] && { ok "$3" && exit; d=${3%/}; [ "${d##*/}" = "$S" ] && echo "SKILL_DIR 무시: $3 에 SKILL.md 가 없다" >&2; }
[ -n "$4" ] && { ok "$4/skills/$S" && exit; echo "CLAUDE_PLUGIN_ROOT 무시: $4/skills/$S 에 SKILL.md 가 없다" >&2; }
c=$(for d in "$H"/plugins/synced/*/"$P"/skills/"$S" "$H"/plugins/synced/*/"$P"~*/skills/"$S" "$H"/plugins/cache/*/"$P"/*/skills/"$S" \
    /root/.claude/plugins/synced/*/"$P"/skills/"$S" /root/.claude/plugins/synced/*/"$P"~*/skills/"$S" \
    /sessions/*/mnt/.remote-plugins/*/skills/"$S" /sessions/*/mnt/.claude/skills/"$S"; do ok "$d"; done | sort -u)
[ "$(printf "%s\n" "$c" | grep -c .)" -gt 1 ] && { printf "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다:\n%s\n" "$c" >&2; exit 1; }
printf "%s\n" "$c"' _ aspect-sentiment itda-data "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```
```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'aspect-sentiment'; $P = 'itda-data'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```
```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/validate_output.py" <출력.jsonl>
# Windows
py -3 "$env:SKILL_DIR\scripts\validate_output.py" <출력.jsonl>
```

## Backend 추상화

현재 `backend=claude`(LLM 직접 추론). 출력 스키마·taxonomy 계약을 고정해, 향후 `ml-absa`(자체 ML 모델) 백엔드로 교체해도 출력이 동일하다. 백엔드 전환은 별도 SPEC.

## 대량 배치 (팬아웃/팬인)

입력이 대량(예: 30건 이상)이면 본 대화가 원문으로 오염되고 처리도 느리다. 서브에이전트를 쓸 수 있는 환경(Cowork 등)에서는 **청크 팬아웃**으로 처리한다:

1. **분할** — Lead 가 입력 doc 을 청크 파일(예: 10~20건/청크, **JSONL** — 한 줄 = 단건 입력 shape)로 나눠 세션 폴더에 저장한다. raw 로그는 `itda-data:pii-redact`(다른 팩 — 미설치면 `itda-data` 설치를 안내하고 마스킹 없이 진행하지 않는다) 로 **선행 비식별화**한다.
2. **팬아웃** — `itda-data:cs-batch-extractor` 를 청크별로 **병렬 명시 디스패치**한다(디스패치 프롬프트에 `task=aspect-sentiment` + 이 파일의 closed-set taxonomy·화자분리·고정 JSON 원칙 + 청크 파일 경로 + `outputs/` 출력 경로). 워커는 각 항목을 무상태로 라벨링해 스키마 호환 JSONL 을 `outputs/` 에 쓰고 경로·건수만 반환한다.
3. **팬인(집계는 Lead 소유)** — Lead 가 반환된 JSONL 들을 `python3 "$SKILL_DIR/scripts/validate_output.py" <출력.jsonl> [taxonomy.yaml]` 로 검증하고 병합한다. **커스텀 taxonomy 를 워커에 줬으면 검증에도 같은 경로를 두 번째 인자로 넘긴다** — 안 넘기면 커스텀 라벨이 내장 taxonomy 기준으로 거짓 거부·`기타` 오강등된다. 집계는 스킬 스크립트가, 라벨링은 무상태 워커가 맡는다(워커는 집계하지 않는다).

서브에이전트 부재 환경은 위 절차 대신 **기존 본 컨텍스트 순차 단건 처리로 폴백**한다(핵심 원칙의 doc별 무상태 반복). **단건 절차·출력 스키마·taxonomy 는 불변** — 배치는 같은 계약을 병렬화·격리할 뿐이다. 오케스트레이션 세부는 `.claude/rules/itda/skills/cowork-agent-orchestration.md`.

## 한계 (정직)

- 사르카즘·반어, 존댓말 완곡부정은 정확도 한계 — few-shot으로 완화하되 저신뢰는 `flags`로 노출.
- 대량(수만 건+) 저비용·저지연 처리는 본 스킬이 아니라 `ml-absa` 백엔드 영역.
- 평가(골드셋·F1·IAA)·집계 리포트는 후속 단계. **측면 라벨의 IAA(어노테이터 일치도) 측정은 같은 플러그인의 `iaa-builder` 스킬**로 수행한다(골드셋 샘플링 → 2인 라벨 → Cohen κ → 졸업 게이트).
  - ⚠️ 측정 단위를 먼저 정한다: 본 스킬 출력은 doc당 `aspects[]`(중첩)이므로 `iaa-builder`의 평면 라벨 컬럼에 바로 넣을 수 없다. **doc 단위**(예: `overall_sentiment`)로 측정하거나, **(doc, aspect) 쌍을 한 행으로 평탄화**해 aspect별 polarity를 라벨로 둔다. cs-intent의 `primary_intent`(평면 단일값)와 달리 한 단계 변환이 필요하다.
