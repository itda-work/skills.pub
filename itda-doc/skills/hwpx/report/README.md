# hwpx / report — 정부 서식 HWPX 생성 (구 hwpx-report)

마크다운 보고서를 대한민국 정부 범용 한글 서식(`.hwpx`, gov-report 템플릿)으로 변환하는 스킬.

- **방향**: 마크다운(쓰기) → `.hwpx`(생성). 반대 방향(읽기·변환)은 통합 hwpx 스킬의 reader 경로.
- **구성**: `scripts/md_to_docspec.py`(결정론 매퍼) → `python -m hwpx_report convert`(서식 보존 생성).
- **분업**: LLM = 콘텐츠 작성, 엔진 = 서식 보존 생성.

상세 워크플로·작성 규약·비목표는 [SKILL.md](SKILL.md) 참조.

## 빠른 사용

```bash
# 1) 마크다운 → DocSpec (py -3 on Windows)
python3 scripts/md_to_docspec.py report.md -o spec.json

# 2) DocSpec → HWPX
PYTHONPATH=. python3 -m hwpx_report convert spec.json -o report.hwpx --template gov-report
```

## 테스트

```bash
python3 -m pytest tests   # Windows: py -3 -m pytest tests
```

## 조직별 맞춤 서식이 필요하면

사용자가 자기 한글 양식을 가진 경우 범용 생성 대신 통합 hwpx 스킬의 채우기 경로(`scripts/fill_hwpx.py`)를 쓴다.
참고 문서의 **서식만** 빌려 새 내용을 쓸 때는 `scripts/derive_profile.py analyze 참고.hwpx -o 프로파일/` 로 프로파일을 뽑고
`python -m hwpx_report convert … --template-dir 프로파일/` 로 생성한 뒤 `derive_profile.py compare … --ref 참고.hwpx` 로 대조한다(USAGE.md §참고 서식 프로파일).
