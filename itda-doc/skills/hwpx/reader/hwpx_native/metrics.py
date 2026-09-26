"""Audit metrics used by HWPX fixture tests."""
from __future__ import annotations

from dataclasses import dataclass

from . import document as docir


@dataclass(slots=True)
class DocumentMetrics:
    paragraphs: int = 0
    headings: int = 0
    tables: int = 0
    images: int = 0
    table_cells: int = 0
    non_empty_table_cells: int = 0
    bold_inlines: int = 0
    italic_inlines: int = 0
    underline_inlines: int = 0
    strikethroughs: int = 0
    styled_texts: int = 0

    def table_cell_fill_rate(self) -> float:
        if self.table_cells == 0:
            return 0.0
        return self.non_empty_table_cells / self.table_cells


def collect_document_metrics(document: docir.Document | None) -> DocumentMetrics:
    metrics = DocumentMetrics()
    if document is None:
        return metrics
    for block in document.blocks:
        _collect_block(metrics, block)
    return metrics


def _collect_block(metrics: DocumentMetrics, block: docir.Block) -> None:
    if isinstance(block, docir.Paragraph):
        metrics.paragraphs += 1
        _collect_inlines(metrics, block.children)
    elif isinstance(block, docir.Heading):
        metrics.headings += 1
        _collect_inlines(metrics, block.children)
    elif isinstance(block, docir.Table):
        metrics.tables += 1
        for row in block.rows:
            for cell in row.cells:
                metrics.table_cells += 1
                if _blocks_plain_text(cell.children).strip():
                    metrics.non_empty_table_cells += 1
                for child in cell.children:
                    _collect_block(metrics, child)
    elif isinstance(block, docir.List):
        for item in block.items:
            for child in item.children:
                _collect_block(metrics, child)
    elif isinstance(block, docir.Image):
        metrics.images += 1


def _collect_inlines(metrics: DocumentMetrics, inlines: list[docir.Inline]) -> None:
    for inline in inlines:
        if isinstance(inline, docir.Text):
            if inline.style is not None and inline.style.has_values():
                metrics.styled_texts += 1
        elif isinstance(inline, docir.Bold):
            metrics.bold_inlines += 1
            _collect_inlines(metrics, inline.children)
        elif isinstance(inline, docir.Italic):
            metrics.italic_inlines += 1
            _collect_inlines(metrics, inline.children)
        elif isinstance(inline, docir.Underline):
            metrics.underline_inlines += 1
            _collect_inlines(metrics, inline.children)
        elif isinstance(inline, docir.Strikethrough):
            metrics.strikethroughs += 1
            _collect_inlines(metrics, inline.children)
        elif isinstance(inline, docir.Link):
            _collect_inlines(metrics, inline.children)


def _blocks_plain_text(blocks: list[docir.Block]) -> str:
    parts: list[str] = []
    for block in blocks:
        _write_block_text(parts, block)
    return "".join(parts)


def _write_block_text(parts: list[str], block: docir.Block) -> None:
    if isinstance(block, docir.Paragraph | docir.Heading):
        _write_inline_text(parts, block.children)
    elif isinstance(block, docir.Table):
        for row in block.rows:
            for cell in row.cells:
                for child in cell.children:
                    _write_block_text(parts, child)
    elif isinstance(block, docir.List):
        for item in block.items:
            for child in item.children:
                _write_block_text(parts, child)
    elif isinstance(block, docir.CodeBlock):
        parts.append(block.code)


def _write_inline_text(parts: list[str], inlines: list[docir.Inline]) -> None:
    for inline in inlines:
        if isinstance(inline, docir.Text):
            parts.append(inline.value)
        elif isinstance(inline, docir.Bold | docir.Italic | docir.Underline | docir.Strikethrough):
            _write_inline_text(parts, inline.children)
        elif isinstance(inline, docir.Link):
            _write_inline_text(parts, inline.children)
        elif isinstance(inline, docir.Code):
            parts.append(inline.value)
        elif isinstance(inline, docir.LineBreak):
            parts.append("\n")
