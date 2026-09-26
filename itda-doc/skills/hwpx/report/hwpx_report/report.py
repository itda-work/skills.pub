from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from importlib import resources
from pathlib import Path, PurePosixPath

from .image import ImageDependencyError, render_report_image
from .layouts import LAYOUTS
from .models import DocSpec, ReportBlock, ReportImage, ReportItem, ReportTable
from .profile import MIME_TYPE, VERSION_XML, ImageEntry, SpecProfile, xml_escape
from .rawzip import RawZipWriter
from .table import render_report_table
from .validator import validate_archive
from .writecontext import WriteContext


class HWPXReportError(Exception):
    pass


@dataclass
class ReportStyle:
    charPrIDRef: str = ""
    paraPrIDRef: str = ""
    borderFillIDRef: str = ""


# 템플릿 리소스 경로 계약 — `tables/<id>.xml` 처럼 단순 이름 세그먼트만 (슬래시·역슬래시·'.'·'..' 금지).
# DocSpec table.template 은 사용자 입력이라, 이것이 없으면 '../../escape' 로 프로파일 루트 밖 XML 을 읽는다(Codex R2 F7).
RESOURCE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def check_resource_segment(name: str) -> bool:
    return bool(name) and name not in (".", "..") and bool(RESOURCE_SEGMENT_RE.match(name))


# 템플릿 디렉토리 계약 — 내장 템플릿과 사용자 프로파일(derive_profile.py 산출)이 같은 파일 집합을 갖는다.
TEMPLATE_REQUIRED_FILES = ("manifest.json", "style-map.json", "header.xml", "section0.skel.xml")


@dataclass
class ReportTemplate:
    id: str
    header: bytes
    section: str
    manifest: dict
    styles: dict[str, ReportStyle]
    # 리소스(tables/*.xml) 루트. None 이면 패키지 내장 템플릿(assets/templates/<id>/)이고,
    # 커스텀 템플릿 디렉토리(--template-dir)면 그 디렉토리다 — 표 템플릿 읽기가 여기를 경유한다.
    root: Path | None = None

    def read_resource(self, rel: str) -> bytes:
        """템플릿 상대 경로(`tables/basic.xml`)의 바이트. 없으면 FileNotFoundError(경로 포함).

        경로 이탈은 FileNotFoundError 가 아니라 HWPXReportError 다 — 호출부가 FileNotFoundError 를
        기본 템플릿 폴백으로 삼키므로, 거부가 조용한 폴백으로 위장되면 안 된다."""
        if "\\" in rel or not all(check_resource_segment(seg) for seg in rel.split("/")):
            raise HWPXReportError(f'hwpx report: invalid template resource path "{rel}" in template "{self.id}"')
        if self.root is not None:
            root = self.root.resolve()
            target = (root / rel).resolve()
            if target != root and root not in target.parents:
                raise HWPXReportError(
                    f'hwpx report: template resource "{rel}" escapes template root "{root}"'
                )
            if not target.is_file():
                raise FileNotFoundError(f"open {self.root / rel}: file does not exist")
            return target.read_bytes()
        base = resources.files("hwpx_report").joinpath("assets", "templates", self.id)
        try:
            return base.joinpath(rel).read_bytes()
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"open templates/{self.id}/{rel}: file does not exist") from exc

    def style(self, name: str) -> ReportStyle:
        try:
            return self.styles[name]
        except KeyError as exc:
            raise HWPXReportError(f'hwpx report: style "{name}" is missing in template "{self.id}"') from exc

    @property
    def layout(self) -> str:
        return str(self.manifest.get("layout", "") or "report")

    @property
    def max_level(self) -> int:
        """항목 계층 상한. manifest `max_level` 이 없으면 종전 계약(□/❍ 2단)."""
        try:
            value = int(self.manifest.get("max_level", 2))
        except (TypeError, ValueError):
            value = 2
        return max(1, min(value, 4))


def resolve_report_template(template: "str | Path | ReportTemplate") -> ReportTemplate:
    """템플릿 인자 해석 정문.

    **Path 는 언제나 디렉토리 로더**로 간다 — 문자열로 넘기면 '경로 구분자 없고 내장 id 가 실재하면 내장'
    규칙을 타서, 프로파일 디렉토리 이름이 `ai-report`·`gov-report` 면 사용자 프로파일이 조용히 무시된다
    (Claude R2 C-F2). `--template-dir`·compare 는 반드시 Path 로 넘긴다.
    """
    if isinstance(template, ReportTemplate):
        return template
    if isinstance(template, Path):
        return load_report_template_dir(template)
    return load_report_template(template)


def build_report(template_id: "str | Path | ReportTemplate", spec: DocSpec) -> bytes:
    tmpl = resolve_report_template(template_id)
    validate_report_spec(spec, tmpl.max_level)
    section, images = build_report_section_xml(tmpl, spec)
    data = package_report_hwpx(tmpl, section.encode(), spec, images)
    result = validate_archive(data)
    if not result.all_passed:
        failed = []
        for check in result.checks:
            if not check.passed:
                failed.append(f"{check.name}: {check.message}" if check.message else check.name)
        raise HWPXReportError("hwpx report: generated archive failed validation: " + "; ".join(failed))
    return data


def write_report_file(template_id: "str | Path | ReportTemplate", spec: DocSpec, output_path: str) -> None:
    if not output_path.strip():
        raise HWPXReportError("hwpx report: output path is required")
    Path(output_path).write_bytes(build_report(template_id, spec))


def load_report_template(template_id: str) -> ReportTemplate:
    """내장 템플릿 id 또는 **실존하는 템플릿 디렉토리 경로**를 받는다.

    구분 규칙: 경로 구분자가 없고 내장 템플릿이 실재하면 내장, 그 외에 실존 디렉토리면 커스텀 디렉토리
    (`derive_profile.py analyze` 산출 프로파일). 둘 다 아니면 종전 오류(잘못된 id / 파일 없음).
    """
    template_id = template_id.strip() or "gov-report"
    if "/" in template_id or "\\" in template_id:
        return load_report_template_dir(template_id)  # 경로 구분자가 있으면 디렉토리 의미(없으면 "not found")
    if not template_id.startswith(".") and _builtin_template_exists(template_id):
        return _load_builtin_template(template_id)
    if Path(template_id).is_dir():
        return load_report_template_dir(template_id)
    if template_id.startswith(".") or str(PurePosixPath(template_id)) != template_id:
        raise HWPXReportError(f'hwpx report: invalid template id "{template_id}"')
    return _load_builtin_template(template_id)


def _builtin_template_exists(template_id: str) -> bool:
    try:
        return resources.files("hwpx_report").joinpath("assets", "templates", template_id, "manifest.json").is_file()
    except (OSError, ValueError):
        return False


def _load_builtin_template(template_id: str) -> ReportTemplate:
    base = resources.files("hwpx_report").joinpath("assets", "templates", template_id)

    def read_bytes(name: str) -> bytes:
        try:
            return base.joinpath(name).read_bytes()
        except FileNotFoundError as exc:
            raise HWPXReportError(f"hwpx report: load {template_id}/{name}: {exc}") from exc

    return _build_template(template_id, read_bytes, root=None)


def load_report_template_dir(path: str | Path) -> ReportTemplate:
    """커스텀 템플릿 디렉토리(프로파일) 로더 — 실존·디렉토리·필수 파일·manifest id = 디렉토리명 을 검사한다."""
    root = Path(path)
    if not root.exists():
        raise HWPXReportError(f'hwpx report: template directory not found: "{root}"')
    if not root.is_dir():
        raise HWPXReportError(f'hwpx report: template path is not a directory: "{root}"')
    # 심볼릭 링크 루트는 기본 거부 — 링크 이름과 대상 이름이 달라 "manifest id = 준 디렉토리명" 계약이
    # 링크 대상 이름으로 우회된다(Codex R2 F7). 필요하면 실제 디렉토리 경로를 직접 지정하라.
    if root.is_symlink():
        raise HWPXReportError(
            f'hwpx report: template directory must not be a symbolic link: "{root}" '
            "(policy: pass the real directory path)"
        )
    missing = [name for name in TEMPLATE_REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        raise HWPXReportError(
            f'hwpx report: template directory "{root}" is missing required files: ' + ", ".join(missing)
        )
    # manifest id 는 **사용자가 준 경로의 basename**(resolve 전)과 대조한다 — resolve 하면 링크·상대경로가
    # 다른 이름으로 통과한다.
    template_id = root.name
    if not template_id:
        raise HWPXReportError(f'hwpx report: template directory needs a name: "{path}"')

    def read_bytes(name: str) -> bytes:
        try:
            return (root / name).read_bytes()
        except OSError as exc:
            raise HWPXReportError(f"hwpx report: load {root / name}: {exc}") from exc

    return _build_template(template_id, read_bytes, root=root.resolve(), require_manifest_id=True)


def _build_template(template_id: str, read_bytes, *, root: Path | None, require_manifest_id: bool = False) -> ReportTemplate:
    header = read_bytes("header.xml")
    section = read_bytes("section0.skel.xml").decode()
    try:
        manifest = json.loads(read_bytes("manifest.json").decode())
        raw_styles = json.loads(read_bytes("style-map.json").decode())
    except json.JSONDecodeError as exc:
        raise HWPXReportError(f'hwpx report: template "{template_id}" has invalid JSON: {exc}') from exc
    if not isinstance(manifest, dict) or not isinstance(raw_styles, dict):
        raise HWPXReportError(f'hwpx report: template "{template_id}" manifest/style-map must be JSON objects')
    if require_manifest_id and not manifest.get("id"):
        raise HWPXReportError(f'hwpx report: template "{template_id}" manifest.json must declare "id"')
    if manifest.get("id") and manifest["id"] != template_id:
        raise HWPXReportError(
            f'hwpx report: manifest id "{manifest["id"]}" does not match template id "{template_id}"'
        )
    styles = {
        name: ReportStyle(
            charPrIDRef=str(data.get("charPrIDRef", "")),
            paraPrIDRef=str(data.get("paraPrIDRef", "")),
            borderFillIDRef=str(data.get("borderFillIDRef", "")),
        )
        for name, data in raw_styles.items()
    }
    tmpl = ReportTemplate(template_id, header, section, manifest, styles, root=root)
    validate_report_template(tmpl)
    return tmpl


def validate_report_template(tmpl: ReportTemplate) -> None:
    if tmpl.layout != "report" and tmpl.layout not in LAYOUTS:
        raise HWPXReportError(f'hwpx report: template "{tmpl.id}" declares unknown layout "{tmpl.layout}"')
    for name in ("heading", "heading_spacer", "body_box", "blank"):
        tmpl.style(name)
    if tmpl.layout in LAYOUTS:
        for level in range(1, tmpl.max_level + 1):
            tmpl.style(f"level{level}")
    ids = collect_report_header_ids(tmpl.header)
    # 언어별 fontRef 실재 검사 — font id 공간은 언어별이라 hangul id 를 7개 언어에 복사하면
    # 존재하지 않는 참조가 생긴다(Codex R2 F5). style-map 이 가리키는 charPr 만 본다.
    bad_fonts = collect_report_missing_font_refs(
        tmpl.header, {st.charPrIDRef for st in tmpl.styles.values() if st.charPrIDRef}
    )
    if bad_fonts:
        shown = ", ".join(f"charPr {cid} {lang}={fid}" for cid, lang, fid in bad_fonts[:6])
        raise HWPXReportError(
            f'hwpx report: template "{tmpl.id}" references missing fontRef ids ({len(bad_fonts)}): {shown}'
        )
    for name, style in tmpl.styles.items():
        if style.charPrIDRef and style.charPrIDRef not in ids["charPr"]:
            raise HWPXReportError(f'hwpx report: style "{name}" references missing charPrIDRef {style.charPrIDRef}')
        if style.paraPrIDRef and style.paraPrIDRef not in ids["paraPr"]:
            raise HWPXReportError(f'hwpx report: style "{name}" references missing paraPrIDRef {style.paraPrIDRef}')
        if style.borderFillIDRef and style.borderFillIDRef not in ids["borderFill"]:
            raise HWPXReportError(
                f'hwpx report: style "{name}" references missing borderFillIDRef {style.borderFillIDRef}'
            )


FONT_REF_LANGS = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")


def collect_report_missing_font_refs(header: bytes, char_ids: set[str]) -> list[tuple[str, str, str]]:
    """`char_ids` 가 가리키는 charPr 의 fontRef 중 그 **언어의 fontface 에 없는** (charPr id, 언어, font id) 목록."""
    try:
        root = ET.fromstring(header)
    except ET.ParseError as exc:
        raise HWPXReportError(f"hwpx report: header.xml is not well-formed: {exc}") from exc
    faces: dict[str, set[str]] = {}
    for el in root.iter():
        if _local_name(el.tag) != "fontface":
            continue
        lang = (el.attrib.get("lang") or "").lower()
        block = faces.setdefault(lang, set())
        for font in el:
            if _local_name(font.tag) == "font" and font.attrib.get("id"):
                block.add(font.attrib["id"])
    if not faces:
        return []  # fontface 선언이 없는 header — 검사 대상이 아니다
    missing: list[tuple[str, str, str]] = []
    for el in root.iter():
        if _local_name(el.tag) != "charPr":
            continue
        cid = el.attrib.get("id", "")
        if cid not in char_ids:
            continue
        for ref in el:
            if _local_name(ref.tag) != "fontRef":
                continue
            for lang in FONT_REF_LANGS:
                fid = ref.attrib.get(lang)
                if fid is None or lang not in faces:
                    continue
                if fid not in faces[lang]:
                    missing.append((cid, lang, fid))
    return missing


def collect_report_header_ids(header: bytes) -> dict[str, set[str]]:
    ids = {"charPr": set(), "paraPr": set(), "borderFill": set()}
    try:
        root = ET.fromstring(header)
    except ET.ParseError as exc:
        raise HWPXReportError(f"hwpx report: header.xml is not well-formed: {exc}") from exc
    for el in root.iter():
        local = _local_name(el.tag)
        if local in ids and el.attrib.get("id"):
            ids[local].add(el.attrib["id"])
    return ids


def validate_report_spec(spec: DocSpec, max_level: int = 2) -> None:
    for si, section in enumerate(spec.sections):
        for ii, item in enumerate(section.items):
            validate_report_item(item, f"sections[{si}].items[{ii}]", max_level)
        for ti, table in enumerate(section.tables):
            validate_report_table(table, f"sections[{si}].tables[{ti}]")
        for bi, block in enumerate(section.blocks):
            path = f"sections[{si}].blocks[{bi}]"
            validate_report_block(block, path, max_level)
    for ti, table in enumerate(spec.tables):
        validate_report_table(table, f"tables[{ti}]")


def validate_report_block(block: ReportBlock, path: str, max_level: int = 2) -> None:
    set_count = sum(value is not None for value in (block.item, block.table, block.image))
    if set_count > 1:
        raise HWPXReportError(f"hwpx report: {path} must set exactly one of item/table/image")
    if block.item is not None:
        validate_report_item(block.item, f"{path}.item", max_level)
    elif block.table is not None:
        validate_report_table(block.table, f"{path}.table")
    elif block.image is not None:
        validate_report_image(block.image, f"{path}.image")
    else:
        raise HWPXReportError(f"hwpx report: {path} must set one of item/table/image")


def validate_report_image(image: ReportImage, path: str) -> None:
    if not image.src.strip():
        raise HWPXReportError(f"hwpx report: {path}.src is required")


def validate_report_item(item: ReportItem, path: str, max_level: int = 2) -> None:
    if item.kind not in ("item", "prose"):
        raise HWPXReportError(f'hwpx report: {path}.kind must be item or prose, got "{item.kind}"')
    if not 1 <= item.level <= max_level:
        raise HWPXReportError(f"hwpx report: {path}.level must be between 1 and {max_level}")
    if not item.text.strip():
        raise HWPXReportError(f"hwpx report: {path}.text is required")


def validate_report_table(table: ReportTable, path: str) -> None:
    if not table.headers:
        raise HWPXReportError(f"hwpx report: {path}.headers must not be empty")
    for ri, row in enumerate(table.rows):
        if len(row) != len(table.headers):
            raise HWPXReportError(f"hwpx report: {path}.rows[{ri}] has {len(row)} cells, want {len(table.headers)}")
    if table.aligns:
        if len(table.aligns) != len(table.headers):
            raise HWPXReportError(f"hwpx report: {path}.aligns has {len(table.aligns)} entries, want {len(table.headers)}")
        for ci, align in enumerate(table.aligns):
            if align.strip().lower() not in {"", "none", "left", "right", "center"}:
                raise HWPXReportError(f'hwpx report: {path}.aligns[{ci}] "{align}" must be left|right|center|none')
    if table.rich_rows:
        if len(table.rich_rows) != len(table.rows):
            raise HWPXReportError(
                f"hwpx report: {path}.rich_rows has {len(table.rich_rows)} rows, want {len(table.rows)}"
            )
        for ri, rich_row in enumerate(table.rich_rows):
            if len(rich_row) != len(table.headers):
                raise HWPXReportError(
                    f"hwpx report: {path}.rich_rows[{ri}] has {len(rich_row)} cells, want {len(table.headers)}"
                )
    if table.col_widths:
        if len(table.col_widths) != len(table.headers):
            raise HWPXReportError(
                f"hwpx report: {path}.col_widths has {len(table.col_widths)} entries, want {len(table.headers)}"
            )
        for ci, width in enumerate(table.col_widths):
            if width <= 0:
                raise HWPXReportError(f"hwpx report: {path}.col_widths[{ci}] {width} must be positive")


def build_report_section_xml(tmpl: ReportTemplate, spec: DocSpec) -> tuple[str, list[ImageEntry]]:
    section = replace_report_placeholders(tmpl.section, spec) if tmpl.manifest.get("placeholders") else tmpl.section
    if tmpl.layout in LAYOUTS:
        body, images = LAYOUTS[tmpl.layout](tmpl, spec, _render_table, _render_image)
    else:
        body, images = build_report_body_xml(tmpl, spec)
    if not body:
        return section, images
    close_idx = section.rfind("</hs:sec>")
    if close_idx < 0:
        raise HWPXReportError("hwpx report: section skeleton missing </hs:sec>")
    return section[:close_idx] + body + section[close_idx:], images


def replace_report_placeholders(section: str, spec: DocSpec) -> str:
    title = spec.title.strip() or "보고자료 제목"
    report_date = normalize_report_date(spec.report_date)
    year2, date_suffix = split_report_date_for_template(report_date)
    dept = spec.dept.strip() or "부서명"
    replacements = [
        (". MM. DD., 부서명)", f"{date_suffix}, {dept})"),
        ("YY", year2),
        ("보고자료 제목", title),
    ]
    for token, value in replacements:
        section = section.replace(token, xml_escape(value))
    return section


def normalize_report_date(value: str) -> str:
    value = value.strip()
    if value:
        parsed = parse_report_date(value)
        return format_report_date(parsed) if parsed else value
    return format_report_date(date.today())


def parse_report_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%Y. %m. %d.", "%y. %m. %d.", "%Y.%m.%d.", "%y.%m.%d."):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def format_report_date(value: date) -> str:
    return f"{value.year % 100:02d}. {value.month}. {value.day}."


def split_report_date_for_template(value: str) -> tuple[str, str]:
    parts = value.strip().split(".", 1)
    if len(parts) != 2:
        now = date.today()
        return f"{now.year % 100:02d}", ". " + value.strip()
    year = parts[0].strip()
    if len(year) >= 2:
        year = year[-2:]
    return year, "." + parts[1]


def build_report_body_xml(tmpl: ReportTemplate, spec: DocSpec) -> tuple[str, list[ImageEntry]]:
    heading_style = tmpl.style("heading")
    spacer_style = tmpl.style("heading_spacer")
    body_style = tmpl.style("body_box")
    blank_style = tmpl.style("blank")

    ctx = WriteContext()
    images: list[ImageEntry] = []
    img_idx = 1
    parts: list[str] = []
    for index, section in enumerate(spec.sections):
        heading = section.heading.strip()
        has_body = bool(section.items or section.blocks)
        if heading:
            parts.append(append_report_paragraph(ctx, heading_style, heading))
            if has_body:
                parts.append(append_report_paragraph(ctx, spacer_style, ""))
        if section.blocks:
            for block in section.blocks:
                if block.item is not None:
                    parts.append(append_report_paragraph(ctx, body_style, format_report_item_text(block.item)))
                elif block.table is not None:
                    parts.append(_render_table(ctx, block.table, tmpl))
                elif block.image is not None:
                    rendered, entry = _render_image(ctx, block.image, img_idx, body_style.charPrIDRef)
                    img_idx += 1
                    images.append(entry)
                    parts.append(rendered)
        else:
            for item in section.items:
                parts.append(append_report_paragraph(ctx, body_style, format_report_item_text(item)))
            for table in section.tables:
                parts.append(_render_table(ctx, table, tmpl))
        if index < len(spec.sections) - 1:
            parts.append(append_report_paragraph(ctx, blank_style, ""))
    for table in spec.tables:
        parts.append(_render_table(ctx, table, tmpl))
    return "".join(parts), images


def _render_table(ctx: WriteContext, table: ReportTable, tmpl: ReportTemplate) -> str:
    try:
        return render_report_table(ctx, table, tmpl)
    except FileNotFoundError as exc:
        raise HWPXReportError(str(exc)) from exc
    except NotImplementedError as exc:
        raise HWPXReportError(str(exc)) from exc


def _render_image(ctx: WriteContext, image: ReportImage, img_idx: int, char_pr_id_ref: str) -> tuple[str, ImageEntry]:
    try:
        return render_report_image(ctx, image, img_idx, char_pr_id_ref)
    except ImageDependencyError as exc:
        raise HWPXReportError(str(exc)) from exc
    except OSError as exc:
        raise HWPXReportError(str(exc)) from exc
    except NotImplementedError as exc:
        raise HWPXReportError(str(exc)) from exc


def append_report_paragraph(ctx: WriteContext, style: ReportStyle, text: str) -> str:
    return (
        f'<hp:p id="{ctx.paragraph_id()}" styleIDRef="0" paraPrIDRef="{xml_escape(style.paraPrIDRef)}" '
        f'pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{xml_escape(style.charPrIDRef)}"><hp:t>{xml_escape(text)}</hp:t></hp:run>'
        "</hp:p>"
    )


def format_report_item_text(item: ReportItem) -> str:
    text = item.text.strip()
    if item.kind == "prose":
        return text  # 서술 문단은 기호 없이(보도자료 리드문·인용문 — #1652 D-5)
    if item.level == 1:
        return text if text.startswith("□") else "□ " + text
    if item.level == 2:
        left_trimmed = text.lstrip(" \t")
        return "  " + left_trimmed if left_trimmed.startswith("❍") else "  ❍ " + text
    return text


def package_report_hwpx(tmpl: ReportTemplate, section: bytes, spec: DocSpec, images: list[ImageEntry]) -> bytes:
    zw = RawZipWriter()
    profile = SpecProfile()
    zw.add_store("mimetype", MIME_TYPE.encode())
    zw.add_deflate("Contents/header.xml", tmpl.header)
    zw.add_deflate("Contents/section0.xml", section)
    zw.add_deflate("version.xml", VERSION_XML.encode())
    zw.add_deflate("Contents/content.hpf", profile.build_content_hpf(images, 1, spec.title, "hyve.hwpx.report"))
    zw.add_deflate("settings.xml", profile.build_settings_xml())
    zw.add_deflate("Preview/PrvText.txt", build_report_preview_text(spec))
    zw.add_deflate("META-INF/container.xml", profile.build_container_xml())
    zw.add_deflate("META-INF/manifest.xml", profile.build_manifest_xml())
    zw.add_deflate("META-INF/container.rdf", profile.build_container_rdf())
    for image in images:
        zw.add_store(image.href, image.data)
    return zw.finish()


def build_report_preview_text(spec: DocSpec) -> bytes:
    lines: list[str] = []
    if spec.title.strip():
        lines.append(spec.title.strip())
    for section in spec.sections:
        if section.heading.strip():
            lines.append(section.heading.strip())
        if section.blocks:
            for block in section.blocks:
                if block.item is not None:
                    lines.append(format_report_item_text(block.item))
        else:
            for item in section.items:
                lines.append(format_report_item_text(item))
    for attachment in spec.attachments:
        if attachment.strip():
            lines.append("붙임 " + attachment.strip())
    text = "\n".join(lines).strip() or "Document"
    return (text + "\n").encode()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
