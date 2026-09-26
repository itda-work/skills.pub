# references/ — 도메인별 PDF 처리 가이드

pdf-context-refinery 스킬의 도메인 특화 어휘·휴리스틱·평가 케이스를 관리한다.
SKILL.md는 도메인 무관 파이프라인 골격만 포함하고, 도메인별 상세는 이 디렉토리에서 on-demand로 로드한다.

## 도메인 감지 매핑표

| 도메인 | 감지 키워드 (sample.txt 등장 시) | references 파일 |
|--------|----------------------------------|-----------------|
| 세무·회계 | 법인세·조특법·법인령·매출원가·손익계산서·세액감면 | `domain-tax-accounting.md` |
| 전기·전자·반도체 | 회로·임피던스·트랜지스터·datasheet·MOSFET·옴·inverter·grid·voltage·current·frequency·AC·DC·capacitor·resistor | `domain-electronics.md` |
| 법률·판례 | 판결·원고·피고·법령·민법·형법·소송·plaintiff·defendant·court·statute·case·judgment | `domain-legal.md` |
| 일반 공학 | 응력·변형률·하중·열역학·유체·재료·KS·stress·strain·load·thermodynamics·fluid·material·Chapter | `domain-engineering.md` |
| 의학·약학 | 환자·진단·증상·용법·약리·임상시험·ICD | `domain-medical.md (미작성, 후속)` |

## 감지 알고리즘

Step 1 Analyze에서 sample.txt를 매핑표와 대조하여 도메인을 결정한다.

```bash
# 도메인별 키워드 매칭 카운트 집계
grep -c -E "(법인세|조특법|법인령|매출원가|손익계산서|세액감면)" .itda-skills/sample.txt
grep -c -iE "(회로|임피던스|트랜지스터|datasheet|MOSFET|옴|inverter|grid|voltage|current|frequency|AC|DC|capacitor|resistor)" .itda-skills/sample.txt
grep -c -iE "(판결|원고|피고|법령|민법|형법|소송|plaintiff|defendant|court|statute|case|judgment)" .itda-skills/sample.txt
grep -c -iE "(응력|변형률|하중|열역학|유체|재료|KS|stress|strain|load|thermodynamics|fluid|material|Chapter)" .itda-skills/sample.txt
```

**최소 매칭 임계값 = 3**

- 임계값 미달 도메인은 후보 제외
- 가장 많이 매칭된 도메인 1개 선택 → 해당 `references/domain-{name}.md` Read
- 동률 시 → 위 매핑표 순서대로 첫 번째 선택 (결정성 보장)

## 미매칭 fallback (OQ-3)

임계값 ≥3 만족 도메인이 0개이면:

- references 파일 미로드
- Analyze 로그에 `Domain: not detected (max match count < 3)` 명시
- SKILL.md 일반 규칙만으로 처리

## medical placeholder (EXC-8)

의학·약학 도메인 키워드가 감지되어도 `domain-medical.md`가 미작성이므로:

- `Domain: medical (후속 SPEC 필요, domain-medical.md 미작성)` 로그 출력
- references 미로드 → SKILL.md 일반 규칙으로 처리

## 새 도메인 추가 방법 (NFR-2)

1. 이 매핑표에 1행 추가 (도메인·감지 키워드·파일명)
2. `domain-{new-name}.md` 1개 신설 (§4.4 7섹션 구조 채움)
3. SKILL.md 수정 불필요
