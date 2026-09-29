"""레이아웃 래퍼 표 해체 (#13, 옵트인).

공고·안내문은 본문 전체를 1×1 표나 한 열짜리 표로 감싸 테두리·배경을 그린다. 그 표를 의미표로 쓰면 본문이
셀 하나 안 `<br>` 덩어리가 되어 절·목록·안쪽 표 구조가 사라진다. 이 모듈은 그런 **래퍼**만 풀어 셀 내용을
본문 블록으로 올린다.

판정은 보수적이다 — 1열 표도 의미표(목차·항목 나열)일 수 있어, 모든 셀이 "문서 조각" 일 때만 푼다:
  - 1×1 표: 셀이 무거우면(아래) 푼다
  - N×1 표(모든 행이 셀 하나, 병합 없음): **모든** 셀이 무거울 때만 푼다
  - 무거운 셀 = 안쪽 표를 품었거나, 비지 않은 문단이 3개 이상이거나, 글자가 300자 이상
그 밖(열이 둘 이상인 표, 가벼운 셀이 하나라도 있는 1열 표)은 그대로 둔다. 푼 내용은 다시 판정한다(래퍼 안의 래퍼).
"""
from __future__ import annotations

from . import document as docir

HEAVY_PARAGRAPHS = 3
HEAVY_CHARS = 300


def _text_len(blocks: list[docir.Block]) -> int:
    total = 0
    for block in blocks:
        if isinstance(block, (docir.Paragraph, docir.Heading)):
            total += sum(len(_inline_text(i)) for i in block.children)
        elif isinstance(block, docir.Table):
            total += sum(_text_len(cell.children) for row in block.rows for cell in row.cells)
    return total


def _inline_text(inline: docir.Inline) -> str:
    if isinstance(inline, docir.Text):
        return inline.value
    return "".join(_inline_text(c) for c in getattr(inline, "children", []) or [])


def _is_heavy(cell: docir.TableCell) -> bool:
    if any(isinstance(b, docir.Table) for b in cell.children):
        return True
    paragraphs = [b for b in cell.children
                  if isinstance(b, (docir.Paragraph, docir.Heading)) and "".join(_inline_text(i) for i in b.children).strip()]
    return len(paragraphs) >= HEAVY_PARAGRAPHS or _text_len(cell.children) >= HEAVY_CHARS


def is_layout_wrapper(table: docir.Table) -> bool:
    if not table.rows or any(len(row.cells) != 1 for row in table.rows):
        return False
    cells = [row.cells[0] for row in table.rows]
    if any(cell.col_span > 1 or cell.row_span > 1 for cell in cells):
        return False
    return all(_is_heavy(cell) for cell in cells)


def unwrap_blocks(blocks: list[docir.Block], depth: int = 0) -> tuple[list[docir.Block], int]:
    """래퍼 표를 풀어 새 블록 목록과 푼 표 수를 돌려준다. 의미표 안쪽의 래퍼는 건드리지 않는다(셀 구조가 의미다)."""
    out: list[docir.Block] = []
    count = 0
    for block in blocks:
        if isinstance(block, docir.Table) and depth < 16 and is_layout_wrapper(block):
            inner: list[docir.Block] = []
            for row in block.rows:
                inner.extend(row.cells[0].children)
            unwrapped, n = unwrap_blocks(inner, depth + 1)
            out.extend(unwrapped)
            count += 1 + n
        else:
            out.append(block)
    return out, count


def unwrap_layout_tables(document: docir.Document) -> int:
    """문서 본문의 래퍼 표를 제자리에서 푼다. 푼 표 수를 돌려준다."""
    document.blocks, count = unwrap_blocks(document.blocks)
    for section in document.sections:
        section.blocks, _ = unwrap_blocks(section.blocks)
    return count
