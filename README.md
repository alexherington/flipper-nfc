# flipper-nfc

[![Release](https://img.shields.io/github/v/release/alexherington/flipper-nfc)](https://github.com/alexherington/flipper-nfc/releases)

Read and write NFC tags from your computer using a **Flipper Zero** over **USB**.

Your computer sends commands to the Flipper; the Flipper drives the NFC coil. You still hold the tag on the Flipper's back, but you never need the on-device NFC app or qFlipper file transfer.

## Status

**Beta.** USB CLI tested on Flipper OFW 1.4.3 + macOS. CI runs on Ubuntu and macOS (Python 3.11–3.12).

## Requirements

- Python 3.11+
- Flipper Zero with official firmware (OFW) 1.4+ recommended
- USB data cable; quit qFlipper while using the CLI (one client on the serial port)

## Limitations

- Requires a **Flipper Zero** over **USB** (not BLE). Quit qFlipper while using the CLI.
- Supports **NTAG / Ultralight** (NFC Forum Type 2) tags via Flipper `.nfc` dumps — not MIFARE Classic or other protocols.
- Tested on **official firmware** 1.4.x; other firmware may use different CLI syntax.
- **Hardware tested on macOS**; Linux works in CI but is less verified on real hardware. Windows is untested.
- You must hold the tag on the Flipper's back for read, write, and inspect.
- Cannot clear **OTP lock bits** or revert CC byte `0F` once set; damaged tags may stay read-only permanently.
- `inspect` reports lock/password status; it does not authenticate or change protection.

## Install

From GitHub (PyPI not published yet):

```bash
pip install git+https://github.com/alexherington/flipper-nfc.git
```

Development install:

```bash
git clone https://github.com/alexherington/flipper-nfc.git
cd flipper-nfc
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
flipper-nfc device-info
flipper-nfc read -o tag.nfc
flipper-nfc emulate -i tag.nfc --duration 10
flipper-nfc write -i tag.nfc --from-page 4   # skip CC page when cloning retail dumps
flipper-nfc write -i tag.nfc --verify        # read back and compare written pages
flipper-nfc inspect                          # lock, CC, password, NDEF summary
flipper-nfc read-page 3                      # read one page (4 bytes)
flipper-nfc write-page 3 E1101200            # write one page (8 hex digits)

# Debug / SD access
flipper-nfc storage list /ext/nfc
flipper-nfc storage read /ext/nfc/some.nfc -o local.nfc
flipper-nfc shell device_info
```

Set a default USB port (saved under your user config directory):

```bash
flipper-nfc config set port /dev/tty.usbmodemflip_C4sr1e1
flipper-nfc config show
flipper-nfc config path      # print config file location
flipper-nfc config unset port
```

On Linux, the port is typically `/dev/ttyACM0` or similar. On macOS, prefer `/dev/tty.usbmodemflip_*` over `/dev/cu.*`.

### Write caveats

- **Write requires a blank writable NTAG** (e.g. NTAG213/215). Do not write to read-only retail tags.
- Page 0 (UID) is read-only on standard tags; magic UID-changeable tags are needed for UID cloning.
- Default `--from-page` is `3` (skips UID/lock pages 0–2), which **includes page 3 (Capability Container)** from the `.nfc` file.

#### Capability Container (page 3)

NTAG213 blanks ship with page 3 = `E1 10 12 00`. Per the [NFC Forum Type 2 Tag spec](https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/nfc/3252/1/NFCForum-Type-2-Tag_1.1%20Specification.pdf), the fourth CC byte is **access control**, not a "formatted" flag:

| CC byte 3 | Meaning (spec §6.3) |
|-----------|---------------------|
| `00` | Read and write access granted — **READ/WRITE** state |
| `0F` | Write access denied — **READ-ONLY** state |

Many Flipper dumps from retail tags show `E1 10 12 0F` because those tags were locked read-only. Do not copy that into writable fixtures. CC bytes are updated by bitwise OR and cannot be cleared once set to `0F`.

**Dynamic lock bytes:** On NTAG213, the Lock Control TLV points to byte address `0x28` (page 10 byte 0). NDEF must end with a `FE` terminator **before** that address. Longer messages (e.g. an 18-byte "Hello World" record) overlap the lock bytes and can set lock bits, which makes phone apps report the tag as read-only even when CC byte 3 is `00`.

Use **`--from-page 4`** to skip page 3 when the dump's CC does not match the tag (e.g. cloning a read-only retail dump onto a blank).

#### Test fixtures

**Hello World** — phone-readable and phone-writable NDEF:

```bash
flipper-nfc write -i tests/fixtures/hello-world.nfc
flipper-nfc read -o after.nfc
# Expect page 3: E1 10 12 00, page 10: 00 00 00 00, text: "Hi World!"
# NFC Tools on iPhone should read the text and allow erase/re-write
```

Reference layout: `tests/fixtures/hello-world-nfc-tools-golden.nfc`

**Erase damaged writes** — restore blank writable NDEF layout:

```bash
flipper-nfc write -i tests/fixtures/ntag213-erased.nfc
```

Tags with CC `0F` or OTP lock bits already set may stay read-only permanently. See `tests/fixtures/README.md`.

## Development

```bash
ruff check flipper_nfc tests
ruff format flipper_nfc tests
pytest tests/
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Disclaimer

Unofficial tool — not affiliated with Flipper Devices Inc.

## License

MIT — see [LICENSE](LICENSE).
