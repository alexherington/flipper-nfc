"""Tests for CliConnection NFC subshell state."""

from __future__ import annotations

from unittest.mock import MagicMock

from flipper_nfc.connection import CliConnection

_DUMP_OK = "Dump saved to '/ext/nfc/test.nfc'"


def _conn() -> tuple[CliConnection, MagicMock]:
    session = MagicMock()
    session._subshell = None
    return CliConnection(session), session


def test_nfc_dump_enters_and_exits_when_not_in_subshell():
    conn, session = _conn()
    session.send.return_value = _DUMP_OK

    conn.nfc_dump("/ext/nfc/test.nfc", 5000)

    session.enter_subshell.assert_called_once_with("nfc")
    session.exit_subshell.assert_called_once()
    assert conn._in_nfc_subshell is False


def test_read_page_then_dump_keeps_subshell():
    conn, session = _conn()
    session.send.side_effect = ["Data: E1 10 12 00", _DUMP_OK]

    conn.nfc_read_page(3)
    assert conn._in_nfc_subshell is True
    session.enter_subshell.reset_mock()
    session.exit_subshell.reset_mock()

    conn.nfc_dump("/ext/nfc/test.nfc", 5000)

    session.enter_subshell.assert_not_called()
    session.exit_subshell.assert_not_called()
    assert conn._in_nfc_subshell is True


def test_dump_then_read_page_reopens_subshell():
    conn, session = _conn()
    session.send.side_effect = [_DUMP_OK, "Data: E1 10 12 00"]

    conn.nfc_dump("/ext/nfc/test.nfc", 5000)
    assert conn._in_nfc_subshell is False

    conn.nfc_read_page(3)

    assert session.enter_subshell.call_count == 2
    assert conn._in_nfc_subshell is True


def test_connection_exit_closes_persistent_subshell():
    conn, session = _conn()
    session.send.return_value = "Data: E1 10 12 00"

    conn.__enter__()
    conn.nfc_read_page(3)
    conn.__exit__(None, None, None)

    session.exit_subshell.assert_called_once()
    assert conn._in_nfc_subshell is False


def test_emulate_uses_subshell_scope():
    conn, session = _conn()

    conn.nfc_emulate("/ext/nfc/tag.nfc", duration_sec=0.0)

    session.enter_subshell.assert_called_once_with("nfc")
    session.exit_subshell.assert_called_once()
    session.interrupt.assert_called_once()


def test_upload_exits_nfc_subshell_after_read_page(tmp_path):
    conn, session = _conn()
    nfc_file = tmp_path / "tag.nfc"
    nfc_file.write_bytes(b"x" * 10)

    session.send.side_effect = ["Data: E1 10 12 00", None]
    conn.nfc_read_page(3)
    assert conn._in_nfc_subshell is True

    conn.upload_file(nfc_file, "/ext/nfc/.flipper-nfc-emulate.nfc")

    session.exit_subshell.assert_called_once()
    assert conn._in_nfc_subshell is False
    session.upload_file.assert_called_once()


def test_download_exits_nfc_subshell_after_read_page():
    conn, session = _conn()
    session.send.side_effect = ["Data: E1 10 12 00", None]
    session.download_file.return_value = "Filetype: Flipper NFC device"

    conn.nfc_read_page(3)
    conn.download_file("/ext/nfc/test.nfc")

    session.exit_subshell.assert_called_once()
    session.download_file.assert_called_once()
