# NovaTech FY2025 실적 통합문서 — 콘텐츠 명세 (SSoT)

> 콘텐츠 고정(SSoT), 디자인만 변수. 모든 수치는 `data.json` 인용. NovaTech 는 가상 기업.

## 시트 1 — 요약
- 제목: NovaTech FY2025 실적 요약 (+ 단위/발행 캡션)
- KPI 블록 4종: 연간 매출·영업이익률·순이익·임직원 (headline_kpis)
- 사업부별 실적 표: 사업부/매출/YoY/마진 (segments) — YoY 는 조건부서식(양수=up/음수=down 색)
- 차트: 사업부 매출 막대 (chart_palette)
- 지역 매출 비중: Americas/EMEA/APAC

## 시트 2 — 분기추이
- 표: 분기/매출/영업이익/영업이익률 (quarterly)
- 차트: 영업이익률 라인 추이

## 시트 3 — 리스크
- 표: 리스크/설명 (risks)

## 디자인 규칙
- 숫자서식 필수(통화 `#,##0.00"B"`·퍼센트 `0.0"%"`·YoY `+0.0"%";-0.0"%"`)
- 헤더 fill + zebra + 테두리(sheetkit data_table)
- 한글 셀 = Korean-capable 폰트(자동 가드)
- freeze panes(헤더 고정)
