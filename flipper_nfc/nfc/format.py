"""Parse and validate Flipper v4 NTAG/Ultralight .nfc files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PAGE_RE = re.compile(r"^Page (\d+): ([0-9A-Fa-f ]+)$")
DROP_LINE_PREFIXES = ("Failed authentication attempts:",)


@dataclass
class NfcDump:
    raw_text: str
    device_type: str
    uid: str
    pages: dict[int, bytes] = field(default_factory=dict)


class NfcFormatError(ValueError):
    pass


def clean_dump_body(text: str) -> str:
    """Remove Flipper-specific metadata lines that are not needed in saved dumps."""
    lines = [line for line in text.splitlines() if not line.startswith(DROP_LINE_PREFIXES)]
    return "\n".join(lines)


def parse_nfc(source: str | Path) -> NfcDump:
    text = source.read_text() if isinstance(source, Path) else source
    if "Filetype: Flipper NFC device" not in text:
        raise NfcFormatError("Not a Flipper NFC device file")

    device_type = ""
    uid = ""
    pages: dict[int, bytes] = {}

    for line in text.splitlines():
        if line.startswith("Device type:"):
            device_type = line.split(":", 1)[1].strip()
        elif line.startswith("UID:"):
            uid = line.split(":", 1)[1].strip()
        elif match := PAGE_RE.match(line):
            page_num = int(match.group(1))
            pages[page_num] = bytes.fromhex(match.group(2).replace(" ", ""))

    return NfcDump(raw_text=text, device_type=device_type, uid=uid, pages=pages)


def validate(dump: NfcDump) -> None:
    if dump.device_type != "NTAG/Ultralight":
        raise NfcFormatError(f"Unsupported device type: {dump.device_type!r}")
    if not dump.uid:
        raise NfcFormatError("Missing UID")
    if not dump.pages:
        raise NfcFormatError("No pages found")


def page_hex(dump: NfcDump, page: int) -> str:
    if page not in dump.pages:
        raise NfcFormatError(f"Page {page} not in dump")
    return dump.pages[page].hex().upper()
