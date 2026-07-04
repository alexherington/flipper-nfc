"""Transport-agnostic Flipper CLI session."""

from __future__ import annotations

import re
import time
from pathlib import Path

from flipper_nfc.transport.base import Transport

ANSI = re.compile(r"\x1b\[[0-9;]*m")
ROOT_PROMPT = ">:"
SUBSHELL_PROMPT_RE = re.compile(r"\[[^\]]+\]>: ?$")
CHUNK_SIZE = 512


class DownloadError(Exception):
    """Failed to download a file from Flipper SD storage."""


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text)


class FlipperSession:
    """Send Flipper CLI commands and parse responses."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._subshell: str | None = None

    def __enter__(self) -> FlipperSession:
        self._transport.open()
        out = self.send("", wait=1.0)
        self._sync_to_root_shell(out)
        return self

    def __exit__(self, *args: object) -> None:
        if self._subshell:
            try:
                self.exit_subshell()
            except Exception:
                pass
        self._transport.close()

    def _sync_to_root_shell(self, recent_output: str = "") -> None:
        """Return to root CLI if we are (or appear to be) inside a subshell."""
        stale = bool(
            self._subshell or "[nfc]" in recent_output or SUBSHELL_PROMPT_RE.search(recent_output)
        )
        if stale:
            self.send("exit", wait=1.0)
            self._subshell = None

    def drain(self, timeout: float, idle: float = 0.1) -> str:
        """Read until no new bytes for *idle* seconds or *timeout* elapsed."""
        end = time.time() + timeout
        last_data = time.time()
        buf = b""
        while time.time() < end:
            chunk = self._transport.read_available()
            if chunk:
                buf += chunk
                last_data = time.time()
            elif time.time() - last_data >= idle:
                break
            else:
                time.sleep(0.02)
        return strip_ansi(buf.decode("utf-8", errors="replace"))

    def send(self, cmd: str, wait: float = 1.5) -> str:
        self._transport.write((cmd + "\r").encode())
        return self.drain(wait)

    def current_prompt(self) -> str:
        if self._subshell:
            return f"[{self._subshell}]>: "
        return ROOT_PROMPT

    def enter_subshell(self, name: str) -> None:
        out = self.send(name, wait=1.5)
        if f"[{name}]" not in out and SUBSHELL_PROMPT_RE.search(out) is None:
            # Prompt may appear only after drain; send empty to fetch it.
            out += self.send("", wait=0.5)
        self._subshell = name

    def exit_subshell(self) -> None:
        self.send("exit", wait=1.0)
        self._subshell = None

    def interrupt(self) -> None:
        self._transport.write(b"\x03")
        self.drain(1.5)

    def upload_file(self, local_path: Path, sd_path: str) -> None:
        data = local_path.read_bytes()
        offset = 0
        while offset < len(data):
            chunk = data[offset : offset + CHUNK_SIZE]
            out = self.send(f"storage write_chunk {sd_path} {len(chunk)}", wait=1.5)
            if "Ready" not in out:
                raise RuntimeError(f"Flipper did not accept write_chunk: {out!r}")
            self._transport.write(chunk)
            self.drain(1.0)
            offset += len(chunk)

    def download_file(self, sd_path: str) -> str:
        out = self.send(f"storage read {sd_path}", wait=3.0)
        if not out.strip():
            raise DownloadError("Empty response from storage read (no dump on SD?)")
        idx = out.find("Filetype:")
        if idx < 0:
            raise DownloadError("Could not find .nfc body in storage read output")
        body = out[idx:]
        for marker in ("\n\n>:", "\n\n[nfc]", "\n>:"):
            if marker in body:
                body = body.split(marker)[0]
        lines = body.splitlines()
        while lines:
            tail = lines[-1].strip()
            if not tail or tail == ">:" or SUBSHELL_PROMPT_RE.search(tail):
                lines.pop()
            else:
                break
        return "\n".join(lines).strip()

    def remove_file(self, sd_path: str) -> None:
        self.send(f"storage remove {sd_path}", wait=1.0)
