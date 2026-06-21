# Evidence Bundle Buyer Pulse - 2026-06-19

## Goal

Home Buyer Pulse made the first screen faster and clearer, but it was still a live UI/API signal. Procurement needs a portable file. This slice turns the first-screen buying pulse into a hash-verifiable Evidence Bundle artifact.

## Implemented

- New `buyer-pulse` artifact in `build_evidence_bundle`.
- ZIP/manifest files: `buyer-pulse.json` and `buyer-pulse.md`.
- `buyer-pulse.md` is a required procurement file.
- Director and Security/procurement recipient packets include `buyer-pulse.md`.
- OPEN_FIRST and archive contents now surface Buyer Pulse through the existing required-file and role-packet flow.
- `/evidence-bundle` UI prioritizes `buyer-pulse.md` in send-ready role packets.
- Buyer Brief now travels next to Buyer Pulse as `buyer-brief.json/.md`; Buyer Pulse remains the numeric purchase signal, while Buyer Brief carries the first-minute room map.

## Buyer Effect

- Director can forward the same first-screen purchase signal that opened the meeting.
- Procurement can verify the AI-rent baseline, proof-route count and governance gates through SHA-256 manifest entries.
- Security sees that the first-screen commercial signal is local and deterministic, not a screenshot or hidden AI response.

## Verification

- `python -m py_compile src/services/rentgen/evidence_bundle.py`
- `python -m pytest tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- API/archive smoke with `monthly_ai_subscription_cost=200000` should include `buyer-pulse.json`, `buyer-pulse.md` and `7 200 000 RUB`.
