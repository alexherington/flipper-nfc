"""Tests for the hello-world fixture."""

from __future__ import annotations

from pathlib import Path

from flipper_nfc.nfc.format import parse_nfc, validate

FIXTURE = Path(__file__).parent / "fixtures" / "hello-world.nfc"
GOLDEN = Path(__file__).parent / "fixtures" / "hello-world-nfc-tools-golden.nfc"
LOCK_PREFIX = bytes.fromhex("0103A00C34")
NDEF_PREFIX = bytes.fromhex("0310")
WRITABLE_CC = bytes.fromhex("E1101200")
LOCK_PAGE = 10


def test_hello_world_fixture_parses():
    dump = parse_nfc(FIXTURE)
    validate(dump)
    assert dump.pages[3] == WRITABLE_CC
    assert dump.pages[4] == bytes.fromhex("0103A00C")
    assert dump.pages[9] == bytes.fromhex("6C6421FE")
    assert dump.pages[LOCK_PAGE] == bytes.fromhex("00000000")


def test_hello_world_ndef_payload():
    dump = parse_nfc(FIXTURE)
    payload = b"".join(dump.pages[p] for p in range(4, 11))
    assert payload.startswith(LOCK_PREFIX + NDEF_PREFIX)
    assert b"Hi World!" in payload
    assert payload.index(0xFE) == 23
    # Dynamic lock bytes on NTAG213 start at byte address 0x28 (page 10 byte 0).
    assert payload[0x28 - 0x10] == 0x00


def test_hello_world_cc_is_writable():
    """CC byte 3 = 00 means read/write granted; 0F means read-only per Type 2 spec."""
    dump = parse_nfc(FIXTURE)
    assert dump.pages[3][3] == 0x00


def test_hello_world_matches_golden_pages():
    """Pages 3–10 match the expected phone-compatible layout."""
    fixture = parse_nfc(FIXTURE)
    golden = parse_nfc(GOLDEN)
    for page in range(3, 11):
        assert fixture.pages[page] == golden.pages[page]
