"""Tests for write verification."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from flipper_nfc.nfc.write import verify_writes, write_tag

FIXTURE = Path(__file__).parent / "fixtures" / "hello-world.nfc"


def test_verify_writes_matches():
    from flipper_nfc.nfc.format import parse_nfc

    dump = parse_nfc(FIXTURE)
    conn = MagicMock()
    conn.nfc_write_page.return_value = True
    conn.nfc_read_page.side_effect = lambda page: dump.pages.get(page)

    write_results = write_tag(conn, FIXTURE, from_page=3)
    verified = verify_writes(conn, FIXTURE, from_page=3, write_results=write_results)

    assert all(ok for _, ok in write_results)
    assert all(ok for _, ok in verified)
    assert {p for p, _ in verified} == set(dump.pages.keys())


def test_verify_writes_detects_mismatch():
    conn = MagicMock()
    conn.nfc_write_page.return_value = True
    conn.nfc_read_page.return_value = bytes.fromhex("00000000")

    write_results = [(3, True)]
    verified = verify_writes(conn, FIXTURE, from_page=3, write_results=write_results)

    assert verified == [(3, False)]
