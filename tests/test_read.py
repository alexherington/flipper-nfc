"""Tests for NFC read orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flipper_nfc.nfc.read import ReadError, read_tag
from flipper_nfc.session import DownloadError

FIXTURE_BODY = """Filetype: Flipper NFC device
Version: 4
Device type: NTAG/Ultralight
UID: 1D D8 2F 91 20 10 80
Page 0: 1D D8 2F 62"""


def test_read_tag_sd_path(tmp_path: Path):
    conn = MagicMock()
    conn.nfc_dump.return_value = "/ext/nfc/dump-123.nfc"
    conn.download_file.return_value = FIXTURE_BODY
    output = tmp_path / "out.nfc"

    body = read_tag(conn, output, timeout_sec=1.0)

    conn.nfc_dump.assert_called_once()
    conn.download_file.assert_called_once_with("/ext/nfc/dump-123.nfc")
    conn.remove_file.assert_not_called()
    assert body == FIXTURE_BODY
    assert output.read_text().strip() == FIXTURE_BODY


def test_read_tag_deletes_ephemeral_dump(tmp_path: Path):
    conn = MagicMock()
    conn.nfc_dump.return_value = "/ext/nfc/.flipper-nfc-dump.nfc"
    conn.download_file.return_value = FIXTURE_BODY
    output = tmp_path / "out.nfc"

    read_tag(conn, output, timeout_sec=1.0)

    conn.remove_file.assert_called_once_with("/ext/nfc/.flipper-nfc-dump.nfc")


def test_read_tag_no_output_file():
    conn = MagicMock()
    conn.nfc_dump.return_value = "/ext/nfc/dump-123.nfc"
    conn.download_file.return_value = FIXTURE_BODY

    body = read_tag(conn, output=None, timeout_sec=1.0)

    assert body == FIXTURE_BODY


def test_read_tag_strips_failed_auth_line(tmp_path: Path):
    conn = MagicMock()
    conn.nfc_dump.return_value = "/ext/nfc/dump-123.nfc"
    conn.download_file.return_value = FIXTURE_BODY + "\nFailed authentication attempts: 0"
    output = tmp_path / "out.nfc"

    body = read_tag(conn, output, timeout_sec=1.0)

    assert "Failed authentication attempts" not in body
    assert "Failed authentication attempts" not in output.read_text()


def test_read_tag_retries_then_succeeds(tmp_path: Path):
    conn = MagicMock()
    conn.nfc_dump.side_effect = [TimeoutError("No tag detected (timeout)"), "/ext/nfc/dump.nfc"]
    conn.download_file.return_value = FIXTURE_BODY
    output = tmp_path / "out.nfc"
    retries_seen: list[tuple[int, int, str]] = []

    with patch("flipper_nfc.nfc.read.time.sleep"):
        body = read_tag(
            conn,
            output,
            timeout_sec=0.1,
            retries=3,
            on_retry=lambda a, t, m: retries_seen.append((a, t, m)),
        )

    assert body == FIXTURE_BODY
    assert retries_seen == [(1, 3, "No tag detected (timeout)")]
    assert conn.nfc_dump.call_count == 2


def test_read_tag_exhausts_retries(tmp_path: Path):
    conn = MagicMock()
    conn.nfc_dump.side_effect = TimeoutError("No tag detected (timeout)")
    output = tmp_path / "out.nfc"

    with patch("flipper_nfc.nfc.read.time.sleep"):
        with pytest.raises(ReadError, match="No tag detected"):
            read_tag(conn, output, timeout_sec=0.1, retries=2)

    assert conn.nfc_dump.call_count == 2


def test_read_tag_empty_download_retries(tmp_path: Path):
    conn = MagicMock()
    conn.nfc_dump.return_value = "/ext/nfc/dump.nfc"
    conn.download_file.side_effect = DownloadError("Empty response from storage read")
    output = tmp_path / "out.nfc"

    with patch("flipper_nfc.nfc.read.time.sleep"):
        with pytest.raises(ReadError, match="Empty response"):
            read_tag(conn, output, timeout_sec=0.1, retries=2)
