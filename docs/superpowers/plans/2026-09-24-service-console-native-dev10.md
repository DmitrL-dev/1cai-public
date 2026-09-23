# Installed service console proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that published Core dev10 runs Source Observer in a separate installed console process and retains exactly one report across restart.

**Architecture:** A standalone verifier creates a fresh owned project/profile, runs the installed module twice with a bounded config, and checks the durable project state and unchanged source. It publishes a path-free acceptance JSON and a human-readable product note.

**Tech Stack:** Python 3.11, installed Rentgen Core `0.1.0.dev10`, Windows process, SQLite registry, public `bsl-scan.exe`.

## Global Constraints

- The input Core ZIP must have SHA256 `11d5f8e850eec13d9a67c9cd1985db212a076e882b8794cb790fb7ac2dbee4e3`.
- The verifier must create a new owned output directory and never accept a pre-existing project, infobase or service name.
- No SCM command, service installation, public network connection or production deployment is permitted.
- Public evidence must contain no absolute local paths, secrets or source code text.

---

### Task 1: Installed runtime verifier

**Files:**
- Create: `scripts/verification/verify_service_console_native_dev10.py`

**Interfaces:**
- Consumes: `--release-zip`, `--release-sha256`, `--scanner`, `--output`, and the current installed Python interpreter.
- Produces: `<output>/acceptance.json` and retained local process/profile evidence.

- [ ] Verify public ZIP/wheel/scanner bytes with the existing `check_release` helper and assert the imported Core path belongs to the installed distribution.
- [ ] Create a new owned BSL project, register the current Windows principal, initialize Observer profile, and record source inventory.
- [ ] Run `sys.executable -I -m rentgen_core.service_entry --console --config <owned-config>` as a bounded subprocess; require exit 0 and one cycle.
- [ ] Read project state and Observer receipts; require one published snapshot/report and unchanged source bytes.
- [ ] Repeat in a new process; require no additional report/generation and released lease. Run a wrong-project negative process and require bounded failure without mutation.
- [ ] Write path-free acceptance JSON and retain complete private logs only in the output directory.

### Task 2: Native verification and product documentation

**Files:**
- Create: `docs/product/SERVICE-CONSOLE-NATIVE-DEV10.md`
- Create: `docs/product/evidence/service-console-native-dev10-20260924.json`
- Modify: `docs/product/READINESS.md`

**Interfaces:**
- Consumes: Task 1 acceptance JSON.
- Produces: public bounded claim and exact evidence hash.

- [ ] Run the verifier with the installed Core dev10 environment and public ZIP on a new local output.
- [ ] Verify receipt and source/report invariants independently; copy only acceptance JSON into the repository.
- [ ] Document steps, versions, hashes, results and the explicit SCM/production limitations; link from READINESS.
- [ ] Run Ruff, Python compilation, relevant Source Observer/service tests and `git diff --check`.
- [ ] Obtain independent read-only review of exact commit; push PR, require push and PR CI, merge, announce in GitHub Release and PR, update checkpoint.
