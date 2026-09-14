# BSL text three-way materialization

`rentgen_core.materialize_bsl_three_way(base, current, upstream, *,
max_bytes=16*1024*1024, max_lines=200_000)` is a pure function over exact
immutable `bytes`. It returns a complete candidate or raises `CoreError`.
It performs no filesystem access, 1C/EDT operation or BSL parser invocation.
Owner identity, module path binding and native BSL validation are outside this
primitive. `ready` means a text candidate was materialized, not that its BSL
syntax or behavior was validated.

All three inputs must be UTF-8 (an initial BOM is allowed), contain no NUL,
and fit the limits. Limits are positive integers and may only decrease the
16 MiB / 200,000-line ceilings. Each physical LF-delimited line, including its
terminator, is capped at 1 MiB. A final terminator does not create a phantom
line; an empty input or BOM-only input contains zero lines.

When `current == upstream`, `current == base`, or `upstream == base`, the
function selects the appropriate complete branch bytes after input validation.
This preserves one-sided BOM, newline style and final-newline changes exactly,
including a branch that already contains mixed line endings. No diff is needed.

When both branches differ, their BOMs must agree. Their line endings must use a
single common LF or CRLF style; lone CR, mixed styles and style changes are
rejected. Inputs without any terminator do not establish a competing style.
Lines retain their original bytes and terminators, including an unterminated
last line. No decoding/re-encoding or newline normalization creates the
candidate.

For a composite merge, each branch is compared with base using deterministic
`difflib.SequenceMatcher` with `autojunk=False`. Equal leading/trailing lines
are removed first; the product of the two remaining span lengths may not exceed
4,000,000 per comparison. Larger spans fail closed with `diff_work_limit`, even
if an unrestricted diff might succeed. This is a line comparison, not semantic
BSL reconciliation.

Distinct edits may combine only when their base intervals do not overlap or
touch. An unchanged line between branch edits separates them. Identical
replacements/deletions over the same nonempty interval are applied once.
Insertions at the same anchor conflict, including identical insertions inside
otherwise different branches. Deletion versus modification, overlapping edits
and touching boundaries also conflict. Exact whole-branch selection precedes
these rules.

The result has `schema: 1`, `scope: bsl-text-v1`, `status: ready`, a `mode`,
`base_digest`, `current_digest`, `upstream_digest`, `candidate_digest`, and
`candidate` bytes. Digests are lowercase SHA-256 of exact bytes. `merged_hunks`
contains at most 256 deterministic evidence rows with fixed kinds/sources and
zero-based half-open line intervals; insertions use empty base intervals.
`counts` includes input/candidate line counts, total `merged_hunks` and
`merged_hunks_omitted`. Exact selection uses at most one `exact_selection` row
covering the complete inputs; it does not claim to have calculated line edits.
Evidence contains no source snippets.

Failures use `BSL_THREE_WAY_INVALID`, `BSL_THREE_WAY_LIMIT`, or
`BSL_THREE_WAY_CONFLICT`. Error details contain fixed reason codes, counts and
bounded intervals only, without candidate bytes or source payload. A conflict
reports the first conflicting pair, not a complete conflict inventory. The
combined candidate must also satisfy byte, line-count and line-byte limits;
no partial candidate is exposed on failure.
