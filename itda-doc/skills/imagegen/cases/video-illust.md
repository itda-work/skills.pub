# Remotion 영상 삽화 — 쇼츠/유튜브 (video-illust)

상태: verified — 실사 템플릿 A 기준 (마스터 판정 "지금 단계에서 일단 OK" 2026-06-13. 일러스트 B 변형은 미판정 draft)
최종 실측: 2026-09-28 (codex-cli 0.157.0)

## 용도

Remotion 영상 제작에 쓰는 장면 삽화. 쇼츠/릴스(9:16 세로)와 유튜브 일반(16:9 가로).
"쇼츠용 삽화", "영상에 들어갈 장면 이미지" 류 요청.
**세로 결과는 1024×1536(2:3)이 최대다(r4).** 쇼츠 9:16 은 양옆을 잘라(864×1536) 쓰거나
Remotion 에서 `cover` 로 채운다 — 위아래 안전 영역이 자르기 여유이기도 하다.
실사가 기본값이다(r2 마스터 판정). 일러스트는 명시 요청 시만.

## 프롬프트 템플릿

쇼츠(세로):

```
Cinematic vertical 9:16 photograph for a short-form video about {장면}.
Cinematic photography, 35mm film aesthetic.
Single focal subject: {피사체/동작 — 절 단위}, with a {subtle|candid} natural
expression — not exaggerated, relaxed posture, placed in the middle vertical band,
clean waist-up framing.
Lighting & mood: {조명 — 예: teal and orange cinematic color grading, soft volumetric
light}, depth of field — must read clearly on a phone screen at a glance.
Natural skin texture preserved, photorealistic, subtle film grain.
Keep the top 20% and bottom 25% of the frame calm and simple
(safe zone for captions and UI overlays).
Portrait 1024x1536. No text, no letters, no watermark.
```

유튜브 가로(16:9)는 같은 템플릿에서 `Vertical 9:16` → `Widescreen 16:9`,
`Portrait 1024x1536` → `Landscape 1536x1024`, 안전 영역을 하단 20% 로 변경.

슬롯: `{장면}` `{팔레트}` `{피사체/동작}`.
영상은 장면 컷이 연속되므로 같은 영상의 컷들은 `{팔레트}` 와 스타일 문구를 고정해 톤을 통일한다.

## 품질 체크리스트

공통 C1~C6 (`_SCHEMA.md`) +

| # | 항목 | 판정 기준 |
|---|---|---|
| V1 | 비율 | 쇼츠: 실제 세로(1024x1536, 2:3)로 나왔는가 — 9:16 은 잘라 맞춘다 |
| V2 | 폰 가독 | 축소(폰 크기)해도 피사체가 한눈에 읽히는 대담한 형태인가 |
| V3 | 자막 안전 영역 | 상/하단이 자막 얹기 좋게 차분한가 |

## 실측 기록

### r4 — 2026-09-28 (codex-cli 0.157.0) — itda-hyve `agent_run` 경로 첫 실측 (5장 한 번에, 임시 격리 홈)

- 프롬프트 전문:

```
Cinematic vertical 9:16 photograph for a short-form video about a young office worker finishing work early thanks to automation.
Cinematic photography, 35mm film aesthetic.
Single focal subject: a woman in her late twenties closing her laptop at a desk and reaching for her bag, with a subtle natural smile — not exaggerated, relaxed posture, placed in the middle vertical band, clean waist-up framing.
Lighting & mood: warm late-afternoon sunlight through blinds, teal and orange cinematic color grading, soft volumetric light, depth of field — must read clearly on a phone screen at a glance.
Natural skin texture preserved, photorealistic, subtle film grain.
Keep the top 20% and bottom 25% of the frame calm and simple (safe zone for captions and UI overlays).
Portrait 1024x1536. No text, no letters, no watermark.
```

- 경로: `agent_run`(recipe `codex.imagegen`, `wait_sec: 0`) 5건을 한꺼번에 넣고 `job_status` 로 회수. 계정당 3개 동시 — 3건 동시 시작, 2건 `queued` 뒤 앞 작업이 끝나며 시작. 5건 모두 `completed`, 장당 결과 1개.
- 토큰(장당): 입력 약 2.1만(캐시 약 9천)·출력 230~360.
- 결과: **1024×1536(2:3)** — 9:16 이 아니다, 92초 = 첫 실행이라 앞 작업의 시스템 스킬 기준값 기록을 41초 기다림 + codex 실행 51초
- 판정: C1 ✅(시네마틱 실사) C2 ✅ C3 ✅(손·가방끈 정상) C4 ✅(가운데 띠, 상단 벽·하단 책상이 비교적 고요) C5 ⚠️(2:3) C6 ✅(블라인드 역광·틸오렌지) / 자연 미소 ✅
- 마스터 판정: 통과 (2026-09-28, 원본 5장 검토 뒤 "좋아")
- 썸네일: `measurements/video-illust-r4.jpg`
- 교훈: (1) 이미지 모델의 세로 최대는 1024×1536(2:3)이라 "9:16" 을 써도 2:3 으로 나온다 — 쇼츠에는 양옆을 잘라 9:16(864×1536)으로 쓰거나 Remotion 에서 cover 로 채운다. 안전 영역(위 20%·아래 25%)은 자르기 여유이기도 하다. (2) 인물 국적을 적지 않으면 서양인으로 나온다 — 한국 대상 콘텐츠면 `{피사체}` 에 "a Korean woman" 처럼 적는다.

### r3 — 2026-06-13 (codex-cli 0.137.0) — 실사 + 자연 표정 전환 (마스터 판정 반영)

- 슬롯: 동일 장면 / cinematic photography, 35mm film aesthetic / "subtle pleased smile,
  candid natural expression — not exaggerated" / 저녁 도시 보케, teal-orange 그레이딩
- 결과: 1024×1536 세로 ✅ (3연속 정확)
- 판정: C1 ✅(실사 사진 수준) C2 ✅ C3 ✅ C4 ✅ C5 ✅ C6 ✅ / V1 ✅ V2 ✅ V3 ✅
- 썸네일: `measurements/video-illust-r3.jpg`
- 교훈: **과장 표정 안티프롬프트 검증 완료** — "not exaggerated" 명시로 절제된 미소가
  나옴(r2 의 "AI 생성 느낌" 해소). 실사 전환 + 자연 표정 + 도시 보케 조합이 쇼츠
  실사 컷의 기준 조합으로 확정 후보.

### r2 — 2026-06-13 (codex-cli 0.137.0) — 시네마틱 층 + 잘림 구도 가설 검증

- 슬롯: r1 과 동일 장면(비교 통제) + "high-end cinematic illustration" + "clean waist-up
  framing" + "dramatic neon teal and orange color grading, volumetric light rays, depth of field"
- 결과: 1024×1536 세로 ✅ (2연속 정확 — 비율 확보법 재현성 확인)
- 판정: C1 ✅ C2 ✅ C3 ✅(**r1 부속물 아티팩트 소멸**) C4 ✅ C5 ✅ C6 ✅ / V1 ✅ V2 ✅ V3 ✅
- 썸네일: `measurements/video-illust-r2.jpg`
- 교훈: "clean waist-up framing" 이 r1 의 잘림 경계 부속물 문제를 해소 — 가설 검증 완료.
  volumetric light rays + teal/orange 그레이딩으로 쇼츠 썸네일급 임팩트. 배경 보케에
  차트 형상이 은은히 깔림(no text 유지된 채 주제 보강).
- **마스터 판정: 불합격** — "너무 AI 생성 느낌이야. 표정이 너무 과해. 그래서 별로야."
  → ① 일러스트 스타일 → 실사 사진 전환, ② "eyes wide with excitement" 류
  과장 표정 지시가 AI 느낌의 직접 원인 → 자연스러운 미세 표정으로 전환(r3).

### r1 — 2026-06-13 (codex-cli 0.137.0)

- 슬롯: 장면 "스마트폰으로 주가 급등을 확인하고 놀라는 사람" / vivid teal and orange /
  피사체 "상승 차트 화살표가 뜬 폰을 치켜든 청년, 휘둥그런 눈"
- 결과: **1024×1536 세로 ✅ — V1 핵심 검증 통과.** 구 전역 스킬의 "해상도 강제 어려움"
  기록을 뒤집음: 한국어 지시문("반드시 세로 방향 1024x1536") + 영문 프롬프트
  ("Portrait 1024x1536") 이중 기입 시 정확히 동작. 같은 배치 5장 전체에서 요청 비율 5/5 일치.
- 판정: C1 ✅ C2 ✅(폰 화면 차트도 글자 없음) C3 ⚠️(우하단에 땋은 줄 형태의 모호한 부속물)
  C4 ✅ C5 ✅ / V1 ✅ V2 ✅(대담한 형태·고대비) V3 ✅(상/하단 차분한 단색 영역)
- 썸네일: `measurements/video-illust-r1.jpg`
- 교훈:
  - **비율 확보법 확정**: 지시문과 프롬프트 양쪽에 해상도 숫자를 이중 기입한다.
  - 인물 하반신 잘림 구도에서 잘린 경계에 모호한 부속물이 생길 수 있음(C3 ⚠️ 사유) —
    "clean waist-up framing" 류 문구를 라운드 2에서 검증 후보.

## 실패 변형 (안티프롬프트)

- **잘림 구도 무명시** (r1): 인물 하반신이 잘리는 구도에서 프레임 명시가 없으면 잘린
  경계에 모호한 부속물(땋은 줄 형태)이 생성됨 → "clean waist-up framing" 으로 해소(r2 검증).
- **과장 표정 지시** (r2, 마스터 판정): "eyes wide with excitement/surprise" 류는
  과장 표정을 만들어 "AI 생성 느낌"의 직접 원인이 됨 → "subtle pleased smile,
  candid natural expression — not exaggerated" 로 대체.
- **일러스트 스타일 기본값** (r2, 마스터 판정): 인물 일러스트는 AI 느낌 — 실사
  (cinematic photography) 가 기본.
