# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-07-05

### Added

- CLI: `device-info`, `read`, `write`, `emulate`, `inspect`, `read-page`, `write-page`, `storage`, `shell`, `config`
- USB transport (pyserial, auto-detect Flipper port)
- Flipper CLI session layer (sub-shells, file upload/download, ANSI strip)
- NTAG/Ultralight `.nfc` parse/validate for write
- `write --verify` read-back verification
- `inspect` for lock, CC, password, and NDEF status
- Saved USB port config and Rich/`--json` output
- Test fixtures for NTAG213 phone-compatible writes and factory erase
- Unit tests with mocked transport

[0.1.0]: https://github.com/alexherington/flipper-nfc/releases/tag/v0.1.0
