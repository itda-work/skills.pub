# human-tone — 차기 세션 인수인계 노트

> 이 문서는 차기 Claude Code 세션이 `../skills/itda-work` (또는 `skills/itda-doc/skills/human-tone`)에서 작업을 이어받기 위한 self-contained 가이드.
> 마지막 갱신: 2026-05-11 (v2.0.0 풀패키지 완료 직후). 2026-09-25: 배포본에 실리는 문서라 개인 절대 경로를 `<저장소 루트>` 등 자리표시자로 바꿨다(내용은 그 시점 기록).

---

## 0. 빠른 시작 (다음 세션에서 처음 할 일)

```bash
cd <저장소 루트>/itda-doc
# 또는 itda-work 루트에서 claude 시작
```

새 세션에서 **반드시 먼저 읽을 파일** (이 순서대로):

1. `skills/human-tone/HANDOFF.md` ← 이 파일
2. `skills/human-tone/README.md` (차용 출처 + 변경 이력)
3. `skills/human-tone/SKILL.md` (현재 v2.0 워크플로우)
4. `CHANGELOG.md` 상단 `[Unreleased]` 섹션
5. (필요 시) `<ref-im-not-ai 체크아웃>/` 원본 풀 시스템 — `metrics_v2.py` 작업 시 필수

**인수인계 컨텍스트 손실 시 복구 경로**: `ref-cowork-plugins/KNOWLEDGE.md`에 cowork-plugins 노하우, 본 HANDOFF.md에 human-tone 진행 상태가 모두 기록됨.

---

## 1. 현재 상태 (2026-05-11 기준)

### 완료

- `skills/human-tone/` v2.0.0 풀패키지 완료
  - SKILL.md (208줄, monolith fast path)
  - README.md (차용 출처 명시)
  - LICENSE-im-not-ai (MIT 원본 사본)
  - references/ 3종 (taxonomy 666줄 / quick-rules 169줄 / playbook 322줄)
  - scripts/ 3종 (metrics.py 404줄 / baseline.json 102줄 / lock_preserved.py 306줄)
- plugin.json: 3.1.0 → 3.2.0
- CHANGELOG.md `[Unreleased] Changed`에 v2.0 전환 기록
- 검증: lock_preserved.py 4개 단위 테스트 통과, metrics.py end-to-end "high" 산출 확인

### 미완 — 우선순위 순

| 우선순위 | 작업 | 예상 시간 | 비고 |
|---|---|---|---|
| ~~**P0**~~ | ~~tests/ 디렉토리 작성 (justfile 호환)~~ | ~~2~3시간~~ | ✅ 2026-05-11 완료 (19 tests passed) |
| ~~**P0**~~ | ~~SKILL.md `metrics.py --output` JSON 파이프 보완~~ | ~~30분~~ | ✅ 2026-05-11 완료 |
| **P1** | metrics_v2.py 통합 (post-editese 3축) | 4~6시간 | baseline_v2.json 자체 calibration 필요 |
| **P1** | 카탈로그 README 갱신 (itda-work/README.md) | 30분 | v1.0 시점 설명 잔존 |
| **P2** | itda-org-tone 신규 스킬 (조직 학습) | 6~8시간 | 별도 SPEC 필요 |
| **P2** | 실사용 피드백 → K 카테고리 검증 | 지속적 | 5건 이상 사례 필요 |
| **P3** | scholarship.md 통합 검토 | 1시간 | 본문 비대 우려, 사용자 가치 평가 후 |

**플랫폼 정책 (2026-05-11 합의)**: Claude Cowork 내 Linux VM 전용 실행. Windows 네이티브 미지원. SKILL.md 예시는 `python3` 단일 명령 유지. `.claude/rules/itda/skills/python-runtime.md`의 Windows `py -3` 권장은 이 스킬에 적용하지 않음.

---

## 2. P0 — tests/ 디렉토리 작성 (가장 시급)

### 배경

itda-work는 `justfile`로 `just test-skill <name>` 운영. 다른 itda 스킬 다수가 `tests/` 보유. human-tone v2.0은 이 컨벤션을 위반 중.

### 작성 대상 (3개 파일)

```
skills/human-tone/tests/
├── test_lock_preserved.py    # 보존 영역 마스킹/복원/감사 회귀
├── test_metrics_smoke.py     # metrics.py CLI 동작 + baseline 로딩
└── test_triggers.py          # SKILL description 트리거/넌트리거 회귀
```

### 1) test_lock_preserved.py

이미 검증된 4개 시나리오를 pytest로 정착:

```python
# 위치: skills/human-tone/tests/test_lock_preserved.py
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))
import lock_preserved as lp

def test_basic_roundtrip():
    s = '2026년 5월 11일 ABC전자 매출이 15.3% 증가. https://example.com / hr@acme.kr / 02-123-4567'
    masked, pmap = lp.mask(s)
    restored, missing = lp.restore(masked, pmap)
    assert restored == s
    assert not missing

def test_quote_and_law():
    s = '근로기준법 제17조 제2항에 따라 "근로계약 체결 시 임금·근로시간을 명시"해야 한다. 위반 시 500만원 이하 벌금.'
    masked, pmap = lp.mask(s)
    restored, _ = lp.restore(masked, pmap)
    assert restored == s
    assert any(item["category"] == "QUOTE" for item in pmap.items)
    assert any(item["category"] == "LAW" for item in pmap.items)

def test_hallucination_detection():
    original = '매출이 15.3% 증가했다.'
    masked, pmap = lp.mask(original)
    hallucinated = original.replace('15.3%', '20%')
    report = lp.audit(original, hallucinated, pmap)
    assert not report["pass"]
    assert '20' in report["extra_numeric"]

def test_placeholder_deletion_detection():
    s = '매출 15% 증가.'
    masked, pmap = lp.mask(s)
    broken = masked.replace(pmap.items[0]["placeholder"], '')
    _, missing = lp.restore(broken, pmap)
    assert missing
```

### 2) test_metrics_smoke.py

metrics.py가 baseline.json을 로드하고 정상적으로 risk_band를 산출하는지만 빠르게 확인:

```python
# 위치: skills/human-tone/tests/test_metrics_smoke.py
import subprocess, pathlib, json, tempfile

SCRIPTS = pathlib.Path(__file__).parent.parent / "scripts"

def _run(text: str, genre="essay") -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(text)
        f.flush()
        out = subprocess.check_output([
            "python3", str(SCRIPTS / "metrics.py"),
            "--input", f.name,
            "--baseline", str(SCRIPTS / "baseline.json"),
            "--genre", genre,
        ], text=True).strip()
    return out

def test_ai_style_high():
    text = "현대 사회에서 기술적 혁신은 중요하다. AI는 빠르게 발전하고, 산업은 변화하며, 사람들은 적응해야 한다. 결론적으로, 우리는 양쪽 모두를 고려해야 한다."
    assert _run(text) == "high"

def test_human_style_low():
    text = "오늘 비가 왔다. 우산을 폈다. 길이 미끄럽다."
    out = _run(text)
    assert out in {"low", "medium"}, f"unexpected: {out}"
```

**주의**: metrics.py 출력은 현재 risk_band 한 줄. JSON 상세는 `--output report.json` 인자가 필요. 두 출력 모드 모두 회귀로 잡아둘 것.

### 3) test_triggers.py

SKILL.md frontmatter description의 트리거 회귀. itda-work에 트리거 회귀 표준 패턴이 있는지 먼저 다른 스킬 (예: blog-seo, draft-post) tests/ 확인 후 동일 패턴 차용.

```python
# Should-trigger (8개)
SHOULD_TRIGGER = [
    "이 보고서 AI 같아",
    "고객사 보낼 메일 너무 딱딱해",
    "기획서 자연스럽게 다듬어줘",
    "AI 티 빼줘",
    "사람이 쓴 것처럼 고쳐줘",
    "ChatGPT로 뽑은 글인데 검수해줘",
    "보고서 톤 다듬어줘",
    "공지문 인간화 부탁해",
]
# Should-NOT-trigger (8개) — draft-post와 충돌하면 안 됨
SHOULD_NOT_TRIGGER = [
    "보고서 작성해줘",  # → draft-post
    "주간 보고 초안 잡아줘",  # → draft-post
    "블로그 글 써줘",  # → draft-post 또는 blog
    "블루키워드 분석해줘",  # → blog-seo
    "PDF 정제해줘",  # → pdf-context-refinery
    "이메일 보내줘",  # → email
    "환율 조회해줘",  # → exchange-rate
    "ETF 시세 알려줘",  # → etf-naver
]
```

회귀 실행은 LLM 응답 시뮬레이션이 어려우므로 description 매칭 키워드 사전을 별도 추출해 단위 테스트화하는 방식 권장.

### 검증

```bash
cd skills/itda-work
just test-skill human-tone
```

전체 통과 확인 후 PR/커밋.

---

## 3. P0 — SKILL.md `metrics.py --output` 보완 (30분)

### 현재 결함

SKILL.md 4단계 호출 예시:
```bash
python3 scripts/metrics.py --input <restored.txt> --baseline scripts/baseline.json --genre <scene>
```

이 호출은 stdout에 `risk_band` 한 줄(`low`/`medium`/`high`)만 반환. risk_score·z_scores·lexicon_hits 등 상세 진단을 후속 단계로 넘기려면 `--output <report.json>` 추가 필요.

### 수정안

SKILL.md 4단계에 다음 두 줄로 분리:

```bash
# 빠른 위험도 한 줄
python3 scripts/metrics.py --input _workspace/03_rewrite.md --baseline scripts/baseline.json --genre report

# 진단 JSON 상세 (5단계 audit·report 블록 생성용)
python3 scripts/metrics.py --input _workspace/03_rewrite.md --baseline scripts/baseline.json --genre report --output _workspace/04_metrics.json
```

`_workspace/04_metrics.json` 스키마는 `metrics.py` `_main()` 함수 끝부분 `json.dump()` 출력 형식을 그대로 참조하면 됨 (대략: `{ risk_band, risk_score, z_scores: {...}, lexicon_hits: {...}, evidence_spans: [...] }`).

### 검증

수정 후 직접 실행해서 _workspace/04_metrics.json이 생성·로드 가능한지 확인.

---

## 4. P1 — metrics_v2.py 통합 (4~6시간, 신중)

### 배경

원본 `ref-im-not-ai/.claude/skills/humanize-korean/references/metrics_v2.py` (746줄)는 v1.6의 metrics.py를 재수출하면서 **post-editese 3축** (Toral 2019) 14개 신규 함수를 추가:

- **Simplification**: lexical_diversity_ttr, lexical_density, ending_diversity
- **Normalisation**: normalisation_score, da_streak_rate
- **Interference (T1~T8)**: inanimate_subject_rate, by_passive_count, double_passive_count, pronoun_density, deul_overuse_rate, relative_clause_nesting, have_make_literal_count, double_particle_count, progressive_aspect_rate

### 본 라운드에서 미통합한 이유

1. `baseline_v2.json`의 모든 셀이 `_placeholder: true` 상태 — 임계값 미정
2. `interference_index` 가중치(T1=1.0, T3=4.0, T4=4.0, T8b=1.0 등)는 ref-im-not-ai 자체에서도 calibration 대기 중
3. v1.6 metrics.py가 직장인 도메인에서 충분히 작동함을 우선 검증

### 차기 통합 절차

1. **이식 비용 평가**:
   - `cp <ref-im-not-ai 체크아웃>/.claude/skills/humanize-korean/references/metrics_v2.py skills/human-tone/scripts/`
   - `cp .../baseline_v2.json skills/human-tone/scripts/`
   - import 의존: metrics_v2.py가 metrics.py를 `from .metrics import *` 식으로 의존하는지 확인 (파일 상단 참조)

2. **baseline_v2 calibration**:
   - 직장인 보고서 5건, 이메일 5건, 기획서 5건, 공지 5건을 사람이 쓴 것 / AI가 쓴 것으로 짝지어 수집
   - 각 텍스트에 metrics_v2의 14개 함수 실행 → mean·stdev 산출
   - baseline_v2.json의 placeholder 셀을 실측값으로 교체
   - **주의**: 이 calibration 없이 metrics_v2.py를 production에 올리면 `interference_index`가 무의미한 값을 반환할 수 있음

3. **K 카테고리와의 매핑**:
   - K-1 보고서식 군더더기 ↔ T2a/T2b (이중 피동) ↔ E (어미 단조)
   - K-3 차용어 ↔ Simplification.lexical_density (낮을수록 차용어 많을 가능성)
   - K-4d 결구 일관성 ↔ Normalisation.da_streak_rate
   - 매핑 표를 references/k-postediteseMapping.md로 별도 작성

4. **SKILL.md 업데이트**:
   - 4단계 결정적 측정에 `--metrics-version v1|v2` 옵션 추가
   - v2 활성화 시 추가 출력 항목 (interference_index, post-editese 3축 점수)

5. **테스트**:
   - tests/test_metrics_v2.py — ref-im-not-ai의 tests/test_metrics_v2.py를 차용해 직장인 corpus로 fixture 갱신

### 결정 포인트

baseline_v2 calibration 비용(직장인 corpus 수집 + 측정 + 검증)이 크므로, **사용자 실사용 피드백이 누적된 후** (예: 3개월 후) 진행 권장. 그 전까지는 v1.6 metrics.py로 충분.

---

## 5. P1 — 카탈로그 README 갱신 (30분)

`skills/itda-work/README.md` 47번째 줄 (현재 v3.1.0 시점에 추가된 행):

```markdown
| **itda-human-tone** | AI가 쓴 듯한 보고서·이메일·기획서를 사람 톤으로 다듬는 후처리 검수 | 📦 |
```

v2.0 가치를 반영해 갱신:

```markdown
| **itda-human-tone** | 보고서·이메일·기획서·공지의 AI 슬롭을 결정적 메트릭(40+ 패턴 SSOT) + 보존 가드로 검수 | 📦 |
```

추가로 README 상단 "콘텐츠·마케팅" 섹션 또는 별도 "글쓰기·검수" 섹션 신설 검토 (org-tone 신설 시점에 함께 진행 권장).

---

## 6. P2 — itda-org-tone 신규 스킬 (6~8시간)

### 사용자 결정 사항 (2026-05-11 합의)

- **인수인계 컨텍스트**: ref-cowork-plugins 디렉토리에서 진행한 대화 (KNOWLEDGE.md 직전)
- **포맷**: 마크다운 (frontmatter는 선택)
- **슬롭 가드**: 1차 슬롭 제거 후 학습 (즉, 입력 샘플을 먼저 human-tone으로 정화한 뒤 시그널 추출)
- **저장소 정책**: 미정 (org-tone 설계 시 재논의)
- **human-tone 연결**: `--profile <path>` 옵션으로 마크다운 직접 참조

### 설계 출발점

`ref-im-not-ai`의 v1.2 `author-context.yaml` 시스템이 이미 존재 → 이 포맷을 마크다운으로 변환한 형태가 itda-org-tone의 출력. 원본 README §1.2 또는 v1.5 monolith path 문서 참조.

### 추출할 시그널 (8종)

1. 어미 분포 (합쇼체/해라체/해요체 비율)
2. 자주 쓰는 결구 (검토 부탁드립니다 vs 의견 주시면 반영하겠습니다)
3. 자주 쓰는 도입 (금일 ~ 건 vs 안녕하세요. ~ 관련하여)
4. 호칭 관습 (귀사/고객사/협력사, 부서 약칭, 직책 표기)
5. 결재 표현 (사료됨/판단됨/제안드림 선호도)
6. 단락 길이 분포 (평균 글자 수, 표/불릿 사용 빈도)
7. 고유 어휘 사전 (시스템명·약어·내부 용어)
8. 금기 표현 (샘플에 없는 영어 차용어 = 이 회사는 안 씀)

### 안전장치 (반드시)

- 샘플 최소 3건 미만 → 거부
- 샘플의 AI 슬롭 1차 제거 후 학습
- 샘플에 이메일·전화·주민번호 패턴 → 학습 전 마스킹 안내
- 프로필 사용 시 출처 명시 (`프로필 적용: acme (샘플 5건, 2026-MM 학습)`)

### 별도 SPEC 권장

복잡도가 크므로 본 인수인계 노트로는 부족. 차기 세션에서 `itda-org-tone-spec.md`를 별도 작성한 뒤 진행.

---

## 7. P2 — K 카테고리 검증 (지속적)

### 배경

K-1~K-5는 직관 기반 가설. 실제 사무 한국어 corpus 빈도 측정 안 됨. 비판적 리뷰에서 짚었던 "검증 안 된 가설" 이슈.

### 검증 절차

1. 사용자가 실제 보고서·이메일·기획서·공지 5건씩 (총 20건) 익명화 후 인간/AI 라벨링
2. 각 텍스트에 quick-rules.md K 패턴 매칭 → 빈도 카운트
3. 인간 vs AI에서 빈도 차이가 z>1.0 이상 나면 K 패턴 유효성 확인
4. 무효 K 항목은 deprecate, 새 패턴 후보(K-6+) 발굴
5. taxonomy 부록 갱신 + CHANGELOG에 검증 기록

### 결과 반영

- K-x 항목별 severity 재조정 (S1↔S2)
- K-x threshold 임계값 조정
- 새 K-6, K-7 추가 또는 기존 K-5 deprecate

---

## 8. P3 — scholarship.md 통합 검토 (1시간)

### 현재 미통합 이유

원본 289줄. 한국 번역학계 8유형 + 국제 이론 3대축의 학술 출처 정리.

- 본문 비대 우려: 직장인 사용자가 "왜 이 카테고리가 학술적으로 정당한가"를 알 가치는 낮음
- 학술 정통성은 분류학 자체에 이미 anchor 부착(`source_anchor`, `see_scholarship`)으로 표시됨

### 통합 시점 판단

- 학술 사용자 (대학원생·연구자) 피드백 누적 시 → 통합
- 그렇지 않으면 references/scholarship.md 별도 파일로 두되 SKILL.md 본문에서는 참조 안 함

---

## 9. 위험 · 주의사항

### 9-1. 라이선스 무결성

- `LICENSE-im-not-ai` 파일을 절대 삭제하지 말 것 — MIT 조건 위반
- references/ai-tell-taxonomy.md, quick-rules.md, rewriting-playbook.md, scripts/metrics.py, scripts/baseline.json은 **MIT 자산**이며 변경 시 K 부록·직장인 §6 등 자체 작성 부분과 명확히 구분 유지
- README.md "차용 출처" 섹션은 자산 추가/수정 시 반드시 동기화

### 9-2. metrics.py 수정 금지

`scripts/metrics.py`는 ref-im-not-ai v1.6 그대로. 직장인 도메인 패턴 추가가 필요하면 **새 파일 `scripts/metrics_k.py`** 작성 후 K 패턴 정규식 카운터 별도 구현. metrics.py 본체는 upstream 동기화 가능성을 위해 보존.

### 9-3. baseline.json 수정 금지

KatFish 베이스라인은 일관성 유지 자산. 직장인 도메인 calibration이 필요하면 별도 `scripts/baseline_workplace.json`을 만들고 metrics.py `--baseline` 인자로 전환.

### 9-4. K 카테고리 ID 안정성

K-1~K-5 ID는 외부 참조(SKILL.md, playbook §6, quick-rules 표) 다수. 재번호 절대 금지. 추가는 K-6, K-7 식으로만.

### 9-5. plugin.json 버전 동기화

itda-work는 cowork-plugins처럼 SKILL.md frontmatter `version`을 별도 관리하지 않고 plugin.json만 단일 소스. SKILL.md frontmatter `metadata.version`은 스킬 자체 버전(인스킬 자율 관리)이므로 plugin.json 버전과 별개로 운영 가능. 단 CHANGELOG에는 둘 다 기록.

---

## 10. 외부 자료 위치

| 자원 | 경로 | 사용처 |
|---|---|---|
| ref-im-not-ai 원본 | `<ref-im-not-ai 체크아웃>/` | metrics_v2.py 통합, scholarship.md 검토 |
| cowork-plugins (humanize-korean Fast 변형) | `<ref-cowork-plugins 체크아웃>/content/skills/humanize-korean/` | Fast 변형 패턴 재참조 |
| cowork-plugins KNOWLEDGE.md | `<ref-cowork-plugins 체크아웃>/KNOWLEDGE.md` | cowork 컨벤션 일반론 |
| im-not-ai GitHub 원본 | https://github.com/epoko77-ai/im-not-ai | 업스트림 변경 추적 |
| itda-work 다른 스킬 (참고 컨벤션) | `skills/itda-work/skills/{blog-seo, draft-post, ...}/` | tests 패턴, frontmatter 스타일 |

---

## 11. 의사결정 로그

본 라운드에서 내려진 주요 결정과 이유. 차기 세션이 같은 결정을 반복 토론하지 않도록 기록.

| 일자 | 결정 | 이유 |
|---|---|---|
| 2026-05-11 | 옵션 A (풀패키지) 채택 | cowork-plugins humanize-korean이 동일 변환 선례, MIT, P0 비판 리뷰 항목 동시 해결 |
| 2026-05-11 | monolith fast path 단일 스킬로 압축 | Cowork 환경은 sub-agent/슬래시 커맨드 미지원. 12 에이전트 풀 스택은 직장인 검수에 과함 |
| 2026-05-11 | metrics_v2.py 차기로 미룸 | baseline_v2 placeholder 상태, 직장인 corpus calibration 미비 |
| 2026-05-11 | scholarship.md 차기로 미룸 | 직장인 사용자 가치 대비 본문 비대 우려 |
| 2026-05-11 | K 카테고리 5종 자체 신설 | A~J는 출판물 대상. 사무 한국어 특유 패턴 별도 신설 필요 |
| 2026-05-11 | lock_preserved.py 자체 작성 | 원본은 변경률 가드만. 보존 영역 결정적 마스킹은 직장인 도메인(숫자·서명·법조항) 환각 위험 차단에 필수 |
| 2026-05-11 | itda-org-tone 신규 스킬로 분리 | 단일 스킬에 학습+검수+적용 모두 담으면 본문 250줄+ 폭발. 책임 분리 |
| 2026-05-11 | "사료됩니다" 단정 완화 | 한국 공문서의 정당한 정중 추정. 단락당 2회+ 시 1회로 압축으로 톤 다운 |

---

## 12. 빠른 검증 명령

차기 세션에서 모든 게 잘 작동하는지 1분 안에 확인:

```bash
cd <저장소 루트>/itda-doc/skills/human-tone

# 1) 디렉토리 구조 확인
find . -type f | sort

# 2) lock_preserved.py 단위 테스트 (현재는 인라인)
python3 -c "
import sys; sys.path.insert(0, 'scripts')
import lock_preserved as lp
s = '2026년 5월 11일 매출이 15% 증가. https://x.com / a@b.kr'
m, pm = lp.mask(s)
r, miss = lp.restore(m, pm)
assert r == s and not miss, 'FAIL'
print('lock_preserved: OK')
"

# 3) metrics.py end-to-end (AI 스타일 → high)
python3 scripts/metrics.py --input <(echo "현대 사회에서 기술적 혁신은 중요하다. 결론적으로, 우리는 양쪽 모두를 신중하게 고려해야 한다.") --baseline scripts/baseline.json --genre essay
```

---

## 끝

이 문서가 다른 세션이 컨텍스트 0에서 P0 작업을 시작할 수 있는 최소 충분 정보입니다. 누락된 게 발견되면 본 문서에 직접 추가해주세요.
