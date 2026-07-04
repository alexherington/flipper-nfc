# Release checklist

Use this when cutting a new version of flipper-nfc.

## Pre-flight

- [ ] `ruff check flipper_nfc tests` passes
- [ ] `pytest tests/` passes
- [ ] Bump `version` in `pyproject.toml` and `flipper_nfc/__init__.py`
- [ ] Update `CHANGELOG.md` with release date and notes
- [ ] Hardware smoke: `read` on a known tag
- [ ] Hardware smoke: `emulate --duration 10`
- [ ] Hardware smoke: `write -i tests/fixtures/hello-world.nfc` on blank NTAG213
- [ ] Optional: `write -i tests/fixtures/ntag213-erased.nfc` to recover a damaged tag
- [ ] No secrets in tree: `grep -rE '(api[_-]?key|password|token|secret)' --exclude-dir=.firecrawl .`

## GitHub release

```bash
git tag -s v0.1.0 -m "v0.1.0"
git push origin v0.1.0
gh release create v0.1.0 --notes "$(sed -n '/## \[0.1.0\]/,$p' CHANGELOG.md | head -n -1)"
```

Replace `v0.1.0` with the new version when cutting later releases. Verify [Actions](https://github.com/alexherington/flipper-nfc/actions) is green on `main` first.

## Repo settings (one-time)

- Description: `CLI to read/write NFC tags via Flipper Zero over USB`
- Topics: `flipper-zero`, `nfc`, `python`, `cli`
- Default branch: `main`

## PyPI (optional)

Not published yet. When ready:

```bash
pip install build twine
python -m build
twine upload dist/*
```

Then add a PyPI badge to `README.md` and keep `pip install flipper-nfc` as the primary install line.
