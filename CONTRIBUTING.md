# Contributing

Thanks for your interest in flipper-nfc.

## Setup

```bash
git clone https://github.com/alexherington/flipper-nfc.git
cd flipper-nfc
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Tests and lint

```bash
ruff check flipper_nfc tests
ruff format flipper_nfc tests
pytest tests/ --cov=flipper_nfc
```

Tests are mocked — no Flipper hardware required for CI (Ubuntu and macOS, Python 3.11–3.12). If you change NFC or transport behaviour, add or update unit tests.

Test fixture layout: [tests/fixtures/README.md](tests/fixtures/README.md).

## Architecture

The host sends Flipper OFW CLI commands over USB (`pyserial`); the Flipper drives NFC. Package layout:

- `cli.py` — argparse entry point
- `connection.py` / `session.py` — serial session, subshells, file upload/download
- `transport/usb.py` — port auto-detect and I/O
- `nfc/` — `.nfc` parse/validate, read, write, emulate orchestration

## Scope

In scope: USB CLI read/write/emulate for NTAG/Ultralight `.nfc` files.

Out of scope for now: BLE transport, MCP wrapper, MIFARE Classic cracking, other Flipper subsystems (Sub-GHz, IR, etc.).

## Known issues

- **USB on macOS:** After a firmware crash or rapid serial open/close, the CLI port can stop responding until the device is replugged or reset.

## Pull requests

- Keep changes focused
- Ensure `ruff check` and `pytest` pass
- Note OFW version if you tested on hardware
