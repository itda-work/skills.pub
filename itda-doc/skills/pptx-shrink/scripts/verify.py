#!/usr/bin/env python3
"""pptx 두 파일의 무손실 대조 — 슬라이드 수 · 슬라이드별 텍스트 · 발표자 노트 · 그림 수 · rels 참조 실재.

    python3 verify.py <원본.pptx> <변환본.pptx> [--json]
exit 0 일치 · 1 불일치 · 4 입력 오류

이미지 바이트는 비교하지 않는다(그것이 바뀌는 게 목적이다). 비교하는 것은 "이미지를 바꿔도
바뀌면 안 되는 것" 전부다. stdlib 만 쓴다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

SLIDE_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
PART_RE = re.compile(r"^ppt/(slideLayouts|slideMasters|notesMasters|notesSlides)/[^/]+\.xml$")
NOTES_RE = re.compile(r"^ppt/notesSlides/notesSlide(\d+)\.xml$")
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def _texts(xml: bytes) -> list[str]:
    root = ET.fromstring(xml)
    return [t.text or "" for t in root.iter(f"{{{NS_A}}}t")]


def _pics(xml: bytes) -> int:
    root = ET.fromstring(xml)
    return sum(1 for _ in root.iter(f"{{{NS_P}}}pic"))


def _rels_targets(z: zipfile.ZipFile) -> list[tuple[str, str]]:
    """(rels 파일, 미해결 Target) — 내부 참조인데 zip 에 없는 것만."""
    missing = []
    names = set(z.namelist())
    for name in names:
        if not name.lower().endswith(".rels"):
            continue
        try:
            root = ET.fromstring(z.read(name))
        except ET.ParseError:
            missing.append((name, "<parse error>"))
            continue
        base = os.path.dirname(os.path.dirname(name))  # ppt/slides/_rels/x.rels → ppt/slides
        for rel in root.iter(f"{{{NS_REL}}}Relationship"):
            if rel.get("TargetMode") == "External":
                continue
            tgt = rel.get("Target") or ""
            if tgt.startswith("/"):
                resolved = tgt.lstrip("/")
            else:
                resolved = os.path.normpath(os.path.join(base, tgt)).replace(os.sep, "/")
            if resolved not in names:
                missing.append((name, tgt))
    return missing


def _content_type_exts(z: zipfile.ZipFile) -> set[str]:
    try:
        root = ET.fromstring(z.read("[Content_Types].xml"))
    except KeyError:
        return set()
    return {(d.get("Extension") or "").lower() for d in root.iter() if d.tag.endswith("}Default")}


def snapshot(path: str) -> dict:
    with zipfile.ZipFile(path, "r") as z:
        names = z.namelist()
        slides = sorted((int(SLIDE_RE.match(n).group(1)), n) for n in names if SLIDE_RE.match(n))
        notes = sorted((int(NOTES_RE.match(n).group(1)), n) for n in names if NOTES_RE.match(n))
        snap = {
            "slide_count": len(slides),
            "slide_texts": {i: _texts(z.read(n)) for i, n in slides},
            "slide_pics": {i: _pics(z.read(n)) for i, n in slides},
            "part_pics": {n: _pics(z.read(n)) for n in names if PART_RE.match(n)},  # 레이아웃·마스터의 그림도 센다
            "notes_texts": {i: _texts(z.read(n)) for i, n in notes},
            "missing_targets": _rels_targets(z),
            "media_exts": {os.path.splitext(n)[1].lower().lstrip(".") for n in names if n.startswith("ppt/media/")},
            "content_type_exts": _content_type_exts(z),
        }
    return snap


def compare(original: str, converted: str) -> dict:
    a, b = snapshot(original), snapshot(converted)
    problems: list[str] = []
    if a["slide_count"] != b["slide_count"]:
        problems.append(f"슬라이드 수 {a['slide_count']} → {b['slide_count']}")
    for i, ta in a["slide_texts"].items():
        tb = b["slide_texts"].get(i)
        if tb != ta:
            problems.append(f"슬라이드 {i} 텍스트 불일치")
    for i, pa in a["slide_pics"].items():
        pb = b["slide_pics"].get(i)
        if pb != pa:
            problems.append(f"슬라이드 {i} 그림 수 {pa} → {pb}")
    for n, pa in a["part_pics"].items():
        pb = b["part_pics"].get(n)
        if pb != pa:
            problems.append(f"{n} 그림 수 {pa} → {pb}")
    if a["notes_texts"] != b["notes_texts"]:
        problems.append("발표자 노트 불일치")
    for rels, tgt in b["missing_targets"]:
        if (rels, tgt) not in a["missing_targets"]:  # 원본에도 있던 고아 참조는 우리 책임이 아니다
            problems.append(f"참조 끊김 {rels} → {tgt}")
    undeclared = b["media_exts"] - b["content_type_exts"]
    if undeclared:
        problems.append(f"[Content_Types] 미선언 확장자 {sorted(undeclared)}")
    return {
        "ok": not problems,
        "problems": problems,
        "slide_count": a["slide_count"],
        "text_runs": sum(len(v) for v in a["slide_texts"].values()),
        "notes_slides": len(a["notes_texts"]),
        "pictures": sum(a["slide_pics"].values()),
        "preexisting_missing_targets": len(a["missing_targets"]),
    }


def format_report(r: dict) -> str:
    head = ("PASS" if r["ok"] else "FAIL") + (
        f" — 슬라이드 {r['slide_count']}장 · 텍스트 런 {r['text_runs']} · 노트 {r['notes_slides']}장 · 그림 {r['pictures']}개")
    lines = [head] + [f"  - {p}" for p in r["problems"]]
    if r["preexisting_missing_targets"]:
        lines.append(f"  (원본에도 있던 미해결 참조 {r['preexisting_missing_targets']}건 — 판정 제외)")
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("converted")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    for p in (a.original, a.converted):
        if not zipfile.is_zipfile(p):
            print(f"오류: pptx(zip) 가 아닙니다: {p}", file=sys.stderr)
            return 4
    r = compare(a.original, a.converted)
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else format_report(r))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
