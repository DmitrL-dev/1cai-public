# Installed draft interoperability check

One bounded Windows test uses the checkout's actual Companion service and
process runner with its already installed Core kit and scanner. It does not
install packages, build another kit, overlay product files, or fetch another
branch. Core, graph, and diagnostics Python bytes must match the raw Git blobs
of the current CI checkout. Companion libraries are checked against that same
tree, with no newline normalization.

The evidence distinguishes the triggering PR HEAD from the actual checkout SHA.
On a pull-request event the latter can be GitHub's temporary test-merge commit.
This is explicit evidence for the tree that produced the installed kit, not a
claim that a branch was merged into main.

The scenario creates an owned BOM/CRLF module and schema-4 SQLite project using
the actual Windows process identity and retained-source/graph adapters. It
checks: opening a Companion source session without committing a draft; v1 with
a deliberately lost acknowledgement; a separate CLI process creating v2 before
receipt recovery; restart/readback of the exact v1 receipt; stale edit refusal
without a resend or loss of local work; a fresh session saving v3; exact replay
of the earlier CLI receipt without v4; immutable history and unchanged source.

Only loss of one successful acknowledgement is injected. No OS gate, principal,
store, core operation, or editor API is mocked. This is service integration;
real editor GUI, native 1C, model quality and release qualification are not
asserted. Windows is mandatory and the gate cannot pass by skipping.

The existing workflow versions, tests, installs and contents:read permissions
are unchanged. The test step has a four-minute cap; its owned children have
shorter limits. Node waits for child termination before deleting the fixture,
and the Python supervisor retries cleanup after timeout recovery. Failure to
clean its owned directory fails acceptance. No user profile or database is used.

The separate artifact contains source-binding.json, acceptance.json,
scenario.json and node.log. It contains source hashes and synthetic test
evidence, not credentials or a release package. Root MIT licensing still applies.
