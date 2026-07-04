"""Tests for page read/write helpers."""

from unittest.mock import MagicMock

from flipper_nfc.connection import parse_rdbl_response
from flipper_nfc.nfc.pages import PageIOError, normalise_page_hex, read_page, write_page


def test_parse_rdbl_response():
    raw = "Block 4\nData: E1 10 12 00\n"
    assert parse_rdbl_response(raw) == bytes.fromhex("E1101200")


def test_parse_rdbl_response_missing():
    assert parse_rdbl_response("Error: timeout") is None


def test_normalise_page_hex_from_bytes():
    assert normalise_page_hex(bytes.fromhex("0103A00C")) == "0103A00C"


def test_normalise_page_hex_from_spaced_string():
    assert normalise_page_hex("01 03 A0 0C") == "0103A00C"


def test_normalise_page_hex_invalid():
    try:
        normalise_page_hex("0103")
        assert False, "expected PageIOError"
    except PageIOError:
        pass


def test_read_page():
    conn = MagicMock()
    conn.nfc_read_page.return_value = bytes.fromhex("E1101200")
    assert read_page(conn, 3) == bytes.fromhex("E1101200")
    conn.nfc_read_page.assert_called_once_with(3)


def test_read_page_failure():
    conn = MagicMock()
    conn.nfc_read_page.return_value = None
    try:
        read_page(conn, 3)
        assert False, "expected PageIOError"
    except PageIOError as exc:
        assert "page 3" in str(exc)


def test_write_page():
    conn = MagicMock()
    conn.nfc_write_page.return_value = True
    write_page(conn, 4, "0103A00C")
    conn.nfc_write_page.assert_called_once_with(4, "0103A00C")
