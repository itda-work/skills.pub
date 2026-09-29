# 발표·슬라이드 비주얼 (slide-visual)

상태: verified — 실사 템플릿 A 기준 (마스터 판정 "지금 단계에서 일단 OK" 2026-06-13. 일러스트 B 변형은 미판정 draft)
최종 실측: 2026-09-28 (codex-cli 0.157.0)

## 용도

슬라이드 배경, 섹션 표지, 개념 비주얼. "발표자료에 넣을 이미지" 류 요청.
발표자료 흐름과 연계 — 슬라이드는 글자가 따로 얹히므로 이미지는 배경 역할에 충실해야 한다.

## 프롬프트 템플릿

**프롬프트 A. 실사 배경 — 기본값, r2 마스터 판정 반영**

```
Clean editorial photograph for a presentation slide background about {개념}.
A realistic scene: {장면 — 절 단위. 실제 공간/사물로 개념을 은유.
예: a minimal modern workspace with a laptop and soft daylight}.
One clear focal element on the {left|right} third; the opposite half stays calm,
softly out of focus and uncluttered for headline text overlay.
Lighting & mood: {조명 — 예: soft diffused natural light}, muted professional tones
(dominant {주조색}), natural color grading.
Shot on 35mm lens, shallow depth of field, photorealistic, subtle film grain.
Landscape 1536x1024. No text, no letters, no watermark.
```

**프롬프트 B. 렌더/일러스트 — 사용자가 명시 요청할 때만**

```
Minimal concept visual for a presentation slide about {개념}.
{isometric|flat geometric} illustration style, professional and restrained.
One strong focal element: {초점요소 — 절 단위}. Background: very simple,
{solid color|soft gradient}. Lighting & render: soft studio lighting, subtle ambient
occlusion, {glossy|matte} materials, octane render quality, highly detailed.
Dominant {주조색} with one {강조색} accent. Large calm empty area covering at least
half the canvas. Landscape 1536x1024. No text, no letters, no watermark.
```

슬롯: `{개념}` `{isometric|flat geometric}` `{초점요소}` `{solid color|soft gradient}` `{팔레트}`.
blog-hero 와의 차이: 장식보다 **절제** — 초점 1개 + 나머지는 비움. 화려하면 슬라이드 글자와 싸운다.

## 품질 체크리스트

공통 C1~C6 (`_SCHEMA.md`) +

| # | 항목 | 판정 기준 |
|---|---|---|
| S1 | 배경 단순 | 글자를 얹었을 때 가독성을 해칠 패턴·노이즈가 없는가 |
| S2 | 단일 초점 | 시선이 가는 요소가 정확히 1개인가 |

## 실측 기록

### r4 — 2026-09-28 (codex-cli 0.157.0) — itda-hyve `agent_run` 경로 첫 실측 (5장 한 번에, 임시 격리 홈)

- 프롬프트 전문:

```
Clean editorial photograph for a presentation slide background about quarterly business growth and planning.
A realistic scene: a minimal modern meeting room corner with a single glass of water and a closed notebook on a white table, large window with city daylight beyond.
One clear focal element on the right third; the opposite half stays calm, softly out of focus and uncluttered for headline text overlay.
Lighting & mood: soft diffused natural light, muted professional tones (dominant soft navy and warm gray), natural color grading.
Shot on 35mm lens, shallow depth of field, photorealistic, subtle film grain.
Landscape 1536x1024. No text, no letters, no watermark.
```

- 경로: `agent_run`(recipe `codex.imagegen`, `wait_sec: 0`) 5건을 한꺼번에 넣고 `job_status` 로 회수. 계정당 3개 동시 — 3건 동시 시작, 2건 `queued` 뒤 앞 작업이 끝나며 시작. 5건 모두 `completed`, 장당 결과 1개.
- 토큰(장당): 입력 약 2.1만(캐시 약 9천)·출력 230~360.
- 결과: 1536×1024 ✅, 40초(codex 실행 40초 — 이 계정의 첫 작업이라 기준값을 기록하며 돌았다)
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅(초점 물컵이 오른쪽 1/3, 왼쪽 절반은 무지 벽 — 헤드라인 자리) C5 ✅ C6 ✅(창 역광·테이블 반사) / 네이비·웜그레이 주조 반영
- 마스터 판정: 통과 (2026-09-28, 원본 5장 검토 뒤 "좋아")
- 썸네일: `measurements/slide-visual-r4.jpg`
- 교훈: "one clear focal element on the right third; the opposite half stays calm" 이 여백을 가장 정확히 만든다 — 5장 중 가장 좋았다.

### r3 — 2026-06-13 (codex-cli 0.137.0) — 실사 배경 전환 (마스터 판정 반영)

- 슬롯: 동일 개념 / 템플릿 A(실사) / 장면 "서버룸 복도, LED 상태등이 멀어지는 원근" /
  우측 초점·좌측 여백 / 35mm 얕은 심도
- 결과: 1536×1024 ✅
- 판정: C1 ✅(실제 서버룸 사진 수준) C2 ✅(LED 점등이 글자로 안 읽힘) C3 ✅ C4 ✅ C5 ✅ C6 ✅
  / S1 ✅(좌측 절반 차분한 블러) S2 ✅
- 썸네일: `measurements/slide-visual-r3.jpg`
- 교훈: 실사 배경 전환 성공 — 개념(데이터 파이프라인)을 실제 공간(서버룸)으로 치환하는
  접근이 유효. 슬라이드 배경은 "실제 장소 + 한쪽 여백 블러" 패턴으로 확정 후보.

### r2 — 2026-06-13 (codex-cli 0.137.0) — 렌더 층 추가 재측정

- 슬롯: r1 과 동일 개념/초점요소(비교 통제) + "soft studio lighting, subtle ambient
  occlusion, glossy materials, octane render quality, highly detailed"
- 결과: 1536×1024 ✅
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅ C5 ✅ C6 ✅ / S1 ✅ S2 ✅
- 썸네일: `measurements/slide-visual-r2.jpg`
- 교훈: "glossy materials, octane render quality" 가 매트 플랫 → 유리질 금속 깔때기 +
  발광 와이어프레임 큐브로 — 동일 구도에서 프리미엄 렌더로 상승. 좌측 ~65% 단색 여백 유지.
- **마스터 판정: 불합격** — "컴퓨터 그래픽 느낌인데 너무 심플하고 별로 효용성이 없음."
  → 아이소메트릭/렌더 계열 자체가 슬라이드 배경 효용 기준 미달.
  기본 스타일을 실사 사진 배경(여백 있는 photographic scene)으로 전환(r3).

### r1 — 2026-06-13 (codex-cli 0.137.0)

- 슬롯: 개념 "데이터 파이프라인 자동화" / isometric / 초점 "빛나는 데이터 큐브가
  컨베이어를 타고 깔때기로 흘러드는 장면" / solid color / deep blue·slate + amber accent
- 결과: 1536×1024 ✅
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅ C5 ✅ / S1 ✅(완전 단색 배경) S2 ✅(단일 초점)
- 썸네일: `measurements/slide-visual-r1.jpg`
- 교훈: **라운드 1 모범 사례.** "Large calm empty area covering at least half the canvas"
  문구가 실제로 좌측 ~60% 를 빈 단색 영역으로 만들어냄 — 헤드라인 오버레이 공간 확보에
  이 문구가 유효함을 실측 확인. amber accent 1색 제한도 정확히 지켜짐.

## 실패 변형 (안티프롬프트)

- **아이소메트릭/렌더 기본값** (r1·r2, 마스터 판정): 깔끔하게 나와도 "컴퓨터 그래픽
  느낌 + 심플 = 효용 없음" — 실사 사진 배경이 기본. 렌더는 명시 요청 시만.
