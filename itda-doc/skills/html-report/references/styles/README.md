# html-report 스타일 시스템 — 골격 축(가족) × 팔레트 축(프리셋)

스타일은 두 축의 조합이다. **가족**은 레이아웃·표면 처리·타이포 위계·히어로·차트 문법을 정하고,
**팔레트**는 색·의미색 관행·라운드·display 폰트를 정한다. 어느 조합이든 SKILL.md §1·§3·§4·§6·§7·§8·§9·§10
품질 계약은 그대로다 — 가족은 §2 컴포넌트 규격의 **변형**이고 팔레트는 §5 토큰의 **값**이다.

## 축 A — 스타일 가족 5종

| 가족 id | 파일 | 골격 한 줄 | 잘 맞는 문서 | 기본 팔레트 |
|---|---|---|---|---|
| `corporate` | `corporate.md` | KPI 스트립 + 카드는 KPI·콜아웃만 + 밝은 히어로 + 좌측 TOC | 분기·주간 현황, 이사회 보고, 재무 요약 | `samsung-sds` |
| `consulting` | `consulting.md` | 결론이 제목(액션 타이틀) + Exhibit 번호 + 차트마다 출처 + 헤어라인·직각 | 전략 검토, IR, 경영진 의사결정 요청 | `consulting-mbb` |
| `editorial` | `editorial.md` | 넓은 여백 + 라틴 세리프 헤딩 + 풀폭 인용 + 사이드노트 | 연차보고서, 브랜드 서사, 심층 분석·리서치 | `warm-editorial` |
| `minimal` | `minimal.md` | 보더 0 + 헤어라인 + 좁은 본문 + 코드·표 중심 | 사내 가이드, 기술 문서, 인시던트 회고, 설명서 | `minimal-mono` |
| `public-kr` | `public-kr.md` | Ⅰ·1·가·1) 개조식 + 격자 표 + 흑백 인쇄 우선 + 명조 제목 | 정부·공공기관·지자체 제출/보고, 연구 성과 보고 | `gov-mono`(자체) |

**가족 판정 트리거** (사용자 문구 → 가족). 신호가 있으면 되묻지 않는다.

- "분기 보고"·"현황 보고"·"이사회"·"경영 현황"·"대시보드처럼" → `corporate`
- "컨설팅"·"MBB"·"전략"·"의사결정"·"IR"·"임원 보고"·"결론 먼저" → `consulting`
- "매거진"·"에디토리얼"·"연차보고서"·"잡지처럼"·"읽는 맛"·"서사" → `editorial`
- "가이드"·"설명서"·"기술 문서"·"회고"·"포스트모템"·"노션처럼"·"깔끔하게" → `minimal`
- "공공기관"·"관공서"·"정부"·"과제 보고"·"개조식"·"보고서 양식"·"흑백 인쇄" → `public-kr`
- 무신호 + 대화형 → AskUserQuestion(콘텐츠 적합 후보 2~3 + "알아서") · 무신호 + 비대화형 → 위 표 "잘 맞는 문서" 로 자동 선택 + 근거 1줄

## 축 B — 팔레트 프리셋 (design-core `../../../design-core/library/` 8종 + 자체 1종)

design-core 토큰(`canvas surface ink muted primary accent hairline up down`)을 html-report CSS 변수로 옮긴 값이다.
링크(`tokens.css`)가 아니라 **`:root` 블록에 인라인**한다(§1 단일 파일). 사용자 DESIGN.md 가 오면 같은 표의 열을 그 hex 로 치환한다.

| 프리셋 | `--bg` | `--paper` | `--tint` | `--ink` | `--g500` | `--accent` | `--accent-2` | `--line` | `--pos` | `--neg` | display 폰트(라틴·숫자 전용) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `samsung-sds` | `#FFFFFF` | `#FFFFFF` | `#EEF2FB` | `#14181F` | `#5C6470` | `#1428A0` | `#5B8DEF` | `#D5DBE8` | `#0E7C4A` | `#C0392B` | Helvetica Neue |
| `consulting-mbb` | `#FFFFFF` | `#FFFFFF` | `#EEF3FC` | `#15193B` | `#5C6470` | `#1E2761` | `#CADCFC` | `#D9DEE8` | `#0E7C4A` | `#C0392B` | Helvetica Neue |
| `warm-editorial` | `#FAF9F5` | `#FFFFFF` | `#F0EEE6` | `#141413` | `#6B675F` | `#CC785C` | `#5DB8A6` | `#E6DFD8` | `#5DB872` | `#C64545` | Georgia |
| `print-broadsheet` | `#F4F1EA` | `#FFFFFF` | `#FFFFFF` | `#111111` | `#55524C` | `#0047AB` | `#0047AB` | `#D8D2C4` | `#0047AB` | `#C0392B` | Georgia |
| `minimal-mono` | `#FFFFFF` | `#FFFFFF` | `#F4F4F4` | `#171A20` | `#5C5E62` | `#171A20` | `#3E6AE1` | `#E8E8E8` | `#3E6AE1` | `#E82127` | Helvetica Neue |
| `kari` (다크 부팅) | `#0A1430` | `#14224A` | `#14224A` | `#EAF0FF` | `#93A0C0` | `#2BC0BD` | `#3C2DA0` | `#2A3A66` | `#2BC07A` | `#E5484D` | Helvetica Neue |
| `equity-research-dark` (다크 부팅) | `#0B0E11` | `#1E2329` | `#1E2329` | `#EAECEF` | `#848E9C` | `#F0B90B` | `#F0B90B` | `#2B3139` | `#0ECB81` | `#F6465D` | Consolas(mono) |
| `tech-vivid-dark` (다크 부팅) | `#121212` | `#1F1F1F` | `#1F1F1F` | `#FFFFFF` | `#B3B3B3` | `#1ED760` | `#1ED760` | `#2A2A2A` | `#1ED760` | `#E22134` | Arial Black |
| `gov-mono` (자체) | `#FFFFFF` | `#FFFFFF` | `#F2F2F2` | `#111111` | `#5A5A5A` | `#1C3F95` | `#1C3F95` | `#BEBEBE` | `#1B6E3A` | `#B3261E` | (없음 — 명조 로컬 스택) |

파생 규칙(표에 없는 변수):
- `--accent-d` = `--accent` 를 15% 어둡게(`color-mix(in srgb, var(--accent) 85%, #000)`), `--g100` = `--tint`, `--g300` = `--line`, `--g700` = `color-mix(in srgb, var(--ink) 80%, var(--bg))`.
- `--warn` = 라이트 `#9A6206` / 다크 `#E0A030` (프리셋 무관 고정).
- **다크 짝**: 라이트 프리셋의 다크 값은 `--bg #0F1218` · `--paper #171B24` · `--tint #1E2430` · `--ink #E7EAF0` · `--g500 #98A2B3` · `--line #2A3140` (warm 계열 `warm-editorial`·`print-broadsheet` 은 색온도를 맞춰 `--bg #1A1915` · `--paper #232219` · `--tint #26241F` · `--ink #E8E6E0` · `--g500 #A39F95` · `--line #35322B`) · `--accent` 는 라이트 accent 를 `color-mix(in srgb, <accent> 65%, #FFF)` 로 밝힌 값 · `--pos #4CC38A` · `--neg #F0776A`. 다크 부팅 프리셋(kari·equity·tech)은 §6 "OS 라이트 감지 시 라이트 부팅" 을 위해 라이트 짝을 `minimal-mono` 표로 대체하되 accent 만 자기 것을 어둡힌 값(`color-mix(in srgb, <accent> 70%, #000)`)으로 쓴다.
- **display 폰트는 라틴·숫자에만** — `h1`·KPI 값·섹션 번호·Exhibit 번호에 `font-family: "<display>", var(--sans)` 로 걸되, 한글 글리프는 Pretendard 로 떨어지게 스택 순서를 지킨다. 음수 letter-spacing·thin weight 를 한글 헤딩에 쓰지 않는다(§5 의 `-0.02em` 은 라틴·숫자 전용으로 축소).
- 의미색 관행: 기본 international(상승 `--pos` 녹 / 하락 `--neg` 적). 사용자가 "증시 관행"·"krx" 를 말하면 상승 적 `#D64545` / 하락 청 `#2B6CB0` 으로 교체하고 범례에 명시.

## 가족 × 팔레트 허용 조합

기본 짝 외의 조합도 허용하되 아래는 금지다(계약 충돌).

- `public-kr` × 다크 부팅 프리셋 — 흑백 인쇄 우선 계약과 충돌. `public-kr` 은 `gov-mono` 고정, 강조색만 사용자 hex 로 치환 가능.
- `editorial` × `tech-vivid-dark` — glow 모티프가 편집 여백 계약과 충돌.
- `consulting` × `tech-vivid-dark` — pill·라운드 0.25 가 직각 계약과 충돌.

## 구 프리셋 이름 하위 호환 (v0.2 → v0.3)

| 구 지정 문구 | 해석 |
|---|---|
| "네이비"·"격식 있게"·"고대비로"(또는 미지정 기본) | `corporate` × `samsung-sds` |
| "웜톤"·"부드럽게"·"매거진 톤으로"·"잡지처럼" | `editorial` × `warm-editorial` |
| "다크 테마로"·"엔지니어링 리포트답게" | `minimal` × `tech-vivid-dark`(엔지니어링·인시던트) 또는 `equity-research-dark`(시장·수치 밀도) |
