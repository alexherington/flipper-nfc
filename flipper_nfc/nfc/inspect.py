"""Inspect NTAG/Ultralight lock, CC, password, and NDEF layout on a live tag."""

from __future__ import annotations

from dataclasses import dataclass, field

from flipper_nfc.connection import FlipperConnection
from flipper_nfc.nfc.pages import PageIOError, read_page


@dataclass
class TagInspect:
    """Snapshot of tag configuration read from live pages."""

    uid: str = ""
    mfu_info: str = ""
    pages: dict[int, bytes] = field(default_factory=dict)
    cc_writable: bool | None = None
    cc_hex: str = ""
    static_lock_hex: str = ""
    static_lock_set: bool = False
    dynamic_lock_page: int | None = None
    dynamic_lock_hex: str = ""
    dynamic_lock_set: bool = False
    auth0: int | None = None
    access: int | None = None
    password_protected: bool = False
    protection_mode: str = ""
    ndef_preview: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "cc_hex": self.cc_hex,
            "cc_writable": self.cc_writable,
            "static_lock_hex": self.static_lock_hex,
            "static_lock_set": self.static_lock_set,
            "dynamic_lock_page": self.dynamic_lock_page,
            "dynamic_lock_hex": self.dynamic_lock_hex,
            "dynamic_lock_set": self.dynamic_lock_set,
            "auth0": self.auth0,
            "access": self.access,
            "password_protected": self.password_protected,
            "protection_mode": self.protection_mode,
            "ndef_preview": self.ndef_preview,
            "warnings": self.warnings,
            "pages": {str(p): d.hex().upper() for p, d in self.pages.items()},
        }


def _try_read(conn: FlipperConnection, page: int) -> bytes | None:
    try:
        return read_page(conn, page)
    except PageIOError:
        return None


def _format_uid(page0: bytes, page1: bytes | None) -> str:
    uid = page0.hex().upper()
    if page1 is not None:
        uid += page1[:3].hex().upper()
    return " ".join(uid[i : i + 2] for i in range(0, len(uid.replace(" ", "")), 2))


def _ndef_preview(pages: dict[int, bytes]) -> str:
    data = b"".join(pages[p] for p in sorted(pages) if p >= 4)
    if not data:
        return ""

    record_start = data.find(b"\xd1\x01")
    if record_start != -1 and record_start + 4 < len(data):
        payload_len = data[record_start + 2]
        payload = data[record_start + 4 : record_start + 4 + payload_len]
        if payload and payload[0] <= 0x3F:
            lang_len = payload[0]
            text = payload[1 + lang_len :]
            try:
                decoded = text.decode("utf-8")
                if decoded:
                    return decoded
            except UnicodeDecodeError:
                pass

    start = data.find(b"\x03")
    if start == -1:
        return data[:32].hex().upper()
    end = data.find(b"\xfe", start)
    chunk = data[start : end + 1] if end != -1 else data[start : start + 32]
    return chunk[:32].hex().upper()


def inspect_tag(conn: FlipperConnection) -> TagInspect:
    """Read lock/CC/password pages from the tag currently on the coil."""
    result = TagInspect(mfu_info=conn.nfc_mfu_info())

    page0 = _try_read(conn, 0)
    page1 = _try_read(conn, 1)
    if page0 is not None:
        result.pages[0] = page0
        result.uid = _format_uid(page0, page1)
    if page1 is not None:
        result.pages[1] = page1

    page2 = _try_read(conn, 2)
    if page2 is not None:
        result.pages[2] = page2
        result.static_lock_hex = f"{page2[2]:02X} {page2[3]:02X}"
        result.static_lock_set = bool(page2[2] or page2[3])
        if result.static_lock_set:
            result.warnings.append("Static lock bytes set — pages 3–15 may be permanently read-only")

    page3 = _try_read(conn, 3)
    if page3 is not None:
        result.pages[3] = page3
        result.cc_hex = " ".join(f"{b:02X}" for b in page3)
        result.cc_writable = page3[3] == 0x00
        if page3[3] == 0x0F:
            result.warnings.append("CC byte 3 is 0F — tag is read-only per Type 2 spec")
        elif page3[3] not in (0x00, 0x0F):
            result.warnings.append(f"CC byte 3 is {page3[3]:02X} — unexpected access value")

    # NTAG213 dynamic lock bytes live at page 10; NTAG203 at page 40.
    page10 = _try_read(conn, 10)
    page40 = _try_read(conn, 40)
    if page10 is not None:
        result.pages[10] = page10
    if page40 is not None:
        result.pages[40] = page40

    if page10 is not None and any(page10[i] for i in range(3)):
        result.dynamic_lock_page = 10
        result.dynamic_lock_hex = " ".join(f"{b:02X}" for b in page10[:3])
        result.dynamic_lock_set = True
        result.warnings.append(
            "Dynamic lock bytes set at page 10 — some user pages may be permanently locked (OTP)"
        )
    elif page40 is not None and any(page40[i] for i in range(3)):
        result.dynamic_lock_page = 40
        result.dynamic_lock_hex = " ".join(f"{b:02X}" for b in page40[:3])
        result.dynamic_lock_set = True
        result.warnings.append(
            "Dynamic lock bytes set at page 40 — pages 16–39 may be permanently locked (OTP)"
        )
    elif page10 is not None:
        result.dynamic_lock_page = 10
        result.dynamic_lock_hex = " ".join(f"{b:02X}" for b in page10[:3])
    elif page40 is not None:
        result.dynamic_lock_page = 40
        result.dynamic_lock_hex = " ".join(f"{b:02X}" for b in page40[:3])

    # Password config: NTAG213 uses AUTH0 on page 42 byte 3; NTAG203 often page 43 byte 0.
    page42 = _try_read(conn, 42)
    page43 = _try_read(conn, 43)
    if page42 is not None:
        result.pages[42] = page42
    if page43 is not None:
        result.pages[43] = page43

    auth0: int | None = None
    access: int | None = None
    if page42 is not None:
        auth0 = page42[3]
        if page43 is not None:
            access = page43[0]
    elif page43 is not None:
        auth0 = page43[0]
        access = page43[1]

    if auth0 is not None:
        result.auth0 = auth0
        result.access = access
        if auth0 == 0xFF:
            result.password_protected = False
            result.protection_mode = "disabled"
        else:
            result.password_protected = True
            mode = "read+write" if access is not None and access & 0x80 else "write-only"
            result.protection_mode = f"from page {auth0} ({mode})"
            result.warnings.append(
                f"Password protection enabled from page {auth0} — PWD_AUTH required before writes"
            )

    ndef_pages: dict[int, bytes] = {}
    for page in range(4, 16):
        data = _try_read(conn, page)
        if data is not None:
            ndef_pages[page] = data
            result.pages[page] = data
    result.ndef_preview = _ndef_preview(ndef_pages)

    if page3 is None and page0 is None:
        raise PageIOError("Could not read tag — hold an NTAG on the Flipper's back")

    return result
