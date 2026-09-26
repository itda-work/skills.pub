# pptx-design — 기본 pptx 스킬 superset · DESIGN.md 적용 크로스플랫폼 PPTX 신규 생성

콘텐츠 명세(Markdown 아웃라인)와 수치 데이터(JSON/표)를 받아, 16:9 PowerPoint(.pptx)를 **macOS/Linux·헤드리스·Office 없이** 신규 생성하는 스킬입니다. Anthropic 기본 `pptx` 스킬의 **superset**(SPEC-PPTX-DESIGN-002): 기본 디자인 가이드(팔레트·타이포·레이아웃·QA)를 토대로 깔고, 그 위에 웹 **DESIGN.md** 토큰·한글 안전 타이포·네이티브 편집 차트·자동 검증 게이트를 추가합니다.

```
"이 콘텐츠로 stripe 디자인 PPTX 만들어줘" → 팔레트·차트·모티프가 적용된 .pptx + 3층+타이포 검증 통과
"발표자료 만들어줘"(DESIGN.md 없이)     → 기본 가이드 + 내장 팔레트로 동등 품질 덱
```

생성은 순수 Python(`python-pptx` + `matplotlib` + `Pillow`)으로 이뤄지며, 차트는 **네이티브 편집 객체(기본 권장)** 또는 디자인 팔레트 matplotlib PNG(고디자인·편집 불가)로, 그라디언트·glow·모티프 배경은 Pillow PNG로 베이크해 임베드합니다. **한글 텍스트는 자동 가드**가 LibreOffice 에서 또렷한 굵은 고딕(Noto Sans KR·Pretendard 우선)으로 보호합니다. 검증·썸네일만 LibreOffice(`soffice`) headless를 사용합니다.

---

## 무엇을 하는가

1. **신규 덱 생성** — 콘텐츠·데이터를 SSoT로 고정하고, 디자인만 변수로 두어 16:9 멀티 슬라이드 PPTX를 결정론적으로 생성합니다(난수 미사용, 동일 입력 → 동일 산출).
2. **DESIGN.md 적용** — awesome-design-md 류 웹 디자인 시스템의 토큰(colors·typography·rounded·spacing·motif·do/don't)을 해석해 팔레트·타이포·모티프·레이아웃에 반영합니다. DESIGN.md 미제공 시 내장 팔레트 중 주제에 맞는 1종을 선택합니다.
3. **3층 자동 검증** — 지오메트리(경계이탈·퇴화도형·겹침) + 콘텐츠 대조(필수 토큰 존재) + OCR 렌더 대조(산출률·한글 명칭)로 산출물을 검증합니다.

---

## 비목표

이 스킬은 macOS/Linux·헤드리스·배치 **신규 덱 생성** 전용입니다. 기존 브랜드 템플릿의 lossless 편집·병합, Windows PowerPoint 실물 충실도·실시간 시연·발표자 노트 같은 네이티브 의미 조작은 범위 밖입니다(python-pptx 라운드트립은 lossy). officecli 는 사용하지 않습니다(python-pptx 직접 생성).

---

## 설치

```bash
pip install -r requirements.txt
```

필수 의존성: `python-pptx`, `matplotlib`, `Pillow`, `numpy`. 인증키는 필요 없습니다(keyless).

> **재현성·폰트 의존(REQ-006)**: 본 스킬은 **시스템 한글 폰트**에 의존합니다. `deckkit.kr_font_name()` 이 결정론적 체인 **Noto Sans KR → Pretendard → Apple SD Gothic Neo → Malgun Gothic → NanumGothic** 순으로 존재하는 첫 폰트를 선택합니다(LibreOffice 에서 또렷한 굵은 고딕 우선 — 실측상 NanumGothic·Apple SD Gothic Neo 는 명조풍 치환이라 후순위). 권장 설치: macOS `Noto Sans KR` 또는 `Pretendard`, Linux `fonts-noto-cjk`. 또한 그라디언트·glow·모티프 배경은 **Pillow 래스터 PNG 로 베이크된 자산**(벡터 아님)이라 확대 시 픽셀화하며, 폰트가 다른 환경에서는 한글 렌더가 달라질 수 있습니다. 중요 산출물은 PowerPoint 실물 검수를 권장합니다.

선택(검증층 C — OCR): `pytesseract` + tesseract 바이너리(`kor+eng`). 미설치 시 OCR 층은 자동 스킵되고 advisory로만 동작합니다.

```bash
# macOS
brew install tesseract tesseract-lang
# Debian/Ubuntu
sudo apt install tesseract-ocr tesseract-ocr-kor
```

검증·썸네일용 렌더러(생성 자체엔 불필요): LibreOffice(`soffice`) + `pdftoppm`(poppler).

```bash
# macOS
brew install --cask libreoffice && brew install poppler
# Debian/Ubuntu
sudo apt install libreoffice poppler-utils
```

---

## 사용 흐름

1. **입력 준비** — 슬라이드 아웃라인(Markdown)과 수치 데이터(JSON/표)를 SSoT로 고정합니다.
2. **디자인 선택** — DESIGN.md를 제공하거나 내장 팔레트 중 주제 적합 1종을 선택합니다.
3. **생성** — per-invocation 생성 스크립트가 `scripts/deckkit.py`의 공개 헬퍼를 import해 .pptx를 만듭니다.
4. **검증(관문)** — `scripts/verify.py`로 3층 검증을 돌립니다.

```bash
# 생성물 검증 — HARD GATE = (경계이탈 + 퇴화도형 + 빈슬라이드 + 토큰누락) == 0
python3 scripts/verify.py deck.pptx --tokens tokens.txt --ko "삼성전자,SK하이닉스"

# 렌더/썸네일만 단독 실행(격리 프로파일, 병렬 안전)
python3 scripts/render.py deck.pptx out_render/
```

```powershell
# Windows
py -3 scripts/verify.py deck.pptx --tokens tokens.txt --ko "삼성전자,SK하이닉스"
```

**HARD GATE 통과(PASS, exit 0)** 가 산출 조건입니다. 텍스트 겹침·OCR 산출률은 advisory(트립와이어)로, 마지막 시각 QA는 렌더 이미지를 직접 확인해 보완합니다.

---

## DESIGN.md → PPTX 재현 한계

7개 DESIGN.md 적용 실험(claude·binance·stripe·tesla·wired·spotify·nintendo-2001)에서 도출한 천장 규칙입니다(원문 실험 디렉토리는 폐기 — 결과는 `references/design-md-mapping.md`에 흡수). 기본 pptx 스킬과의 동일 브리프 A/B 실측(2026-06-11, 기본 83.5 vs 본 스킬 90.0/100)은 저장소 개발 문서 `skills/docs/analysis-pptx-design-ab-compare/` 에 박제돼 있습니다.

- **잘 이식**: 색 팔레트(hex 1:1)·레이아웃/그리드/surface 리듬·평면 색블록·반복 모티프(도형+Pillow)·차트 팔레트화.
- **이식 한계**: 독점 디스플레이 서체(1순위 손실)·음수 자간·weight 축·한글 세리프 부재·그라디언트/blur/glow(래스터 베이크 필요)·그림자 양방향·px 라운드 정밀도·OpenType 기능·모션·사진-as-정체성.
- **천장 규칙**: "정체성이 색·레이아웃·평면기하에 살면 높은 재현, 폰트·사진·모션에 살면 한계." 시각 복잡도 자체는 장애물이 아닙니다.

상세 카탈로그는 `references/design-md-mapping.md`, 레시피·함정·CJK 폰트·렌더 명령은 `references/pptx-toolkit.md`를 참조하세요.

---

## 구성

| 경로 | 설명 |
|---|---|
| `SKILL.md` | Claude 오케스트레이션 지시서([HARD] 관문) |
| `scripts/deckkit.py` | pptx/차트/이미지 공개 헬퍼 API(생성 스크립트가 import). 한글 가드·`add_native_chart` 내장 |
| `scripts/verify.py` | 3층+타이포 배치/렌더 검증기(CLI) |
| `scripts/render.py` | soffice 격리 프로파일 렌더 + 썸네일 |
| `../design-core/library/` | ★ready-to-use DESIGN.md 프리셋 6종(consulting-mbb 등) — 팔레트 + 슬라이드 문법, 선택 표는 내부 README |
| `references/anthropic-pptx-design-ideas.md` | 기본 pptx 스킬 흡수 — 팔레트·타이포·레이아웃·QA(DESIGN.md 없을 때 1급) |
| `references/pptx-toolkit.md` | 레시피·함정·CJK 폰트·네이티브 차트·렌더 명령 |
| `references/design-md-mapping.md` | 웹 DESIGN.md → pptx 3열 필터 매핑 + 재현 가능/불가 카탈로그 |
| `examples/` | 콘텐츠+데이터+DESIGN.md(또는 내장 팔레트) 예제 |
| `tests/` | deckkit 헬퍼·가드·네이티브 차트·verify 검출·타이포 advisory·구조 정책 테스트 |
| `requirements.txt` | 외부 의존성 선언 |

---

## 라이선스

Apache-2.0
