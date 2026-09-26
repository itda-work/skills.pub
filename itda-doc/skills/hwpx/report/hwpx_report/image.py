from __future__ import annotations

from io import BytesIO
from pathlib import Path

from .models import ReportImage
from .profile import ImageEntry, xml_escape

REPORT_IMAGE_PX_TO_HU = 75
REPORT_IMAGE_MAX_WIDTH_HU = 47000
REPORT_IMAGE_FALLBACK_W_HU = 30000
REPORT_IMAGE_FALLBACK_H_HU = 22500
REPORT_IMAGE_MAX_PX = 50000


class ImageDependencyError(RuntimeError):
    pass


def render_report_image(ctx: object, image: ReportImage, idx: int, char_pr_id_ref: str) -> tuple[str, ImageEntry]:
    try:
        data = Path(image.src).read_bytes()
    except OSError as exc:
        raise OSError(f'hwpx report: read image "{image.src}": {exc}') from exc
    ext = _report_image_ext(image.src)
    bin_id = f"image{idx}"
    entry = ImageEntry(
        id=bin_id,
        href=f"BinData/{bin_id}.{ext}",
        media_type=_image_media_type_for_ext(ext),
        data=data,
    )
    nat_w, nat_h, disp_w, disp_h = _report_image_size_hu(data)
    return _build_report_pic_paragraph(ctx, bin_id, nat_w, nat_h, disp_w, disp_h, char_pr_id_ref), entry


def _report_image_ext(src: str) -> str:
    ext = Path(src).suffix.lower().removeprefix(".")
    if ext in {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif"}:
        return ext
    return "png"


def _image_media_type_for_ext(ext: str) -> str:
    if ext in {"jpg", "jpeg"}:
        return "image/jpeg"
    if ext == "gif":
        return "image/gif"
    if ext == "bmp":
        return "image/bmp"
    if ext in {"tiff", "tif"}:
        return "image/tiff"
    return "image/png"


def _report_image_size_hu(data: bytes) -> tuple[int, int, int, int]:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise ImageDependencyError(
            "hwpx report: 이미지 임베딩에 Pillow 필요 - pip install -r requirements.txt"
        ) from exc
    try:
        with Image.open(BytesIO(data)) as img:
            px_w, px_h = img.size
    except (OSError, UnidentifiedImageError):
        return (
            REPORT_IMAGE_FALLBACK_W_HU,
            REPORT_IMAGE_FALLBACK_H_HU,
            REPORT_IMAGE_FALLBACK_W_HU,
            REPORT_IMAGE_FALLBACK_H_HU,
        )
    if px_w <= 0 or px_h <= 0:
        return (
            REPORT_IMAGE_FALLBACK_W_HU,
            REPORT_IMAGE_FALLBACK_H_HU,
            REPORT_IMAGE_FALLBACK_W_HU,
            REPORT_IMAGE_FALLBACK_H_HU,
        )
    px_w = min(px_w, REPORT_IMAGE_MAX_PX)
    px_h = min(px_h, REPORT_IMAGE_MAX_PX)
    nat_w = px_w * REPORT_IMAGE_PX_TO_HU
    nat_h = px_h * REPORT_IMAGE_PX_TO_HU
    disp_w, disp_h = nat_w, nat_h
    if disp_w > REPORT_IMAGE_MAX_WIDTH_HU:
        disp_h = disp_h * REPORT_IMAGE_MAX_WIDTH_HU // disp_w
        disp_w = REPORT_IMAGE_MAX_WIDTH_HU
    if disp_h <= 0:
        disp_h = 1
    return nat_w, nat_h, disp_w, disp_h


def _build_report_pic_paragraph(
    ctx: object,
    bin_id: str,
    nat_w: int,
    nat_h: int,
    disp_w: int,
    disp_h: int,
    char_pr_id_ref: str,
) -> str:
    pic_id = str(1_000_000 + _report_image_seq(bin_id))
    cx, cy = str(disp_w // 2), str(disp_h // 2)
    dw, dh = str(disp_w), str(disp_h)
    nw, nh = str(nat_w), str(nat_h)
    return (
        f'<hp:p id="{ctx.paragraph_id()}" paraPrIDRef="18" styleIDRef="0" pageBreak="0" '
        f'columnBreak="0" merged="0"><hp:run charPrIDRef="{xml_escape(char_pr_id_ref)}">'
        f'<hp:pic id="{pic_id}" zOrder="0" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" '
        f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" '
        f'instid="{pic_id}" reverse="0">'
        '<hp:offset x="0" y="0"/>'
        f'<hp:orgSz width="{dw}" height="{dh}"/>'
        f'<hp:curSz width="{dw}" height="{dh}"/>'
        '<hp:flip horizontal="0" vertical="0"/>'
        f'<hp:rotationInfo angle="0" centerX="{cx}" centerY="{cy}" rotateimage="1"/>'
        '<hp:renderingInfo>'
        '<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        '<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        '<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        '</hp:renderingInfo>'
        f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{dw}" y="0"/>'
        f'<hc:pt2 x="{dw}" y="{dh}"/><hc:pt3 x="0" y="{dh}"/></hp:imgRect>'
        f'<hp:imgClip left="0" right="{nw}" top="0" bottom="{nh}"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        f'<hp:imgDim dimwidth="{nw}" dimheight="{nh}"/>'
        f'<hc:img binaryItemIDRef="{xml_escape(bin_id)}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
        '<hp:effects/>'
        f'<hp:sz width="{dw}" widthRelTo="ABSOLUTE" height="{dh}" heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
        'vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
        '</hp:pic></hp:run></hp:p>'
    )


def _report_image_seq(bin_id: str) -> int:
    if bin_id.startswith("image"):
        try:
            return int(bin_id.removeprefix("image"))
        except ValueError:
            return 0
    return 0
