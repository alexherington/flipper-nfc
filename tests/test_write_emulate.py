"""Tests for emulate and write orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from flipper_nfc.nfc.emulate import emulate_tag
from flipper_nfc.nfc.write import write_tag

FIXTURE = Path(__file__).parent / "fixtures" / "hello-world.nfc"


def test_emulate_with_duration(tmp_path: Path):
    nfc_file = tmp_path / "tag.nfc"
    nfc_file.write_text("Filetype: Flipper NFC device\n")

    conn = MagicMock()
    emulate_tag(conn, nfc_file, duration_sec=10.0)

    conn.upload_file.assert_called_once()
    conn.nfc_emulate.assert_called_once()
    assert conn.nfc_emulate.call_args.kwargs.get("duration_sec") == 10.0


def test_write_sends_wrbl_commands():
    conn = MagicMock()
    conn.supports_shell.return_value = True
    conn.nfc_write_page.return_value = True

    results = write_tag(conn, FIXTURE, from_page=4)

    assert conn.nfc_write_page.call_count >= 1
    pages = [call.args[0] for call in conn.nfc_write_page.call_args_list]
    assert any(p >= 4 for p in pages)
    assert all(ok for _, ok in results)
