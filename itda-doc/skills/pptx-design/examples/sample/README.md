# pptx-design 예제 덱 — 삼성전자 vs SK하이닉스 (Stripe DESIGN.md 적용)

pptx-design 스킬의 동작을 보여주는 정식 예제다. **콘텐츠·데이터는 고정(SSoT)**, **디자인만 변수**라는
SPEC-PPTX-DESIGN-001 의 핵심 원리를 그대로 보여준다 — 동일 `content.md` + `data.json` 에 다른
`design.md` 를 끼우면 같은 정보가 전혀 다른 룩으로 렌더된다.

## 입력 (SSoT)

| 파일 | 역할 |
|---|---|
| `content.md` | 슬라이드 콘텐츠 명세(11장 고정). **기본 pptx 스킬과 동일 콘텐츠 비교용으로 고정.** |
| `data.json` | 수치 데이터(차트/표/스탯 콜아웃). 모든 수치의 단일 출처. |
| `design.md` | 적용 DESIGN.md = **Stripe designspec**(gradient mesh · 단일 indigo CTA · deep navy ink · thin display + 음수 자간 · tabular numerics · pill · cream band). |

> ⚠️ `data.json` 의 수치는 디자인 렌더링 테스트용 **예시(illustrative)** 데이터다. 실제 투자 자문이 아니다.

## 산출

| 경로 | 내용 |
|---|---|
| `deck.pptx` | 11장 16:9 와이드 덱(생성물) |
| `assets/*.png` | matplotlib 차트(팔레트화) + Pillow gradient mesh 베이크 |

## 실행

```bash
# macOS/Linux — 반드시 저장소 루트에서 실행(deckkit import 경로 안정)
cd <저장소 루트>
python3 itda-doc/skills/pptx-design/examples/sample/gen.py

# Windows
cd C:\path\to\skills
py -3 itda-doc\skills\pptx-design\examples\sample\gen.py
```

## 검증 (HARD GATE)

```bash
# macOS/Linux
cd <저장소 루트>
python3 itda-doc/skills/pptx-design/scripts/verify.py \
  itda-doc/skills/pptx-design/examples/sample/deck.pptx \
  --tokens <(printf "삼성전자\n하이닉스\n목표주가\n") --ko "삼성전자,하이닉스"
```

HARD GATE = (경계이탈 + 퇴화도형 + 빈슬라이드 + 필수토큰누락) == 0 → PASS 시 exit 0.
검증 산출물(렌더 JPG · 주석 몽타주 PNG · JSON)은 `_verify/` 아래에 생성된다.

## 이 예제가 보여주는 패턴

- **deckkit 공개 API 전용** — 도형/텍스트/표/이미지 배치는 전부 `scripts/deckkit.py`(`rect`/`add_text`/
  `set_run_font`/`add_native_chart`/`blank_slide`/`set_bg`/`save_deck` 등)로 한다.
- **차트 두 갈래(superset)** — ① **S3 HBM 시장 규모 = `add_native_chart` 네이티브 편집 차트**(PowerPoint
  에서 수치 직접 편집 가능, REQ-003 시연). ② 나머지(매출/영업이익·주가 궤적 면적채움·점유율 스택·목표주가
  슬라이더) = matplotlib 팔레트 PNG(고디자인·편집 불가). 둘 다 indigo/navy/ruby(기본 파랑/주황 금지),
  음수 영업이익(2023 하이닉스 −7.7조)은 0 기준선 아래로 정확히.
- **gradient mesh = Pillow+numpy 베이크** — python-pptx 그라디언트 미지원 대응. 표지/콘텐츠 strip/dark
  결론 3종 mesh.
- **한글 안전(가드)** — `deckkit.kr_font_name()`(Noto Sans KR·Pretendard 우선, LibreOffice 또렷 고딕)으로
  통일. `set_run_font` 가드가 한글 run 의 비안전 폰트·음수 자간(design.md 의 thin display+음수 자간)을
  자동 교정 → 또렷한 굵은 고딕 렌더.
- **레이아웃 다양화** — 표지/스탯 콜아웃/포인트+차트/풀폭 차트/도형 표/시나리오/리스크 그리드/dark 결론을
  11장 내내 다르게 구성(같은 레이아웃 반복 금지).
