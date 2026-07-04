"""USB serial transport for Flipper Zero CLI."""

from __future__ import annotations

import glob
import time
from typing import TYPE_CHECKING

import serial

if TYPE_CHECKING:
    from serial import Serial

BAUD = 230400

# macOS Flipper USB serial patterns, then Linux ACM / by-id symlinks.
_PORT_PATTERNS = (
    "/dev/tty.usbmodemflip_*",
    "/dev/cu.usbmodemflip_*",
    "/dev/ttyACM*",
    "/dev/serial/by-id/*flipper*",
    "/dev/serial/by-id/*Flipper*",
)


def find_usb_port(explicit: str | None = None) -> str:
    """Return USB serial port path, preferring tty over cu on macOS."""
    if explicit:
        return explicit
    for pattern in _PORT_PATTERNS:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[0]
    raise serial.SerialException("No Flipper USB port found. Connect via USB or pass --port PATH.")


class UsbTransport:
    """pyserial-backed transport at 230400 baud."""

    def __init__(self, port: str | None = None) -> None:
        self._port_path = port
        self._ser: Serial | None = None

    @property
    def port_path(self) -> str:
        if self._port_path is None:
            self._port_path = find_usb_port()
        return self._port_path

    def open(self) -> None:
        self._ser = serial.Serial(self.port_path, BAUD, timeout=0.5)
        time.sleep(0.2)
        self._ser.reset_input_buffer()

    def close(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def write(self, data: bytes) -> None:
        if self._ser is None:
            raise RuntimeError("USB transport not open")
        self._ser.write(data)

    def read_available(self) -> bytes:
        if self._ser is None:
            raise RuntimeError("USB transport not open")
        n = max(1, self._ser.in_waiting)
        return self._ser.read(n)
