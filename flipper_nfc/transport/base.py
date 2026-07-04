"""Transport protocol for Flipper CLI byte streams."""

from __future__ import annotations

from typing import Protocol


class Transport(Protocol):
    """Low-level connection: open, write bytes, read available bytes, close."""

    def open(self) -> None: ...

    def close(self) -> None: ...

    def write(self, data: bytes) -> None: ...

    def read_available(self) -> bytes: ...
