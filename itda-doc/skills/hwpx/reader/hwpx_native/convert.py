"""Conversion entry points for the native HWPX package."""
from __future__ import annotations

import zlib
from pathlib import Path

from .hwp5.reader import Hwp5DependencyError, Hwp5FormatError, read_hwp5_file
from .hwpx.reader import HwpxFormatError, read_hwpx_file
from .layout_tables import unwrap_layout_tables
from .safe_archive import UnsafeArchiveError, open_zip, read_prefix
from .writer_html import write_html
from .writer_md import write_markdown


def convert_file(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    format: str = "md",
    extract_images: bool = True,
    images_dir: str | Path | None = None,
    unwrap_layout: bool = False,
) -> tuple[Path, int]:
    input_path = Path(input_path)
    output = Path(output_path) if output_path is not None else input_path.with_suffix(f".{format}")
    if format not in {"md", "markdown", "html"}:
        raise ValueError(f"unsupported output format: {format}")
    document = _read_input_file(input_path)
    if unwrap_layout:
        unwrap_layout_tables(document)
    if format == "html":
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(write_html(document), encoding="utf-8")
        return output, 0
    if images_dir is None and extract_images:
        images_dir = output.with_suffix("")
    markdown, image_count = write_markdown(document, images_dir=images_dir, extract_images=extract_images)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    return output, image_count


def convert_to_markdown(
    input_path: str | Path,
    *,
    output_path: str | Path | None = None,
    extract_images: bool = True,
    images_dir: str | Path | None = None,
    unwrap_layout: bool = False,
) -> str:
    input_path = Path(input_path)
    document = _read_input_file(input_path)
    if unwrap_layout:
        unwrap_layout_tables(document)
    resolved_images_dir = images_dir
    if resolved_images_dir is None and output_path is not None and extract_images:
        resolved_images_dir = Path(output_path).with_suffix("")
    markdown, _ = write_markdown(document, images_dir=resolved_images_dir, extract_images=extract_images)
    return markdown


OLE_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
HWPX_MIMETYPES = (b"application/hwp+zip", b"application/haansofthwp+zip")
FALLBACK_HINT = (
    "한글(한컴오피스)에서 열어 HWPX 로 저장한 뒤 다시 읽거나, SKILL.md 「읽기 — 이 리더가 못 읽는 형식」의 "
    "kordoc(npm) 대체 경로를 쓰세요"
)


class UnsupportedFormatError(ValueError):
    """이 리더가 읽지 못하는 입력 — 무엇인지와 대체 경로를 말한다(#16).

    `code` 는 실패 종류다(unsupported·encrypted·distribution_protected·unsafe_archive·corrupt·missing_dependency). 호출자·fuzz 게이트가
    메시지 문구가 아니라 이 값으로 가른다 — 코드 없는 실패는 게이트가 결함으로 센다(#29).
    """

    def __init__(self, message: str, *, code: str = "unsupported") -> None:
        super().__init__(message)
        self.code = code


class CorruptDocumentError(UnsupportedFormatError):
    """형식은 맞는데 내용이 깨진 문서 — 잘린 파일·비트 오류·깨진 XML·풀리지 않는 압축 스트림(#29)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="corrupt")


def detect_format(input_path: Path) -> str:
    """확장자가 아니라 **내용 서명**으로 판정한다 — 확장자가 틀린 실 공고가 실재한다(.hwpx 인데 OLE, #16).

    반환: hwp5 | hwpx | hwp3 | hwpml | ole-other | zip-other | unknown
    """
    with open(input_path, "rb") as fh:
        head = fh.read(4096)
    if head.startswith(OLE_MAGIC):
        return "hwp5"  # .doc/.xls 등 다른 OLE 는 파싱에서 가린다(read 단계)
    if head.startswith(b"HWP Document File"):
        return "hwp3"
    if head.startswith(b"PK\x03\x04"):
        import zipfile

        try:
            # 엔트리 목록을 만들기 전에 EOCD 로 개수부터 센다 — 목록 자체가 메모리를 먹는다(#27)
            with open_zip(input_path) as zf:
                names = set(zf.namelist())
                # 앞부분만 푼다 — mimetype 엔트리가 폭탄이어도 판별이 자원을 쓰지 않는다(#27)
                mimetype = read_prefix(zf, "mimetype").strip() if "mimetype" in names else b""
        except zipfile.BadZipFile:
            return "unknown"
        if mimetype in HWPX_MIMETYPES or "Contents/section0.xml" in names:
            return "hwpx"
        return "zip-other"
    stripped = head.lstrip(b"\xef\xbb\xbf").lstrip()
    if stripped.startswith(b"<") and b"<HWPML" in head.upper():
        return "hwpml"
    if head[:2] in (b"\xff\xfe", b"\xfe\xff") and "<HWPML".encode("utf-16-le" if head[:2] == b"\xff\xfe" else "utf-16-be") in head:
        return "hwpml"
    return "unknown"


def _read_input_file(input_path: Path):
    try:
        return _read_detected(input_path)
    except UnsafeArchiveError as exc:
        # 압축 폭탄·위조 ZIP·DOCTYPE·경로 탐색 — 트레이스백·부분 처리 대신 무엇이 걸렸는지 말한다(#27)
        raise UnsupportedFormatError(f"{input_path.name}: 안전하게 열 수 없는 파일입니다 — {exc}", code="unsafe_archive") from exc


def _read_detected(input_path: Path):
    kind = detect_format(input_path)
    if kind == "hwpx":
        try:
            return read_hwpx_file(input_path)
        except HwpxFormatError as exc:
            raise CorruptDocumentError(f"{input_path.name}: 손상된 HWPX 문서입니다 — {exc}. 한글에서 열어 다시 저장한 파일을 주세요") from exc
    if kind == "hwp5":
        try:
            return read_hwp5_file(input_path)
        except Hwp5DependencyError as exc:
            raise UnsupportedFormatError(
                f"{input_path.name}: HWP 5 문서를 읽으려면 olefile 패키지가 필요합니다 — "
                "python3 \"$SKILL_DIR/scripts/install_skill_deps.py\" 로 의존성을 설치한 뒤 다시 실행하세요",
                code="missing_dependency",
            ) from exc
        except Hwp5FormatError as exc:
            raise CorruptDocumentError(f"{input_path.name}: 손상된 HWP 5 문서입니다 — {exc}. 한글에서 열어 다시 저장한 파일을 주세요") from exc
        except zlib.error as exc:
            # 압축 스트림(DocInfo·본문)이 풀리지 않는다 — 잘렸거나 비트가 깨졌다(#29 fuzz 실측)
            raise CorruptDocumentError(f"{input_path.name}: 손상된 HWP 5 문서입니다 — 압축 스트림을 풀 수 없습니다({exc})") from exc
        except ValueError as exc:
            # 암호·배포용 보호 문서 — 본문을 읽을 수 없다. 트레이스백 대신 무엇인지와 조치를 말한다(#22 검수)
            message = str(exc)
            if message.startswith("hwp: encrypted"):
                raise UnsupportedFormatError(
                    f"{input_path.name}: 암호가 걸린 한글 문서입니다 — 한글에서 암호를 해제해 저장한 파일을 주세요",
                    code="encrypted",
                ) from exc
            if message.startswith("hwp: distribution-protected"):
                raise UnsupportedFormatError(
                    f"{input_path.name}: 배포용(보호) 한글 문서입니다 — 본문이 암호화돼 읽을 수 없습니다. "
                    "배포용이 아닌 원본을 주세요",
                    code="distribution_protected",
                ) from exc
            raise
        except (OSError, KeyError) as exc:
            # FileHeader·BodyText 스트림이 없는 OLE — Word .doc·Excel .xls 등, 또는 잘려 디렉터리가 깨진 HWP
            raise UnsupportedFormatError(
                f"{input_path.name}: 한글(HWP 5) 문서가 아니거나 손상된 OLE 파일입니다(Word .doc·Excel .xls 등일 수 있음) — {exc}"
            ) from exc
    names = {
        "hwp3": "HWP 3.x(1990년대 한글) 문서",
        "hwpml": "HWPML(.hml, 한글 XML) 문서",
        "zip-other": "한글 문서가 아닌 ZIP 파일(Word .docx·Excel .xlsx 등일 수 있음)",
        "unknown": "알 수 없는 형식",
    }
    raise UnsupportedFormatError(f"{input_path.name}: {names[kind]} — 이 리더는 HWP 5.x·HWPX 만 읽습니다. {FALLBACK_HINT}")
