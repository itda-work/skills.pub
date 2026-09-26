# hwpx — 한글 문서 통합 스킬

한글 HWP·HWPX 문서의 **읽기 / 양식 채우기 / 정부 서식 생성**을 한 스킬로 처리한다.
외부 서버(hyve MCP 등) 없이 스킬 단독으로 동작한다.

| 작업 | 엔진/스크립트 | 상세 문서 |
|---|---|---|
| 읽기 (HWP/HWPX → MD·HTML) | `reader/hwpx_native` | [reader/USAGE.md](reader/USAGE.md) · [reader/GUIDE.md](reader/GUIDE.md) |
| 양식 채우기 (서식 유지 치환·빈 셀·체크박스·사전검증·잔재 대조) | `scripts/fill_hwpx.py` → `scripts/hwpxfill/` (stdlib 전용) | [SKILL.md §채우기](SKILL.md) |
| 참고 서식 프로파일 (사용자 .hwpx 서식으로 생성) | `report/scripts/derive_profile.py` + `--template-dir` (stdlib 전용) | [report/USAGE.md §참고 서식 프로파일](report/USAGE.md) |
| 서식 생성 (MD → ai-report·기안문·gov-report·보도자료·briefing) | `report/hwpx_report` (`layouts.py` 조판) | [report/USAGE.md](report/USAGE.md) · [규격 근거](report/references/document-style-rules.md) |

- 라우팅·실행 명령: [SKILL.md](SKILL.md) · 사용자 가이드: [GUIDE.md](GUIDE.md)
- 테스트: `tests/{reader,report,fill}` — 저장소 체크아웃에서 `python3 -m pytest tests`
- 템플릿 header.xml 파생: `python3 report/scripts/derive_template_headers.py` (`--check` 로 정합 검사)
- 이력: [CHANGELOG.md](CHANGELOG.md) (v1.0.0 에서 hwpx-reader v4.0.1 + hwpx-report v0.3.3 병합)

## 차용 출처

- `scripts/hwpxfill/fold.py` 의 혼동문자 접기 표(`_FOLD_GROUPS`)·PUA 범위 판정은 [jkf87/hwpx-skill](https://github.com/jkf87/hwpx-skill)
  (MIT — README §라이선스 명시, 리비전 96a2633) `scripts/map_preflight.py:FOLD` 의 데이터성 상수를 차용해 확장했다. 그 밖의 코드·템플릿·hwpx 자산은
  차용하지 않았고(검증 관점·결함 클래스만 참고), 채우기·프로파일 구현은 본 저장소 독자 구현이다. 대조 기록: `docs/research/hwpx-skill-review-jkf87/`.
