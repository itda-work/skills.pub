# 포스터 (poster)

상태: verified — 한글 제목 행사 포스터(A, 짧은 문구 베이킹) 기준 (마스터 판정 통과 2026-09-28, r4). 긴 카피·영화·타이포·빈 존 변형은 Claude 1차 통과 뒤 마스터 판정 대기 draft
최종 실측: 2026-09-28 (codex-cli 0.157.0)

## 용도

영화/이벤트/홍보/타이포 포스터. "포스터 만들어줘", "행사 포스터", "영화 포스터풍" 류 요청.
**이 케이스만 공통 품질 하한의 "no text" 규칙에서 예외다** — 포스터는 제목·태그라인이
본질이기 때문. 단, 텍스트 렌더링은 모델 능력에 종속되므로 두 경로를 분기한다:

- **경로 A (텍스트 베이킹)**: 모델이 직접 글자를 그린다. 철자 정확도는 **영문·한글 모두
  높다** — 실측 안전 범위는 한글 4줄 정보 블록(콜론·숫자·괄호 포함) / 영문 3줄 단락까지
  (r3). 빠르고 텍스트가 디자인에 녹아든다.
- **경로 B (타이틀 존 비우기)**: 글자 자리를 비워 두고 레이아웃만 생성 → 문구는 후가공
  (imagekit·사용자 디자인 툴)으로 얹는다. 폰트·자간·문구를 완전 통제.

판단 (r3 실측으로 개정): **분기 기준은 길이가 아니라 "통제 필요도"다.**
- **경로 A** — 제목·부제·행사 정보(일시/장소/가격)처럼 정보 전달이 목적이고 약간의 서체
  변동이 무방하면 베이킹이 1차. 한글 다줄도 정확(r3).
- **경로 B** — ① 특정 폰트/정확한 자간·행간이 필요, ② 법적 고지·정확 브랜드 표기처럼
  **오차 0이 계약**, ③ 같은 레이아웃으로 여러 버전을 찍어야 할 때. (재생성마다 배치가 달라짐)
- 테스트 범위 초과(영문 50단어+·한글 6줄+)는 미검증 — 그 분량이면 B 권장. A 결과에
  드물게 오타가 나오면 재생성 또는 B 폴백.

## 스타일 자동 제안 (사용자가 스타일을 지정하지 않을 때)

포스터는 같은 주제라도 스타일이 효과를 좌우한다. 사용자가 스타일을 명시하지 않으면
**에이전트가 내용·의도를 읽어 스타일을 제안**한다. 사용자 명시 스타일은 항상 우선.

### 제안 프로토콜 (4단계)

1. **의도 신호 추출** — 요청에서 4축을 읽는다:
   - **장르**: 영화 / 음악·공연 / 전시·문화 / 캠페인·공익 / 제품·세일 / 채용·기업 / 행사·축제
   - **감정 톤**: 진지·서사 / 우아·고급 / 향수·레트로 / 긴박·강렬 / 유쾌·경쾌 / 차분·신뢰
   - **청중**: 대중 / 전문가·B2B / 청년·서브컬처 / 가족·아동
   - **행동 목표**: 관람 유도 / 구매 / 참여·인식 제고 / 지원·신청
2. **스타일 매핑** — 아래 표로 후보 1~3개를 근거와 함께 도출.
3. **제안 or 자동 선택** — 사용자가 "알아서/추천해줘"면 1순위 자동 채택, 그 외엔
   "이 내용엔 A(근거)/B(근거) 스타일이 어울립니다. 어느 쪽?" 한 줄 제안 후 진행.
4. **5층 공식으로 베이킹** — 선택 스타일을 `{스타일}` 슬롯 + 조명/분위기 층에 풀어 넣는다.

### 의도 → 스타일 매핑

| 스타일 군집 | 신호 (장르·톤·청중) | 스타일 문구(슬롯 주입용) |
|---|---|---|
| **시네마틱** | 영화·서사, 진지/긴박, 대중 | `dramatic cinematic photography, moody lighting, high contrast, teal-orange grade, depth of field` |
| **스위스/타이포 미니멀** | 전시·기업·채용, 차분/신뢰, 전문가 | `Swiss international typographic style, strong grid, bold sans-serif, generous negative space, flat, 1~2 colors` |
| **빈티지/레트로** | 음악·문화·축제, 향수, 대중 | `vintage retro poster, screenprint texture, warm muted palette, mid-century / 90s aesthetic, halftone` |
| **볼드 플랫 그래픽(공익·선동)** | 캠페인·공익, 강렬, 대중 | `bold flat graphic propaganda-poster style, limited high-contrast palette, strong silhouette, stencil shapes` |
| **에디토리얼 엘레강스** | 제품·패션·럭셔리·클래식, 우아/고급 | `elegant editorial design, refined minimal, soft premium lighting, sophisticated muted palette, fine serif accents` |
| **플레이풀 일러스트** | 아동·가족·캐주얼 행사, 유쾌 | `playful flat illustration, rounded shapes, bright cheerful palette, friendly hand-drawn feel` |
| **그런지/펑크** | 인디·록·청년 서브컬처, 강렬/반항 | `gritty grunge punk poster, distressed textures, photocopy zine aesthetic, raw high-energy collage` |

복수 신호가 충돌하면(예: 고급 + 음악) 1순위·2순위로 제안하고 사용자가 고르게 한다.
표에 없는 의도는 가장 가까운 군집을 변형하되 근거를 실측 기록에 남긴다.

## 프롬프트 템플릿

**프롬프트 A. 텍스트 베이킹 — 짧은 문구, 영문·한글 (한글 4줄·영문 3줄까지 실측)**

```
A {cinematic movie|event|promotional} poster about {주제}.
{스타일 — 예: dramatic cinematic photography / bold graphic design}.
Hero subject: {피사체 — 절 단위}, dramatic composition.
Lighting & mood: {조명/분위기 — 예: moody backlit, high contrast, teal-orange grade}.
The {Korean |}title text "{제목}" rendered in bold clean sans-serif
at the {bottom|top} center, perfectly spelled, crisp legible lettering.
{보조 문구 — 예: and a smaller second line "{날짜·장소}" below it, perfectly spelled. 없으면 이 줄을 뺀다}
Portrait 1024x1536, poster layout with margins. No watermark.
```

**프롬프트 B. 타이틀 존 비우기 — 기본 권장**

```
A {cinematic movie|event|promotional} poster layout about {주제}, WITHOUT any text.
{스타일}. Hero subject: {피사체 — 절 단위}, dramatic composition positioned in the
{upper|center} area. Lighting & mood: {조명/분위기}.
Leave the {bottom third} as a clean, calm, uncluttered area reserved for a title
to be added later (smooth gradient or simple backdrop, no text, no lettering).
Portrait 1024x1536, poster layout with margins. No text, no letters, no watermark.
```

슬롯: `{주제}` `{스타일}` `{피사체}` `{조명/분위기}` `{제목 — 영문 1~3단어 또는 한글 짧은 구}` `{날짜·장소}`.
한글 제목이면 "The Korean title text" 로 쓴다. 채운 예(r4 verified): `The Korean title text "봄꽃 축제" rendered in bold clean sans-serif at the bottom center, perfectly spelled, crisp legible lettering, and a smaller second line "4월 5일 – 4월 7일" below it, perfectly spelled.`
포스터 비율: 영화 2:3(≈1024x1536) 기본, 와이드 행사물은 가로 1536x1024 도 가능.

## 품질 체크리스트

공통 C1~C6 (`_SCHEMA.md`) — **단 C2(텍스트 아티팩트 없음)는 경로 A 에서 비적용**
(텍스트가 의도된 요소). 대신 아래 W 항목으로 대체 평가. +

| # | 항목 | 판정 기준 |
|---|---|---|
| W1 (A) | 철자 정확 | 베이킹한 제목의 철자·자간이 정확한가 (오타·깨짐 0) |
| W2 (A) | 가독성 | 글자가 또렷하고 배경과 충분히 분리되는가 |
| W1 (B) | 타이틀 존 | 하단(또는 지정부)이 글자 얹기 좋게 실제로 비어 있는가 |
| PO1 | 포스터다움 | 히어로 피사체·여백·구도가 "포스터"로 읽히는가 (스냅샷 아님) |
| PO2 | 비율 | 세로 포스터 비율(2:3 근사)이 나왔는가 |

## 실측 기록

### r4 — 2026-09-28 (codex-cli 0.157.0) — itda-hyve `agent_run` 경로 첫 실측 (5장 한 번에, 임시 격리 홈)

- 프롬프트 전문:

```
An event poster about a spring cherry blossom festival in a Korean city park.
Bold graphic design with soft photographic background.
Hero subject: a winding park path under full-bloom cherry trees with petals drifting in the air, dramatic composition in the upper area.
Lighting & mood: bright warm spring afternoon, soft pink and fresh green palette, gentle backlight on the petals.
The Korean title text "봄꽃 축제" rendered in bold clean sans-serif at the bottom center, perfectly spelled, crisp legible lettering, and a smaller second line "4월 5일 – 4월 7일" below it, perfectly spelled.
Portrait 1024x1536, poster layout with margins. No watermark.
```

- 경로: `agent_run`(recipe `codex.imagegen`, `wait_sec: 0`) 5건을 한꺼번에 넣고 `job_status` 로 회수. 계정당 3개 동시 — 3건 동시 시작, 2건 `queued` 뒤 앞 작업이 끝나며 시작. 5건 모두 `completed`, 장당 결과 1개.
- 토큰(장당): 입력 약 2.1만(캐시 약 9천)·출력 230~360.
- 결과: 1024×1536 ✅, 176초 = 대기열 92초 + codex 실행 84초
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅(위쪽 벚꽃길 히어로, 아래 연분홍 면에 글자) C5 ✅ C6 ✅ / W1 ✅ **"봄꽃 축제"·"4월 5일 – 4월 7일" 한 글자도 틀리지 않음**(겹받침 "꽃" 포함, 엔대시 유지) W2 ✅
- 마스터 판정: 통과 (2026-09-28, 원본 5장 검토 뒤 "좋아")
- 썸네일: `measurements/poster-event-kr-r4.jpg`
- 교훈: 한글 2줄(제목+날짜)은 0.157 에서도 정확하다. 제목을 짙은 초록으로 골라 팔레트와 맞췄다 — 색을 지정하지 않아도 배경과 대비를 잡는다.

### r3 — 2026-06-13 (codex-cli 0.137.0) — 긴 카피·한글 장문 베이킹 한계 검증 (5장, #343)

**검증 설계: 난이도 점증 5종으로 베이킹(경로 A)이 깨지는 임계 탐색. 결과 — 테스트 범위
전 구간 철자 0오류, 임계 미발견. 베이킹 안전 한계가 가정보다 훨씬 높음.**

| # | 부하 | 내용 | 결과 |
|---|---|---|---|
| 1 | 영문 3블록 | `BLUE NOTE NIGHTS` + `Live Jazz Every Friday` + `8 PM — Downtown Hall — Free Entry` | ✅ 3줄 전부 정확, 빈티지 스크린프린트 |
| 2 | 한글 2줄 | `서울 여름 음악 축제` + `6월 20일 한강공원` | ✅ 자모·숫자 정확 |
| 3 | 한글 1문장 | `음악이 흐르는 가을밤, 당신을 초대합니다` (쉼표 포함 16자) | ✅ 문장·쉼표 정확 |
| 4 | **한글 4줄 정보 블록** | `동네 플리마켓` + `일시: 6월 28일 토요일 오전 10시` + `장소: 행복아파트 중앙광장` + `참가비: 무료 (누구나 환영)` | ✅ **콜론·숫자·괄호 포함 4줄 전부 정확** — 최고 난이도 통과 |
| 5 | 영문 단락 | `WORK SMARTER` + 3줄 단락(약 24단어) | ✅ 헤드라인+단락 전부 정확 |

- 썸네일: `measurements/text-{1-en-multi,2-kr-2line,3-kr-sentence,4-kr-info,5-en-paragraph}.jpg`
- 비율 1024×1536 5/5.
- 교훈:
  - **베이킹(경로 A) 안전 범위 = 한글 4줄 정보 블록 / 영문 3줄 단락까지 확인.** 깨짐 임계는
    이 범위 너머라 미발견 → "긴 카피·한글 장문은 깨진다"는 r1 잔여 가설을 사실상 폐기.
  - **단, 경로 B 권장 사유는 "깨짐"에서 "통제"로 이동**: 철자는 정확해도 (a) 폰트 종류·
    정확한 자간/행간을 지정 못 하고, (b) 재생성마다 레이아웃이 달라지며, (c) 법적 고지·
    정확 브랜드 표기처럼 **오차 0이 계약인 텍스트**는 후가공이 안전. 길이가 아니라 **통제
    필요도**가 A/B 분기 기준.
  - 테스트 범위 초과(영문 50단어+·한글 6줄+)는 여전히 미검증 — 실무 포스터 정보량은
    대부분 범위 안.

### r2 — 2026-06-13 (codex-cli 0.137.0) — 스타일 자동 제안 검증 (5장 병렬, #337)

**검증 설계: 스타일을 지정하지 않은 주제 5종을 제안 프로토콜대로 추론 → 서로 다른 군집으로
매핑되는지 + 결과가 의도에 맞는지.** 전부 의도-적합 + 군집 5/5 별개 = 추론 레이어 작동 확인.

| 주제 | 추론 의도 신호 | 선택 군집 | 결과 (제목) | 판정 |
|---|---|---|---|---|
| 해양 플라스틱 캠페인 | 공익·강렬·대중·인식제고 | 볼드 플랫(선동) | `PROTECT THE BLUE` | ✅ 스크린프린트·강한 실루엣, 활동가 포스터다움 |
| 클래식 피아노 리사이틀 | 공연·우아/고급·전문가 | 에디토리얼 엘레강스 | `NOCTURNE` | ✅ 스포트라이트 그랜드피아노·세리프, 고급감 |
| 인디 록 페스티벌 | 음악·반항·청년 | 그런지/펑크 | `NOISE FEST` | ✅ 찢긴 콜라주·네온핑크·zine 질감 |
| 스타트업 개발자 채용 | 기업·신뢰·B2B | 스위스/타이포 | `BUILD WITH US` | ✅ 그리드·볼드 그로테스크·커서 모티프 |
| 여름 호러 영화 | 영화·긴박·대중 | 시네마틱 | `THE HOLLOW` | ✅ 안개 복도·핏빛 세리프, 스릴러다움 |

- 모든 제목 텍스트 철자 0오류(영문 5/5). 비율 1024×1536 5/5.
- 썸네일: `measurements/style-{eco,classic,indie,hiring,horror}-r1.jpg`
- 교훈: **의도→스타일 매핑표가 실측으로 작동.** 동일 "포스터" 요청이 내용에 따라 선동/
  엘레강스/펑크/스위스/시네마틱으로 정확히 갈림 — 사용자가 스타일을 지정하지 않아도
  내용 적합 다양성 산출. 마스터 취향(실사 우선)은 인물 콘텐츠 한정이고, 포스터는
  장르 관습이 우선(호러=시네마틱 실사풍, 캠페인=그래픽)임을 확인.

### r1 — 2026-06-13 (codex-cli 0.137.0) — 텍스트 렌더링 능력 검증 (5장 병렬)

**핵심 발견: codex `image_generation` 의 텍스트 렌더링이 영문·한글 모두 정확.**
구 스킬·`_PATTERNS.md` §5 의 "글자 거의 항상 깨짐" 가정을 실측으로 폐기.

- **영문 베이킹** `THE LAST SIGNAL` (영화 포스터): 1024×1536 ✅. 철자·자간 완벽,
  볼드 산세리프, 우주비행사+성운 히어로 구도. W1 ✅ W2 ✅ PO1 ✅ PO2 ✅.
- **한글 베이킹** `서울 재즈 페스티벌` (재즈 페스티벌): 1024×1536 ✅. **한글 자모 깨짐 0,
  띄어쓰기 정확.** 색소폰 실루엣+레트로 팔레트+남산타워. W1 ✅ W2 ✅ — 가장 놀라운 결과.
- **타이포그래피** `FORM` (전시 포스터): 1024×1536 ✅. 스위스 인터내셔널 스타일,
  거대 지오메트릭 산세리프 완벽, 하단 자막 자리 플레이스홀더 바. W1 ✅ W2 ✅ PO1 ✅.
- **빈 존(B)** (우주비행사, 글자 없이): 1024×1536 ✅. 하단 1/3 다크 그래디언트로 깔끔히
  비움 — 후가공 타이틀 오버레이 최적. W1(B) ✅ PO1 ✅. C2 ✅(글자 0).
- **제품 포스터(B)** (텀블러 런칭): 1024×1536 ✅. 부유 그림자+밝은 베이지, 하단 헤드라인
  존 확보. product-catalog 연계 확인. W1(B) ✅ PO1 ✅.
- 썸네일: `measurements/poster-{movie-en,event-kr,typographic,empty-zone,product}-r1.jpg`
- 비율: 세로 1024×1536 5/5 정확.
- 교훈:
  - **"no text" 하한 규칙 재정의 필요** → SKILL.md 개정. 텍스트는 이제 "거의 깨짐"이
    아니라 "짧은 1줄은 신뢰 가능(영/한)". no-text 는 *원치 않는* 글자 차단용 기본값일 뿐.
  - 베이킹 강점은 **짧은 단일 문구**. 긴 카피·정확 브랜드명·서체 통제는 미검증 → B 권장.

## 실패 변형 (안티프롬프트)

(없음 — r1 5/5 통과. 다음 검증 후보: 긴 카피·다중 문구 베이킹 한계, 한글 장문 깨짐 임계)
