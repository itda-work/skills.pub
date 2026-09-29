# 블로그·문서 히어로/삽화 (blog-hero)

상태: verified — 실사 템플릿 A 기준 (마스터 판정 "지금 단계에서 일단 OK" 2026-06-13. 일러스트 B 변형은 미판정 draft)
최종 실측: 2026-09-28 (codex-cli 0.157.0)

## 용도

글 상단 대표(히어로) 이미지, 본문 개념 삽화. "블로그 대표 이미지 만들어줘",
"이 글에 어울리는 삽화" 류 요청. blog-seo·draft-post 산출물과 연계.

## 프롬프트 템플릿

**프롬프트 A. 실사 — 기본값, r2 마스터 판정 반영**

```
Editorial photograph for a blog article about {주제}.
A realistic scene: {장면 — 절 단위. 사람의 손/사물/공간으로 주제를 은유.
예: hands typing on a laptop beside a neat stack of documents in a bright office}.
Composition: subject on the {left|right} third, soft out-of-focus negative space
on the opposite side for a title overlay.
Lighting & mood: {조명 — 예: soft morning window light from the left},
{분위기 — 예: calm focused} atmosphere, natural color grading.
Shot on 35mm lens, f/2.0, shallow depth of field, photorealistic,
natural textures preserved, subtle film grain.
Landscape 1536x1024. No text, no letters, no watermark, no signature.
```

**프롬프트 B. 일러스트 — 사용자가 명시 요청할 때만**

```
Editorial hero illustration for a blog article about {주제}.
{스타일 군집 — _PATTERNS.md §3}. A single clear visual metaphor: {메타포 — 절 단위}.
Composition: subject on the {left|right} third, generous negative space for title overlay.
Lighting & mood: {조명}, {분위기} atmosphere. Color: dominant {주조색}, {보조색} accents.
Highly detailed, subtle film grain. Landscape 1536x1024.
No text, no letters, no watermark, no signature.
```

슬롯: `{주제}` `{스타일 군집}` `{메타포}` `{left|right}` `{조명}` `{분위기}`
`{주조색}` `{보조색}`.
메타포 슬롯이 핵심 — "about X" 만 주면 모델이 진부한 클립아트를 그린다.
팔레트는 주조/보조 비중을 반드시 구분(r1 교훈). 조명·기술스펙 층 생략 금지(r1→r2 개정 사유).

## 품질 체크리스트

공통 C1~C6 (`_SCHEMA.md`) +

| # | 항목 | 판정 기준 |
|---|---|---|
| B1 | 제목 여백 | 한쪽에 제목 얹을 빈 공간이 실제로 비어 있는가 |
| B2 | 메타포 전달 | 주제를 모르는 사람이 봐도 무엇에 관한 글인지 연상되는가 |

## 실측 기록

### r4 — 2026-09-28 (codex-cli 0.157.0) — itda-hyve `agent_run` 경로 첫 실측 (5장 한 번에, 임시 격리 홈)

- 프롬프트 전문:

```
Editorial photograph for a blog article about how small teams automate repetitive office paperwork with AI.
A realistic scene: a person's hands sorting a neat stack of printed invoices beside an open laptop showing a clean dashboard, a ceramic coffee cup and a small potted plant on a light oak desk in a bright office.
Composition: subject on the left third, soft out-of-focus negative space on the right side for a title overlay.
Lighting & mood: soft morning window light from the left, calm focused atmosphere, natural color grading.
Shot on 35mm lens, f/2.0, shallow depth of field, photorealistic, natural textures preserved, subtle film grain.
Landscape 1536x1024. No text, no letters, no watermark, no signature.
```

- 경로: `agent_run`(recipe `codex.imagegen`, `wait_sec: 0`) 5건을 한꺼번에 넣고 `job_status` 로 회수. 계정당 3개 동시 — 3건 동시 시작, 2건 `queued` 뒤 앞 작업이 끝나며 시작. 5건 모두 `completed`, 장당 결과 1개.
- 토큰(장당): 입력 약 2.1만(캐시 약 9천)·출력 230~360.
- 결과: 1536×1024 ✅, 93초 = 첫 실행이라 앞 작업의 시스템 스킬 기준값 기록을 41초 기다림 + codex 실행 52초
- 판정: C1 ✅ C2 ✅(서류·화면이 글자 없는 회색 블록 — 가짜 글자 0) C3 ✅(손 정상) C4 ⚠️(인물이 왼쪽 1/3보다 조금 안쪽) C5 ✅ C6 ✅ / B1 ✅(오른쪽 절반이 흐린 바닥 — 제목 자리) B2 ✅
- 마스터 판정: 통과 (2026-09-28, 원본 5장 검토 뒤 "좋아")
- 썸네일: `measurements/blog-hero-r4.jpg`
- 교훈: 0.137 → 0.157 에서도 템플릿 A 가 그대로 통한다. "No text, no letters" 가 화면·서류 속 글자까지 막아 준다.

### r3 — 2026-06-13 (codex-cli 0.137.0) — 실사 전환 (마스터 판정 반영)

- 슬롯: 동일 주제 / 템플릿 A(실사) / 장면 "손이 노트북 타이핑, 옆에 서류 더미와
  스마트 스피커, 밝은 사무실 보케" / 35mm f/2.0 / 창가 아침광
- 결과: 1536×1024 ✅
- 판정: C1 ✅(실제 스톡 사진 수준) C2 ✅ C3 ✅(손가락 정상) C4 ✅(좌측 밝은 블러 여백 —
  어두운 제목 글자에 최적) C5 ✅ C6 ✅ / B1 ✅ B2 ✅(사무 자동화 연상, "AI" 는 암시적)
- 썸네일: `measurements/blog-hero-r3.jpg`
- 교훈: 실사 전환으로 "컴퓨터 그래픽 느낌" 문제 해소 — 35mm + 얕은 심도 + 자연광 조합이
  에디토리얼 스톡 사진급. AI 라는 추상 개념은 실사에서 소품(스마트 스피커 등)으로
  암시하는 정도가 한계 — 개념 직설이 필요하면 일러스트(B) 영역.

### r2 — 2026-06-13 (codex-cli 0.137.0) — 5층 공식 적용 재측정

- 슬롯: r1 과 동일 주제/메타포(비교 통제) + 스타일 "sophisticated tech-magazine editorial,
  rich textures" + 조명 "soft volumetric morning light through a tall window, calm focused
  cinematic" + 색 "dominant deep navy, warm coral accents, rich color grading"
  + "Highly detailed, subtle film grain"
- 결과: 1536×1024 ✅
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅ C5 ✅ C6 ✅ / B1 ✅ B2 ✅
- 썸네일: `measurements/blog-hero-r2.jpg` (r1 과 비교)
- 교훈: **동일 메타포에 4·5층(조명/분위기·기술스펙)만 추가했는데 클립아트풍 → 매거진급으로
  체감 품질 급상승.** 5층 공식의 효과가 통제 비교로 검증됨. 좌측 여백이 어두운 네이비 면이라
  제목은 밝은 글자 전제 — 밝은 여백이 필요하면 조명 방향을 좌측 창으로 바꿀 것.
- **마스터 판정: 불합격** — "컴퓨터 그래픽 느낌이고 효용성이 없음. 실사 위주의 다양한
  예시가 있었으면 함." → 일러스트 스타일 자체가 이 케이스의 효용 기준 미달.
  기본 스타일을 실사 사진(editorial photography)으로 전환(r3).

### r1 — 2026-06-13 (codex-cli 0.137.0)

- 슬롯: 주제 "AI 에이전트의 반복 사무 업무 자동화" / 메타포 "로봇 비서가 흐르는 문서들을
  빛나는 폴더로 차분히 분류" / right / warm coral and navy with soft cream
- 결과: 1536×1024 ✅ (요청 비율 정확). 5장 병렬 배치 중 1장, wall-clock 약 2분대.
- 판정: C1 ⚠️ C2 ✅ C3 ✅ C4 ✅ C5 ✅ / B1 ✅(좌측 절반 빈 여백 확보) B2 ✅(분류 메타포 즉시 전달)
- 썸네일: `measurements/blog-hero-r1.jpg`
- 교훈:
  - "flat illustration with subtle gradients" → 순수 2D 플랫이 아닌 소프트 3D(클레이풍)
    하이브리드로 렌더됨(C1 ⚠️ 사유). 결과 자체는 고품질이라 1차 통과. 엄격한 2D 가
    필요하면 "strictly 2D flat, no 3D rendering" 추가 — 라운드 2 검증 후보.
  - 팔레트 3색 지정 시 비중을 안 주면 모델이 임의 배분(navy 가 거의 소거됨).
    주조색 명시 권장: "dominant navy, coral accents" 식.

## 실패 변형 (안티프롬프트)

- **일러스트 스타일 기본값** (r1·r2, 마스터 판정): 일러스트/3D 렌더 히어로는 "컴퓨터
  그래픽 느낌"으로 효용 미달 — 실사 editorial photography 가 기본. 일러스트는 명시 요청 시만.
