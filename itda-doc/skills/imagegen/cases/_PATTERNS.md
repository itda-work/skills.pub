# 수집 프롬프트 패턴 종합 (Threads + 웹, 2026-06-13)

Threads 소셜 미디어에서 바이럴·검증된 이미지 생성 프롬프트 사례를 수집·종합한 어휘집.
모든 카드 템플릿은 이 패턴 위에서 작성한다. 수집 경위: #329 — r1 자작 프롬프트의
품질이 마스터 기준 미달("조명·분위기·기술스펙 층 부재"가 원인 진단).

## 1. 5층 공식 (구조)

```
[주제/피사체] + [스타일] + [세부묘사] + [조명/분위기] + [기술스펙]
```

r1 자작 프롬프트는 1~3층만 있었다. **4·5층(조명/분위기·기술스펙)이 체감 품질을 가른다.**
출처: tloghost 나노바나나 40선 공식, pxz.ai 바이럴 프롬프트 공통 구조.

## 2. 어휘집 (층별)

### 조명 (4층)
`soft morning sunlight` · `golden hour` · `dramatic side lighting` · `volumetric lighting`
· `cinematic lighting` · `studio-quality lighting, soft fill light` · `rim lighting`
· `stark cinematic lighting and intense contrast`

### 분위기 (4층)
`cinematic` · `moody` · `dreamy` · `nostalgic` · `whimsical atmosphere` · `cozy`

### 렌즈/카메라 (5층 — 실사 계열)
- **카메라 기종보다 렌즈 모델을 명시하라** — Threads 실측 팁
  (threads.com/@baene.studio/post/DOYNaZoE6uG)
- `85mm lens, f/1.8` (인물) · `50mm lens` (스트릿) · `35mm film aesthetic` (시네마틱)
- `shallow depth of field` · `macro` · `motion blur` (배경만)

### 재질/렌더 (5층)
`octane render` · `glossy material` · `clay material` · `film grain` · `hyper-realistic`
· `highly detailed` · `8k resolution` · `soft cel shading`

### 진정성 (실사 계열 필수)
`natural skin texture preserved` · `authentic` — 피부를 인형처럼 뭉개는 과보정 차단.

## 3. 스타일 군집 완성형 (복붙 가능)

| 군집 | 원문 | 출처 |
|---|---|---|
| 지브리풍 | `Studio Ghibli style, anime aesthetic, soft lighting, whimsical atmosphere, painterly background, highly detailed, hand-drawn look, fantasy vibe, gentle color palette, cinematic composition` | threads.com/@ai_tool_dog/post/DH9p4kOzkLu |
| 픽사 3D | `3D Pixar-style character, smooth polished rendering, soft lighting, slightly exaggerated expressive features, warm atmosphere, professional animation-quality lighting` | pxz.ai 바이럴 모음 |
| 상품화 피규어 | `1/7 scale commercialized figure of the character, in a realistic style and environment` + `스튜디오 촬영처럼 배경은 깨끗하고, 피규어의 질감과 디테일이 살아있도록` | fotor 나노바나나 모음 + threads.com/@ai.mr.ha/post/DN-dpfhE2rQ |
| 액션 피규어+패키지 | 전신 액션 피겨 + 상징 소품 + 패키지 박스 구성, "현실감 있게 시각화" | threads.com/@choi.openai/post/DH3Xnpyv_me |
| 시네마틱 인물 | `hyper-realistic neo-noir portrait, deep blue and magenta neon lighting, high contrast, cinematic photography, 9:16 vertical format` | pxz.ai |
| 글로시 3D 아이콘 | 명상앱 아이콘류: `glossy 3D icon, gradient, studio lighting` | tloghost 로고 카테고리 |
| 빈티지 필름 | `vintage analog film photograph 1970s-80s, Kodak film characteristics, warm tones, subtle light leaks, vignetting, natural film grain` | pxz.ai |

## 4. 메타 기법 (Threads 실전 팁)

1. **역프롬프팅** — 마음에 드는 레퍼런스 이미지를 멀티모달 모델에 첨부하고
   "이 이미지를 프롬프트로 그대로 묘사해줘" → 전문 프롬프트로 재구성받아 그대로 생성.
   디테일 어휘가 자동으로 풍부해짐. (threads.com/@aitrendmaster/post/DRLeoRik07u)
   → 이 스킬에서는 **Claude 가 그 변환기 역할**: 사용자가 레퍼런스를 주면 Read 로 보고
   5층 공식으로 묘사문을 작성한 뒤 `agent_run` 에 전달.
2. **2단계 프롬프트 생성기** — 캐릭터/장면 설명을 먼저 "이미지 생성 최적화 프롬프트로
   변환"시킨 후 생성. (threads.com/@ai__frontier/post/DH0xUgcSVLp)
   → 카드 템플릿의 슬롯 채우기가 곧 이 단계다. 슬롯을 한 단어로 채우지 말 것 —
   세부묘사 층은 절(clause) 단위로.

## 4.5 마스터 취향 프로필 (판정 누적 — 라우팅 기본값에 직결)

r2 판정(2026-06-13)에서 도출. 새 판정이 나올 때마다 갱신한다.

- **실사 > 일러스트/렌더**: 일러스트·아이소메트릭·3D 렌더는 완성도가 높아도
  "컴퓨터 그래픽 느낌 = 효용 낮음". 콘텐츠 이미지는 photorealistic 이 기본값.
- **표정은 미세하게**: "eyes wide with excitement" 류 과장 표정 = "AI 생성 느낌".
  `subtle, candid, natural expression — not exaggerated` 가 표준 문구.
- **다양성 요구**: 한 케이스당 단일 모범답안이 아니라 변형(표정·장면·구도) 풀을 원함.

## 5. 미검증 가설 (실측 대기)

- ~~**이미지 내 텍스트**~~ → **검증 완료 (2026-06-13, poster r1+r3)**: codex
  `image_generation` 텍스트 렌더링이 영문·한글 모두 철자 정확. **안전 범위 = 한글 4줄
  정보 블록(콜론·숫자·괄호) / 영문 3줄 단락까지**(r3, 임계 미발견). 구 "거의 깨짐" 가정 폐기.
  경로 B 권장 사유는 길이가 아니라 **통제 필요도**(폰트·오차0 계약·다버전). 미검증 잔여:
  영문 50단어+·한글 6줄+ 초장문, 폰트 종류 지정력.
- ~~**참조 이미지 입력**~~ → **검증 완료 (2026-06-13, product-catalog r2)**:
  이미지 첨부(당시 `codex exec -i`, 지금은 `agent_run` 의 `inputs`) + "첨부 이미지와 동일한 제품을 …" 지시로
  image_generation 이 참조를 반영함. 재질·구성·색 충실, 실루엣 비례는 다소 변형
  (중간~높은 충실도), 출력 해상도가 비정형(1122×1402)이 될 수 있음.
  → 스타일 변환(지브리화·피규어화) 케이스 신설 가능, 멀티앵글 세트의 앵커 컷 방식 권장.

## 6. Threads 트렌드 스냅샷 (2026-06-13 조사)

어떤 이미지 생성이 많은가 — 바이럴 강도순. 핵심 발견: **상위 트렌드 대부분이
"내 사진 업로드 + 변환"형**(텍스트 단독 생성이 아님) → 참조 입력 경로(`agent_run` 의 `inputs`, §5 검증 완료)가
트렌드 대응의 전제.

| 순위 | 트렌드 | 형태 | 우리 카드 커버리지 |
|---|---|---|---|
| 1 | 피규어화/토이화 (액션피규어+박스, Funko, Chibi) | 사진→변환 | `figurine`(텍스트형만 실측) — 사진 변환·박스 연출 미실측 |
| 2 | 폴라로이드 합성 (연예인/어린 시절 나/가족) | 사진→변환 | 미커버. 실존 인물 합성은 초상권 게이트 필요 — 본인 사진 한정 |
| 3 | 증명사진/프로 헤드샷 (한국 강세 — 취준·이력서) | 사진→변환 | `photoreal-portrait`(verified) 인접 — 규격/복장 교체 변형 후보 |
| 4 | 지브리풍/픽사풍 스타일 변환 | 사진→변환 | 미커버 — style-transfer 케이스 후보 (§3 군집 원문 보유) |
| 5 | 감성 낙서 데코 (흰 펜 손그림+한글 손글씨, 3:4) | 사진→변환 | 미커버. 한국 최신 (threads.com/@jinslei/post/DXqZRMpCTHd) |
| 6 | 유튜브/블로그 썸네일 (텍스트 유/무 2버전) | 텍스트 생성 | `blog-hero`·`video-illust` 인접 — 썸네일 전용 변형 후보 |
| 7 | 광고·마케팅·인포그래픽·컨셉아트 모음 | 텍스트 생성 | `product-catalog`·`slide-visual` 부분 커버 |

메타 기법 진화: **JSON 역프롬프팅** — 레퍼런스 이미지의 카메라·조명·색감·텍스처·레이어
구성까지 JSON 으로 추출 → 일부 수정 → 재생성 (threads.com/@choi.openai/post/DRuFdr_j3AX).
§4 역프롬프팅의 고도화판으로, 반복 재생성·시리즈 제작에 유리.
Google 공식 Gemini 가이드(문장형 서술 + 사진 용어 — threads.com/@ai.vibe.code/post/DN4YMxDEz0L)는
우리 5층 공식과 일치(외부 교차검증).

## History

- 2026-06-13: 초안. Threads 포스트 6건 + 모음 페이지 3종(tloghost·fotor·pxz) 수집 종합 (#329).
- 2026-06-13: §4.5 마스터 취향 프로필(r2 판정) · §5 참조 입력 가설 검증 완료 표기 · §6 트렌드 스냅샷 추가.
