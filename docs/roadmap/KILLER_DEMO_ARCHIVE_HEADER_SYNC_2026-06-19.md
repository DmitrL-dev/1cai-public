# Killer Demo Archive Header Sync - 2026-06-19

## Why

Evidence Bundle ZIP and Killer Demo ZIP are now both part of the buying handoff.
Using the same generic `X-Archive-Sha256` label everywhere made the receipt harder to execute:
procurement could not immediately tell which hash belongs to the close-room archive.

## Implemented

1. Added `KILLER_DEMO_ARCHIVE_HASH_HEADER = "X-Killer-Demo-Archive-Sha256"` in Killer Demo service code.
2. `POST /api/v1/killer-demo/archive` now returns:
   - `X-Killer-Demo-Archive-Sha256` for the close-room ZIP;
   - `X-Archive-Sha256` as a compatibility alias;
   - `X-Evidence-Archive-Sha256` for the nested Evidence Archive hash.
3. Killer Demo proof packet, meeting close receipt, archive README/open-first helpers and Evidence Bundle bridge now use the specialized header.
4. Tests cover the header in Killer Demo path and API archive response.

## Buyer Impact

The procurement ticket can record two distinct hashes without ambiguity:

- Evidence Bundle ZIP: `X-Archive-Sha256`;
- linked Killer Demo ZIP: `X-Killer-Demo-Archive-Sha256`.

This makes the dual-archive handoff operational rather than merely descriptive.
