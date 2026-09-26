# hwpx / reader — HWP/HWPX Python Native Reader (구 hwpx-reader)

한글 HWP5(.hwp)와 HWPX(.hwpx) 문서를 Markdown/HTML로 변환하는 Claude Cowork 스킬입니다.

```text
"이 HWP 파일 읽어줘" -> Python native 변환 -> Claude가 내용 요약
```

## 주요 기능

- HWP5/HWPX -> Markdown
- HWP5/HWPX -> HTML
- Markdown 이미지 추출: `<stem>/image_NNNN.ext`
- HTML 이미지 Base64 임베드
- 한국 공공문서 Table 평탄화 지침
- 선택적 이미지 캡션 워크플로

## 요구 사항

```bash
python3 -m pip install -r requirements.txt
```

의존성:

- `Pillow`
- `olefile`

## 사용 예

```bash
PYTHONPATH=. python3 -m hwpx_native convert sample.hwp -o sample.md --format md
PYTHONPATH=. python3 -m hwpx_native convert sample.hwpx -o sample.html --format html
PYTHONPATH=. python3 -m hwpx_native convert sample.hwp -o sample.md --format md --no-extract-images
```

Python API:

```python
from hwpx_native.convert import convert_file

convert_file("sample.hwp", "sample.md", format="md")
convert_file("sample.hwpx", "sample.html", format="html")
```

## 지원 요소

| 요소 | HWP5 | HWPX |
|------|------|------|
| 단락/제목 | O | O |
| 표/셀 병합 | O | O |
| 이미지 | O | O |
| 볼드/이탤릭/밑줄 | O | O |
| 취소선 | O | O |
| 하이퍼링크 | X | O |
| HTML Base64 이미지 | O | O |

## 검증

```bash
python3 -m pytest tests -q
```

테스트는 HWPX 현 Go 엔진 출력과 삭제 전 HWP5 Go 엔진 출력의 Markdown/HTML 골든을 byte 단위로 비교합니다.

## 라이선스

Apache-2.0
