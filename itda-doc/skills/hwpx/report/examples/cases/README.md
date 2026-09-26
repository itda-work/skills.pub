# 현업 케이스북 (#1652)

이 스킬로 실제 공공기관 문서 20종을 만들어 본 소스입니다(2026-09-06). 각 파일은 그대로 재생성됩니다.
`SKILL_DIR` 확정 뒤:

```bash
python3 "$SKILL_DIR/report/scripts/md_to_docspec.py" <소스.md> -o spec.json --layout <layout>
PYTHONPATH="$SKILL_DIR/report" python3 -m hwpx_report convert spec.json -o out.hwpx --template <template>
```

| 디렉토리 | 파일 | 유형 | layout / template | 이렇게 말하면 |
|---|---|---|---|---|
| ai-report | 01-project-plan.md | 사업 추진 계획(표 2) | ai-report | "어르신 스마트기기 교육 확대 추진계획을 한글 보고서로, 과정별 편성표와 예산표 넣어서" |
| ai-report | 02-progress-roman.md | 추진 현황 중간보고(절 Ⅰ.Ⅱ., 산문 포함) | ai-report | "상수관로 정비 중간보고서, 절 번호는 로마숫자로" |
| ai-report | 03-result-report.md | 결과 보고(성과 표 2) | ai-report | "청년창업 지원사업 결과보고서, 연도별 실적·분야별 성과 표로" |
| ai-report | 04-meeting-outline.md | 회의 결과 보고(항목 가. 1)) | ai-report | "재난안전 대책회의 결과보고, 참석자·결정사항·후속조치, 항목기호는 가. 1) 방식" |
| ai-report | 05-review-proposal.md | 검토·건의(대안 비교표, 무제목 표 경고 예) | ai-report | "공영주차장 요금 개편 검토보고, 대안 3개 비교표" |
| ai-report | 06-image-report.md (+png) | 이미지 포함 현황 보고 | ai-report | "민원앱 이용률 현황보고, 이 그래프 넣고" |
| official-letter | 01-cooperation-request.md | 협조 요청(외부 수신) | official-letter | "상공회의소에 세무 상담 부스 협조 요청 공문" |
| official-letter | 02-event-notice.md | 개최 안내(붙임 2건, 별칭 키) | official-letter | "정보보호 실무협의회 개최 안내 공문, 붙임 2건" |
| official-letter | 03-data-submission-request.md | 자료 제출 요청(항목 4단) | official-letter | "산학협력 실적 제출 요청 공문, 항목별 세분" |
| official-letter | 04-result-notice.md | 결과 통보(표로 끝나는 본문) | official-letter | "선정 결과 통보 공문, 건수·지원금 표로" |
| official-letter | 05-internal-approval.md | 내부결재 기안(수신 없음, 붙임 1건) | official-letter | "사무용품 일괄 구매 내부결재 기안문" |
| official-letter | 06-short-notice.md | 항목 1개 단문(기호 생략) | official-letter | "단수 안내 공문 한 줄짜리" |
| others | briefing-01.md / briefing-02.md | 표지·목차형 결재 보고 / 짧은 현안 | briefing | "표지·목차 붙여서 결재용으로" |
| others | gov-report-01.md | 구 개조식 통계표(열 정렬·굵게) | report / gov-report | "예전 개조식 서식으로, 숫자는 우측 정렬" |
| others | press-release-01.md | 보도자료(리드문·인용) | press-release | "이 내용 보도자료로" |
| others | fill-01-template.md + fill-01-map.json | 주간보고 양식 생성 → 16자리 채우기 | gov-report → fill_hwpx | "이 양식 빈칸 채워줘" |
| others | fill-02-template.md + fill-02-map.json | 반복 문구 순차 치환 | briefing → fill_hwpx `--map` 배열 | "같은 칸 3개를 순서대로 다른 내용으로" |
| others | fill-03-map.json | 미발견·표기 차이 키(`--strict` exit 3) | fill_hwpx | — |
| others | read-01-with-image.md (+png) | 표+이미지 문서 읽기 md/html | gov-report → reader | "이 문서 HTML로, 서식 그대로" |

실험 원문(경고·결함 추적 기록)은 저장소 `docs/research/hwpx-format-comparison-1651/experiments/` 에 있습니다. 거기서 지목된 결함은 v1.2.0 에서 교정됐습니다.

## v1.3 샘플 (v13-samples/, #1653)

`bash v13-samples/run.sh <출력 디렉토리>` 로 13종을 한 번에 다시 만든다(hwpx + 역변환 md + 경고 + `SUMMARY.md`). 환경변수 `PYTHON` 으로 인터프리터를 지정할 수 있다.

| 파일 | 유형 | layout / template |
|---|---|---|
| 01-ai-outline-roman.md (+chart.png) | AI 친화 보고서 — `Ⅰ. 1. 가. 1)` 체계·산문·표·그림 | ai-report |
| 02-ai-brief-memo.md | AI 친화 보고서 — 한 쪽 대면보고 | ai-report |
| 03-ai-inspection-tables.md | AI 친화 보고서 — 표 3 결과보고 | ai-report |
| 04-letter-external-full.md | 기안문 — 외부 수신·경유·협조자·공개구분·붙임 3·표로 끝남·`가. 1)` 직접 표기 | official-letter |
| 05-letter-internal-approval.md | 기안문 — 내부결재·부분공개 | official-letter |
| 06-press-release-table.md | 보도자료 — 리드문·표·인용 2 | press-release |
| 07-briefing-attachments.md | 표지목차형 — 붙임 2 | briefing |
| 08-gov-report-legacy.md | 구 개조식 통계표 | report / gov-report |
| (09) | 01 을 실제 기관 보고서(`tests/reader/fixtures/inputs/multi_section_with_image.hwpx`) 서식으로 | derive_profile analyze → `--template-dir` → compare |
| (10) | 02 를 08 산출의 서식으로(report 조판) | derive_profile analyze → `--template-dir` → compare |
| 11-form-application.md | 빈칸 신청서 양식 → `--label`·`--cell`·`--tick` 채우기 → `--residue` | gov-report → fill_hwpx |
| 12-form-guided.md + 12-form-guided-map.json | 안내문 양식 → `--check --fix`(혼동문자) → `--strict` 채움 → `--residue --keep` | ai-report → fill_hwpx |
| (13) | 01 을 HTML 로 읽기 | reader |

이 샘플을 만들며 잡은 결함: 기안문 소스의 `가.`·`1)`·`가)` 직접 표기가 이중 번호로 나가던 것(매퍼 교정), compare 가 표 셀 정렬을 서식으로 대조하던 것(제외).
