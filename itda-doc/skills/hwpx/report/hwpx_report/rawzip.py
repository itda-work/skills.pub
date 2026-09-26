from __future__ import annotations

import binascii
import io
import struct
import zlib
from dataclasses import dataclass


@dataclass
class _Entry:
    name: str
    method: int
    crc32: int
    comp_size: int
    uncomp_size: int
    offset: int


class RawZipWriter:
    def __init__(self) -> None:
        self._buf = io.BytesIO()
        self._entries: list[_Entry] = []

    def add_store(self, name: str, data: bytes) -> None:
        entry = _Entry(name, 0, binascii.crc32(data) & 0xFFFFFFFF, len(data), len(data), self._buf.tell())
        self._write_local_header(entry)
        self._buf.write(data)
        self._entries.append(entry)

    def add_deflate(self, name: str, data: bytes) -> None:
        comp_obj = zlib.compressobj(level=-1, wbits=-15)
        compressed = comp_obj.compress(data) + comp_obj.flush()
        entry = _Entry(
            name,
            8,
            binascii.crc32(data) & 0xFFFFFFFF,
            len(compressed),
            len(data),
            self._buf.tell(),
        )
        self._write_local_header(entry)
        self._buf.write(compressed)
        self._entries.append(entry)

    def finish(self) -> bytes:
        cd_offset = self._buf.tell()
        for entry in self._entries:
            self._write_central_dir_entry(entry)
        cd_size = self._buf.tell() - cd_offset
        self._buf.write(
            struct.pack(
                "<IHHHHIIH",
                0x06054B50,
                0,
                0,
                len(self._entries),
                len(self._entries),
                cd_size,
                cd_offset,
                0,
            )
        )
        return self._buf.getvalue()

    def _write_local_header(self, entry: _Entry) -> None:
        name = entry.name.encode()
        self._buf.write(
            struct.pack(
                "<IHHHHHIIIHH",
                0x04034B50,
                20,
                0,
                entry.method,
                0,
                0x0021,
                entry.crc32,
                entry.comp_size,
                entry.uncomp_size,
                len(name),
                0,
            )
        )
        self._buf.write(name)

    def _write_central_dir_entry(self, entry: _Entry) -> None:
        name = entry.name.encode()
        self._buf.write(
            struct.pack(
                "<IHHHHHHIIIHHHHHII",
                0x02014B50,
                20,
                20,
                0,
                entry.method,
                0,
                0x0021,
                entry.crc32,
                entry.comp_size,
                entry.uncomp_size,
                len(name),
                0,
                0,
                0,
                0,
                0,
                entry.offset,
            )
        )
        self._buf.write(name)
