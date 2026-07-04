# Test fixtures

`hello-world.nfc` is an NTAG213 text NDEF payload ("Hi World!") sized to fit before the dynamic lock bytes at page 10 byte 0 (address `0x28`). Includes writable CC (`E1 10 12 00`), factory Lock Control TLV, and clears page 10. Write with default `--from-page 3`.

`hello-world-nfc-tools-golden.nfc` is a reference capture aligned with `hello-world.nfc`.

`ntag213-erased.nfc` restores factory-style empty NDEF on pages 3–39 (writable CC, empty `03 00 FE`, page 10 cleared). Use to wipe damaged writes:

```bash
flipper-nfc write -i tests/fixtures/ntag213-erased.nfc
```

Tags with CC `0F` or OTP lock bits already set may stay read-only permanently.
