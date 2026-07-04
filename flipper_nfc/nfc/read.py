"""Read NFC tags via Flipper dump command."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from flipper_nfc.connection import FlipperConnection
from flipper_nfc.nfc.format import clean_dump_body
from flipper_nfc.session import DownloadError

DUMP_SD_PATH = "/ext/nfc/.flipper-nfc-dump.nfc"
# Only these tool-owned paths are safe to remove from the Flipper SD card.
_EPHEMERAL_BASENAMES = frozenset(
    {
        ".flipper-nfc-dump.nfc",
        ".flipper-nfc-emulate.nfc",
    }
)


class ReadError(Exception):
    """Tag read failed after all retry attempts."""


def read_tag(
    conn: FlipperConnection,
    output: Path | None = None,
    timeout_sec: float = 30.0,
    retries: int = 3,
    on_retry: Callable[[int, int, str], None] | None = None,
) -> str:
    """Dump tag to SD, download body, optionally write *output*. Retries on failure."""
    if retries < 1:
        raise ValueError("retries must be at least 1")

    last_msg = "No tag detected"
    for attempt in range(1, retries + 1):
        try:
            return _read_once(conn, output, timeout_sec)
        except (TimeoutError, DownloadError, ReadError) as exc:
            last_msg = str(exc)
            if attempt < retries:
                if on_retry:
                    on_retry(attempt, retries, last_msg)
                time.sleep(0.5)
                continue
            raise ReadError(last_msg) from exc

    raise ReadError(last_msg)


def _read_once(conn: FlipperConnection, output: Path | None, timeout_sec: float) -> str:
    timeout_ms = int(timeout_sec * 1000)
    try:
        sd_path = conn.nfc_dump(DUMP_SD_PATH, timeout_ms)
    except TimeoutError as exc:
        raise ReadError(str(exc)) from exc

    try:
        body = conn.download_file(sd_path)
    except DownloadError as exc:
        raise ReadError(str(exc)) from exc

    if not body.startswith("Filetype:"):
        raise ReadError("Invalid dump — missing Flipper NFC header")

    body = clean_dump_body(body)

    if output is not None:
        _write_output(output, body)
    if _is_ephemeral_sd_path(sd_path):
        try:
            conn.remove_file(sd_path)
        except Exception:
            pass
    return body


def _is_ephemeral_sd_path(sd_path: str) -> bool:
    """True only for hidden temp files this tool uploads/writes itself."""
    return sd_path.rsplit("/", 1)[-1] in _EPHEMERAL_BASENAMES


def _write_output(output: Path, body: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(body + "\n")
