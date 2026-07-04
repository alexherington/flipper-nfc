"""Write .nfc page data to physical NTAG/Ultralight tags."""

from __future__ import annotations

from pathlib import Path

from flipper_nfc.connection import FlipperConnection
from flipper_nfc.nfc.format import NfcDump, NfcFormatError, page_hex, parse_nfc, validate
from flipper_nfc.nfc.pages import PageIOError, read_page


def write_tag(
    conn: FlipperConnection,
    input_path: Path,
    from_page: int = 3,
) -> list[tuple[int, bool]]:
    """Write pages from *input_path* starting at *from_page*. Returns (page, ok) pairs."""
    dump = _load_dump(input_path)

    results: list[tuple[int, bool]] = []
    for page in sorted(dump.pages):
        if page < from_page:
            continue
        hex_data = page_hex(dump, page)
        ok = conn.nfc_write_page(page, hex_data)
        results.append((page, ok))

    return results


def verify_writes(
    conn: FlipperConnection,
    input_path: Path,
    from_page: int,
    write_results: list[tuple[int, bool]],
) -> list[tuple[int, bool]]:
    """Read back pages that were written successfully and compare to the dump."""
    dump = _load_dump(input_path)
    verified: list[tuple[int, bool]] = []

    for page, written in write_results:
        if not written:
            continue
        expected = dump.pages[page]
        try:
            actual = read_page(conn, page)
        except PageIOError:
            verified.append((page, False))
            continue
        verified.append((page, actual == expected))

    return verified


def _load_dump(input_path: Path) -> NfcDump:
    try:
        dump = parse_nfc(input_path)
        validate(dump)
    except NfcFormatError as exc:
        raise SystemExit(str(exc)) from exc
    return dump
