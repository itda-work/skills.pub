from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReportRun:
    text: str = ""
    bold: bool = False
    italic: bool = False

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ReportRun":
        return cls(
            text=str(data.get("text", "")),
            bold=bool(data.get("bold", False)),
            italic=bool(data.get("italic", False)),
        )


@dataclass
class ReportCell:
    runs: list[ReportRun] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ReportCell":
        return cls(runs=[ReportRun.from_json(run) for run in data.get("runs", []) or []])


@dataclass
class ReportTable:
    template: str = ""
    headers: list[str] = field(default_factory=list)
    aligns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    rich_rows: list[list[ReportCell]] = field(default_factory=list)
    col_widths: list[int] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)
    caption: str = ""  # 표 위에 두는 제목(AI 친화 원칙 — 표·그림은 상단에 제목·번호)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ReportTable":
        rich_rows = [
            [ReportCell.from_json(cell or {}) for cell in row]
            for row in data.get("rich_rows", []) or []
        ]
        return cls(
            template=str(data.get("template", "")),
            headers=[str(x) for x in data.get("headers", []) or []],
            aligns=[str(x) for x in data.get("aligns", []) or []],
            rows=[[str(cell) for cell in row] for row in data.get("rows", []) or []],
            rich_rows=rich_rows,
            col_widths=[int(x) for x in data.get("col_widths", []) or []],
            summary=[str(x) for x in data.get("summary", []) or []],
            caption=str(data.get("caption", "") or ""),
        )


@dataclass
class ReportImage:
    src: str = ""
    alt: str = ""
    caption: str = ""

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ReportImage":
        return cls(src=str(data.get("src", "")), alt=str(data.get("alt", "")), caption=str(data.get("caption", "") or ""))


@dataclass
class ReportItem:
    level: int = 0
    text: str = ""
    kind: str = "item"  # item(항목기호 붙음) | prose(서술 문단 — ai-report 조판만 구분)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ReportItem":
        kind = str(data.get("kind", "item") or "item")
        return cls(level=int(data.get("level", 0)), text=str(data.get("text", "")), kind=kind)


@dataclass
class ReportBlock:
    item: ReportItem | None = None
    table: ReportTable | None = None
    image: ReportImage | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ReportBlock":
        return cls(
            item=ReportItem.from_json(data["item"]) if data.get("item") is not None else None,
            table=ReportTable.from_json(data["table"]) if data.get("table") is not None else None,
            image=ReportImage.from_json(data["image"]) if data.get("image") is not None else None,
        )


@dataclass
class ReportSection:
    heading: str = ""
    items: list[ReportItem] = field(default_factory=list)
    tables: list[ReportTable] = field(default_factory=list)
    blocks: list[ReportBlock] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ReportSection":
        return cls(
            heading=str(data.get("heading", "")),
            items=[ReportItem.from_json(item) for item in data.get("items", []) or []],
            tables=[ReportTable.from_json(table) for table in data.get("tables", []) or []],
            blocks=[ReportBlock.from_json(block) for block in data.get("blocks", []) or []],
        )


@dataclass
class DocSpec:
    title: str = ""
    report_date: str = ""
    dept: str = ""
    sections: list[ReportSection] = field(default_factory=list)
    tables: list[ReportTable] = field(default_factory=list)
    # 템플릿별 추가 필드(기안문의 수신·발신명의·기안자…, 표지의 기관명). 키는 manifest `fields` 가 정의.
    fields: dict[str, str] = field(default_factory=dict)
    attachments: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DocSpec":
        report_date = ""
        for key in ("report_date", "reportDate", "ReportDate"):
            value = str(data.get(key, "") or "").strip()
            if value:
                report_date = value
                break
        return cls(
            title=str(data.get("title", "")),
            report_date=report_date,
            dept=str(data.get("dept", "")),
            sections=[ReportSection.from_json(section) for section in data.get("sections", []) or []],
            tables=[ReportTable.from_json(table) for table in data.get("tables", []) or []],
            fields={str(k): str(v) for k, v in (data.get("fields", {}) or {}).items()},
            attachments=[str(x) for x in data.get("attachments", []) or []],
        )
