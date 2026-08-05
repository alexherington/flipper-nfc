"""Tests for FlipperSession with a mocked transport."""

from __future__ import annotations

from pathlib import Path

import pytest

from flipper_nfc.session import CHUNK_SIZE, DownloadError, FlipperSession, strip_ansi


class MockTransport:
    def __init__(self, responses: list[bytes] | None = None) -> None:
        self.written: list[bytes] = []
        self._responses = list(responses or [])
        self._queue: list[bytes] = []

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def write(self, data: bytes) -> None:
        self.written.append(data)
        if self._responses:
            self._queue.append(self._responses.pop(0))

    def read_available(self) -> bytes:
        if self._queue:
            return self._queue.pop(0)
        return b""


def test_strip_ansi():
    assert strip_ansi("\x1b[31mhello\x1b[0m") == "hello"


def test_enter_subshell():
    transport = MockTransport(
        responses=[
            b"[nfc]>: \r\n",
        ]
    )
    session = FlipperSession(transport)
    session.enter_subshell("nfc")
    assert session._subshell == "nfc"
    assert b"nfc\r" in transport.written[0]


def test_download_file_strips_trailing_prompt():
    body = "Filetype: Flipper NFC device\r\nVersion: 4\r\nUID: AA BB CC DD\r\n\r\n\r\n>: "
    transport = MockTransport(responses=[body.encode()])
    session = FlipperSession(transport)
    result = session.download_file("/ext/nfc/test.nfc")
    assert "Filetype: Flipper NFC device" in result
    assert "UID: AA BB CC DD" in result
    assert ">:" not in result


def test_download_file_empty_raises():
    transport = MockTransport(responses=[b""])
    session = FlipperSession(transport)
    with pytest.raises(DownloadError, match="Empty response"):
        session.download_file("/ext/nfc/missing.nfc")


def test_download_file_extracts_body():
    body = "Size: 100\r\nFiletype: Flipper NFC device\r\nVersion: 4\r\nUID: AA BB CC DD\r\n\r\n>: "
    transport = MockTransport(responses=[body.encode()])
    session = FlipperSession(transport)
    result = session.download_file("/ext/nfc/test.nfc")
    assert result.startswith("Filetype: Flipper NFC device")
    assert ">: " not in result


def test_upload_file_chunks(tmp_path: Path):
    data = b"x" * (CHUNK_SIZE + 100)
    local = tmp_path / "test.nfc"
    local.write_bytes(data)

    transport = MockTransport(
        responses=[
            b"Ready\r\n",
            b"OK\r\n",
            b"Ready\r\n",
            b"OK\r\n",
        ]
    )
    session = FlipperSession(transport)
    session.upload_file(local, "/ext/nfc/upload.nfc")

    chunk_cmds = [w for w in transport.written if b"write_chunk" in w]
    assert len(chunk_cmds) == 2
    assert f"storage write_chunk /ext/nfc/upload.nfc {CHUNK_SIZE}".encode() in chunk_cmds[0]
    assert b"storage write_chunk /ext/nfc/upload.nfc 100" in chunk_cmds[1]

    raw_writes = [w for w in transport.written if b"storage" not in w]
    assert raw_writes[0] == data[:CHUNK_SIZE]
    assert raw_writes[1] == data[CHUNK_SIZE:]


def test_interrupt_sends_ctrl_c():
    transport = MockTransport()
    session = FlipperSession(transport)
    session.interrupt()
    assert transport.written == [b"\x03"]


def test_enter_recovers_stale_nfc_subshell():
    transport = MockTransport(
        responses=[
            b"Welcome back\r\n[nfc]>: \r\n",
            b"Bye\r\n>: \r\n",
        ]
    )
    session = FlipperSession(transport)
    with session:
        assert session._subshell is None
    assert any(b"exit\r" in w for w in transport.written)
