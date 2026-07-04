"""Tests for .nfc format parsing."""

from pathlib import Path

import pytest

from flipper_nfc.nfc.format import NfcFormatError, clean_dump_body, page_hex, parse_nfc, validate

FIXTURE = Path(__file__).parent / "fixtures" / "hello-world.nfc"


def test_parse_fixture():
    dump = parse_nfc(FIXTURE)
    assert dump.device_type == "NTAG/Ultralight"
    assert dump.uid == "04 00 00 00 00 00 00"
    assert len(dump.pages) == 8
    assert dump.pages[3] == bytes.fromhex("E1101200")


def test_validate_passes():
    validate(parse_nfc(FIXTURE))


def test_validate_wrong_device_type():
    dump = parse_nfc(FIXTURE)
    dump.device_type = "Mifare Classic"
    with pytest.raises(NfcFormatError, match="Unsupported device type"):
        validate(dump)


def test_page_hex():
    dump = parse_nfc(FIXTURE)
    assert page_hex(dump, 4) == "0103A00C"


def test_clean_dump_body_removes_failed_auth():
    body = "Filetype: Flipper NFC device\nPage 0: 1D D8 2F 62\nFailed authentication attempts: 0"
    cleaned = clean_dump_body(body)
    assert "Failed authentication attempts" not in cleaned
    assert "Page 0:" in cleaned
