"""Tests for user configuration."""

from __future__ import annotations

import pytest

from flipper_nfc.config import (
    config_path,
    load_file,
    resolve_connection,
    save_file,
    set_value,
    unset_value,
)


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def test_config_path_uses_xdg(config_home):
    assert config_path() == config_home / "flipper-nfc" / "config.toml"


def test_set_and_load_port(config_home):
    set_value("port", "/dev/tty.usbmodemflip_test")
    data = load_file()
    assert data["connection"]["port"] == "/dev/tty.usbmodemflip_test"


def test_resolve_precedence(config_home, monkeypatch):
    set_value("port", "/dev/tty.from-file")
    monkeypatch.setenv("FLIPPER_NFC_PORT", "/dev/tty.from-env")

    resolved = resolve_connection(cli_port=None)
    assert resolved.port == "/dev/tty.from-env"

    resolved = resolve_connection(cli_port="/dev/tty.from-cli")
    assert resolved.port == "/dev/tty.from-cli"


def test_resolve_defaults_to_none(config_home):
    resolved = resolve_connection(None)
    assert resolved.port is None


def test_invalid_key_rejected(config_home):
    with pytest.raises(ValueError, match="Unknown config key"):
        set_value("transport", "usb")


def test_unset_removes_key(config_home):
    set_value("port", "/dev/tty.test")
    unset_value("port")
    assert not config_path().is_file()


def test_save_file_round_trip(config_home):
    save_file({"connection": {"port": "/dev/tty.usb"}})
    data = load_file()
    assert data == {"connection": {"port": "/dev/tty.usb"}}
