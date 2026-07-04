"""Tests for tag inspect."""

from __future__ import annotations

from unittest.mock import MagicMock

from flipper_nfc.nfc.inspect import inspect_tag


def _conn_with_pages(pages: dict[int, bytes]) -> MagicMock:
    conn = MagicMock()
    conn.nfc_mfu_info.return_value = "NTAG213\nUID: 04 00 00 00 00 00 00"

    def read_page(page: int) -> bytes | None:
        return pages.get(page)

    conn.nfc_read_page.side_effect = read_page
    return conn


def test_inspect_writable_hello_world_layout():
    pages = {
        0: bytes.fromhex("04000000"),
        1: bytes.fromhex("00000000"),
        2: bytes.fromhex("00000000"),
        3: bytes.fromhex("E1101200"),
        4: bytes.fromhex("0103A00C"),
        5: bytes.fromhex("340310D1"),
        6: bytes.fromhex("010C5402"),
        7: bytes.fromhex("656E4869"),
        8: bytes.fromhex("20576F72"),
        9: bytes.fromhex("6C6421FE"),
        10: bytes.fromhex("00000000"),
        42: bytes.fromhex("000000FF"),
        43: bytes.fromhex("00000000"),
    }
    for page in range(11, 16):
        pages[page] = bytes.fromhex("00000000")

    report = inspect_tag(_conn_with_pages(pages))
    assert report.cc_writable is True
    assert report.static_lock_set is False
    assert report.dynamic_lock_set is False
    assert report.password_protected is False
    assert report.ndef_preview == "Hi World!"


def test_inspect_read_only_cc_and_static_lock():
    pages = {
        0: bytes.fromhex("04000000"),
        2: bytes.fromhex("0000FF00"),
        3: bytes.fromhex("E110120F"),
        10: bytes.fromhex("00000000"),
    }
    report = inspect_tag(_conn_with_pages(pages))
    assert report.cc_writable is False
    assert report.static_lock_set is True
    assert any("read-only" in w for w in report.warnings)


def test_inspect_password_protected():
    pages = {
        0: bytes.fromhex("04000000"),
        3: bytes.fromhex("E1101200"),
        42: bytes.fromhex("00000004"),
        43: bytes.fromhex("80000000"),
    }
    report = inspect_tag(_conn_with_pages(pages))
    assert report.password_protected is True
    assert "page 4" in report.protection_mode
