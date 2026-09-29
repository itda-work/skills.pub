# 실사 인물 (photoreal-portrait)

상태: verified (마스터 긍정 r1 + "일단 OK" 2026-06-13 — 표정 변형 포함)
최종 실측: 2026-09-28 (codex-cli 0.157.0)

## 용도

프로필 사진, 헤드샷, 실사 모델 컷. "실사 느낌 인물", "프로필용 사진" 류 요청.
핵심 팁(Threads 실측, `_PATTERNS.md` §2): **카메라 기종이 아니라 렌즈 모델을 명시**한다.
실존 인물 재현·합성 요청은 거절하고 가상 인물 명세로 유도한다.

## 프롬프트 템플릿

```
Photorealistic portrait of {가상 인물 명세 — 절 단위: 연령대/분위기/복장}.
{장면/배경 — 예: seated by a large window in a minimal studio, neutral backdrop}.
Lighting: {조명 — 예: soft window light from the left, gentle fill}, cinematic color grading.
Shot on 85mm lens, f/1.8, shallow depth of field.
Natural skin texture preserved, authentic, subtle film grain — do not over-retouch.
{Portrait 1024x1536|Square 1024x1024}. No text, no watermark.
```

슬롯: `{가상 인물 명세}` `{장면/배경}` `{조명}` `{비율}`.
"natural skin texture preserved" 가 인형 피부 과보정 차단의 핵심(수집 사례 공통).
LinkedIn 헤드샷 변형: 배경을 `clean soft gray gradient`, 조명을
`studio-quality even illumination, soft catchlights in eyes` 로.

## 품질 체크리스트

공통 C1~C6 (`_SCHEMA.md`) +

| # | 항목 | 판정 기준 |
|---|---|---|
| P1 | 피부 질감 | 모공/잔결이 살아 있는가 — 왁스 인형/과보정이 아닌가 |
| P2 | 심도 | 배경 보케·피사체 분리가 지정 렌즈답게 나왔는가 |
| P3 | 불쾌한 골짜기 | 눈동자·치아·손에 위화감이 없는가 |

## 실측 기록

### r3 — 2026-09-28 (codex-cli 0.157.0) — itda-hyve `agent_run` 경로 첫 실측 (5장 한 번에, 임시 격리 홈)

- 프롬프트 전문:

```
Photorealistic portrait of a Korean man in his early forties, a friendly small-business owner, wearing a navy knit sweater over a white collared shirt.
Seated by a large window in a minimal studio, neutral light-gray backdrop.
Lighting: soft window light from the left, gentle fill, cinematic color grading.
Shot on 85mm lens, f/1.8, shallow depth of field.
Natural skin texture preserved, authentic, calm confident expression — not exaggerated, subtle film grain — do not over-retouch.
Portrait 1024x1536. No text, no watermark.
```

- 경로: `agent_run`(recipe `codex.imagegen`, `wait_sec: 0`) 5건을 한꺼번에 넣고 `job_status` 로 회수. 계정당 3개 동시 — 3건 동시 시작, 2건 `queued` 뒤 앞 작업이 끝나며 시작. 5건 모두 `completed`, 장당 결과 1개.
- 토큰(장당): 입력 약 2.1만(캐시 약 9천)·출력 230~360.
- 결과: 1024×1536 ✅, 106초 = 대기열 41초(첫 작업이 끝나자 시작) + codex 실행 65초
- 판정: C1 ✅ C2 ✅ C3 ✅(깍지 낀 손 정상) C4 ✅(왼쪽 창 빛) C5 ✅ C6 ✅ / 한국인 40대·네이비 니트+흰 셔츠 ✅, 피부 질감 과보정 없음 ✅
- 마스터 판정: 통과 (2026-09-28, 원본 5장 검토 뒤 "좋아")
- 썸네일: `measurements/photoreal-portrait-r3.jpg`
- 교훈: 인물 명세(국적·연령·복장)를 절 단위로 적으면 그대로 나온다. 0.157 에서도 r1·r2 품질 유지.

### r2 — 2026-06-13 (codex-cli 0.137.0) — 표정 변형 검증 (마스터 요청)

- 슬롯: r1 과 동일 인물 명세 + "warm genuine laugh, eyes slightly crinkled, head tilted
  a little, candid and natural — not exaggerated"
- 결과: 1024×1536 ✅
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅ C5 ✅ C6 ✅ / P1 ✅ P2 ✅ P3 ✅(웃음 치아 자연스러움)
- 썸네일: `measurements/photoreal-portrait-r2.jpg` (r1 차분한 표정과 비교)
- 교훈: **표정 슬롯 변형 성공** — 동일 명세 재사용으로 "같은 사람 느낌"을 유지하며
  표정만 전환. 단 텍스트 명세만으로는 완전 동일 인물 보장이 아님(유사 수준) —
  엄밀한 동일 인물 시리즈는 참조 이미지 입력 가설(`_PATTERNS.md` §5) 검증 후 가능.
  표정 어휘 풀: calm confident / warm genuine laugh / soft thoughtful / candid mid-talk.

### r1 — 2026-06-13 (codex-cli 0.137.0)

- 슬롯: 가상 인물 "차분하고 자신감 있는 30대 초반 한국인 여성, 내추럴 메이크업, 차콜
  블레이저 + 화이트 톱" / 미니멀 스튜디오 창가 / soft window light from the left / Portrait 1024x1536
- 결과: 1024×1536 세로 ✅
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅ C5 ✅ C6 ✅ /
  P1 ✅(모공·잔결 살아있음, 왁스 인형 아님) P2 ✅(85mm f/1.8 다운 배경 분리·보케)
  P3 ✅(눈동자·치아 위화감 없음)
- 썸네일: `measurements/photoreal-portrait-r1.jpg`
- 교훈: Threads 렌즈 팁("카메라 기종 대신 렌즈 모델") + "natural skin texture preserved,
  do not over-retouch" 조합이 첫 시도에 통과 — 실사 케이스의 핵심 두 문구로 확정.
- **마스터 판정: 긍정** — "실사 느낌이라 괜찮은데, 다양한 표정이 가능했으면 함."
  → 동일 인물 명세 + 표정 슬롯 변형의 일관성·자연스러움 검증이 승격 조건(r2 예정).

## 실패 변형 (안티프롬프트)

(없음 — 실측과 함께 누적)
