"""Tests for USB port auto-detection."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import serial

from flipper_nfc.transport.usb import find_usb_port


def test_find_usb_port_explicit():
    assert find_usb_port("/dev/tty.custom") == "/dev/tty.custom"


def test_find_usb_port_macos():
    with patch("flipper_nfc.transport.usb.glob.glob") as glob_mock:
        glob_mock.side_effect = lambda pattern: (
            ["/dev/tty.usbmodemflip_ABC"] if "usbmodemflip" in pattern else []
        )
        assert find_usb_port() == "/dev/tty.usbmodemflip_ABC"


def test_find_usb_port_linux_acm():
    with patch("flipper_nfc.transport.usb.glob.glob") as glob_mock:
        glob_mock.side_effect = lambda pattern: (
            ["/dev/ttyACM0"] if pattern == "/dev/ttyACM*" else []
        )
        assert find_usb_port() == "/dev/ttyACM0"


def test_find_usb_port_linux_by_id():
    with patch("flipper_nfc.transport.usb.glob.glob") as glob_mock:
        glob_mock.side_effect = lambda pattern: (
            ["/dev/serial/by-id/usb-Flipper_Devices_Zero"] if "flipper" in pattern.lower() else []
        )
        assert find_usb_port() == "/dev/serial/by-id/usb-Flipper_Devices_Zero"


def test_find_usb_port_not_found():
    with (
        patch("flipper_nfc.transport.usb.glob.glob", return_value=[]),
        pytest.raises(serial.SerialException, match="No Flipper USB port found"),
    ):
        find_usb_port()
