from __future__ import annotations

import importlib.util
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

VALID_MIMETYPES = {"application/hwp+zip", "application/haansofthwp+zip"}
REQUIRED_FILES = {
    "Contents/header.xml",
    "Contents/section0.xml",
    "Contents/content.hpf",
    "META-INF/container.xml",
}


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str = ""


@dataclass
class ValidationResult:
    checks: list[CheckResult]
    all_passed: bool


def _load_safe_archive():
    """ZIP 가드 정본(reader/hwpx_native/safe_archive.py, 표준 라이브러리만)을 파일로 읽는다 — 이 파일도 단독 로드된다(#27)."""
    cached = sys.modules.get("hwpx_safe_archive")
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parents[2] / "reader" / "hwpx_native" / "safe_archive.py"
    spec = importlib.util.spec_from_file_location("hwpx_safe_archive", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"ZIP 가드를 찾지 못했습니다: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hwpx_safe_archive"] = module
    spec.loader.exec_module(module)
    return module


def _unsafe_archive(data: bytes) -> str | None:
    """압축 폭탄·위조 CD·경로 탐색·DOCTYPE 이면 그 사유. XML 을 파싱하는 검사들보다 먼저 돈다(#27)."""
    guard = _load_safe_archive()
    try:
        with guard.open_zip(data) as zf:
            budget = guard.Budget()
            for info in zf.infolist():
                if info.filename.lower().endswith(guard.XML_SUFFIXES):
                    guard.read_entry(zf, info, budget)
    except guard.UnsafeArchiveError as exc:
        return str(exc)
    except zipfile.BadZipFile:
        return None  # 형식 오류는 아래 zipfile 이 그대로 말한다
    return None


def validate_archive(data: bytes) -> ValidationResult:
    unsafe = _unsafe_archive(data)
    if unsafe is not None:
        return ValidationResult(checks=[CheckResult("archive safety", False, unsafe)], all_passed=False)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        checks = [
            _check_mimetype_position(zf),
            _check_mimetype_compression(zf),
            _check_mimetype_content(zf),
            _check_required_files(zf),
            _check_xml_validity(zf),
            _check_section_continuity(zf),
            _check_bindata_refs(zf),
            _check_section_count(zf),
            _check_manifest_hrefs(zf),
        ]
    return ValidationResult(checks=checks, all_passed=all(c.passed for c in checks))


def _check_mimetype_position(zf: zipfile.ZipFile) -> CheckResult:
    name = "mimetype position"
    infos = zf.infolist()
    if not infos:
        return CheckResult(name, False, "archive is empty")
    if infos[0].filename != "mimetype":
        return CheckResult(name, False, f'first entry is "{infos[0].filename}", expected "mimetype"')
    return CheckResult(name, True)


def _check_mimetype_compression(zf: zipfile.ZipFile) -> CheckResult:
    name = "mimetype compression"
    infos = zf.infolist()
    if not infos or infos[0].filename != "mimetype":
        return CheckResult(name, False, "mimetype entry not found at position 0")
    if infos[0].compress_type != zipfile.ZIP_STORED:
        return CheckResult(name, False, f"mimetype uses method {infos[0].compress_type}, expected Store (0)")
    return CheckResult(name, True)


def _check_mimetype_content(zf: zipfile.ZipFile) -> CheckResult:
    name = "mimetype content"
    infos = zf.infolist()
    if not infos or infos[0].filename != "mimetype":
        return CheckResult(name, False, "mimetype entry not found at position 0")
    content = zf.read(infos[0]).decode().strip()
    if content not in VALID_MIMETYPES:
        return CheckResult(
            name,
            False,
            f'mimetype content is "{content}", expected application/hwp+zip or application/haansofthwp+zip',
        )
    return CheckResult(name, True)


def _check_required_files(zf: zipfile.ZipFile) -> CheckResult:
    name = "required files"
    names = set(zf.namelist())
    missing = sorted(REQUIRED_FILES - names)
    if missing:
        return CheckResult(name, False, "missing: " + ", ".join(missing))
    return CheckResult(name, True)


def _check_xml_validity(zf: zipfile.ZipFile) -> CheckResult:
    name = "XML validity"
    invalid: list[str] = []
    for info in zf.infolist():
        lower = info.filename.lower()
        if not (lower.endswith(".xml") or lower.endswith(".hpf")):
            continue
        try:
            ET.fromstring(zf.read(info))
        except ET.ParseError as exc:
            invalid.append(f"{info.filename}: {exc}")
    if invalid:
        return CheckResult(name, False, "; ".join(invalid))
    return CheckResult(name, True)


def _check_section_continuity(zf: zipfile.ZipFile) -> CheckResult:
    name = "section continuity"
    indices = sorted(_section_index(n) for n in zf.namelist() if _is_section_file(n))
    if not indices:
        return CheckResult(name, False, "no section files found")
    for expected, actual in enumerate(indices):
        if actual != expected:
            return CheckResult(name, False, f"gap detected: expected section{expected}, found section{actual}")
    return CheckResult(name, True)


def _check_bindata_refs(zf: zipfile.ZipFile) -> CheckResult:
    name = "BinData reference integrity"
    try:
        manifest = _parse_manifest(zf)
    except KeyError:
        return CheckResult(name, True)
    except ET.ParseError as exc:
        return CheckResult(name, False, str(exc))
    try:
        refs = _collect_bin_refs(zf)
    except ET.ParseError as exc:
        return CheckResult(name, False, str(exc))
    if not refs:
        return CheckResult(name, True)
    names = set(zf.namelist())
    problems: list[str] = []
    for ref in refs:
        href = manifest.get(ref)
        if not href:
            problems.append(f"{ref} not found in manifest")
            continue
        if f"Contents/{href}" not in names and href not in names:
            problems.append(f"{ref} (href={href}) not found in ZIP")
    if problems:
        return CheckResult(name, False, "; ".join(problems))
    return CheckResult(name, True)


def _check_section_count(zf: zipfile.ZipFile) -> CheckResult:
    """header.xml 의 secCnt 가 실제 섹션 파일 수와 같은가 (#10).

    한컴은 secCnt 로 섹션을 읽는다 — 어긋나면 뒤 섹션이 안 보이거나 열기를 거부한다. 속성이 없으면 판정하지 않는다.
    실 한컴 저장본 50개 실측에서 전부 일치."""
    name = "section count (secCnt)"
    try:
        root = ET.fromstring(zf.read("Contents/header.xml"))
    except (KeyError, ET.ParseError):
        return CheckResult(name, True)  # 파일 부재·파싱 오류는 required files·XML validity 가 보고한다
    declared = root.attrib.get("secCnt")
    if declared is None:
        return CheckResult(name, True)
    actual = sum(1 for n in zf.namelist() if _is_section_file(n))
    if not declared.isdigit() or int(declared) != actual:
        return CheckResult(name, False, f"header.xml secCnt={declared} but {actual} section file(s)")
    return CheckResult(name, True)


def _check_manifest_hrefs(zf: zipfile.ZipFile) -> CheckResult:
    """content.hpf 의 모든 item href 가 ZIP 안에 있는가 (#10) — 없는 파트를 가리키면 한컴독스가 거부한다.
    (BinData reference integrity 는 본문이 쓰는 그림만 본다.)"""
    name = "manifest hrefs"
    try:
        manifest = _parse_manifest(zf)
    except KeyError:
        return CheckResult(name, True)  # content.hpf 부재는 required files 가 보고한다
    except ET.ParseError as exc:
        return CheckResult(name, False, str(exc))
    names = set(zf.namelist())
    missing = sorted(f"{item_id} (href={href})" for item_id, href in manifest.items()
                     if href and href not in names and f"Contents/{href}" not in names)
    if missing:
        return CheckResult(name, False, "not found in ZIP: " + "; ".join(missing))
    return CheckResult(name, True)


def _parse_manifest(zf: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = ET.fromstring(zf.read("Contents/content.hpf"))
    except ET.ParseError as exc:
        raise ET.ParseError(f"Contents/content.hpf: {exc}") from exc
    result: dict[str, str] = {}
    for el in root.iter():
        if _local_name(el.tag) == "item":
            item_id = el.attrib.get("id", "")
            href = el.attrib.get("href", "")
            if item_id:
                result[item_id] = href
    return result


def _collect_bin_refs(zf: zipfile.ZipFile) -> list[str]:
    seen: set[str] = set()
    refs: list[str] = []
    for name in zf.namelist():
        if not _is_section_file(name):
            continue
        try:
            root = ET.fromstring(zf.read(name))
        except ET.ParseError as exc:
            raise ET.ParseError(f"{name}: {exc}") from exc
        for el in root.iter():
            for key, value in el.attrib.items():
                if _local_name(key) == "binaryItemIDRef" and value and value not in seen:
                    seen.add(value)
                    refs.append(value)
    return refs


def _is_section_file(name: str) -> bool:
    base = name.rsplit("/", 1)[-1]
    return base.startswith("section") and base.endswith(".xml")


def _section_index(name: str) -> int:
    base = name.rsplit("/", 1)[-1]
    match = re.match(r"section(\d+)\.xml$", base)
    return int(match.group(1)) if match else 0


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
