"""Core image processing module for itda-imagekit.

Provides info, resize, crop-edges, and set-dpi operations using Pillow.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from PIL import Image, ImageOps


# --- Constants ---

MIN_DPI = 1
MAX_DPI = 3000
MIN_QUALITY = 1
MAX_QUALITY = 100
DEFAULT_QUALITY = 85
MIN_MULTIPLIER = 0.1
MAX_MULTIPLIER = 5.0
DEFAULT_THRESHOLD = 10
MAX_THRESHOLD = 255

# EXIF tag IDs
TAG_ORIENTATION = 0x0112
TAG_X_RESOLUTION = 0x011A
TAG_Y_RESOLUTION = 0x011B
TAG_RESOLUTION_UNIT = 0x0128


# --- Exceptions ---

class ImageKitError(Exception):
    """Structured error with code, message, and details."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


# --- Helpers ---

def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    for unit in ("KB", "MB", "GB", "TB"):
        size_bytes /= 1024
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
    return f"{size_bytes:.1f} PB"


def calculate_aspect_ratio(width: int, height: int) -> str:
    """Calculate simplified aspect ratio using GCD."""
    if width <= 0 or height <= 0:
        return "0:0"
    g = math.gcd(width, height)
    return f"{width // g}:{height // g}"


def _detect_format(path: str) -> str:
    """파일 확장자로 이미지 포맷을 감지한다. (출력 경로 결정용)"""
    ext = Path(path).suffix.lower().lstrip(".")
    if ext in ("jpg", "jpeg"):
        return "jpeg"
    if ext == "png":
        return "png"
    return ext


def _validate_format_by_content(path: str) -> str:
    """실제 이미지 콘텐츠로 포맷을 검증한다. 확장자가 아닌 실제 데이터 기반."""
    try:
        with Image.open(path) as img:
            fmt = (img.format or "").lower()
        if fmt in ("jpeg", "jpg"):
            return "jpeg"
        if fmt == "png":
            return "png"
        raise ImageKitError(
            "UNSUPPORTED_FORMAT",
            f"Unsupported format: {fmt}",
            {"suggestion": "Only JPEG and PNG formats are supported."},
        )
    except ImageKitError:
        raise
    except Exception as e:
        raise ImageKitError(
            "UNSUPPORTED_FORMAT",
            f"Cannot read image: {e}",
            {"suggestion": "Ensure the file is a valid JPEG or PNG image."},
        )


def _validate_input(path: str) -> None:
    """입력 파일 존재 여부 및 지원 포맷 여부를 검증한다."""
    if not os.path.isfile(path):
        raise ImageKitError(
            "FILE_NOT_FOUND",
            f"File not found: {path}",
            {"suggestion": "Check the file path and ensure the file exists."},
        )
    # 실제 콘텐츠 기반으로 포맷 검증
    _validate_format_by_content(path)


def _validate_output(path: str, overwrite: bool) -> None:
    """Validate output path does not already exist (unless overwrite)."""
    if os.path.exists(path) and not overwrite:
        raise ImageKitError(
            "OUTPUT_EXISTS",
            f"Output file already exists: {path}",
            {"suggestion": "Use --overwrite flag or choose a different output path."},
        )


def _validate_quality(quality: int) -> None:
    """Validate JPEG quality value."""
    if quality < MIN_QUALITY or quality > MAX_QUALITY:
        raise ImageKitError(
            "INVALID_QUALITY",
            f"JPEG quality must be {MIN_QUALITY}-{MAX_QUALITY}: {quality}",
            {"suggestion": f"Enter a value between {MIN_QUALITY} and {MAX_QUALITY}."},
        )


def _load_image(path: str) -> tuple[Image.Image, bool]:
    """Load image with EXIF orientation correction.

    Returns (image, orientation_corrected).
    """
    img = Image.open(path)
    img.load()

    orientation_corrected = False
    try:
        exif = img.getexif()
        orientation = exif.get(TAG_ORIENTATION, 1)
        if orientation != 1:
            orientation_corrected = True
    except Exception:
        pass

    img = ImageOps.exif_transpose(img) or img

    # Convert to RGB if needed (e.g., RGBA, P, L modes)
    if img.mode == "RGBA" and _detect_format(path) == "jpeg":
        img = img.convert("RGB")

    return img, orientation_corrected


def _read_dpi(path: str) -> int:
    """Read DPI from image metadata."""
    try:
        img = Image.open(path)
        # Try img.info['dpi'] (works for both JPEG and PNG)
        dpi_info = img.info.get("dpi")
        if dpi_info:
            return int(round(dpi_info[0]))
        # For JPEG, try EXIF tags
        try:
            exif = img.getexif()
            x_res = exif.get(TAG_X_RESOLUTION)
            if x_res is not None:
                if hasattr(x_res, "numerator"):
                    return int(x_res.numerator / x_res.denominator) if x_res.denominator else 0
                return int(x_res)
        except Exception:
            pass
    except Exception:
        pass
    return 0


def _save_image(img: Image.Image, path: str, quality: int, dpi: int | None = None,
                exif_bytes: bytes | None = None) -> None:
    """Save image with format auto-detection."""
    fmt = _detect_format(path)
    # Ensure parent directory exists
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    save_kwargs: dict = {}
    if fmt == "jpeg":
        if img.mode != "RGB":
            img = img.convert("RGB")
        save_kwargs["quality"] = quality
        save_kwargs["subsampling"] = 0  # Best quality
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
        if dpi:
            save_kwargs["dpi"] = (dpi, dpi)
    elif fmt == "png":
        if dpi:
            save_kwargs["dpi"] = (dpi, dpi)

    img.save(path, **save_kwargs)


def parse_dimension(value: str | None) -> int:
    """Parse dimension value like '1920' or '1920px'."""
    if value is None:
        return 0
    s = str(value).strip().lower()
    if s.endswith("px"):
        s = s[:-2]
    try:
        v = int(s)
        if v < 0:
            raise ImageKitError(
                "INVALID_DIMENSION",
                f"Dimension must be positive: {value}",
                {"suggestion": "Enter a positive integer value."},
            )
        return v
    except ValueError:
        raise ImageKitError(
            "INVALID_DIMENSION",
            f"Invalid dimension value: {value}",
            {"suggestion": "Use an integer or 'Npx' format (e.g., 1920 or 1920px)."},
        )


def parse_crop_value(value: str | None, dimension: int) -> int:
    """Parse crop value like '100' (pixels) or '10%' (percentage)."""
    if value is None:
        return 0
    s = str(value).strip()
    if not s:
        return 0
    try:
        if s.endswith("%"):
            percent = float(s[:-1])
            if percent < 0:
                raise ImageKitError(
                    "INVALID_CROP_VALUE",
                    f"Crop percentage must be non-negative: {value}",
                    {"suggestion": "Use a non-negative percentage value."},
                )
            return int(dimension * percent / 100.0)
        v = int(s)
        if v < 0:
            raise ImageKitError(
                "INVALID_CROP_VALUE",
                f"Crop value must be non-negative: {value}",
                {"suggestion": "Use a non-negative pixel or percentage value."},
            )
        return v
    except ValueError:
        raise ImageKitError(
            "INVALID_CROP_VALUE",
            f"Invalid crop value: {value}",
            {"suggestion": "Use pixels (e.g., 100) or percentage (e.g., 10%) format."},
        )


# --- Operations ---

def get_info(image_path: str) -> dict:
    """이미지 메타데이터 읽기: 크기, 포맷, DPI, EXIF 방향, 비율."""
    _validate_input(image_path)

    stat = os.stat(image_path)
    img, orientation_corrected = _load_image(image_path)
    width, height = img.size
    # 실제 콘텐츠 기반 포맷 사용
    fmt = _validate_format_by_content(image_path)
    dpi = _read_dpi(image_path)
    aspect_ratio = calculate_aspect_ratio(width, height)

    return {
        "file_name": os.path.basename(image_path),
        "file_size": stat.st_size,
        "file_size_human": format_file_size(stat.st_size),
        "width": width,
        "height": height,
        "format": fmt,
        "dpi": dpi,
        "aspect_ratio": aspect_ratio,
        "orientation_corrected": orientation_corrected,
    }


def resize_image(
    input_path: str,
    output_path: str,
    target_width: int = 0,
    target_height: int = 0,
    multiplier: float = 0.0,
    resize_mode: str = "fit",
    jpeg_quality: int = DEFAULT_QUALITY,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict:
    """fit/fill/exact 모드 또는 배율로 이미지를 리사이즈한다."""
    _validate_input(input_path)
    if not dry_run:
        _validate_output(output_path, overwrite)
    _validate_quality(jpeg_quality)

    if resize_mode not in ("fit", "fill", "exact"):
        raise ImageKitError(
            "INVALID_RESIZE_MODE",
            f"Invalid resize mode: {resize_mode}",
            {"suggestion": "Use one of: fit, fill, exact."},
        )

    img, _ = _load_image(input_path)
    orig_w, orig_h = img.size
    input_size = os.path.getsize(input_path)

    # Calculate target dimensions
    tw, th = _calc_target_dims(orig_w, orig_h, target_width, target_height, multiplier)

    # 리사이즈 수행
    if resize_mode == "fill" and tw > 0 and th > 0:
        resized = _resize_fill(img, tw, th)
    elif resize_mode == "exact" and tw > 0 and th > 0:
        resized = img.resize((tw, th), Image.LANCZOS)
    else:
        # fit 모드 (기본값)
        resized = _resize_fit(img, orig_w, orig_h, tw, th)

    out_w, out_h = resized.size

    if not dry_run:
        _save_image(resized, output_path, jpeg_quality)
        output_size = os.path.getsize(output_path)

    result: dict = {
        "operation": "resize",
        "input_path": input_path,
        "output_path": output_path,
        "input_width": orig_w,
        "input_height": orig_h,
        "output_width": out_w,
        "output_height": out_h,
    }
    if not dry_run:
        result["input_size"] = input_size
        result["output_size"] = output_size
    else:
        result["dry_run"] = True
    return result


def _calc_target_dims(
    orig_w: int, orig_h: int,
    target_w: int, target_h: int,
    multiplier: float,
) -> tuple[int, int]:
    """Calculate target dimensions from width/height/multiplier."""
    if multiplier > 0:
        if multiplier < MIN_MULTIPLIER or multiplier > MAX_MULTIPLIER:
            raise ImageKitError(
                "INVALID_DIMENSION",
                f"Multiplier must be {MIN_MULTIPLIER}-{MAX_MULTIPLIER}: {multiplier}",
                {"suggestion": f"Use a value between {MIN_MULTIPLIER} and {MAX_MULTIPLIER}."},
            )
        return int(orig_w * multiplier), int(orig_h * multiplier)

    if target_w == 0 and target_h == 0:
        raise ImageKitError(
            "INVALID_DIMENSION",
            "At least one of target-width, target-height, or multiplier must be specified.",
            {"suggestion": "Provide --target-width, --target-height, or --multiplier."},
        )

    # Fill in missing dimension preserving aspect ratio
    if target_w > 0 and target_h == 0:
        ratio = orig_h / orig_w
        target_h = max(1, int(target_w * ratio))
    elif target_h > 0 and target_w == 0:
        ratio = orig_w / orig_h
        target_w = max(1, int(target_h * ratio))

    return target_w, target_h


def _resize_fit(img: Image.Image, orig_w: int, orig_h: int, tw: int, th: int) -> Image.Image:
    """비율을 유지하면서 지정 크기 내에 맞추는 리사이즈. 업/다운스케일 동일 로직."""
    if tw > 0 and th > 0:
        w_ratio = tw / orig_w
        h_ratio = th / orig_h
        ratio = min(w_ratio, h_ratio)
        tw = max(1, int(orig_w * ratio))
        th = max(1, int(orig_h * ratio))
    return img.resize((tw, th), Image.LANCZOS)


def _resize_fill(img: Image.Image, tw: int, th: int) -> Image.Image:
    """Resize to fill target dimensions (may crop)."""
    orig_w, orig_h = img.size
    scale = max(tw / orig_w, th / orig_h)
    new_w = max(1, int(orig_w * scale))
    new_h = max(1, int(orig_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    # Center crop
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def crop_edges(
    input_path: str,
    output_path: str,
    crop_top: str | None = None,
    crop_bottom: str | None = None,
    crop_left: str | None = None,
    crop_right: str | None = None,
    auto_detect: bool = False,
    threshold: int = DEFAULT_THRESHOLD,
    jpeg_quality: int = DEFAULT_QUALITY,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict:
    """픽셀, 퍼센트 또는 자동 감지로 이미지 가장자리를 자른다."""
    _validate_input(input_path)
    if not dry_run:
        _validate_output(output_path, overwrite)
    _validate_quality(jpeg_quality)

    if threshold < 0 or threshold > MAX_THRESHOLD:
        raise ImageKitError(
            "INVALID_THRESHOLD",
            f"Threshold must be 0-{MAX_THRESHOLD}: {threshold}",
            {"suggestion": f"Enter a value between 0 and {MAX_THRESHOLD}."},
        )

    img, _ = _load_image(input_path)
    orig_w, orig_h = img.size
    input_size = os.path.getsize(input_path)

    # 크롭 값 파싱
    t = parse_crop_value(crop_top, orig_h)
    b = parse_crop_value(crop_bottom, orig_h)
    l = parse_crop_value(crop_left, orig_w)
    r = parse_crop_value(crop_right, orig_w)

    # 수동 크롭 값 존재 여부 확인
    has_manual = any([t, b, l, r])
    warning: str | None = None

    if auto_detect and has_manual:
        # auto-detect와 수동 값 동시 지정: 수동 값 우선, 경고 추가
        warning = "auto-detect was ignored because manual crop values were provided."
    elif auto_detect and not has_manual:
        # auto-detect만 지정: 자동 감지 사용
        t, b, l, r = auto_detect_edges(img, threshold)
    elif not auto_detect and not has_manual:
        # 소스 없음: 에러
        raise ImageKitError(
            "INVALID_CROP_VALUE",
            "No crop source specified.",
            {"suggestion": "Use --auto-detect or provide --crop-top/bottom/left/right values."},
        )

    # Validate crop won't eliminate the image
    out_w = orig_w - l - r
    out_h = orig_h - t - b
    if out_w <= 0 or out_h <= 0:
        raise ImageKitError(
            "CROP_ERROR",
            "Crop values exceed image dimensions.",
            {
                "original_size": f"{orig_w}x{orig_h}",
                "crop": f"top={t}, bottom={b}, left={l}, right={r}",
                "suggestion": "Reduce crop values.",
            },
        )

    # 크롭 수행 (dry_run이 아닐 때만)
    if not dry_run:
        cropped = img.crop((l, t, orig_w - r, orig_h - b))
        _save_image(cropped, output_path, jpeg_quality)
        output_size = os.path.getsize(output_path)
    else:
        output_size = None

    result: dict = {
        "operation": "crop",
        "input_path": input_path,
        "output_path": output_path,
        "input_width": orig_w,
        "input_height": orig_h,
        "output_width": out_w,
        "output_height": out_h,
        "crop_top": t,
        "crop_bottom": b,
        "crop_left": l,
        "crop_right": r,
    }
    if not dry_run:
        result["input_size"] = input_size
        result["output_size"] = output_size
    else:
        result["dry_run"] = True
    if warning:
        result["warning"] = warning
    return result


def auto_detect_edges(img: Image.Image, threshold: int = DEFAULT_THRESHOLD) -> tuple[int, int, int, int]:
    """Scan from each edge toward center to detect uniform borders.

    Uses top-left corner pixel as reference color.
    Returns (top, bottom, left, right) crop amounts in pixels.
    """
    width, height = img.size
    if width <= 1 or height <= 1:
        return (0, 0, 0, 0)

    # Ensure RGB for consistent comparison
    rgb = img.convert("RGB")
    pixels = rgb.load()
    ref_r, ref_g, ref_b = pixels[0, 0]

    def exceeds_threshold(x: int, y: int) -> bool:
        pr, pg, pb = pixels[x, y]
        return max(abs(pr - ref_r), abs(pg - ref_g), abs(pb - ref_b)) > threshold

    # Scan top
    top = 0
    for y in range(height - 1):
        if any(exceeds_threshold(x, y) for x in range(width)):
            break
        top = y + 1

    # Scan bottom
    bottom = 0
    for y in range(height - 1, 0, -1):
        if any(exceeds_threshold(x, y) for x in range(width)):
            break
        bottom = height - y

    # Scan left
    left = 0
    for x in range(width - 1):
        if any(exceeds_threshold(x, y) for y in range(height)):
            break
        left = x + 1

    # Scan right
    right = 0
    for x in range(width - 1, 0, -1):
        if any(exceeds_threshold(x, y) for y in range(height)):
            break
        right = width - x

    # Ensure at least 1px remains
    if top + bottom >= height:
        top = bottom = 0
    if left + right >= width:
        left = right = 0

    return (top, bottom, left, right)


def set_dpi(
    input_path: str,
    output_path: str,
    target_dpi: int,
    jpeg_quality: int = DEFAULT_QUALITY,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict:
    """JPEG(EXIF) 또는 PNG(pHYs)에 DPI 메타데이터를 설정한다."""
    _validate_input(input_path)
    if not dry_run:
        _validate_output(output_path, overwrite)
    _validate_quality(jpeg_quality)

    if target_dpi < MIN_DPI or target_dpi > MAX_DPI:
        raise ImageKitError(
            "INVALID_DPI",
            f"DPI must be {MIN_DPI}-{MAX_DPI}: {target_dpi}",
            {"suggestion": f"Enter a value between {MIN_DPI} and {MAX_DPI}. Common values: 72, 150, 300."},
        )

    fmt = _detect_format(input_path)
    # _load_image()로 EXIF 방향 자동 보정
    img, _ = _load_image(input_path)
    orig_w, orig_h = img.size
    input_size = os.path.getsize(input_path)

    # 원본 DPI 읽기
    original_dpi = _read_dpi(input_path)

    if not dry_run:
        if fmt == "jpeg":
            # EXIF에 DPI 태그 작성
            exif = img.getexif()
            exif[TAG_X_RESOLUTION] = target_dpi
            exif[TAG_Y_RESOLUTION] = target_dpi
            exif[TAG_RESOLUTION_UNIT] = 2  # inches
            # 방향 태그 제거 (이미 보정됨)
            exif.pop(TAG_ORIENTATION, None)
            _save_image(img, output_path, jpeg_quality, dpi=target_dpi, exif_bytes=exif.tobytes())
        else:
            # PNG: Pillow가 pHYs 청크로 DPI 기록
            _save_image(img, output_path, jpeg_quality, dpi=target_dpi)
        output_size = os.path.getsize(output_path)

    result: dict = {
        "operation": "set-dpi",
        "input_path": input_path,
        "output_path": output_path,
        "input_width": orig_w,
        "input_height": orig_h,
        "output_width": orig_w,
        "output_height": orig_h,
        "original_dpi": original_dpi,
        "target_dpi": target_dpi,
    }
    if not dry_run:
        result["input_size"] = input_size
        result["output_size"] = output_size
    else:
        result["dry_run"] = True
    return result


def convert_image(
    input_path: str,
    output_path: str,
    jpeg_quality: int = DEFAULT_QUALITY,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict:
    """PNG↔JPEG 포맷 변환."""
    _validate_input(input_path)
    if not dry_run:
        _validate_output(output_path, overwrite)
    _validate_quality(jpeg_quality)

    # 실제 콘텐츠 기반 포맷 확인
    input_fmt = _validate_format_by_content(input_path)
    output_fmt = _detect_format(output_path)

    if output_fmt not in ("jpeg", "png"):
        raise ImageKitError(
            "UNSUPPORTED_FORMAT",
            f"Unsupported output format: {output_fmt}",
            {"suggestion": "Output must be .jpg/.jpeg or .png"},
        )

    # 동일 포맷 변환 방지
    if input_fmt == output_fmt:
        raise ImageKitError(
            "SAME_FORMAT",
            f"Input and output formats are the same: {input_fmt}",
            {"suggestion": "Choose a different output format."},
        )

    img, _ = _load_image(input_path)
    input_size = os.path.getsize(input_path)
    orig_w, orig_h = img.size

    if output_fmt == "jpeg":
        # RGBA/P/LA → RGB (흰 배경으로 투명도 합성)
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
    elif output_fmt == "png":
        if img.mode not in ("RGBA", "RGB", "P", "L"):
            img = img.convert("RGBA")

    if not dry_run:
        _save_image(img, output_path, jpeg_quality)
        output_size = os.path.getsize(output_path)

    result: dict = {
        "operation": "convert",
        "input_path": input_path,
        "output_path": output_path,
        "input_width": orig_w,
        "input_height": orig_h,
        "output_width": orig_w,
        "output_height": orig_h,
        "input_format": input_fmt,
        "output_format": output_fmt,
    }
    if not dry_run:
        result["input_size"] = input_size
        result["output_size"] = output_size
    else:
        result["dry_run"] = True
    return result


def rotate_image(
    input_path: str,
    output_path: str,
    angle: int | None = None,
    flip: str | None = None,
    jpeg_quality: int = DEFAULT_QUALITY,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict:
    """이미지 회전(90/180/270) 및 반전(수평/수직)."""
    _validate_input(input_path)
    if not dry_run:
        _validate_output(output_path, overwrite)
    _validate_quality(jpeg_quality)

    if angle is None and flip is None:
        raise ImageKitError(
            "INVALID_INPUT",
            "At least one of --angle or --flip must be specified.",
            {"suggestion": "Use --angle (90, 180, 270) or --flip (horizontal, vertical)."},
        )
    if angle is not None and angle not in (90, 180, 270):
        raise ImageKitError(
            "INVALID_ANGLE",
            f"Angle must be 90, 180, or 270: {angle}",
            {"suggestion": "Use one of: 90, 180, 270."},
        )
    if flip is not None and flip not in ("horizontal", "vertical"):
        raise ImageKitError(
            "INVALID_FLIP",
            f"Flip must be horizontal or vertical: {flip}",
            {"suggestion": "Use one of: horizontal, vertical."},
        )

    img, _ = _load_image(input_path)
    input_size = os.path.getsize(input_path)
    orig_w, orig_h = img.size

    # 회전 먼저, 반전 나중에
    if angle is not None:
        # Pillow rotate는 반시계방향이므로 360-angle로 시계방향 구현
        img = img.rotate(360 - angle, expand=True)
    if flip == "horizontal":
        img = ImageOps.mirror(img)
    elif flip == "vertical":
        img = ImageOps.flip(img)

    out_w, out_h = img.size

    if not dry_run:
        _save_image(img, output_path, jpeg_quality)
        output_size = os.path.getsize(output_path)

    result: dict = {
        "operation": "rotate",
        "input_path": input_path,
        "output_path": output_path,
        "input_width": orig_w,
        "input_height": orig_h,
        "output_width": out_w,
        "output_height": out_h,
    }
    if not dry_run:
        result["input_size"] = input_size
        result["output_size"] = output_size
    else:
        result["dry_run"] = True
    return result
