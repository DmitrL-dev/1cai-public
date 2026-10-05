# Experimental diagnostic kernel: contract proposal v1

Status: **experimental synthetic contract v1. Implementation/evaluation acceptance
is recorded separately; no native or product qualification is implied.**
Base: public documentation commit `6751cf437e79c7cbf7d9b36b10512601ffc08063`.
This isolated experiment does not change Core `25743f7`, Companion `a4d8504`,
Rust input-core, the Go scanner, packaging, or any release acceptance claim.

## 1. Boundary

A pure, deterministic Rust function accepts a bounded host envelope and returns
an advisory result. An optional one-request stdin/stdout adapter is synthetic-only.
There are no probes, file reads, subprocesses, network, LLMs, commands, patches,
or execution capabilities. The host owns authentication, adapter qualification,
read/check/disclosure permissions, receipt verification, deadlines and cancellation.
The kernel **cannot authenticate any supplied provenance, permission or counter**.
An input saying `synthetic_v1` or `same_attested` proves nothing outside this test
contract. Every result says `experimental_synthetic_not_authenticated`.

Only a synthetic semantic profile is supported. No real 1C build/OS/native adapter
is qualified. The first call slice supports statically resolved external calls to
common modules, with same-context or thin-client-to-server bridge routes. Form
modules, dynamic dispatch and all other call routes explicitly abstain. Receiver
shape covers structures, saved query result/selection schemas and current-session
application-object metadata. Mismatch covers application-object metadata only.
This narrows, rather than claims completion of, the planned three classes.

## 2. Exact envelope

All objects deny unknown fields. Every listed field is required, including
Fact.check_id; its value alone may be null. Check IDs in capabilities, attempts,
candidates and elsewhere are never nullable. No free text, arbitrary maps, source/error text, business
values, names, paths, UUIDs, commands or raw labels are accepted. JSON integers
must use unsigned integer token syntax and be in range: no sign (including -0),
fraction or exponent (1.0 and 1e0 are invalid). Leading zeroes follow strict JSON
syntax. Duplicate object keys and nesting beyond 16 levels are rejected. All local IDs
are integers 1..65535, opaque only within their case; there is no cross-case join.
JSON enum strings below are the only strings accepted.

Envelope fields:

- `schema_version`, `rule_version`, `catalog_version`: integer `1` only.
- `scope`: Scope below; `target`: Target below.
- `sequence`: integer 0..65535, host observation-sequence clock.
- `access`: `usable | revoked`; `cancelled`: boolean. These are host assertions,
  never grants of authority.
- `budget`: `{observations_remaining: 0..3, cost_remaining: 0..9,
  rule_applications_remaining: 0..256}`.
- `attempted_checks`: unique CheckId array, length <=3; includes each completed,
  failed, unavailable or timed-out attempt, but not merely proposed/pending checks.
- `capabilities`: unique-by-check array of `{check_id: CheckId,
  state: ready | consent_required | unavailable}`, length <=6. Omission is unavailable.
- `facts`: Fact array, length <=128; fact IDs unique.

`observations_remaining + attempted_checks.length <=3` and
`cost_remaining + sum(catalog cost of attempted_checks) <=9` are required. The
host must maintain authentic cumulative counters across turns. The kernel is
stateless and cannot detect a forged/reset history.

Scope is `{case_id, snapshot_id, revision_id, session_id, context_id,
platform, compatibility, execution}`. IDs use the local range above.
`platform = synthetic_8_3_27 | unsupported`;
`compatibility = synthetic_v1 | unsupported`;
`execution = thin_client | server | unknown`.
Every scope component must match exactly. Real build numbers are deliberately
not accepted as evidence of qualification; synthetic_8_3_27 is a fixture label.

Target is a tagged object:

- `{kind: call, site, module, method, module_kind: common | form,
  route: same_context | server_bridge | dynamic}`.
- `{kind: receiver, site, receiver, member,
  expected_kind: structure | query_result | query_selection | application_object | other}`.
- `{kind: mismatch, site, receiver, member, source_type, runtime_type}`.

Fact is `{id, scope, target, predicate, value, state, adapter, adapter_version,
input_id, check_id, sequence, valid_until, supersedes}`:

- `scope` and `target` have the same exact shapes as above. A fact for another
  target, receiver, type pair, member, session, revision, context or case is foreign.
- `state = observed | unavailable | stale | conflicting | revoked`.
- `adapter = synthetic_v1 | unverified_zip | untrusted`; `adapter_version = 1`.
  Only synthetic_v1 contributes to this simulation; other origins cannot attest
  identity or supersede accepted evidence.
- `input_id`: local receipt token; kernel checks syntax, not receipt authenticity.
- `check_id`: null for initial input, or one catalog CheckId. Non-null IDs must
  appear in attempted_checks and the predicate must be an output of that check.
- `sequence`, `valid_until`: integers 0..65535; sequence <= valid_until.
- `supersedes`: unique array of predecessor fact IDs; at most 128 total edges
  across the envelope. Every predecessor exists, has the same adapter/version,
  scope, target and predicate, and a strictly lower sequence. Cycles therefore
  fail validation. A superseding record must have state observed, stale or revoked
  and adapter synthetic_v1. A nonempty supersedes array additionally requires
  successor.sequence <= envelope.sequence: a future replacement cannot suppress
  one side of a present conflict. Invalid replacement structure rejects the envelope.

Predicate/value pairs are closed and type-checked:

| Predicate | Exact value |
| --- | --- |
| `call_edge` | `{kind: edge, value: static_external_resolved | unresolved | dynamic}` |
| `receiver_retained` | `{kind: bool, value: boolean}` |
| `context_enabled` | `{kind: bool, value: boolean}`: selected target-side module flag |
| `server_call_enabled` | `{kind: bool, value: boolean}`: source ServerCall flag |
| `exported` | `{kind: bool, value: boolean}`: exact method declaration's Export flag |
| `compiled_copy_present` | `{kind: bool, value: boolean}`: complete selected preprocessor copy witness |
| `receiver_kind` | `{kind: receiver_kind, value: structure | query_result | query_selection | application_object | other}` |
| `member_present` | `{kind: shape, present: boolean, receiver_kind: ReceiverKind, witness: key_presence | query_schema | session_metadata}` |
| `source_member` | `{kind: source_presence, value: present | absent_complete | unresolved}` |
| `object_correlation` | `{kind: correlation, value: same_attested | different_attested | unverified}` |

`member_present` requires key_presence for structure, query_schema for query
result/selection, or session_metadata for application_object. `other` has no
shape witness. A fresh accepted receiver_kind fact must agree with the shape's
kind before that shape contributes. These are presence/schema observations,
never rows, key values, getters, object serialization or re-executed queries.
`source_member=absent_complete` asserts a complete relevant source inventory;
`unresolved`, including an incomplete export, supplies no negative evidence.
Unverified ZIP identity never satisfies object_correlation=same_attested.

Predicates allowed for each fact's own target kind are closed: call accepts only
call_edge, context_enabled, server_call_enabled, exported, compiled_copy_present;
receiver accepts only receiver_retained, receiver_kind, member_present; mismatch
accepts those receiver predicates plus source_member and object_correlation.
A predicate outside its own target's set rejects the entire envelope. A well-formed
fact for a different target/scope is instead excluded with the foreign reason.
server_call_enabled is valid call evidence even for same_context (c02 discloses
it), but it is not a same_context rule dependency and earns no resolution credit.

Every call predicate refers to the exact CALLEE module/method and its selected
callee copy, never the caller. The selected side is scope.execution for
same_context and server for server_bridge. context_enabled is that callee-side
module flag; compiled_copy_present is that precise callee-side preprocessed
method copy. exported is the exact callee method declaration's flag and
server_call_enabled the exact callee common module's ServerCall flag. E attests
this binding, including the route. Neither matching text nor two copies implies E.

## 3. Admission, freshness, replacement and conflicts

1. Validate complete envelope and hard bounds before inference. Over-limit,
   malformed, duplicate, unsupported protocol/rule/catalog versions, unknown
   fields/enums and invalid predicate/value pairs are generic protocol errors.
   Unsupported scope/profile is a valid abstention, not a parser error.
2. Access revoked or cancelled returns a terminal result with no echoed IDs,
   hypotheses, facts, targets or evidence trace. Host must independently recheck
   disclosure permission immediately before delivery, including after evaluation.
3. Supersession permanently removes predecessor contribution within the supplied
   history. A successor becoming stale/revoked does **not** resurrect its ancestor.
   Foreign chains cannot supersede a current-scope fact (validation forbids the
   cross-scope edge). An untrusted record cannot supersede an accepted one.
4. A contributing record must be observed, synthetic_v1/version1, current exact
   scope/target, not superseded, and satisfy fact.sequence <= envelope.sequence
   <= fact.valid_until. Explicit stale/revoked/unavailable states never count as false.
5. Resolve receiver_kind before grouping member_present. Exclude a shape whose
   family cannot bind to the current unique accepted receiver_kind. A conflict in
   receiver_kind still makes every hypothesis depending on it unknown, even when
   all associated shapes are excluded as unbound. Fresh explicit conflicting
   records have conflict authority but never become accepted witness evidence;
   their IDs appear only in the exclusion trace with conflicting, not evidence_ids. Then group current records by
   predicate. Identical values are duplicate witnesses,
   not votes. Different values, or a current explicit conflicting record, make
   that predicate conflicting. Freshness/admission still apply to conflicting
   records. No majority, timestamp winner, convenient branch or implicit replacement.
6. A conflict in any dependency of a hypothesis overrides both support and
   refutation and makes it unknown. Other hypotheses remain independently usable.
   Explicit withdrawal/replacement fully recomputes the result; no confidence,
   cached diagnosis, or prior conclusion survives without current witnesses.

Trace lists the sorted contributing IDs and excluded IDs with fixed reasons
`foreign_scope`, `foreign_target`, `untrusted`, `superseded`, `stale`,
`future_observation`, `revoked`, `unavailable`, `conflicting`, or
`receiver_shape_unbound`. Multiple reasons are preserved where applicable.
No prior-output input is accepted: revision is demonstrated by paired fresh
invocations and the evidence-exclusion trace, not by trusting previous labels.

## 4. Rules and hypotheses

The kernel instantiates only the listed hypotheses for the target kind; callers
cannot add/remove hypotheses. Hypotheses are **not mutually exclusive**. The
full supported set is returned. Refuting one never supports another; even a sole
remaining hypothesis needs all of its own witnesses. Supported means a bounded
rule finding, not root-cause exclusivity, probability or complete business diagnosis.

`E` below is an accepted static_external_resolved call_edge for this exact target.
`R` is an accepted receiver_retained=true for the exact immediate receiver.
Missing/unresolved/dynamic E, or missing/false R, is `missing_anchor` and no check
is proposed: this first profile has no safe adapter to recreate a lost anchor.
Anchor conflicts instead report `conflicting_anchor`. Both leave all dependent
hypotheses unknown, and do not convert unavailability to refutation.

| Stable hypothesis / rule | Supported | Refuted | Dependencies |
| --- | --- | --- | --- |
| `call_context_unavailable` / `r_call_context_v1` | E and context_enabled=false OR compiled_copy_present=false; for server_bridge, server_call_enabled=false is another sufficient gate | E and context_enabled=true AND compiled_copy_present=true AND (same_context OR server_call_enabled=true) | E, context_enabled, compiled_copy_present, plus server_call_enabled only for bridge |
| `method_not_exported` / `r_call_export_v1` | E and exported=false | E and exported=true | E, exported |
| `receiver_kind_mismatch` / `r_receiver_kind_v1` | R and actual receiver_kind differs from target.expected_kind | R and actual receiver_kind equals target.expected_kind | R, receiver_kind |
| `immediate_member_absent` / `r_receiver_member_v1` | R, accepted receiver_kind and bound shape present=false | R, accepted receiver_kind and bound shape present=true | R, receiver_kind, member_present |
| `source_runtime_mismatch` / `r_mismatch_v1` | R, receiver_kind=application_object, source_member=present, bound runtime shape present=false, object_correlation=same_attested | R and any explicit contrary premise: receiver_kind != application_object; source_member=absent_complete; bound runtime shape present=true; or object_correlation=different_attested | R, receiver_kind, source_member, member_present, object_correlation |

Every other case is unknown. All dependencies obey conflict override even where
another disjunct would otherwise support/refute. Unknown receiver_kind prevents
using a shape witness; `other` cannot supply one. Wrong type and member absence
can coexist. A non-application kind refutes only the catalog's narrowly defined
metadata-mismatch proposition; it says nothing about other mismatch mechanisms.
Mismatch support leaves old session, extension applicability and wrong export
source **unclassified**: none is a hypothesis or permitted output cause in v1.

Call same_context is supported for synthetic thin_client or server execution.
Server_bridge is supported only with thin_client execution and a selected server
copy. The route itself must be attested by E; two contextual copies alone cannot
construct a bridge. Forms, unknown execution, dynamic route, or unsupported
platform/compatibility yield unsupported_scope before rule application.

## 5. Closed check catalog

A request only describes retrieval of already retained/authorized synthetic
witnesses. It is never permission to run anything. All checks have one atomic
adapter-observation charge, even when that observation discloses several facts.
Fixed synthetic cost equals the declared maximum number of disclosed facts.
There is no real latency or native safety claim behind these cost units.

| Check ID (fixed-order baseline order) | Additional prerequisites | Outcome evidence (complete declared alternatives) | Max disclosed facts / cost |
| --- | --- | --- | --- |
| `c01_call_copy` | call target, E | compiled_copy_present false / true | 1 / 1 |
| `c02_call_flags` | call target, E | all 8 combinations of context_enabled, server_call_enabled, exported booleans | 3 / 3 |
| `c10_receiver_kind` | receiver or mismatch target, R | each of the 5 ReceiverKind values | 1 / 1 |
| `c11_receiver_shape` | receiver or mismatch target, R, nonconflicting accepted receiver_kind != other | member_present false / true with required family/witness | 1 / 1 |
| `c20_source_presence` | mismatch target, R | source_member present / absent_complete | 1 / 1 |
| `c21_object_correlation` | mismatch target, R | object_correlation same_attested / different_attested / unverified | 1 / 1 |

There are exactly six checks; unknown check IDs remain invalid. Initial anchors
are not check outputs. A successful c02 observation discloses all three listed
facts with unique new IDs, even if only one affects the outcome. A failed attempt
may disclose no facts. A duplicate fact ID is invalid even when its values agree.
The host/harness enforces complete observation bundles before submitting a turn;
the pure kernel accepts partial evidence, marks each missing predicate unknown,
and never fabricates missing bits. Another supplied sufficient premise may still
support its own bounded finding (for example exported=false), even if the bundle
is incomplete. The independent harness must not claim such a partial bundle as
a successful complete c02 observation or undercharge its disclosure/cost.
Unavailable/timeout is a possible attempt failure for every check; it adds no
truth value, consumes its one observation and full fixed cost, and records the
attempt. No automatic retry, stronger probe, alternate capability or privilege
expansion occurs. The maximum disclosure count is reported independently of
observation/check-request count; duplicates still consume the declared cost.

A check is structurally eligible only if target/scope/prerequisites match, it is
not already in attempted_checks, and capability is ready or consent_required.
First enumerate compatible outcomes and pre-reserve the exact full projection
charge (number of hypotheses times total compatible outcomes across structurally
eligible checks). This enumeration itself applies no rules. If the reservation
does not fit after current assessment, stop budget_exhausted, charge only the
completed current-hypothesis assessment, and return no partial scores/candidates.
Otherwise evaluate the complete projection pass within that reserved rule budget. Then enforce remaining atomic observations >=1 and cost >=declared cost.
This separates a genuinely useful check blocked only by budget from a check that
cannot help. A full projection pass that cannot fit the rule budget stops without
partially selecting. In this small experiment the same check is never repeated
in one case, even after other inputs change. Revalidation/replacement can still
be supplied by the host in a later envelope; a new case/scope is not permission
or a budget bypass.

Project only outcomes compatible with existing fresh, accepted, unambiguous,
resolved values in every output slot. Such established values cannot change in
this immutable scope merely because a check might reread them. For missing,
unresolved, stale, revoked, conflicting or unbound slots, the outcome supplies a
hypothetical revalidated value. Preserve every other current fact and scope.
In particular, a known compiled_copy_present=true makes c01 a redundant reread,
not an opportunity to imagine a false value. A c02 request still discloses the
full tuple, but existing known bits constrain its outcome set and earn no new
resolution credit. A check with no compatible outcomes is not useful.

The real next envelope must revoke/supersede old conflicting records; a newly
appended opposite observation alone creates a conflict. Projected outcomes never
enter actual facts, traces, diagnosis or another policy's input. Failures project
no change. This is reasoning about catalog possibilities, not hidden observations.

For each candidate, reevaluate the same rules for each declared outcome:

- `pair_score`: number of unordered pairs of currently non-refuted hypotheses
  for which at least one outcome gives the two different status values. This
  describes different bounded findings, **not elimination of exclusive causes**.
- `resolve_score`: number of currently unknown hypotheses for which at least
  one outcome changes the status to supported or refuted.
- Useful iff pair_score >0 or resolve_score >0. No useful candidate is invented
  from text, from an oracle label or from knowledge of an unrevealed outcome.

Choose lexicographically: descending pair_score, descending resolve_score,
ascending observation charge (always 1 here), ascending fixed cost, ascending
CheckId. The fixed baseline selects the smallest CheckId from the **identical
admissible useful set**, with the same inference and terminal conditions.
Expose the entire admissible useful list with both scores and costs for auditing.

This is a one-step heuristic, not a general planner. If two conflicting mandatory
dependencies require two sequential repairs but neither single projected check
changes any hypothesis status, no candidate is useful and the result is
no_useful_check. A possible multi-check repair chain is intentionally not explored.
That abstention is a stated coverage limit, not a claim that no witness can exist.

Consent-required candidates participate with the same score, but the selected
request says `pending_consent`; no observation or synthetic cost is charged for
requesting consent. The host must obtain separate approval. An unavailable
capability is excluded and cannot turn into a pending executable command.

## 6. Budget and terminal semantics

At most 64 KiB input bytes (65,536), 128 facts, 128 supersession edges, two
hypotheses per target (one for mismatch), six candidate checks, three newly
attempted adapter observations, nine fixed cost units, and 256 cumulative rule
applications. There are no nested error-cause chains in v1. A rule application
is one complete evaluation of one hypothesis, either current or projected.
Admission/conflict grouping is bounded separately by the fact/edge limits.

Every turn first reserves/evaluates all current hypotheses, never a prefix.
If remaining rule budget cannot cover that, return budget_exhausted with all
hypotheses unknown and no evidence claim. Charge each projected hypothesis
assessment, including repeated identical projections. If the full selection
pass cannot fit, do not select from a partial candidate set: stop budget_exhausted.
Return the actual rule-application count; the host subtracts it for the next
turn. The caller must not interpret the lack of authentication as a budget grant.

Terminal priority after valid parsing:

1. access_revoked; cancelled (both redact IDs/trace/hypotheses);
2. unsupported_scope;
3. missing_anchor or conflicting_anchor;
4. current rule budget cannot evaluate all hypotheses: budget_exhausted;
5. one or more supported findings: `diagnosis`, stop `bounded_finding` and return
   the full supported set plus every refuted/unknown hypothesis;
6. all hypotheses refuted: `insufficient_data`, stop `all_refuted` (catalog
   explanations exhausted; no claim that no other explanation exists);
7. insufficient rule budget for a complete projection pass, or one or more
   useful structurally eligible checks exist but all are blocked by observation
   or cost budget: budget_exhausted;
8. select a useful check: `check_request`, stop `awaiting_observation` or
   `pending_consent`;
9. otherwise `insufficient_data`, stop `no_useful_check`, with sorted reasons
   for unavailable capabilities, missing prerequisites, already attempted
   checks, conflicts, stale/unavailable/revoked/unbound evidence.

### Exact result JSON shape

Every successful parse returns exactly these fields (no extra keys):

- `schema_version`, `rule_version`, `catalog_version`: 1.
- `assurance`: `experimental_synthetic_not_authenticated`.
- `kind`: `diagnosis | check_request | insufficient_data`.
- `stop`: `access_revoked | cancelled | unsupported_scope | missing_anchor |
  conflicting_anchor | budget_exhausted | bounded_finding | all_refuted |
  awaiting_observation | pending_consent | no_useful_check`.
  kind is diagnosis exactly for bounded_finding, check_request exactly for
  awaiting_observation/pending_consent, and insufficient_data for every other stop.
- `hypotheses`: array of `{id: HypothesisId, state: supported | refuted | unknown,
  rule_id: RuleId, evidence_ids: [FactId], unknown_reasons: [UnknownReason],
  missing_predicates: [Predicate]}` in HypothesisId order. evidence_ids are all
  current accepted nonconflicting records in that hypothesis's dependencies;
  for an unknown state they are explicitly only partial evidence. Supported and
  refuted states have empty unknown_reasons and missing_predicates. Unknown
  states list each unresolved required dependency in missing_predicates. Valid
  source_presence=unresolved and correlation=unverified count as unresolved.
- `supported`: sorted array of all supported HypothesisIds.
- `trace`: `{contributing_ids: [FactId], excluded: [{fact_id: FactId,
  reasons: [ExclusionReason]}]}`. contributing_ids is the union of hypothesis
  evidence_ids, including partial witnesses explicitly marked unknown above.
- `candidates`: Candidate array in the selector's lexicographic ranking; contains
  exactly the admissible useful candidates after observation/cost filtering.
- `selected_check`: null or an exact copy of the selected Candidate.
- `blocked_checks`: sorted array of `{check_id: CheckId, reasons: [BlockReason]}`
  for all catalog checks not in candidates during a completed selection pass.
- `rule_applications_used`: integer 0..256, actual cumulative charge of this turn.

Candidate is exactly:

`{check_id: CheckId, pair_score: 0..1, resolve_score: 0..2,
observation_charge: 1, max_disclosed_facts: 1 | 3, cost: 1 | 3,
consent: ready | pending_consent, prerequisite_fact_ids: [FactId],
affected_hypotheses: [HypothesisId], missing_predicates: [Predicate],
outcomes: [{outcome_id: 0..7, facts: [{predicate: Predicate, value: Value}]}]}`.

prerequisite_fact_ids includes the accepted anchor and, for c11, receiver-kind
witness IDs. affected_hypotheses lists those whose projected status differs from
their current state in at least one compatible outcome. missing_predicates lists
unresolved output slots the check can fill. Outcomes contain **only the compatible
catalog possibilities**, never the actual unseen outcome. Their Values use the
exact input Value shape, and contain no evidence IDs or target tokens.

Stable outcome IDs: c01 false=0/true=1; c02 bit index
`4*context_enabled + 2*server_call_enabled + exported`; c10 structure=0,
query_result=1, query_selection=2, application_object=3, other=4; c11 false=0/true=1
with the current accepted kind and its required witness; c20 present=0,
absent_complete=1; c21 same_attested=0, different_attested=1, unverified=2.

UnknownReason is `missing_witness | unresolved_witness | conflicting_evidence |
stale_evidence | revoked_evidence | unavailable_evidence | untrusted_evidence |
unbound_shape | missing_anchor | conflicting_anchor | unsupported_scope |
budget_exhausted`. ExclusionReason is the fixed set from section 3. BlockReason
is `unsupported_target | missing_anchor | missing_prerequisite |
unavailable_capability | already_attempted | observation_budget | cost_budget |
no_status_change`. All reason lists are deduplicated and lexically sorted.
When several apply, preserve all supported reasons; missing_witness is the fallback
for a dependency with no current contributing or classified record. Unresolved
finite values use unresolved_witness. Dependent conflicts always include
conflicting_evidence. A whole-turn early stop uses its matching UnknownReason.

access_revoked/cancelled return empty hypotheses/supported/candidates/blocked_checks,
empty trace, null selected_check and rule_applications_used=0. unsupported_scope
and missing_anchor/conflicting_anchor return the instantiated hypotheses as unknown
with the corresponding whole-turn reason, empty evidence IDs, no candidate or
selection and zero rule applications. A current-rule-budget early stop does the
same with budget_exhausted. Their missing_predicates are empty because inference
has not run. Other terminal results preserve the completed current assessment.
If no selection pass is needed or it cannot fit rule budget, candidates and
blocked_checks are empty. No input scope/target token is echoed in any result.

Error output is exactly the raw JSON bytes `{"error":"invalid_envelope"}`
(optionally followed by one newline) with nonzero exit;
oversize is `{"error":"input_limit"}`. Stderr is empty for protocol failures.
The adapter reads at most 65,537 bytes and rejects rather than truncating input.
Parser recursion/resource errors use the same redacted invalid_envelope result;
no parser message, offending token or input substring is printed. No filesystem
paths or environment variables configure the protocol. The result
contains no observed evidence values; hypothetical outcome values above are the
closed catalog declaration and must not be mistaken for disclosed observations.

## 7. Development examples (not held-out evaluation)

Each example starts with accepted E, both call checks ready, no prior attempts,
and full budgets. Same actual initial facts, prerequisites, cost and outcome
visibility are available to both policies. No text/oracle label enters input.

1. Selected copy exists; target context enabled; exported=false. Initially both
   hypotheses unknown. c01 outcomes affect context alone (pair=1, resolve=1).
   c02 outcomes can affect both (pair=1, resolve=2). Adaptive requests c02 and
   stops on method_not_exported after 1 request, 1 observation, 3 disclosed facts,
   cost 3. Fixed order requests c01 then c02: 2 requests/observations, 4 facts,
   cost 4. Context may remain unknown in adaptive output: it is not invented.
2. Selected copy exists; context disabled; exported=true. The same ranking gives
   context-unavailable support after c02, saving the otherwise redundant c01.
   These are missing-gate findings, not a claim about why the flag is disabled.
3. Selected copy absent; context enabled; exported=true. Fixed c01 stops after
   one observation/cost1; adaptive c02 then c01 uses two observations/cost4.
   This is the declared counterexample: no uniform dominance is claimed.
4. Shape says key present, with any locally retained value including Undefined:
   immediate_member_absent is refuted. Values never enter this envelope. An empty
   query result with saved column schema behaves identically to a nonempty one.
5. Source present + runtime member absent + correlation unverified: mismatch is
   unknown and c21 can request a proof. An observed ZIP UUID is not that proof.
   Revoking a previously accepted same_attested witness retracts the support.
6. Conflicting export true/false makes method_not_exported unknown regardless of
   duplicates. A host-issued explicit replacement that supersedes both removes
   the conflict; simply appending a newer true does not.

These examples are for contract development only. Independent held-out fixtures,
manifest hashes and numerical acceptance criteria must freeze before any build,
test or evaluation. Candidate implementation must freeze before held-out access.
A mismatch case starting with only R needs four witness checks (kind, shape,
source, correlation) to support the finding, exceeding the three-observation
budget. It must abstain unless at least one required witness is initially present;
it may refute earlier on an explicit contrary premise. This experiment therefore
does not claim full-class coverage even of its synthetic mismatch domain.

Synthetic tests may qualify only the experimental component/source candidate.
They never establish native 1C acceptance, user-ready product accuracy or
full-product release readiness.
