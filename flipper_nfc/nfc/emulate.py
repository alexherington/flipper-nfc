"""Emulate NFC tags via Flipper."""

from __future__ import annotations

from pathlib import Path

from flipper_nfc.connection import FlipperConnection

EMULATE_SD_PATH = "/ext/nfc/.flipper-nfc-emulate.nfc"


def emulate_tag(
    conn: FlipperConnection,
    input_path: Path,
    duration_sec: float | None = None,
) -> None:
    """Upload *input_path* if local, emulate on Flipper, wait, then stop."""
    sd_path = EMULATE_SD_PATH
    if input_path.exists():
        conn.upload_file(input_path, sd_path)

    conn.nfc_emulate(sd_path, duration_sec=duration_sec)

    try:
        conn.remove_file(sd_path)
    except Exception:
        pass
