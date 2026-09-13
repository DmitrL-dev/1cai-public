# External analyzer adapters

`rentgen_diagnostics.sarif_adapter.parse_sarif` converts a restricted SARIF 2.1.0
report into the existing exact-Git `FindingReport`. It only imports supplied
bytes or reads one supplied `Path`. It does not run Sonar, Vanessa, Git or any
other process, access the network, change source files, persist findings or
register a watcher. A producer that exports the supported SARIF subset can use
this adapter; native Sonar/Vanessa execution and conversion are not implemented.

## Trusted input contract

```python
from rentgen_diagnostics.sarif_adapter import SarifContext, parse_sarif

# Supplied by a trusted producer after it verified the exact analyzed commit,
# profile, scope, complete analysis and digest of the final report bytes.
context = SarifContext(
    observation=analyzed_observation,
    profile_id="sonar-profile-v1",
    scope_id="whole-repository",
    complete=True,
    report_sha256=producer_report_sha256,
)
report = parse_sarif(
    report_bytes_or_path,
    observation=expected_observation,
    profile_id="sonar-profile-v1",
    scope_id="whole-repository",
    context=context,
    authorize=authorize_project_access,
)
```

The context is a trusted caller attestation, not a signature or proof of analyzer
execution. Never build it solely from an untrusted report's fields or successful
process exit. The caller must establish that the producer analyzed exactly the
observed repository/commit/ref and the declared full profile/scope, then retain
the report digest with that evidence. This parser cannot independently prove
which files an external analyzer inspected. It compares all expected context
fields and SHA-256 of the imported bytes; a foreign context or changed report
fails with `SARIF_CONTEXT`. It does not probe whether HEAD has subsequently moved.

`complete` must be the boolean `True`. A missing, false or incorrectly typed
completion attestation raises `SARIF_INCOMPLETE`, even if results are empty and
SARIF declares a successful invocation. An explicit failed invocation also
raises `SARIF_INCOMPLETE`. An empty results array is successful only with the
complete trusted input contract. Consumers may reconcile findings only after
the import returns successfully.

Authorization uses the existing callback contract: refusal raises an exception.
The callback runs before any report read, after JSON parsing, and immediately
before returning the validated report. Revocation exceptions propagate. `Path`
inputs use `read_retained` with a 2 MiB bound and the existing Windows no-follow
file/ancestor handle checks. The supplied path must already be absolute and
local, without `..` segments or control characters. Relative, empty and UNC
locators raise `SARIF_PATH_INVALID` before retained reading. The adapter never
expands a locator against the current directory or resolves symlinks.
Retained-read failures raise `SARIF_READ_FAILED`; the adapter never falls back
to an ordinary file read. Bytes input requires an immutable `bytes` value.

## Supported SARIF subset

The root requires `version: "2.1.0"` and a nonempty `runs` array. `$schema` is
optional; when present it must be one of the fixed SARIF 2.1.0 schema URIs listed
in the adapter. It is never fetched. Each run requires:

- `tool.driver.name`; optional driver `version`, `semanticVersion`,
  `informationUri` strings are validated and ignored.
- An explicit `results` array, including `[]` for a completed empty result.
- Optional `invocations`: each requires `executionSuccessful: true` and permits
  an integer `exitCode` only when zero. These fields never establish completeness.

Each result requires `ruleId`, `message.text` and exactly one `locations` entry
with `physicalLocation.artifactLocation.uri` and `physicalLocation.region.startLine`.
The region may also contain `startColumn`, `endLine`, `endColumn`; coordinates
must be positive integers no larger than 2^31-1, with a non-reversed range.
Optional `level` accepts `none`, `note`, `warning`, `error`; it is validated but
not retained because the current `Finding` contract has no severity field.
Text fields are nonempty, at most 4096 characters and contain no control or
surrogate characters.

Artifact URIs must already be canonical repository-relative POSIX paths.
Absolute paths, `..`, backslashes, colons, duplicate separators, dot segments,
control/format/surrogate characters, URI queries/fragments and percent escapes
are rejected. URI bases, artifact indices and URI decoding are unsupported.
No referenced artifact is opened. Unsupported fields at every supported object
level fail closed, including suppressions, rule tables, external result files,
multiple locations and extension metadata. Producers must explicitly normalize
their reports to this subset while retaining their original evidence; the
adapter never silently drops potentially relevant structures.

## Identity, limits and errors

Finding identity is `(ruleId, path, anchor)`, with anchor
`startLine:startColumn:endLine:endColumn`. Absent columns use `0` as an
unspecified-coordinate sentinel; absent `endLine` uses `startLine`. Message,
severity, result order and run order do not define identity. Findings are sorted
by identity. Duplicate identities across any runs are rejected, even when their
messages differ. This location anchor is deterministic but does not track a
finding across line moves; those moves can produce resolved/new events. Producers
needing semantic anchors require a separate versioned adapter contract.

The input is limited to 2 MiB, 16 runs and 5000 total findings across runs.
Malformed UTF-8/JSON, duplicate JSON members, non-finite numbers, excessive JSON
nesting and unsupported structures raise `SARIF_INVALID`. Other parser errors
are `SARIF_LIMIT`, `SARIF_PATH_INVALID`, `SARIF_READ_FAILED`, `SARIF_DUPLICATE`, `SARIF_CONTEXT` and
`SARIF_INCOMPLETE`. Parse failure never returns an empty successful report.

Focused validation:

```powershell
python -m pytest tests/unit/test_sarif_adapter.py -q
python -m black --check rentgen_diagnostics/sarif_adapter.py tests/unit/test_sarif_adapter.py
python -m ruff check rentgen_diagnostics/sarif_adapter.py tests/unit/test_sarif_adapter.py
```
