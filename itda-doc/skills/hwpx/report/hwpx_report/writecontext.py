from __future__ import annotations


class WriteContext:
    def __init__(self, next_paragraph_id: int = 1_000_000_001, next_table_id: int = 1) -> None:
        self.next_paragraph_id = next_paragraph_id
        self.next_table_id = next_table_id

    def paragraph_id(self) -> str:
        value = self.next_paragraph_id
        self.next_paragraph_id += 1
        return str(value)

    def table_id(self) -> str:
        value = self.next_table_id
        self.next_table_id += 1
        return str(value)
