# Killer Demo Manifest Headers

Date: 2026-06-20.

## Why

The Killer Demo ZIP already carries `killer-demo-manifest.json`, but procurement and the portal only saw the archive hash. The close-room archive should expose the demo manifest hash the same way Evidence Bundle exposes its archive manifest hash.

## Added

- `/api/v1/killer-demo/archive` returns `X-Killer-Demo-Manifest`, `X-Killer-Demo-Manifest-Sha256` and `X-Killer-Demo-Manifest-Files`.
- `killer-demo-manifest.json` SHA is computed from the exact bytes written into the ZIP.
- `VERIFY_ARCHIVE.md` is written into the Killer Demo ZIP and covered by `killer-demo-manifest.json`.
- `OPEN_FIRST_KILLER_DEMO.md` and `README-KILLER-DEMO.md` name `X-Killer-Demo-Manifest-Sha256` next to the archive hash header.
- Killer Demo UI shows the manifest filename, hash and entry count after ZIP download.
- Evidence Bundle linked Killer Demo ZIP download shows the same manifest metadata.

## Verification

- `python -m py_compile src/api/killer_demo_api.py`
- `pytest tests/unit/test_killer_demo_api.py -q`
- `npm run build` in `portal`

## Buyer Impact

The live-demo close archive now has a directly visible manifest proof: procurement can record the ZIP hash and the manifest hash without manually opening the archive first.
