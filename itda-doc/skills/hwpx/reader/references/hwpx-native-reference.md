# hwpx Native Reference

`hwpx_native`는 HWP5(.hwp)와 HWPX(.hwpx)를 Markdown/HTML로 변환하는 Python 패키지입니다.

## CLI

```bash
PYTHONPATH=/path/to/hwpx/reader python3 -m hwpx_native convert input.hwp -o output.md --format md
PYTHONPATH=/path/to/hwpx/reader python3 -m hwpx_native convert input.hwpx -o output.html --format html
```

옵션:

| 옵션 | 설명 |
|------|------|
| `input` | 입력 `.hwp` 또는 `.hwpx` |
| `-o, --output` | 출력 파일 |
| `--format md` | Markdown 출력 |
| `--format html` | HTML fragment 출력 |
| `--no-extract-images` | Markdown 이미지 파일 추출 생략 |

## Python API

```python
from hwpx_native.convert import convert_file, convert_to_markdown
from hwpx_native.hwpx.reader import read_hwpx_file
from hwpx_native.hwp5.reader import read_hwp5_file
from hwpx_native.writer_html import write_html
from hwpx_native.writer_md import write_markdown

convert_file("doc.hwp", "doc.md", format="md")
convert_file("doc.hwpx", "doc.html", format="html")

markdown = convert_to_markdown("doc.hwp", output_path="doc.md")
document = read_hwpx_file("doc.hwpx")
html = write_html(document)
```

## 이미지 경로

Markdown 변환에서 이미지 추출이 켜져 있으면 출력 파일 stem 디렉토리에 저장합니다.

```text
output.md
output/image_0001.png
output/image_0002.jpg
```

본문 참조도 같은 상대 경로를 사용합니다.

```html
<img src="output/image_0001.png" alt="image3" width="22800" height="14940" />
```

HTML 변환은 이미지 데이터를 Base64 data URI로 임베드하므로 별도 이미지 파일을 만들지 않습니다.

## 검증 기준

- HWPX: 현 hyve Go HWPX 엔진 출력과 Markdown/HTML byte 비교
- HWP5: 삭제 전 Go HWP5 엔진 출력과 Markdown/HTML byte 비교
- 이미지 BMP 선언 데이터는 Pillow로 PNG 변환을 시도하며, 실패 시 원본 확장자로 저장합니다.

## 미지원

- HWP/HWPX 편집 또는 생성
- Markdown/HTML 입력 변환
- HWP5 하이퍼링크 추출
- HWP5 수식/차트의 완전 복원
