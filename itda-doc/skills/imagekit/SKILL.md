---
name: imagekit
description: >
  이미지 조회·리사이즈·여백 크롭·DPI 변경·포맷 변환·회전을 단일 CLI로 처리하는 스킬입니다.
  "이미지 크기 줄여줘", "여백 크롭해줘", "PNG를 JPG로 변환해줘"처럼 말하면 됩니다.
  한국 사무환경에서 자주 묻는 사진 편집 요청을 모두 다룹니다.
license: Apache-2.0
compatibility: Claude Code & Cowork
allowed-tools: Bash, Read, mcp__workspace__bash
user-invocable: true
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "media"
  version: "0.10.6"
  created_at: "2026-03-18"
  updated_at: "2026-07-26"
  tags: "image, resize, shrink, scale, crop, trim, dpi, resolution, convert, rotate, flip, imagekit"
---

# imagekit

이미지 정보 조회, 리사이즈, 가장자리 크롭, DPI 변경, 포맷 변환, 회전/반전 작업을 수행합니다.

## Prerequisites

Python 3.10 이상과 Pillow 라이브러리가 필요합니다.

먼저 스킬 디렉토리를 확정합니다.

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/imagekit}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/imagekit' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
# Windows
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\imagekit"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

```bash
python3 "$SKILL_DIR/scripts/install_skill_deps.py"          # 정문
# Windows: py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

## Workflow

### Step 1: Parse Request

사용자 요청에서 다음을 추출합니다:

- **Operation**: info / resize / crop-edges / set-dpi / convert / rotate
- **File path**: 입력 이미지 경로
- **Parameters**: 크기, 모드, DPI 등 작업별 옵션

### Step 2: Validate File

`Read` tool로 파일 존재 여부를 확인합니다. 파일이 없으면 경로를 다시 확인하고 사용자에게 알립니다.

### Step 3: Determine Output Path

사용자가 출력 경로를 지정하지 않으면 기본 경로를 생성합니다:

| 입력 파일 | 작업 | 기본 출력 파일 |
|-----------|------|----------------|
| `photo.jpg` | resize | `photo-resized.jpg` |
| `image.png` | crop-edges | `image-cropped.png` |
| `scan.jpg` | set-dpi | `scan-300dpi.jpg` |
| `logo.png` | convert | `logo.jpg` |
| `photo.jpg` | rotate | `photo-rotated.jpg` |

### Step 4: Confirm (destructive ops only)

resize / crop-edges / set-dpi / convert / rotate 작업 전에 다음을 확인합니다:

- 입력 파일 경로
- 출력 파일 경로
- 작업 파라미터 요약

파일이 10MB 이상이면 처리 시간이 걸릴 수 있음을 사용자에게 알립니다.

### Step 5: Execute

`Bash` tool로 Python 스크립트를 실행하고 JSON stdout을 파싱합니다.

### Step 6: Report

JSON `data` 필드를 파싱해 사람이 읽기 쉬운 형태로 결과를 출력합니다.

---

## Operations

### info — 이미지 정보 조회

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/imagekit.py" info --image-path <path>

# Windows
py -3 "$env:SKILL_DIR\scripts\imagekit.py" info --image-path <path>
```

**응답 데이터 필드:**

| 필드 | 설명 |
|------|------|
| `file_name` | 파일명 |
| `file_size_human` | 파일 크기 (사람이 읽기 좋은 형태) |
| `width` / `height` | 가로 × 세로 (픽셀) |
| `format` | 포맷 (`jpeg` / `png`) |
| `aspect_ratio` | 가로세로 비율 |
| `dpi` | DPI (없으면 0) |
| `orientation_corrected` | EXIF 방향 자동 보정 여부 |

**예시 출력:**

```
이미지 정보: photo.jpg
- 크기: 3840 × 2160 px (4K)
- 파일 크기: 4.2 MB
- 포맷: JPEG
- 비율: 16:9
- DPI: 72
```

---

### resize — 이미지 리사이즈

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/imagekit.py" resize \
  --input-image-path <in> \
  --output-image-path <out> \
  [--target-width W] \
  [--target-height H] \
  [--multiplier M] \
  [--resize-mode fit|fill|exact] \
  [--jpeg-quality Q] \
  [--overwrite]

# Windows
py -3 "$env:SKILL_DIR\scripts\imagekit.py" resize \
  --input-image-path <in> \
  --output-image-path <out> \
  [--target-width W] \
  [--target-height H] \
  [--multiplier M] \
  [--resize-mode fit|fill|exact] \
  [--jpeg-quality Q] \
  [--overwrite]
```

**필수:** `--input-image-path`, `--output-image-path`

**크기 지정 (셋 중 하나 이상 필수):**

| 플래그 | 형식 | 예시 |
|--------|------|------|
| `--target-width` | 정수 또는 `px` | `1920`, `1920px` |
| `--target-height` | 정수 또는 `px` | `1080`, `1080px` |
| `--multiplier` | 소수 (0.1–5.0) | `0.5` (절반), `2.0` (2배) |

**리사이즈 모드:**

| 모드 | 동작 | 사용 케이스 |
|------|------|-------------|
| `fit` (기본값) | 비율 유지, 지정 크기 내에 맞춤 | 일반 리사이즈 |
| `fill` | 비율 유지, 지정 크기를 가득 채움 | 썸네일, 배경 이미지 |
| `exact` | 비율 무시, 정확히 지정 크기로 늘임 | 특정 규격 필요 시 |

**옵션:**

- `--jpeg-quality`: JPEG 출력 품질 1–100 (기본값: 85)
- `--overwrite`: 출력 파일이 이미 존재할 때 덮어쓰기 허용

**예시:**

```bash
# 가로 1920px로 비율 유지 리사이즈
python3 "$SKILL_DIR/scripts/imagekit.py" resize \
  --input-image-path photo.jpg \
  --output-image-path photo-resized.jpg \
  --target-width 1920

# 0.5배로 축소
python3 "$SKILL_DIR/scripts/imagekit.py" resize \
  --input-image-path photo.jpg \
  --output-image-path photo-half.jpg \
  --multiplier 0.5

# 정확히 800×600으로 (비율 무시)
python3 "$SKILL_DIR/scripts/imagekit.py" resize \
  --input-image-path photo.jpg \
  --output-image-path photo-800x600.jpg \
  --target-width 800 --target-height 600 \
  --resize-mode exact
```

---

### crop-edges — 가장자리 크롭

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/imagekit.py" crop-edges \
  --input-image-path <in> \
  --output-image-path <out> \
  [--crop-top V] [--crop-bottom V] [--crop-left V] [--crop-right V] \
  [--auto-detect] \
  [--threshold T] \
  [--jpeg-quality Q] \
  [--overwrite]

# Windows
py -3 "$env:SKILL_DIR\scripts\imagekit.py" crop-edges \
  --input-image-path <in> \
  --output-image-path <out> \
  [--crop-top V] [--crop-bottom V] [--crop-left V] [--crop-right V] \
  [--auto-detect] \
  [--threshold T] \
  [--jpeg-quality Q] \
  [--overwrite]
```

**필수:** `--input-image-path`, `--output-image-path`

**크롭 값 형식:**

| 형식 | 예시 | 설명 |
|------|------|------|
| 픽셀 | `100` | 해당 방향에서 100픽셀 제거 |
| 퍼센트 | `10%` | 이미지 크기의 10% 제거 |

**주요 옵션:**

- `--auto-detect`: 균일한 가장자리(여백)를 자동 감지해 크롭
- `--threshold`: 자동 감지 임계값 0–255 (기본값: 10; 값이 클수록 더 공격적으로 크롭)

**예시:**

```bash
# 자동 감지로 흰 여백 제거
python3 "$SKILL_DIR/scripts/imagekit.py" crop-edges \
  --input-image-path scan.png \
  --output-image-path scan-cropped.png \
  --auto-detect

# 상단/하단 각 50px 제거
python3 "$SKILL_DIR/scripts/imagekit.py" crop-edges \
  --input-image-path photo.jpg \
  --output-image-path photo-cropped.jpg \
  --crop-top 50 --crop-bottom 50

# 좌우 각 5% 제거
python3 "$SKILL_DIR/scripts/imagekit.py" crop-edges \
  --input-image-path banner.jpg \
  --output-image-path banner-cropped.jpg \
  --crop-left 5% --crop-right 5%
```

---

### set-dpi — DPI 변경

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/imagekit.py" set-dpi \
  --input-image-path <in> \
  --output-image-path <out> \
  --target-dpi D \
  [--jpeg-quality Q] \
  [--overwrite]

# Windows
py -3 "$env:SKILL_DIR\scripts\imagekit.py" set-dpi \
  --input-image-path <in> \
  --output-image-path <out> \
  --target-dpi D \
  [--jpeg-quality Q] \
  [--overwrite]
```

**필수:** `--input-image-path`, `--output-image-path`, `--target-dpi`

**DPI 범위:** 1–3000

**일반적인 DPI 값:**

| DPI | 용도 |
|-----|------|
| 72 | 화면 표시 (웹) |
| 96 | Windows 기본 화면 |
| 150 | 초안 인쇄 |
| 300 | 고품질 인쇄 (권장) |
| 600 | 정밀 인쇄 |

**예시:**

```bash
# 인쇄용 DPI 300으로 변경
python3 "$SKILL_DIR/scripts/imagekit.py" set-dpi \
  --input-image-path photo.jpg \
  --output-image-path photo-300dpi.jpg \
  --target-dpi 300
```

**참고:** `set-dpi`의 `--jpeg-quality` 기본값은 95입니다 (다른 명령은 85). DPI 변경 시 화질 손실을 최소화합니다.

---

### convert — 포맷 변환

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/imagekit.py" convert \
  --input-image-path <in> \
  --output-image-path <out> \
  [--jpeg-quality Q] \
  [--overwrite] \
  [--dry-run]

# Windows
py -3 "$env:SKILL_DIR\scripts\imagekit.py" convert \
  --input-image-path <in> \
  --output-image-path <out> \
  [--jpeg-quality Q] \
  [--overwrite] \
  [--dry-run]
```

**필수:** `--input-image-path`, `--output-image-path`

출력 파일의 확장자로 변환 포맷이 결정됩니다:

| 변환 | 동작 |
|------|------|
| JPEG → PNG | RGB → RGBA로 변환 후 PNG 저장 |
| PNG → JPEG | 투명 영역을 흰색으로 채운 후 JPEG 저장 |

**주의:**

- 동일 포맷 변환 (예: JPG → JPG)은 `SAME_FORMAT` 에러를 반환합니다.
- PNG의 투명 영역은 흰색 배경으로 대체됩니다.

**예시:**

```bash
# PNG를 JPEG로 변환
python3 "$SKILL_DIR/scripts/imagekit.py" convert \
  --input-image-path logo.png \
  --output-image-path logo.jpg

# JPEG를 PNG로 변환
python3 "$SKILL_DIR/scripts/imagekit.py" convert \
  --input-image-path photo.jpg \
  --output-image-path photo.png
```

---

### rotate — 회전 / 반전

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/imagekit.py" rotate \
  --input-image-path <in> \
  --output-image-path <out> \
  [--angle 90|180|270] \
  [--flip horizontal|vertical] \
  [--jpeg-quality Q] \
  [--overwrite] \
  [--dry-run]

# Windows
py -3 "$env:SKILL_DIR\scripts\imagekit.py" rotate \
  --input-image-path <in> \
  --output-image-path <out> \
  [--angle 90|180|270] \
  [--flip horizontal|vertical] \
  [--jpeg-quality Q] \
  [--overwrite] \
  [--dry-run]
```

**필수:** `--input-image-path`, `--output-image-path`, `--angle` 또는 `--flip` 중 하나 이상

| 옵션 | 값 | 설명 |
|------|-----|------|
| `--angle` | 90, 180, 270 | 시계방향 회전 |
| `--flip` | horizontal, vertical | 수평/수직 반전 |

**동시 지정 가능:** `--angle`과 `--flip`을 함께 사용하면 회전 먼저, 반전 나중에 적용됩니다.

**예시:**

```bash
# 시계방향 90도 회전
python3 "$SKILL_DIR/scripts/imagekit.py" rotate \
  --input-image-path photo.jpg \
  --output-image-path photo-rotated.jpg \
  --angle 90

# 수평 반전 (좌우 뒤집기)
python3 "$SKILL_DIR/scripts/imagekit.py" rotate \
  --input-image-path photo.jpg \
  --output-image-path photo-flipped.jpg \
  --flip horizontal

# 90도 회전 후 수평 반전
python3 "$SKILL_DIR/scripts/imagekit.py" rotate \
  --input-image-path photo.jpg \
  --output-image-path photo-transformed.jpg \
  --angle 90 --flip horizontal
```

---

## --dry-run (미리보기)

모든 write 명령에 `--dry-run` 플래그를 추가하면 실제 파일을 생성하지 않고 결과를 미리 볼 수 있습니다.

```bash
python3 "$SKILL_DIR/scripts/imagekit.py" resize \
  --input-image-path photo.jpg \
  --output-image-path photo-resized.jpg \
  --target-width 500 \
  --dry-run
```

**동작:**

- 입력 파일 유효성 검사는 수행됩니다
- 출력 치수와 예상 결과를 반환합니다
- 출력 파일을 생성하지 않습니다
- 응답에 `"dry_run": true` 필드가 포함됩니다
- `input_size`/`output_size` 필드는 생략됩니다

---

## Overwrite Safety

`--overwrite` 플래그 기본값은 `false`입니다.

- 출력 파일이 이미 존재하면 CLI는 에러를 반환합니다.
- 사용자가 명시적으로 덮어쓰기를 요청하지 않는 한 `--overwrite`를 사용하지 않습니다.
- 파일이 이미 존재한다면 대안 경로를 기본값으로 제안합니다.

---

## JSON Response Parsing

모든 명령은 표준 JSON 응답을 stdout으로 출력합니다.

**성공 응답:**

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "metadata": {
    "plugin": "imagekit",
    "version": "0.3.0",
    "execution_time_ms": 123
  }
}
```

**에러 응답:**

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "File not found: photo.jpg",
    "details": { "suggestion": "Check the file path and ensure the file exists." }
  },
  "metadata": { ... }
}
```

파싱 방법:
1. `success` 필드를 확인합니다.
2. `true`면 `data` 필드를 파싱해 결과를 표시합니다.
3. `false`면 `error.message`와 `error.details.suggestion`을 사용자에게 보여줍니다.

---

## Error Handling

| 에러 코드 | 원인 | 조치 |
|-----------|------|------|
| `FILE_NOT_FOUND` | 파일 없음 | 파일 경로 확인 |
| `UNSUPPORTED_FORMAT` | JPEG/PNG 외 형식 | JPEG 또는 PNG 사용 |
| `INVALID_DIMENSION` | 크기/배수 미지정 또는 잘못된 값 | `--target-width`, `--target-height`, `--multiplier` 중 하나 이상 지정 |
| `INVALID_RESIZE_MODE` | 잘못된 리사이즈 모드 | `fit`, `fill`, `exact` 중 선택 |
| `INVALID_CROP_VALUE` | 크롭 값 없음 또는 잘못된 형식 | 픽셀 수 또는 `10%` 형식으로 지정, 또는 `--auto-detect` 사용 |
| `INVALID_THRESHOLD` | threshold가 0–255 범위 밖 | 0–255 사이 값 입력 |
| `INVALID_DPI` | DPI가 1–3000 범위 밖 | 1–3000 사이 값 입력 |
| `INVALID_QUALITY` | JPEG 품질이 1–100 범위 밖 | 1–100 사이 값 입력 |
| `INVALID_ANGLE` | 회전 각도가 90/180/270이 아님 | 90, 180, 270 중 선택 |
| `INVALID_FLIP` | 반전 방향이 horizontal/vertical이 아님 | `horizontal` 또는 `vertical` 지정 |
| `OUTPUT_EXISTS` | 출력 파일이 이미 존재 | `--overwrite` 플래그 추가 또는 다른 경로 사용 |
| `CROP_ERROR` | 크롭 후 크기가 0 이하 | 크롭 값 줄이기 |
| `SAME_FORMAT` | 변환 시 입출력 포맷이 동일 | 다른 확장자를 가진 출력 경로 지정 |
| `CONVERT_ERROR` | 포맷 변환 중 오류 | 입력 파일이 유효한 JPEG/PNG인지 확인 |
| `ROTATE_ERROR` | 회전/반전 중 오류 | 입력 파일이 유효한 JPEG/PNG인지 확인 |
| `INTERNAL_ERROR` | 예상치 못한 오류 | 입력 파일과 파라미터 확인 후 재시도 |
