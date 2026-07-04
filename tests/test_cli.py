"""Tests for CLI output modes."""

import json
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
import serial

from flipper_nfc.cli import apply_connection_config, dispatch
from flipper_nfc.nfc.pages import PageIOError
from flipper_nfc.nfc.read import ReadError
from flipper_nfc.output import CliOutput, parse_device_info

FIXTURE_BODY = """Filetype: Flipper NFC device
Version: 4
Device type: NTAG/Ultralight
UID: 1D D8 2F 91 20 10 80
Page 0: 1D D8 2F 62"""


def _args(**kwargs):
    defaults = {
        "command": "read",
        "port": None,
        "output": None,
        "json": False,
        "quiet": False,
        "no_color": False,
        "from_page": 3,
        "verify": False,
        "input": None,
        "page": None,
        "data": None,
    }
    defaults.update(kwargs)
    return type("Args", (), defaults)()


def test_parse_device_info():
    raw = "firmware_version              : 1.4.3\nhardware_name                 : C4sr1e"
    info = parse_device_info(raw)
    assert info["firmware_version"] == "1.4.3"
    assert info["hardware_name"] == "C4sr1e"


def test_cli_read_json(capsys, tmp_path):
    output = tmp_path / "tag.nfc"
    session = MagicMock()
    with (
        patch("flipper_nfc.cli.open_connection") as open_mock,
        patch("flipper_nfc.cli.read_tag", return_value=FIXTURE_BODY),
    ):
        open_mock.return_value.__enter__ = MagicMock(return_value=session)
        open_mock.return_value.__exit__ = MagicMock(return_value=False)
        dispatch(
            _args(
                command="read",
                json=True,
                quiet=True,
                output=str(output),
                timeout=1.0,
                retries=1,
            )
        )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["uid"] == "1D D8 2F 91 20 10 80"
    assert payload["pages"] == 1


def test_cli_read_stdout(capsys):
    session = MagicMock()
    with (
        patch("flipper_nfc.cli.open_connection") as open_mock,
        patch("flipper_nfc.cli.read_tag", return_value=FIXTURE_BODY) as read_mock,
    ):
        open_mock.return_value.__enter__ = MagicMock(return_value=session)
        open_mock.return_value.__exit__ = MagicMock(return_value=False)
        dispatch(_args(command="read", timeout=1.0, retries=1))
    read_mock.assert_called_once()
    assert read_mock.call_args[0][1] is None
    assert FIXTURE_BODY in capsys.readouterr().out


def test_cli_usb_connect_failure(capsys):
    conn_ctx = MagicMock()
    conn_ctx.__enter__.side_effect = serial.SerialException(
        "No Flipper USB port found. Connect via USB or pass --port PATH."
    )
    with (
        patch("flipper_nfc.cli.open_connection", return_value=conn_ctx),
        pytest.raises(SystemExit) as exc,
    ):
        dispatch(_args(command="read", timeout=1.0, retries=1))
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "No Flipper USB port found" in err


def test_cli_config_show_json(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from flipper_nfc.config import set_value

    set_value("port", "/dev/tty.usbmodemflip_test")
    dispatch(_args(command="config", config_command="show", json=True, quiet=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["connection"]["port"] == "/dev/tty.usbmodemflip_test"


def test_apply_connection_config_uses_saved_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from flipper_nfc.config import set_value

    set_value("port", "/dev/tty.saved")
    args = _args(command="read", port=None)
    apply_connection_config(args)
    assert args.port == "/dev/tty.saved"


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "flipper_nfc.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--json" in result.stdout
    assert "inspect" in result.stdout
    assert "read-page" in result.stdout
    assert "write-page" in result.stdout
    assert "--transport" not in result.stdout


def test_cli_no_args_prints_help():
    result = subprocess.run(
        [sys.executable, "-m", "flipper_nfc.cli"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout


def test_cli_version():
    result = subprocess.run(
        [sys.executable, "-m", "flipper_nfc.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_cli_inspect_json(capsys):
    from flipper_nfc.nfc.inspect import TagInspect

    report = TagInspect(uid="04 00 00 00 00 00 00", cc_writable=True, cc_hex="E1 10 12 00")
    session = MagicMock()
    with (
        patch("flipper_nfc.cli.open_connection") as open_mock,
        patch("flipper_nfc.cli.inspect_tag", return_value=report),
    ):
        open_mock.return_value.__enter__ = MagicMock(return_value=session)
        open_mock.return_value.__exit__ = MagicMock(return_value=False)
        dispatch(_args(command="inspect", json=True, quiet=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["cc_writable"] is True


def test_cli_output_quiet_when_json():
    o = CliOutput.from_args(_args(json=True))
    assert o.quiet is True
    assert o.json_mode is True


def test_cli_read_json_error(capsys):
    session = MagicMock()
    with (
        patch("flipper_nfc.cli.open_connection") as open_mock,
        patch("flipper_nfc.cli.read_tag", side_effect=ReadError("No tag detected")),
    ):
        open_mock.return_value.__enter__ = MagicMock(return_value=session)
        open_mock.return_value.__exit__ = MagicMock(return_value=False)
        with pytest.raises(SystemExit) as exc:
            dispatch(_args(command="read", json=True, quiet=True, timeout=1.0, retries=1))
    assert exc.value.code == 1
    err = json.loads(capsys.readouterr().err)
    assert err["ok"] is False
    assert "No tag detected" in err["error"]


def test_cli_write_json(capsys, tmp_path):
    nfc_file = tmp_path / "tag.nfc"
    nfc_file.write_text(FIXTURE_BODY + "\nPage 1: 00 00 00 00\n")
    session = MagicMock()
    with (
        patch("flipper_nfc.cli.open_connection") as open_mock,
        patch("flipper_nfc.cli.write_tag", return_value=[(3, True), (4, True)]),
    ):
        open_mock.return_value.__enter__ = MagicMock(return_value=session)
        open_mock.return_value.__exit__ = MagicMock(return_value=False)
        dispatch(
            _args(
                command="write",
                input=str(nfc_file),
                from_page=3,
                json=True,
                quiet=True,
            )
        )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["failed"] == []


def test_cli_write_verify_json(capsys, tmp_path):
    nfc_file = tmp_path / "tag.nfc"
    nfc_file.write_text(FIXTURE_BODY)
    session = MagicMock()
    with (
        patch("flipper_nfc.cli.open_connection") as open_mock,
        patch("flipper_nfc.cli.write_tag", return_value=[(3, True)]),
        patch("flipper_nfc.cli.verify_writes", return_value=[(3, True)]),
    ):
        open_mock.return_value.__enter__ = MagicMock(return_value=session)
        open_mock.return_value.__exit__ = MagicMock(return_value=False)
        dispatch(
            _args(
                command="write",
                input=str(nfc_file),
                from_page=3,
                verify=True,
                json=True,
                quiet=True,
            )
        )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["verified"] == [{"page": 3, "match": True}]


def test_cli_write_invalid_nfc_json(capsys, tmp_path):
    bad = tmp_path / "bad.nfc"
    bad.write_text("not a flipper file")
    session = MagicMock()
    with (
        patch("flipper_nfc.cli.open_connection") as open_mock,
        pytest.raises(SystemExit) as exc,
    ):
        open_mock.return_value.__enter__ = MagicMock(return_value=session)
        open_mock.return_value.__exit__ = MagicMock(return_value=False)
        dispatch(
            _args(
                command="write",
                input=str(bad),
                from_page=3,
                json=True,
                quiet=True,
            )
        )
    assert exc.value.code == 1
    err = json.loads(capsys.readouterr().err)
    assert err["ok"] is False


def test_cli_read_page_json(capsys):
    session = MagicMock()
    with (
        patch("flipper_nfc.cli.open_connection") as open_mock,
        patch("flipper_nfc.cli.read_page", return_value=bytes.fromhex("E1101200")),
    ):
        open_mock.return_value.__enter__ = MagicMock(return_value=session)
        open_mock.return_value.__exit__ = MagicMock(return_value=False)
        dispatch(_args(command="read-page", page=3, json=True, quiet=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["page"] == 3
    assert payload["data"] == "E1101200"


def test_cli_write_page_json(capsys):
    session = MagicMock()
    with (
        patch("flipper_nfc.cli.open_connection") as open_mock,
        patch("flipper_nfc.cli.write_page"),
    ):
        open_mock.return_value.__enter__ = MagicMock(return_value=session)
        open_mock.return_value.__exit__ = MagicMock(return_value=False)
        dispatch(_args(command="write-page", page=4, data="0103A00C", json=True, quiet=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["page"] == 4


def test_cli_write_page_json_error(capsys):
    session = MagicMock()
    with (
        patch("flipper_nfc.cli.open_connection") as open_mock,
        patch("flipper_nfc.cli.write_page", side_effect=PageIOError("Could not write page 4")),
        pytest.raises(SystemExit) as exc,
    ):
        open_mock.return_value.__enter__ = MagicMock(return_value=session)
        open_mock.return_value.__exit__ = MagicMock(return_value=False)
        dispatch(_args(command="write-page", page=4, data="0103A00C", json=True, quiet=True))
    assert exc.value.code == 1
    err = json.loads(capsys.readouterr().err)
    assert err["ok"] is False
