"""Low-level NTAG/Ultralight page read and write via Flipper mfu commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flipper_nfc.connection import FlipperConnection


class PageIOError(Exception):
    """Page read or write failed."""


def normalise_page_hex(data: bytes | str) -> str:
    """Return 8 hex digits (4 bytes) for ``mfu wrbl -d``."""
    if isinstance(data, str):
        cleaned = data.replace(" ", "")
        if len(cleaned) != 8 or any(c not in "0123456789ABCDEFabcdef" for c in cleaned):
            raise PageIOError(f"Page data must be 4 bytes (8 hex digits), got {data!r}")
        return cleaned.upper()
    if len(data) != 4:
        raise PageIOError(f"Page data must be 4 bytes, got {len(data)}")
    return data.hex().upper()


def read_page(conn: FlipperConnection, page: int) -> bytes:
    """Read one Ultralight page (4 bytes)."""
    data = conn.nfc_read_page(page)
    if data is None:
        raise PageIOError(f"Could not read page {page} — is a tag on the coil?")
    return data


def write_page(conn: FlipperConnection, page: int, data: bytes | str) -> None:
    """Write one Ultralight page (4 bytes)."""
    hex_data = normalise_page_hex(data)
    if not conn.nfc_write_page(page, hex_data):
        raise PageIOError(f"Could not write page {page}")
