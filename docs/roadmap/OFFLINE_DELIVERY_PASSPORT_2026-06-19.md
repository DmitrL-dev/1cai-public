# Offline Delivery Passport - 2026-06-19

## Why This Slice Exists

Evidence Bundle proves demo and approval artifacts. Productization already builds
an offline ZIP archive with manifest and verification. The missing buyer-facing
piece was a delivery passport: one file security, architects, operations and the
sponsor can read before a closed-contour pilot.

## Implemented

- Backend: `src/services/offline_bundle.py`
- ZIP contents now include:
  - `manifest.json`
  - `DELIVERY_PASSPORT.json`
  - `DELIVERY_PASSPORT.md`
  - `VERIFY.txt`
  - `payload/<repo-relative-path>`
- Archive verification checks that the passport exists and points to the same
  manifest SHA-256.
- API response from `POST /api/v1/productization/offline-bundle/archive` returns
  `delivery_passport`, `delivery_passport_markdown` and `archive_files`.
- Portal `/productization` shows the Delivery Passport decision, signature
  state, target profile, acceptance gates and role handoff.
- Enterprise Trust Center now names the delivery passport in offline bundle,
  procurement and export proof.

## Buyer Value

1. Security sees signature policy, hash verification and caveats without opening
   source files.
2. Operations sees the exact verify command and install-profile services.
3. Architects see productization readiness and closed-contour gates in one file.
4. Directors see that the purchase is a local verifiable product asset, not a
   mandatory recurring AI subscription.
5. Vendors can hand over one ZIP plus Evidence Bundle instead of explaining a
   folder full of technical files.

## Caveats

- The passport proves archive integrity and handoff gates; it is not an
  OS-native signed installer.
- Production and airgap profiles still require a signing key and customer-local
  verification.
- IdP handshakes, backup drills and customer infrastructure acceptance remain
  rollout tasks.

## Verification

- `python -m py_compile src/services/offline_bundle.py src/api/productization_api.py`
- `python -m pytest tests/unit/test_offline_bundle.py tests/unit/test_productization_readiness.py tests/unit/test_enterprise_trust_center.py -q`
- `npm run build` from `portal/`
