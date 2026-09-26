# 웹 DESIGN.md → PPTX 디자인 토큰 매핑 가이드

웹 UI 용으로 쓰인 DESIGN.md(awesome-design-md 등)의 토큰을 정적 PPTX 로 옮기는 방법, 그리고 **무엇이 잘 넘어오고 무엇이 구조적으로 막히는가**를 정리한다.
근거: 7개 DESIGN.md 적용 실험(claude·binance·stripe·tesla·wired·spotify·nintendo-2001)의 천장 규칙·한계 카탈로그·덱별 한계(원문 실험 디렉토리 `out-pptx-design/`은 폐기 — 결과는 본 문서 §1~§3 에 전부 흡수됨).

> **천장 규칙(한 줄)**: 정체성이 **색·레이아웃·평면 기하**에 살면 높은 재현(80~88%), **폰트·사진·모션**에 살면 한계가 있다. **시각 복잡도 자체는 장애물이 아니다** — Y2K 크롬(nintendo)이 충실도 1위, "깔끔한 미니멀"(tesla, 사진 의존)이 꼴찌였다. 재현도를 가르는 건 "정체성이 무엇으로 만들어졌나"다.

DESIGN.md 미제공 시 §3 의 내장 추천 팔레트 + `anthropic-pptx-design-ideas.md`(기본 스킬 흡수, 1급 경로) 중 주제 적합 1종을 선택한다(REQ-002).

> **3열 필터 원칙(SPEC-PPTX-DESIGN-002 REQ-004)**: 각 토큰을 **① pptx 적용(라틴/일반)** · **② 한글 적용** · **③ 필터(불가·금지)** 세 축으로 분리해 읽는다. 특히 `letterSpacing(음수)`·`fontWeight(thin)`·`serif display` 는 **한글=필터**(자동 차단)다 — 웹 타이포를 한글에 문자 그대로 적용하면 LibreOffice 가 자간 벌어진 명조/붓글씨로 폴백한다. `deckkit.set_run_font` 의 한글 가드가 이 셋을 **자동으로 안전화**한다.
>
> **'① 적용 ✅'의 의미 (#701 정정)**: '적용 ✅'는 *재현 가능*을 뜻하지 *어댑터의 토큰 자동 소비*가 아니다. 그중 **`layout.three_zone`·`layout.grid`·`space` 만 P0 부터 `to_pptx_layout()`→deckkit `zone_bounds`/`grid_cells` 로 토큰을 자동 소비**하고, 색·타이포 등 나머지는 Claude 가 gen.py 에서 값을 읽어 손으로 적용한다. 둘을 혼동하지 말 것.

---

## 1. 토큰 매핑 표 (DESIGN.md 토큰 → PPTX 3열 필터)

`scripts/deckkit.py` 헬퍼 기준(`dk` = deckkit). 자세한 코드는 `references/pptx-toolkit.md`.

| DESIGN.md 토큰 | ① pptx 적용 (라틴/일반) | ② 한글 적용 | ③ 필터(불가/금지) |
|---|---|---|---|
| **colors.* (hex)** | `dk.set_bg`·`dk.rect(fill=)`·`set_run_font(color=)`·차트 `palette=[hex]` 에 **hex 1:1** ✅ | 동일(색은 글자 언어 무관) ✅ | — |
| **typography.fontFamily (디스플레이)** | 시스템 근접 라틴(Georgia/Impact/Arial Black/Helvetica Neue/Palatino)을 **영문/숫자 run** 에 ⚠️폴백 | **항상 `dk.kr_font_name()` 안전 고딕**. 라틴 디스플레이 지정 시 가드가 자동 교체 | ▣ **세리프/thin 디스플레이를 한글 run 에 = 필터**(가드가 강제 교체). 독점 서체 = 불가 |
| **typography.fontWeight (300/600)** | regular/bold 2단계(`bold=True/False`) ⚠️ | 동일 2단계 | ▣ **thin(300)을 한글에 = 필터**(명조 폴백 유발). semibold·가변축 = 불가 |
| **typography.fontSize (px)** | pt 환산(타이틀 36~48·본문 14~18·캡션 10~12) ✅ | 동일 ✅ | — |
| **typography.letterSpacing (음수)** | 라틴 run 은 `spacing=음수pt` 허용(약하게 적용) ⚠️ | ▣ **음수 자간 한글 = 필터** → 가드가 **0 으로 클램프**(LibreOffice 에서 음수가 오히려 자간을 벌림) | ▣ 과대 양수도 캡(`KR_SPACING_CAP_PT`) |
| **typography.fontFeature (tnum/ss01)** | — | — | ▣ OpenType 기능 적용 불가 |
| **rounded / radius (px)** | `dk.rect(shape=ROUNDED_RECTANGLE, radius=비율 0~0.5)`. pill=0.5 ⚠️근사 | 동일 | ▣ 4/8/12/16px 위계 1:1 불가(비율 기반) |
| **spacing / layout(three_zone·grid) / surface** | 인치 좌표 충실 ✅ — **P0(#701)부터 `to_pptx_layout()`→deckkit `zone_bounds`/`grid_cells` 로 어댑터가 토큰 자동 소비**(종전엔 gen.py 손 재현만) | 동일 ✅ | — |
| **motif (반복 시각 요소)** | 도형(`dk.rect`)+Pillow PNG(`linear_gradient`/`radial_glow`/numpy) ✅ | 동일 ✅ | ▣ 벡터 아님(래스터 베이크) |
| **gradient / glow / blur** | Pillow 고해상도 PNG 베이크(2667×1500) 풀블리드 ⚠️래스터 | 동일 | ▣ python-pptx 네이티브 그라디언트 fill 없음. 텍스트 위 그라디언트 불가 |
| **shadow / box-shadow** | `dk.rect` 기본 중화·의도 시 `shadow=True` ⚠️ | 동일 | ▣ soft box-shadow 네이티브 불가(Pillow blur 흉내) |
| **chart / data viz 색** | **권장: `dk.add_native_chart(palette=[hex])` 네이티브 편집 차트** ✅ / 고디자인: matplotlib PNG(편집 불가) ✅ | 네이티브 차트는 CJK 폰트 자동 주입(`font_name=kr_font_name()`) ✅ | ▣ **기본 matplotlib 파랑/주황 금지** |
| **motion / transition / hover** | — | — | ▣ 정적 포맷 표현 불가(이 스킬 범위 밖) |
| **photography (사진-as-정체성)** | 색면+여백 대체 ⚠️ | 동일 | ▣ 사진이 본질이면 대체 불가 |
| **do / don't** | 생성 규칙으로 반영(함정 체크리스트) ✅ | 동일 ✅ | — |

### 1.1 ★한글 타이포 필터 — 가드 자동 적용 (REQ-001 실측 근거)

SPEC-PPTX-DESIGN-002 §1 의 LibreOffice 폰트 렌더 실측 결과:

| 폰트 | LibreOffice 한글 렌더 | 판정 |
|---|---|---|
| **Noto Sans KR** · **Pretendard** | **또렷한 굵은 고딕** | ✅ 안전(기본 선택) |
| Apple SD Gothic Neo | 얇고 넓은 face | △ 가용 시 후순위 |
| **NanumGothic** | **자간 벌어진 얇은 명조풍 치환** | ✗ 후순위(구버전 결함 주범) |

→ `dk.kr_font_name()` 은 **Noto Sans KR · Pretendard 를 우선** 선택하도록 정렬됐다(`_KR_FONT_FILES`). 이것이 구버전 "표지 한글이 명조/붓글씨로 보이던" 결함의 **지배적 교정**이며, 음수 자간 클램프는 보조 교정이다.

`dk.set_run_font` 한글 가드(자동):
1. 한글 run 에 비-Korean-capable 폰트(Georgia·Impact·Helvetica Neue 등) → `kr_font_name()` 안전 고딕으로 **강제 교체**.
2. 한글 run 의 **음수 자간 → 0**, 과대 양수 → `KR_SPACING_CAP_PT(2.0)` 캡.
3. 라틴 전용 run 은 음수 자간·세리프 디스플레이 **그대로 허용**(DESIGN.md 정체성 보존).
4. `force=True` 로 우회 가능(고급 사용자가 의도적으로 적용할 때만).

`verify.py` 의 (D) 타이포 정적 검사가 한글 음수/과대 자간·비안전 폰트를 **advisory** 로 적발해 가드 우회·구버전 덱의 회귀를 감지한다.

---

## 2. 재현 잘됨 vs 한계 카탈로그 (REPORT.md §4·§5 교차)

### ✅ PPTX 로 잘 이식되는 것

1. **색 팔레트** — hex 1:1 재현. 가장 확실하게 넘어오는 토큰.
2. **레이아웃·그리드·surface 리듬·여백 스케일** — 크림↔다크 교차(claude), 풀폭/2분할/그리드 다양화 모두 충실.
3. **평면 색블록 디자인** — flat·no-atmosphere(binance)는 **손실 0**(PPTX 제약과 디자인이 오히려 합치).
4. **반복 시각 모티프** — 도형+Pillow PNG 로: 스파이크 마크, 베벨 플레이트·도트매트릭스, 마스트헤드, 진행바, 그라디언트 메시.
5. **차트 브랜드화** — matplotlib 로 팔레트·축·라벨·의미색(trading green/red)을 디자인 톤에 맞춰 렌더.

### ❌ PPTX 가 못 따라가는 것 (전 덱 공통 한계)

1. **독점 디스플레이 서체 = 1순위 손실** — Copernicus·Söhne·BinanceNova·Universal Sans·WiredDisplay·CircularSp·Arial Black 박스아트가 전부 대체 폰트로 폴백. 브랜드 타이포 정체성이 가장 크게 깎인다.
2. **음수 자간/미세 트래킹 미반영** — pptx `spc` 가 LibreOffice 에서 약하게만 적용. **em-dash(U+2014) 글리프가 통째로 드롭**되는 함정은 음수 자간 run(stripe)만이 아니라 **한글 인접 일반 run 에서도 실측**(2026-06-11) → en-dash(U+2013)·middle-dot 으로 교체.
3. **폰트 weight 축 붕괴** — 가변폰트 300(thin)·600(semibold)이 regular/bold 2단계로 뭉개짐(stripe·spotify·tesla). LibreOffice 가 일부를 다른 weight 로 렌더.
4. **한글 세리프/디스플레이 부재** — 세리프가 브랜드인 곳(claude·wired)에서 한글은 고딕 폴백 → 한 헤드라인에 "영문=세리프 / 한글=고딕" 이질 페어링. 한국어 덱 특유의 정체성 누수.
5. **그라디언트·blur·glow 네이티브 미지원** — python-pptx 에 그라디언트 fill 없음 → 전부 **Pillow 래스터 PNG 베이크**(벡터 아님, 확대 시 픽셀화, 텍스트 그라디언트 불가).
6. **그림자 양방향 문제** — LibreOffice 가 preset 도형 그림자를 강제 상속(deckkit `rect` 가 `effectLst` 비워 중화) + CSS soft box-shadow 는 네이티브로 못 냄(Pillow blur 흉내).
7. **둥근 모서리 px 토큰 부정확** — adjustments 가 비율 기반이라 4/8/12/16px px 위계를 1:1 못 맞춤.
8. **OpenType 기능 불가** — tnum(등폭 숫자)·ss01(stylistic set) 등 재무 데이터의 "조용한 신호" 미적용.
9. **인터랙션·모션 전무** — hover/transition/carousel(정적 포맷의 당연한 한계).
10. **사진-as-정체성 대체 불가** — tesla 최대 갭. 사진이 본질인 브랜드는 PPTX 에서 영혼이 빈다.
11. **(환경 특유) LibreOffice CJK 폰트 해석 비결정성 — ★REQ-006 으로 교정됨** — NanumGothic·Apple SD Gothic Neo 의 regular face 가 LibreOffice 에서 자간 벌어진 명조/붓글씨로 치환되는 버그. **`dk.kr_font_name()` 이 또렷한 굵은 고딕(Noto Sans KR·Pretendard)을 우선 선택**하도록 정렬해(`_KR_FONT_FILES`) 이 결함을 차단했다(SPEC-PPTX-DESIGN-002 §1 실측). 그래도 **PowerPoint 실제 렌더는 LibreOffice 프리뷰와 다를 수 있으므로** 중요 산출물은 PowerPoint 실물 검수를 권장.

### 충실도를 높이는 우회책 (REPORT.md §6 + SPEC-002 보강)

- **한글은 항상 `dk.kr_font_name()`(Noto Sans KR·Pretendard 우선) — 가드가 자동 강제**. 이것이 한글 가독성의 지배적 레버다(폰트 > 자간).
- 브랜드 폰트(또는 근접 대체 + **한글 동반 고딕**)를 시스템에 실제 설치하면 라틴 1순위 손실을 줄인다.
- 그라디언트·glow·베벨은 처음부터 Pillow 고해상도 PNG 로 베이크하는 전제로 설계(네이티브 fill 기대 금지).
- 표는 기본 PPTX 표 스타일을 피하고 **도형+텍스트로 직접** 그린다.
- 차트는 **편집 필요 시 `dk.add_native_chart`(네이티브 편집 객체)**, **고디자인/특수 시각 필요 시 matplotlib PNG**(편집 불가) 로 갈래를 나눈다.
- 세리프-정체성 브랜드의 한국어 덱은 "라틴 세리프 헤드 / 한글 고딕" 분리를 감수하고, **색·레이아웃으로 정체성을 보강**한다.
- 본 재현도는 LibreOffice 렌더 기준 — 중요한 산출물은 PowerPoint 실물 검수를 권장.

---

## 3. 내장 추천 팔레트 (DESIGN.md 없을 때 주제별 선택)

> **먼저 `../../design-core/library/` 를 확인하라** — 아래 팔레트 중 6종(컨설팅·트레이딩 다크·에디토리얼·신문·테크 다크·미니멀)은 슬라이드 문법 레시피까지 갖춘 **ready-to-use DESIGN.md 프리셋**으로 승격돼 있다(#303). 톤 키워드가 있으면 프리셋을 통째로 적용하는 쪽이 우선이고, 아래 표는 프리셋에 없는 톤을 조합할 때 쓴다.

DESIGN.md 미제공 시 주제 적합 1종을 골라 `dk.set_bg`·`dk.rect(fill=..)`·차트 색·`set_run_font(color=..)` 에 hex 를 그대로 쓴다. 모두 위 실험 7덱에서 게이트 통과한 검증 팔레트의 핵심 축이다.

| 팔레트 | 적합 주제 | 배경(canvas) | 잉크(text) | primary | accent / 보조 | 의미색(상승/하락) |
|---|---|---|---|---|---|---|
| **Warm Editorial** (claude 계열) | 리포트·에디토리얼·따뜻한 신뢰 | `faf9f5` 크림 / `181715` 다크 교차 | `141413` | `cc785c` 코랄 | `5db8a6` 틸 · `e8a55a` 앰버 | `5db872` / `c64545` |
| **Indigo Gradient** (stripe 계열) | 핀테크·인프라·SaaS | `ffffff` / `f6f9fc` | `0d253d` 네이비 | `533afd` 인디고 | `ea2261` 루비 · 그라디언트 메시(`1c1e54`→`0d253d`) | `5db872` / `ea2261` |
| **Trading Yellow/Black** (binance 계열) | 거래·금융 데이터·flat | `0b0e11` 블랙 / `ffffff` | `eaecef` / `1e2329` | `f0b90b` 옐로(희소 사용) | 단일 보이스 + mono 숫자 | `0ecb81` / `f6465d` |
| **Vivid Green Dark** (spotify 계열) | 미디어·테크·몰입형 다크 | `121212` 다크 + green glow(`radial_glow`) | `ffffff` / `b3b3b3` | `1ed760` 그린 | 기능적 그린·진행바 모티프 | `1ed760` / `e22134` |
| **Print Broadsheet** (wired 계열) | 저널·인쇄 감각·분석 | `f4f1ea` 페이퍼 / `ffffff` | `111111` 잉크 | `0047ab` 잉크블루(단일 액센트) | 헤어라인·마스트헤드 | `0047ab` / `c0392b` |
| **Cinematic Minimal** (tesla 계열) | 프리미엄·여백·거대 타이포 | `ffffff` 갤러리 / `0a0a0a` | `171a20` | `171a20` monochrome | `3e6ae1` 단일 액센트(+1) | 절제(거대 여백 위주) | `3e6ae1` / `e82127` |

> 선택 기준: 데이터·분석 리포트 → Warm Editorial / Print Broadsheet, 금융·거래 → Trading Yellow/Black / Indigo Gradient, 테크·미디어 → Vivid Green Dark, 프리미엄·제품 → Cinematic Minimal.
> 다크 팔레트는 차트 PNG 를 `transparent=True` 로 굽고 축/라벨을 밝은 톤으로(`references/pptx-toolkit.md` §4). green glow·그라디언트 배경은 Pillow 로 베이크해 맨 먼저 깐다.
