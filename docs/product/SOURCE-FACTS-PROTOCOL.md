# Submitted source facts v1: frozen implementation contract

Status: protocol freeze for the next experimental Linux-only slice, 2026-10-05.
Reviewed base bytes: public commit `93c7c7470126e18e05f52e628c5d31e2a9a7f747`.
Implementation branch base after the byte-identical public merge:
`eb2f4074b51094309b570aa8423bef7450d595f3`.
Controlling scope review SHA-256:
`e27752f19d58c9b87271ed50ea999494dbc6d4a55759bb61ac2367ea206e081a`.
This document freezes mechanics before independently authored withheld source
fixtures. It does not claim implementation acceptance, measured accuracy, Designer
serialization qualification, compilation, native execution, or production utility.

## 1. Scope and entry points

The only observations are (1) one exact qualified-looking lexical selector,
(2) the Export marker on a matching declaration header in the explicitly selected
candidate BSL file, and (3) the explicit Server property in its exactly paired XML.
Receiver binding and runtime relation are always `unknown`. No supported/refuted
call diagnoses, method-absence facts, effective server availability, namespace
closure, configuration completeness, or no-shadowing conclusions are produced.
A missing matching declaration is unavailable, never evidence that a method is
absent. Same-file caller/candidate, local shadowing, platform-property-looking
names, and orphan/partial configurations do not strengthen either relation.

New local command:

```text
rentgen source-facts --registry ABS --project PROJECT
  [--identity-profile ABS]
  --archive ABS --archive-sha256 HEX64
  --input-core ABS --input-core-sha256 HEX64
  --source-scanner ABS --source-scanner-sha256 HEX64
  --source-kernel ABS --source-kernel-sha256 HEX64
  --caller-entry ZIPPATH --candidate-entry ZIPPATH
  --selector-start UINT --selector-end UINT
```

Each option occurs exactly once, except the optional identity profile. No positional
arguments, abbreviated flags, path globbing, selector text, query, error text,
user-supplied observation, binding override, or alternate profile is accepted.
UINT CLI lexemes are `0|[1-9][0-9]*`, bounded as below; no sign or whitespace.
ZIPPATH is an accepted inventory path, not a host path. Caller must have exact
`.bsl` suffix. Candidate must have the exact layout
`CommonModules/<name>/Ext/Module.bsl`, with `<name>` a valid identifier (§4).
The paired path is exactly `CommonModules/<name>.xml`; no searching, prefix
stripping, case-insensitive lookup, or first-match fallback. Both explicit BSL
entries must exist in the accepted inventory. Missing paired XML is an abstention.
An ambiguous inventory is rejected by existing input/path admission, not searched.
Existing `source_paths` NFC/casefold collision rejection remains unchanged; it is
not the identifier-equality function of this profile.

Reuse existing local identity/context and `project:read` plus `analysis:run`.
One invocation owns one `RustInputSession`, takes its accepted immutable ZIP
inventory, and reads only the two selected BSL entries and the paired XML if
present. Read each distinct entry once into a verified host buffer, reusing it
for equal caller/candidate entries. Never reopen original ZIP members or source
paths after acceptance; never extract a tree, publish a snapshot, mutate source,
store a result persistently, or call a runtime/native service. Root metadata is
not read. Existing ZIP/input-core wire and archive limits are unchanged.

Use a separate Go executable `bsl-source-facts` (new `go/cmd/bsl-source-facts`),
not a changed legacy scanner mode. Use a separate Rust library entry point
`rentgen_diagnostic_core::source_facts::evaluate(&[u8])` and small binary
`rentgen-source-facts`. Existing diagnostic-core synthetic v1 entry point, binary,
wire, exact regression outputs, and entry-point semantics remain unchanged.
Newly linked executable bytes may change when this crate gains the new profile;
record their new build hashes rather than promise the historical ELF hash.

## 2. Common encoding and bounds

All new child messages use a 4-byte unsigned little-endian payload length followed
by exactly that many UTF-8 JSON bytes. Length is checked before allocation.
JSON starts with `{` and ends with `}`: no BOM or surrounding whitespace. Interior
JSON whitespace is permitted. Every record is an object, never a positional array;
this contract defines no arrays. Reject duplicate keys after JSON unescaping,
unknown fields, omitted required fields, wrong types, and unknown enum strings.
Objects have exactly the fields listed for their selected variant. Null is legal
only where explicitly listed. Integers must have raw lexeme `0|[1-9][0-9]*`;
reject `-0`, all signs, fractions, exponents, NaN/Infinity, and booleans-as-integers.
Check this before conversion; parsing a float then coercing is nonconforming.
All JSON strings must decode to valid Unicode scalars; reject lone surrogates.
Escaped keys/enums are compared by decoded value. All field names are case-sensitive.
Maximum JSON nesting is 12 containers, counting the root as 1. No parser recovery.

Bounds (inclusive):

| Item | Limit |
|---|---:|
| Distinct BSL buffers | 2 |
| One raw BSL buffer | 524,288 bytes |
| Relevant BSL + XML reads | 8,388,608 bytes |
| Paired XML bytes/nodes/depth | 4,194,304 / 50,000 / 64 |
| Go request JSON payload | 1,500,000 bytes |
| Go response JSON payload | 65,536 bytes |
| Rust request or response JSON payload | 65,536 bytes each |
| Hello JSON payload | 512 bytes |
| Discarded stderr | 65,536 bytes per new child |
| Lexical tokens per BSL buffer | 32,768 |
| Bytes in one string/comment/number token | 65,536 / 65,536 / 128 |
| Identifier Unicode scalars / UTF-8 bytes | 128 / 512 |
| Routine blocks / parameters per routine | 256 / 128 |
| Parenthesis/bracket nesting | 128 |
| New command's serialized success envelope | 65,536 bytes, plus final LF |
| Opaque Rust IDs | 1 through 2,147,483,647 |
| Input-core entry IDs sent to Go | 0 through 4,095 |

The Go request bound accommodates two canonical padded base64 encodings of the
largest BSL buffers plus the fixed header. A 64 KiB source request limit would
be incorrect. Base64 is RFC 4648 standard alphabet with mandatory canonical
padding, no whitespace; re-encoding the decoded bytes must equal the input.
Hashes are exactly 64 lowercase hexadecimal ASCII characters, SHA-256 of the
original raw bytes. No decoding, newline normalization, or BOM removal precedes
hashing. Crossing a bound never returns truncated facts.

`Span` is exactly `{"start":UINT,"end":UINT}`. It is a zero-based half-open raw
byte range `[start,end)`, includes the initial BOM in its coordinate system,
and must end on UTF-8 scalar boundaries. Observed spans are nonempty, bounded
by the referenced raw size. Selection input endpoints are 0..524288; reversed,
empty, out-of-buffer, non-boundary, or non-exact spans abstain. Selector spans
start at the receiver identifier and end at the method identifier, excluding
parentheses/arguments and leading/trailing trivia. No line/column coordinates
are on this wire. A later UI may compute one-based scalar columns, omit the
initial BOM from display, count TAB as one scalar and CRLF as one line break;
those display coordinates are never evidence or accepted selector input.

## 3. Linux one-shot ownership and completion

Both new executables accept only `--parent-pid UINT` (PID > 1). Before reading
any stdin bytes, each installs Linux parent-death SIGKILL, verifies the installed
signal and checks actual parent PID against the supplied PID *after* installation.
It disables core dumps. Only after success does it flush exactly one hello frame:

```json
{"protocol":"source_fact_scan_v1","kind":"hello","ownership":"linux_parent_death_v1"}
```

The Rust hello substitutes `submitted_source_facts_v1` for the protocol value.
The host must validate this exact object before sending source bytes or kernel
input. There is no source-bearing argv/environment or filesystem input in either
new executable. No child subprocesses or network activity are permitted.

Linux parent-death notification is thread-sensitive. The launching Python thread
must remain alive through reap. In Go, the setup/main ownership goroutine must
remain locked to its OS thread until process exit; it must not set PR_SET_PDEATHSIG
on a transient runtime worker and then unlock it. Verify the actual arrangement
with parent-death tests. Do not close all descriptors after Go runtime startup:
its polling/thread machinery can already own descriptors. Inheritance must instead
be explicitly closed by the launcher except stdio and the sealed image descriptor;
any image descriptor cleanup in the child must be targeted and runtime-safe.
Do not copy input-core's 128 MiB RLIMIT_AS to Go. Go virtual-address reservation
and runtime threads require a separately reviewed resource implementation.
Fixed byte/token/depth caps and deadlines are mandatory here; runtime-compatible
memory limits and measured RSS are implementation-acceptance evidence, not an
unverified sandbox guarantee. Keep native setup out of the pure Rust library.

The Python owner seals and executes the verified image bytes using the reviewed
`rust_input._executable` primitive or an equally reviewed exact-byte equivalent.
Hashing a path and later executing that mutable path is forbidden. Pin actual
Go/kernel/input-core build hashes before withheld fixtures are opened. Trusted
Linux kernel, loader/runtime libraries and authorized local host are assumptions;
sealing the main image does not pin every dynamic dependency.

Host deadlines: 60 seconds for the entire operation (including input acceptance,
new children and cleanup); hello within 5 seconds of each launch; completed Go
exchange within 10 seconds and Rust exchange within 5 seconds of launch, also
bounded by the overall deadline. On failure allow at most a separate 2-second
termination/reap cleanup interval. The host simultaneously pumps stdin/stdout/
stderr non-blockingly. Every wait iteration polls cancellation, current permission,
and monotonic deadline, with no wait longer than 100 ms. This is bounded polling,
not instantaneous revocation. Apply the same checks around input-core exchanges
used by this command without changing input-core's wire. Child startup and parse
work must not create a route around the overall deadline.

After hello the child consumes one bounded request frame and requires stdin EOF;
trailing input, a second frame, a partial frame, or missing EOF cannot succeed.
The host writes every input byte and closes stdin. Only then may the child return
one bounded response frame and exit. Success requires all of: complete input
written, stdin closed, one complete valid response, no trailing stdout at all,
stdout and stderr EOF, exit status 0, and confirmed reap. A complete response
received before cancellation is still withheld. No report escapes while any
owned child (including input-core) remains unreaped. Input-core retains its
existing close/ACK protocol, with verified drain/exit/reap before disclosure.

On any failure terminate only the exact owned child, drain within bounds, and
confirm reap. Never kill by name or an unverified/reused PID. Cleanup unconfirmed
is terminal and overrides a would-be success; do not claim the child stopped.
Bound and discard stderr; never forward stderr, panic text, OS exception text,
protocol excerpts, paths embedded in errors, or source snippets. Silence panic
hooks for these executables. Protocol-valid abstentions use status `ok` and exit 0;
child error envelopes use status `error` and exit 2. Pre-hello setup failure exits
2 without a source-bearing message. The host does not treat an error envelope or
nonzero exit as a completed observation.

Authorization checks occur before input access, each launch and each source read;
after each read, parse and evaluation; during waits; and after final serialization
for both success and error. A failed final check replaces all prior payload with
a fixed authorization error. No result cache bypasses these checks.

## 4. Exact BSL lexical/header admission

Profile identifier: `bsl_lexical_headers_v1`. Admission covers the *whole* selected
buffer before any of its spans are released; source outside the selected routine
can therefore force abstention. Bodies are lexically admitted but semantically
unvalidated. This is deliberately not a compiler or general BSL parser.

1. Decode strict UTF-8. Allow at most one initial UTF-8 BOM. Reject NUL, any
   further U+FEFF, U+0000..U+001F except HT/LF/CR, and U+007F..U+009F everywhere,
   including strings/comments. CR is allowed only as part of CRLF. LF and CRLF
   are physical line breaks; mixed LF/CRLF is allowed. Code whitespace is only
   ASCII SPACE, HT and those line breaks. Non-ASCII whitespace is code-invalid.
2. IDENT is `[A-Za-zА-Яа-яЁё_][A-Za-z0-9А-Яа-яЁё_]*`, within both identifier
   limits. Equality lowercases only ASCII A..Z, Russian А..Я and Ё to ё.
   No NFC, general Unicode casefold, transliteration or `strings.EqualFold`.
   Ё differs from Е; Latin/Cyrillic lookalikes differ. Outside strings/comments,
   any non-ASCII scalar not in this alphabet is invalid, including an adjacent
   combining mark; do not split it off and accept an identifier prefix.
3. `//` starts a comment through, but excluding, the physical line break/EOF.
   Double-quoted strings are single physical line only, with doubled `""`
   for one embedded quote. Empty strings are allowed. Unterminated strings,
   physical newline inside a string, and single-quoted/date literals abstain.
   Other valid Unicode scalars are allowed inside strings/comments.
4. Number token grammar is `[0-9]+(\.[0-9]+)?`. No exponent, sign inside the
   token, hex, leading-dot/trailing-dot decimal, or suffix. A number directly
   adjacent to IDENT or an additional dot is invalid rather than split/recovered;
   signs are separate punctuation tokens. For example `1.2.3`, `1e2`, `12x`,
   `.5`, and `2.` abstain. Ordinary punctuation tokens are exactly
   `(` `)` `[` `]` `.` `,` `;` `=` `+` `-` `*` `/` `%` `<` `>` `<=` `>=` `<>`,
   with longest-match comparison operators and comment recognition before `/`.
   Every other code character abstains, including `#`, `&`, `~`, `:`, `?`, `|`,
   braces and backslash. No unsupported directive/literal recovery.
5. Reserved spellings use the same explicit equality function. Reject
   `Execute/Выполнить`, `Eval/Вычислить`, `Async/Асинх`, `Await/Ждать` anywhere
   as code identifiers, even harmless same-spelling members. In this document
   slash separates bilingual alternatives; it is not literal keyword syntax.
6. Top level permits only whitespace/comments and complete routine blocks.
   No module-level declaration or executable code. A header starts at the first
   code token of a physical line and its entire grammar is on that one line:

   ```text
   (Procedure|Процедура|Function|Функция) IDENT (
     [ [Val|Знач] IDENT { , [Val|Знач] IDENT } ]
   ) [Export|Экспорт]
   ```

   The displayed breaks are notation only. All actual header tokens occupy one
   physical line; only SPACE/HT can separate them, with an optional trailing
   `//` comment after the complete header. No defaults, annotations, interception
   forms, other trailing code or duplicate parameter names under IDENT equality.
   Routine/parameter names cannot equal any member of the following frozen
   reserved-name set under IDENT equality (each slash lists two alternatives):

   ```text
   Procedure/Процедура Function/Функция
   EndProcedure/КонецПроцедуры EndFunction/КонецФункции Export/Экспорт Val/Знач
   If/Если Then/Тогда ElsIf/ИначеЕсли Else/Иначе EndIf/КонецЕсли ElseIf
   For/Для Each/Каждого In/Из To/По While/Пока Do/Цикл EndDo/КонецЦикла
   Return/Возврат Continue/Продолжить Break/Прервать Var/Перем
   And/И Or/Или Not/Не New/Новый Goto/Перейти
   True/Истина False/Ложь Undefined/Неопределено Null
   Try/Попытка Except/Исключение EndTry/КонецПопытки Raise/ВызватьИсключение
   AddHandler/ДобавитьОбработчик RemoveHandler/УдалитьОбработчик
   Execute/Выполнить Eval/Вычислить Async/Асинх Await/Ждать
   ```

   This is a conservative closed lexical guard, not an assertion of a complete
   platform keyword catalogue. Routine/parameter violation is `invalid_header`
   (unless earlier lexical rejection, e.g. Execute, already applies). Keep this
   name guard separate from §4.7's small structural-word ban in body positions:
   ordinary control-flow words are still permitted body tokens. Bilingual
   structural words may be mixed within a routine. A recognized header is still
   a lexical header observation, never a validated/compiled BSL declaration.
7. `EndProcedure/КонецПроцедуры` or `EndFunction/КонецФункции` must match the
   opener kind and be alone on its own physical line apart from whitespace and
   optional comment; no trailing semicolon. Require one terminator for every
   header. Structural words `Procedure`, `Function`, both end words, `Export`,
   `Val` and Russian equivalents in any other code position abstain. Reject
   nested headers, mismatched/missing/stray terminators and duplicate routine
   names anywhere in one buffer, regardless of Export or routine kind.
8. Bodies are sequences of the admitted tokens, strings and numbers. Every `(`/
   `[` must close with its matching `)`/`]` within the same body, respecting
   nesting. Reject unmatched/crossed delimiters. No If/loop/statement/type/return
   semantic validation is claimed. Token counts include identifiers, strings,
   numbers and each punctuation token; whitespace/comments are not tokens.
   Check comment-size bounds even though comments do not contribute token count.

Selected selector admission requires all of:

- Inside one admitted routine body, exact tokens `IDENT . IDENT (`; receiver,
  dot, method and opening parenthesis are on one physical line, separated only
  by SPACE/HT. Exact requested span equals receiver start through method end.
  Receiver or method spelling in the reserved-name set above is rejected as
  `selector_not_qualified` (earlier whole-buffer lexical/structural rejection
  still takes precedence). Thus `If.X()` and `R.Return()` do not qualify.
- A matching closing parenthesis exists inside that routine body; arguments may
  span physical lines and contain admitted nested balanced tokens. No argument
  semantics is inferred.
- Previous nontrivia body token is absent, one of `; = ( [ , + - * / % < > <= >= <>`,
  or one of `Return/Возврат`, `If/Если`, `While/Пока`, `Not/Не`, `And/И`, `Or/Или`.
  This intentionally narrow lexical predecessor allowlist excludes member dots,
  `New/Новый`, literal/identifier adjacency and computed receiver chains. A line
  break does not itself override an otherwise excluded predecessor.
- The next nontrivia token after the matching close is not `.`, `[`, or `(`.
  Thus trailing member/index/call chains abstain. Parenthesized/computed receivers
  do not meet the selected pattern. String/comment decoys never count.

The exact span chooses a single selector even when several occur on one line;
never choose the first approximate match. The scanner compares the selected
method spelling against *all* candidate routine names using IDENT equality.
Exactly one admitted matching header yields an Export boolean independently of
whether Export occurs. No match is `declaration_unavailable`; duplicate routine
names already make candidate admission unavailable. No lexical result proves
what receiver denotes, including when explicit parameters/variables shadow it.

Observed `header_span` starts at the opener keyword and ends after closing `)`
or the optional Export keyword, excluding trailing whitespace/comment.
`routine_span` starts at the opener keyword and ends after the matching terminator
keyword. `name_span`, `receiver_span`, `method_span`, and optional `export_span`
are exact identifier/keyword token spans. The enclosing routine span contains
its header or selected selector; selector contains receiver and method spans.

## 5. Go bytes-only schema

Request (notation `Buffer` denotes an object defined below, not a JSON string):

```text
{
  "protocol": "source_fact_scan_v1",
  "caller": Buffer,
  "candidate": {"kind":"same_as_caller"}
             OR {"kind":"distinct_entry","buffer":Buffer},
  "selection": Span
}
Buffer = {"entry_id":UINT,"size_bytes":UINT,"raw_sha256":HEX64,"data_base64":STRING}
```

Caller and distinct candidate entry IDs must differ. Same-file uses only the alias
variant; identical byte content in two distinct entries is still two buffers.
Size can be zero; an empty module has no selector/declaration. Recompute both
size and SHA-256 from raw decoded bytes before lexical work. A mismatch is a
wire error, never a source abstention. No filenames, names, XML, expected facts,
query text, environment-dependent option or filesystem locator enters Go.

Successful response:

```text
{
  "protocol":"source_fact_scan_v1", "status":"ok",
  "caller":AdmissionRecord, "candidate":AdmissionRecord,
  "selector":Selector, "header":Header
}
AdmissionRecord = {
  "entry_id":UINT,"size_bytes":UINT,"raw_sha256":HEX64,
  "admission":{"state":"admitted"}
           OR {"state":"unavailable","reason":LexReason}
}
Selector = {
  "state":"observed","entry_id":UINT,"routine_span":Span,
  "selector_span":Span,"receiver_span":Span,"method_span":Span
} OR {"state":"unavailable","reason":SelectorReason}
Header = {
  "state":"observed","entry_id":UINT,"routine_span":Span,
  "header_span":Span,"name_span":Span,"export":BOOLEAN,"export_span":Span OR null
} OR {"state":"unavailable","reason":HeaderReason}
```

Both role admission records are returned, even for the alias (then identical).
Admit caller and candidate independently. Do not let an invalid candidate suppress
an otherwise admitted selector. Selector requires admitted caller. Header requires
an observed selector plus admitted candidate. When true, Export has a nonnull exact
keyword span; when false it is null. No partial spans accompany unavailable values.
Go returns no copied identifiers, routine bodies, snippets, query text, arbitrary
error string, `BslFunction`, graph, or global namespace claim.

Closed Go reasons:

- LexReason: `invalid_utf8`, `invalid_bom`, `forbidden_control`,
  `invalid_line_ending`, `unsupported_code_character`, `identifier_limit`,
  `token_bytes_limit`, `token_count_limit`, `invalid_number`,
  `unsupported_literal`, `unterminated_string`, `multiline_string`,
  `unsupported_keyword`, `unsupported_top_level`, `invalid_header`,
  `duplicate_parameter`, `parameter_limit`, `duplicate_routine`, `routine_limit`,
  `nested_routine`, `mismatched_terminator`, `missing_terminator`,
  `stray_structural_keyword`, `unbalanced_delimiter`, `delimiter_depth_limit`.
- SelectorReason: `caller_not_admitted`, `selector_span_invalid`,
  `selector_not_qualified`, `selector_outside_body`, `selector_chained`.
- HeaderReason: `selector_unavailable`, `candidate_not_admitted`,
  `declaration_unavailable`.

Precedence is deterministic: byte decoding/BOM/controls/line-ending checks first
in that order; then lexical scanning from lowest raw byte offset (token bound
before token classification at that offset); then routine parsing in source order;
then selector. A syntactically valid span outside every body uses
`selector_outside_body`; malformed/endpoints/non-exact token extent uses
`selector_span_invalid`; wrong pattern uses `selector_not_qualified`; pattern
with rejected predecessor/trailing chain uses `selector_chained`. For header,
`selector_unavailable` precedes `candidate_not_admitted`, then no-match.
A matching-kind terminator sharing its physical line with body code or followed
by a semicolon is `stray_structural_keyword`; a wrong-kind terminator in otherwise
valid standalone position is `mismatched_terminator`. A missing terminator is
`missing_terminator` at EOF even if opening body delimiters remain unclosed;
a matching standalone terminator reached with open delimiters is
`unbalanced_delimiter`. A new header while in a body is `nested_routine`.
Within a routine body, Procedure/Function or either Russian equivalent yields
`nested_routine` only when it is the first code token on its physical line,
irrespective of whether the remaining line forms a valid header; otherwise it
yields `stray_structural_keyword`. Terminator position is checked before kind,
so embedded `R.EndFunction()` is also `stray_structural_keyword`.
The first actual mismatching closing delimiter is `unbalanced_delimiter` before
later missing-terminator checks. For selector precedence, first reject endpoints
that are not exact token boundaries, then exact token extents outside all bodies,
then wrong token patterns, then rejected predecessor/trailing chains.

Wire failure response is exactly
`{"protocol":"source_fact_scan_v1","status":"error","code":Code}`,
where Code is `invalid_request`, `input_limit`, `hash_mismatch`, `size_mismatch`,
`io_error`, or `internal_error`. Prefer shape/input validation before hash checks;
check caller before distinct candidate, size before hash. No free-form detail.

## 6. Host XML and candidate agreement

XML profile: `handwritten_common_module_properties_v1`. This name is mandatory;
never label it Designer/native verified. Parse verified raw bytes with the existing
bounded no-DOCTYPE `metadata_xml.parse_xml` boundary, not a file/URL resolver.
DTD/entity declarations are forbidden; external resource resolution is forbidden.
Its existing XML encoding decoding is retained. Comments and processing
instructions are ignored according to that parser's infoset; text includes its
normal XML entity/line-ending decoding. No source-span claim for XML is made.

Let `N = http://v8.1c.ru/8.3/MDClasses`. Supported element expanded names and shape:

```text
{N}MetaDataObject
  {N}CommonModule
    {N}Properties
      {N}Name
      {N}Server
```

The root has exactly one direct CommonModule; CommonModule exactly one direct
Properties. Only these elements, and direct Name/Server property children, are
supported; no unknown unrelated elements or ordinary attributes are accepted.
Namespace declarations are not ordinary attributes. Match complete expanded
names, not prefixes, local names or case-insensitive spellings. Namespace prefixes
may vary but the URI cannot. No root version/UUID attribute is interpreted or
accepted in this deliberately smaller handwritten shape. Element order of Name
and Server is unrestricted. Root/object/container text and every element tail must
be only XML whitespace U+0020/U+0009/U+000A/U+000D. Properties have no nested
element or ordinary attribute. XML comments/PIs do not count as property elements.

First validate root/container structure and Name; then Server independently.
Exactly one Name must have simple text, stripped only of that XML whitespace,
which is a valid bounded IDENT. Exactly one Server must have simple text that is
exactly `true` or `false` after the same stripping. No defaults, empty-to-false,
case folding, `0/1`, or other boolean coercion. Duplicate identical values also
abstain. Duplicate Name makes identity unavailable; duplicate Server alone does
not invalidate an otherwise verified Name. Missing Name and Server differ from
malformed text. Unknown property elements invalidate the shape.

Host compares three spellings using §4 IDENT equality: receiver sliced from the
verified Go span, candidate path `<name>`, and XML Name. All three must agree
before either candidate-derived observation is emitted. This is only file/name
consistency. It never proves registered metadata ownership or receiver binding.
If selector is unavailable, both candidate observations are unavailable with
`selector_unavailable`. If Name cannot be admitted, Export is unavailable with
`candidate_identity_unavailable`; Server retains its precise XML reason. If
receiver/path/Name disagree, both use `candidate_name_mismatch`. With admitted
Name but missing/malformed Server, Export may still be observed. A missing
matching declaration does not prevent an explicit, consistently paired Server
observation. Do not gate declaration search on Export or Server values.

Closed XML reasons: `xml_missing`, `xml_limit`, `xml_forbidden`, `xml_invalid`,
`xml_shape_unsupported`, `xml_duplicate_container`, `xml_name_missing`,
`xml_name_duplicate`, `xml_name_invalid`, `xml_server_missing`,
`xml_server_duplicate`, `xml_server_invalid`.

Precedence: missing file; byte/node/depth bound; forbidden DTD; malformed XML;
wrong namespace/root or unsupported element/attribute/text shape; duplicate
root/object/properties container; missing/malformed container shape; Name
missing/duplicate/invalid; then Server missing/duplicate/invalid. In an otherwise
supported container duplicate Name/Server uses its duplicate reason before
inspecting those property contents. A nested Name/Server child or ordinary
attribute on that property uses the corresponding `*_invalid`, not generic shape.
The bounded parser can encounter DTD/limit/malformed failures in stream order;
when more than one is present, the first parser failure determines that code.
Name failure prevents use of even a valid Server boolean.

## 7. Rust source-only envelope and receipt claims

The pure library is deterministic and performs no IO, authorization, discovery,
execution, scheduling, fact-graph search, costs, or provenance authentication.
No caller-provided stronger binding state is accepted. This is a closed typed
source envelope, not an extension of synthetic facts/IAM/capability machinery.

Input exact fields:

```text
{
  "schema_version":2,
  "profile":"submitted_source_facts_v1",
  "rule_set":"source_observations_v1",
  "scope":Scope,
  "observations":{
    "selector":SelectorObservation,
    "export":ExportObservation,
    "server":ServerObservation
  },
  "receipts":{"selector":SelectorReceipt OR null,
              "export":ExportReceipt OR null,"server":ServerReceipt OR null},
  "receiver_binding":"unknown",
  "runtime_relation":"unknown"
}
Scope = {"case_id":ID,"input_id":ID,"selector_id":ID,
         "caller_entry_id":ID,"candidate_entry_id":ID,"xml_entry_id":ID OR null}
SelectorObservation = {"state":"observed","value":"qualified_selector","receipt_id":ID}
                   OR {"state":"unavailable","reason":SelectorUnavailable}
ExportObservation = {"state":"observed","value":BOOLEAN,"receipt_id":ID,"header_id":ID}
                 OR {"state":"unavailable","reason":ExportUnavailable}
ServerObservation = {"state":"observed","value":BOOLEAN,"receipt_id":ID,"property_id":ID}
                 OR {"state":"unavailable","reason":ServerUnavailable}
SelectorReceipt = {"receipt_id":ID,"case_id":ID,"input_id":ID,"selector_id":ID,
                   "entry_id":ID}
ExportReceipt = {"receipt_id":ID,"case_id":ID,"input_id":ID,"selector_id":ID,
                 "entry_id":ID,"header_id":ID}
ServerReceipt = {"receipt_id":ID,"case_id":ID,"input_id":ID,"selector_id":ID,
                 "entry_id":ID,"property_id":ID}
```

Each observation slot is mandatory. Observed requires its nonnull corresponding
receipt and matching receipt ID; unavailable requires null. Receipt IDs are
pairwise distinct, nonzero bounded integers. Receipt scope triple must equal
scope's case/input/selector triple. Entry is caller for selector, candidate for
Export and nonnull XML for Server. Header/property IDs equal their observation's
IDs. XML ID cannot equal either BSL ID. Caller/candidate IDs may coincide only
for same-file selection. IDs occupy typed local namespaces; equality across
unrelated namespaces has no meaning. Export or Server observed requires selector
observed. Selector unavailable requires both dependent unavailable reasons to be
`selector_unavailable`. No `present`, `supported`, `refuted`, `resolved`,
`static_external_resolved`, stronger relation, arbitrary reason, confidence,
text name/path/hash, source string, permission or capability field is admitted.
The Rust wire has only bounded integers, fixed string enums, booleans, objects
and the explicitly nullable slots. Names/paths/hashes remain in host references.

Closed Rust unavailable reasons:

- SelectorUnavailable = every LexReason (§5), plus `selector_span_invalid`,
  `selector_not_qualified`, `selector_outside_body`, `selector_chained`.
- ExportUnavailable = `selector_unavailable`, `candidate_identity_unavailable`,
  `candidate_name_mismatch`, `candidate_not_admitted`, `declaration_unavailable`.
- ServerUnavailable = `selector_unavailable`, `candidate_name_mismatch`, or any
  closed XML reason (§6).

Host converts Go selector `caller_not_admitted` into the actual caller LexReason.
Candidate admission reason remains available in the authorized host scan record;
Rust's Export slot uses only `candidate_not_admitted`. Candidate identity gate
precedes candidate admission/no-declaration when selecting Export reason.

The following dependency matrix is exhaustive for both host construction and
Rust admission; every combination not listed is invalid. Here `E` means Export,
`S` means Server, `observed` allows either explicit boolean, and an enum name
means an unavailable observation with that exact reason. Existing receipt/ID
constraints apply in addition to every row.

| Selector | E | S | XML entry ID |
|---|---|---|---|
| unavailable (any SelectorUnavailable) | selector_unavailable | selector_unavailable | null or ID, as host inventory says |
| observed | candidate_identity_unavailable | xml_missing | null |
| observed | candidate_identity_unavailable | IdentityFailureExceptMissing | ID |
| observed | candidate_name_mismatch | candidate_name_mismatch | ID |
| observed | observed OR candidate_not_admitted OR declaration_unavailable | observed OR ServerOnlyFailure | ID |

`IdentityFailureExceptMissing` is exactly `xml_limit`, `xml_forbidden`,
`xml_invalid`, `xml_shape_unsupported`, `xml_duplicate_container`,
`xml_name_missing`, `xml_name_duplicate`, `xml_name_invalid`.
`ServerOnlyFailure` is exactly `xml_server_missing`, `xml_server_duplicate`,
`xml_server_invalid`. These sets are closed enum subsets, not wire strings.
When selector is unavailable all three receipt slots are null. When selector is
observed, XML ID is null if and only if S is `xml_missing`; dependent
`selector_unavailable` is then always invalid. Either candidate mismatch reason
requires the other; candidate identity unavailable requires, and is required by,
a Name/shape/missing-file failure in S. In particular observed Export with
`xml_missing`/`xml_name_invalid`, and candidate identity unavailable with observed
Server, are rejected. If caller and candidate entry IDs are equal, E cannot be
`candidate_not_admitted`: an observed selector already proves that same buffer's
lexical admission within the host assertion. Receipt scope or role mismatch is
invalid regardless of this matrix. The host checks inventory-dependent XML
presence even in the selector-unavailable row; the pure kernel cannot infer it.

Rust cannot prove whether hashes, parser receipts, names or spans are authentic. A raw caller can fabricate a shape-valid host assertion, which
is why this assurance deliberately does not authenticate the workflow.

Success output exact fields, in this serialization order:

```text
{
  "schema_version":2,"profile":"submitted_source_facts_v1",
  "rule_set":"source_observations_v1",
  "assurance":"source_facts_host_asserted_no_binding_no_runtime",
  "scope":Scope,"observations":Observations,
  "receiver_binding":"unknown","runtime_relation":"unknown"
}
```

Scope and observations retain the validated input values and their listed field
order. No receipt table or additional inference is emitted. Output is compact
JSON without a newline inside the frame. Library returns a typed result or typed
error. Rust child error response is exactly
`{"protocol":"submitted_source_facts_v1","status":"error","code":Code}`,
Code one of `invalid_envelope`, `input_limit`, `io_error`, `internal_error`.
No dynamic details, and a shape-valid success cannot add workflow assurance.

## 8. Host receipts, cross-validation and disclosure

The Python host creates case/input/selector IDs locally for this invocation;
entry tokens are accepted input-core entry ID + 1. Header/property/receipt IDs
are locally allocated nonzero bounded numbers, not caller assertions. There is
one accepted input hash for the whole case. Maintain a private in-memory receipt
ledger binding each observed slot to the case/input/selector, accepted entry,
raw hash/size, verified executable hash, and exact scanner spans or XML expanded
property path. Receipt IDs are local references, not signatures or authorizations.
Before building Rust input, validate Go's complete field/enum shape; echo IDs,
size/hash against the request; every span's bounds/scalar boundaries/containment;
selected span exact equality; receiver/method/header/Export token bytes and
IDENT equality; and candidate pairing/Name/receiver agreement from the verified
buffers. The selector's entry ID must equal the caller's; the header's must equal
the candidate's. Header name bytes must equal selected method bytes under IDENT
equality. Same-file alias role admission records must be exactly equal. Validate
these response dependencies explicitly: caller unavailable iff selector reason
is `caller_not_admitted`; observed selector requires admitted caller; selector
unavailable requires header `selector_unavailable`; otherwise candidate unavailable
requires header `candidate_not_admitted`, and admitted candidate permits only an
observed header or `declaration_unavailable`. No observed header can reference an
unadmitted candidate, and no unavailable reason may contradict the admission
records. Export span must contain exactly an Export keyword. False Export must
have a null Export span and a complete recognized returned header without it.
Do not independently rerun broad BSL heuristics or infer declaration absence.
The verified scanner remains the grammar implementation; malformed evidence or
contradictory receipts fail the whole workflow instead of being repaired.

Validate kernel output against the exact submitted envelope: fixed fields,
scope, observations/receipt IDs and unknown relations must be unchanged.
Foreign, missing, duplicated, wrong-entry or cross-case/input/selector receipts
are host failures. A raw kernel replay never gets host workflow verification.

The command uses the existing CLI outer `{"result":...,"request_id":...}`
success convention, exit 0 and one final LF. Pass `output_limit=65536` explicitly
to `_ProposalCommandResult`; its existing 2 MiB default is not this contract.
Its result has exactly:

```text
{
  "schema":1,"scope":"submitted_source_facts",
  "workflow":"verified_bytes_to_source_facts_v1",
  "configuration_membership":"unverified",
  "configuration_completeness":"unverified",
  "xml_profile":"handwritten_common_module_properties_v1",
  "input_sha256":HEX64,
  "images":{"input_core":HEX64,"source_scanner":HEX64,"source_kernel":HEX64},
  "references":{"caller":SourceRef,"candidate":SourceRef,"metadata":SourceRef OR null},
  "admission":{"caller":Admission,"candidate":Admission},
  "locations":{"selector":Selector OR null,"export":Header OR null},
  "kernel":RustSuccessfulResponse
}
SourceRef = {"entry_id":UINT,"relative_path":ZIPPATH,"size_bytes":UINT,"raw_sha256":HEX64}
Admission = {"state":"admitted"} OR {"state":"unavailable","reason":LexReason}
```

SourceRef entry IDs are original input-core IDs (0..4095), unlike Rust's +1 tokens.
Only this authorized local CLI response may contain selected relative paths and
hashes; absolute archive/executable/registry paths, arbitrary identifier copies,
code, literals, XML text, query text, error text and unrelated inventory are not
disclosed. Paths can themselves contain names and are disclosed only as authorized
source references. The admission records contain only the closed Go admission results. A location
is the §5 observed Selector/Header object only when its corresponding final Rust
observation is observed; otherwise it is null. Never expose a raw Go header
whose candidate identity gate failed, even if its grammar was admitted. Do not
serialize the full Go response, private ledger or raw buffers. Human presentation must say
“lexical selector”, “candidate header Export marker” and “candidate XML Server
property”; a false boolean must not be phrased as an accessibility/runtime defect.
`workflow` asserts successful local byte-chain checks within the stated threat
model, never provenance, binding or runtime authenticity. All-abstained output
may still be a successful completed workflow.

New source-fact operation failures use closed codes only:
`SOURCE_FACTS_INVALID_ARGUMENT`, `SOURCE_FACTS_CAPABILITY_UNAVAILABLE`,
`SOURCE_FACTS_PERMISSION_DENIED`, `SOURCE_FACTS_ACCESS_UNAVAILABLE`,
`SOURCE_FACTS_INPUT_REJECTED`, `SOURCE_FACTS_ENTRY_NOT_FOUND`,
`SOURCE_FACTS_EXECUTABLE_INVALID`, `SOURCE_FACTS_READ_LIMIT`,
`SOURCE_FACTS_CANCELLED`, `SOURCE_FACTS_TIMEOUT`, `SOURCE_FACTS_LAUNCH_FAILED`,
`SOURCE_FACTS_HANDSHAKE_INVALID`, `SOURCE_FACTS_PROTOCOL_INVALID`,
`SOURCE_FACTS_CHILD_FAILED`, `SOURCE_FACTS_OUTPUT_LIMIT`,
`SOURCE_FACTS_RECEIPT_INVALID`, `SOURCE_FACTS_CLEANUP_UNCONFIRMED`,
`SOURCE_FACTS_INTERNAL_ERROR`.
Use the existing CoreError outer shape/request ID with fixed message
`Submitted source facts could not be completed` and no free-form details.
The new command needs its own non-echoing error boundary from raw argv selection
through final output. Do not rely on inherited `_Parser.error`, `_Once`,
`_emit_error`, or generic `KeyboardInterrupt` handling to satisfy this contract.
Use command-aware hooks/wrapping; leave every valid legacy command's existing
error behavior unchanged. Determine this boundary before argparse can fail:
if the first raw argument is `source-facts`, enter it; if the first argument is
not a recognized legacy command but another raw argument is exactly
`source-facts`, return fixed INVALID_ARGUMENT for invalid command placement.
A recognized legacy command in first position keeps the legacy flow even if a
later argument value happens to equal `source-facts`. Other invocations are
unchanged. This dispatch inspection does not open or echo any argument value.

Within that boundary, unknown/repeated flags, missing arguments, invalid integer
lexemes, invalid command placement and other argument failures map to
SOURCE_FACTS_INVALID_ARGUMENT without argparse's original text or usage echo.
Normal explicit `source-facts --help` may print static help and exit 0. Wrap
identity/registry/context admission too: explicit `PROJECT_FORBIDDEN` maps to
SOURCE_FACTS_PERMISSION_DENIED; inability to establish current identity/project
access maps to SOURCE_FACTS_ACCESS_UNAVAILABLE. Do not let a generic access code
or message escape in this command, including before a context exists. Reapply
this mapping to `_emit_error`-equivalent final permission replacement *after*
serialization. A final permission-check exception cannot restore its arbitrary
message/details or the previous source-bearing response. Emit `details: {}`
with the fixed message and current request ID. KeyboardInterrupt/cancellation
at argument, identity, read, child wait, parse, serialization or final-error phase
maps to SOURCE_FACTS_CANCELLED after owned-child cleanup, never generic
publication/recovery wording. Other unexpected exceptions map to the listed
phase code, or SOURCE_FACTS_INTERNAL_ERROR when no narrower listed code applies.
All paths require the same no-echo policy; no traceback or chained exception
may be printed. Preserve other commands' existing codes and recovery language.
Input-core/archive/path-admission failure maps to INPUT_REJECTED; an exact
selected BSL inventory path absent maps to ENTRY_NOT_FOUND; a source cap before
read maps to READ_LIMIT. XML parse/shape failures are observations, not operation
failures. New child invalid/error/nonzero results never release partial facts.
Cleanup-unconfirmed overrides other operation failures; otherwise a final
permission/access failure overrides all source-bearing payloads. Cancellation
uses this command's fixed error, never existing publication-recovery language.

## 9. Freeze and finite acceptance

Freeze this document's SHA-256, implementation source commit/build inputs, and
all three executable hashes before withheld ZIP access. Fixture authoring must
use this contract and independent handwritten sources; expected labels never
enter source request arguments or observation inputs. Do not inspect future
held-out contents during implementation. Any protocol/grammar change requires
an explicit recorded new freeze and fresh independent withheld qualification;
never silently tune acceptance after seeing withheld cases.

Required positive mechanics include both Export and Server values, paired
counterfactuals, RU/EN/mixed keywords and identifiers, BOM and CRLF, same-line
multiple selectors, comment/string decoys, same-file alias, source preservation,
immutable input and image replacement, and independently checked hashes/spans.
Mandatory negatives include reserved routine/parameter/selector names in RU/EN,
every lexical/XML reason, every limit, malformed
exact selection, missing declaration, mismatched Name/path/receiver, duplicate
identical XML values, shadowing, platform-property names and partial/orphan inputs.
Binding-negative inputs can yield scoped facts but never a stronger relation.
Test each wire's duplicate/unknown fields, object-only records, integer lexemes,
null/enum/type errors, EOF/trailing/partial data, bad hashes, wrong spans, forged
binding, cross-case receipts, stderr/stdout floods, cancellation/revocation at
read/launch/wait/parse/serialization, parent death, nonzero exit and cleanup failure.
Canaries in source literals/names/paths/malformed errors are checked separately
at Go, Rust, host error and authorized-reference disclosure boundaries.

Run the actual Python -> immutable input-core -> Go -> Rust path, not fixture
labels or synthetic-only substitutes. Preserve synthetic v1 exact-output and
input-core ownership regressions. Independently record passed/failed/unrun
stages, denominator of known facts and abstentions, wall time and peak RSS.
Acceptance in the frozen finite suite requires zero incorrect source facts,
zero missing mandatory abstentions, zero stronger diagnoses/binding claims and
zero unauthorized disclosure/action. Prior 22/24 diagnosis and proposed 20%
broader-call coverage thresholds do not apply and are not considered passed.
A full compiler, genuine Designer/native execution, stronger namespace premises,
general evidence framework and real call-diagnosis qualification remain deferred.
