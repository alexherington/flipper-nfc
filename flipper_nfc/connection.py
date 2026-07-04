"""Connection abstraction for USB CLI."""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

from flipper_nfc.session import FlipperSession
from flipper_nfc.transport.usb import UsbTransport

SAVED_RE = re.compile(r"Dump saved to '([^']+)'")
RDBL_DATA_RE = re.compile(r"Data:\s*((?:[0-9A-Fa-f]{2}\s*){4})", re.IGNORECASE)


def parse_rdbl_response(raw: str) -> bytes | None:
    """Extract 4 page bytes from an ``mfu rdbl`` response."""
    match = RDBL_DATA_RE.search(raw)
    if not match:
        return None
    return bytes.fromhex(match.group(1).replace(" ", ""))


class FlipperConnection(Protocol):
    """High-level Flipper operations used by CLI and NFC modules."""

    def device_info(self) -> str: ...

    def storage_list(self, path: str) -> str: ...

    def storage_read(self, path: str) -> str: ...

    def nfc_dump(self, sd_path: str, timeout_ms: int) -> str: ...

    def nfc_emulate(self, sd_path: str, duration_sec: float | None = None) -> None: ...

    def nfc_mfu_info(self) -> str: ...

    def nfc_read_page(self, page: int) -> bytes | None: ...

    def nfc_write_page(self, page: int, hex_data: str) -> bool: ...

    def upload_file(self, local_path: Path, sd_path: str) -> None: ...

    def download_file(self, sd_path: str) -> str: ...

    def remove_file(self, sd_path: str) -> None: ...

    def send_raw(self, cmd: str, wait: float = 1.5) -> str: ...


class CliConnection:
    """USB CLI session implementing FlipperConnection."""

    def __init__(self, session: FlipperSession) -> None:
        self._session = session
        self._in_nfc_subshell = False

    def __enter__(self) -> CliConnection:
        self._session.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        if self._in_nfc_subshell or self._session._subshell:
            try:
                self._session.exit_subshell()
            except Exception:
                pass
            self._in_nfc_subshell = False
        self._session.__exit__(*args)

    def _ensure_root_shell(self) -> None:
        """Storage and device commands require the root CLI, not the NFC subshell."""
        if self._in_nfc_subshell or self._session._subshell:
            try:
                self._session.exit_subshell()
            except Exception:
                pass
            self._in_nfc_subshell = False

    @contextmanager
    def _nfc_scope(self) -> Iterator[None]:
        """Enter NFC subshell if needed; exit on leave only if this scope entered it."""
        entered_here = not self._in_nfc_subshell
        if entered_here:
            self._session.enter_subshell("nfc")
            self._in_nfc_subshell = True
        try:
            yield
        finally:
            if entered_here:
                try:
                    self._session.exit_subshell()
                except Exception:
                    pass
                self._in_nfc_subshell = False

    def _ensure_nfc_subshell(self) -> None:
        if not self._in_nfc_subshell:
            self._session.enter_subshell("nfc")
            self._in_nfc_subshell = True

    def device_info(self) -> str:
        self._ensure_root_shell()
        return self._session.send("device_info", wait=2.0)

    def storage_list(self, path: str) -> str:
        self._ensure_root_shell()
        return self._session.send(f"storage list {path}", wait=2.0)

    def storage_read(self, path: str) -> str:
        self._ensure_root_shell()
        return self._session.download_file(path)

    def nfc_dump(self, sd_path: str, timeout_ms: int) -> str:
        timeout_sec = timeout_ms / 1000.0
        with self._nfc_scope():
            out = self._session.send(f"dump -f {sd_path} -t {timeout_ms}", wait=timeout_sec + 2.0)
            if not out.strip() or "Error: timeout" in out or re.search(r"\bError:", out):
                msg = "No tag detected (timeout)" if "Error: timeout" in out else "Dump failed"
                raise TimeoutError(msg)
            saved = SAVED_RE.search(out)
            if saved:
                return saved.group(1)
            return sd_path

    def nfc_emulate(self, sd_path: str, duration_sec: float | None = None) -> None:
        with self._nfc_scope():
            self._session.send(f"emulate -f {sd_path}", wait=2.0)
            if duration_sec is not None:
                time.sleep(duration_sec)
                self._session.interrupt()
            else:
                self._wait_interrupt()

    def nfc_mfu_info(self) -> str:
        self._ensure_nfc_subshell()
        return self._session.send("mfu info", wait=2.0)

    def nfc_read_page(self, page: int) -> bytes | None:
        self._ensure_nfc_subshell()
        out = self._session.send(f"mfu rdbl -b {page}", wait=2.0)
        if "Error" in out:
            return None
        return parse_rdbl_response(out)

    def nfc_write_page(self, page: int, hex_data: str) -> bool:
        self._ensure_nfc_subshell()
        out = self._session.send(f"mfu wrbl -b {page} -d {hex_data}", wait=1.5)
        return "Error" not in out

    def _wait_interrupt(self) -> None:
        import signal

        interrupted = False

        def _handler(_signum: int, _frame: object) -> None:
            nonlocal interrupted
            interrupted = True

        prev = signal.signal(signal.SIGINT, _handler)
        try:
            while not interrupted:
                time.sleep(0.2)
        finally:
            signal.signal(signal.SIGINT, prev)
        self._session.interrupt()

    def upload_file(self, local_path: Path, sd_path: str) -> None:
        self._ensure_root_shell()
        self._session.upload_file(local_path, sd_path)

    def download_file(self, sd_path: str) -> str:
        self._ensure_root_shell()
        return self._session.download_file(sd_path)

    def remove_file(self, sd_path: str) -> None:
        self._ensure_root_shell()
        self._session.remove_file(sd_path)

    def send_raw(self, cmd: str, wait: float = 1.5) -> str:
        return self._session.send(cmd, wait=wait)


def open_connection(*, port: str | None = None) -> CliConnection:
    usb = UsbTransport(port=port)
    return CliConnection(FlipperSession(usb))
