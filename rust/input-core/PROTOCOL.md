# submitted-zip-v1 wire protocol

Every frame is a four-byte unsigned little-endian payload length, followed by
exactly that many UTF-8 JSON bytes. Length must be 1..65,536 and is checked before
allocating the payload. No NDJSON, trailing JSON documents, NaN/Infinity, duplicate
fields or unknown request fields are accepted. Integer fields must be JSON
integers, not booleans/floats/strings. IDs, offsets and limits are nonnegative.

First output, after Linux ownership/resource setup:

```json
{"protocol":1,"kind":"hello","implementation":"rentgen-input-core","contract":"submitted-zip-v1"}
```

Requests are flat objects. `seq` is a u64, starts at 1, and increases by exactly
one for every request, including requests returning nonfatal errors. Only one
import attempt is allowed. A failed import ends the process. A second import
following success returns INVALID_STATE and terminates.

```json
{"protocol":1,"seq":1,"op":"open_import","path":"/trusted/export.zip","expected_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
{"protocol":1,"seq":2,"op":"entries","offset":0,"limit":32}
{"protocol":1,"seq":3,"op":"read_entry","entry_id":0,"offset":0,"limit":32768}
{"protocol":1,"seq":4,"op":"close"}
```

`expected_sha256` is exactly 64 lowercase hexadecimal ASCII characters. The
archive must fully validate before `open_import` returns. Result shapes:

```json
{"protocol":1,"seq":1,"result":{"input_sha256":"<64 lowercase hex>","entries_count":2,"files_count":1,"total_bytes":7}}
{"protocol":1,"seq":2,"result":{"entries":[{"entry_id":0,"path":"Configuration.xml","size_bytes":7,"raw_sha256":"<64 lowercase hex>"}],"next_offset":null}}
{"protocol":1,"seq":3,"result":{"entry_id":0,"offset":0,"total_bytes":7,"raw_sha256":"<whole file SHA256>","data_base64":"PHJvb3QvPg==","next_offset":null}}
{"protocol":1,"seq":4,"result":{"closed":true}}
```

`entries_count` includes directories; `files_count` and metadata pagination include
only files. IDs are zero-based, sequential in central-directory order. Paths are
archive-relative and never unwrap a top-level folder. `total_bytes` in the open
result counts all decoded file bytes. `raw_sha256` always hashes the whole decoded
file, not the returned chunk. `next_offset` is null at the end; otherwise it is the
next index (metadata) or byte offset (read). An offset exactly at the end returns
an empty page/chunk with null continuation. A zero limit or offset beyond the end
is invalid. Metadata pages may be shorter than the requested limit to keep
escaped names and the envelope inside the frame bound.

Replies contain either `result` or `error`, never both. Error codes and messages:

| Code | Exact message |
|---|---|
| INVALID_REQUEST | Invalid request. |
| INVALID_SEQUENCE | Invalid request sequence. |
| INVALID_STATE | Operation is not valid in this session state. |
| INVALID_PATH | Input path is not an accepted local regular file. |
| INPUT_CHANGED | Input changed while being imported. |
| HASH_MISMATCH | Input bytes do not match the expected SHA256. |
| LIMIT_EXCEEDED | Input or request exceeds a configured limit. |
| INVALID_ARCHIVE | Input is not an accepted ZIP archive. |
| UNSUPPORTED_ARCHIVE | ZIP feature is outside the accepted profile. |
| IO_ERROR | Input or transport operation failed. |
| DEADLINE_EXCEEDED | Session deadline exceeded. |
| INTERNAL_ERROR | Input session failed. |

```json
{"protocol":1,"seq":1,"error":{"code":"HASH_MISMATCH","message":"Input bytes do not match the expected SHA256."}}
```

Malformed JSON/fields or malformed/oversized framing return error sequence 0,
then exit nonzero. Wrong protocol or sequence returns the supplied sequence, then
exits nonzero. Failed import exits nonzero after its error. Invalid pagination,
read IDs/offsets/limits or reads before import return a bounded error and permit
close. A transport failure or kernel deadline may end the process without any
error frame. Startup failure emits no hello. Error messages never include caller
paths, OS error text, XML or source snippets.

Close is valid before or after import. It drops the owned source/buffers before
acknowledging, then exits 0. EOF also releases the process-owned session but exits
nonzero, since it is not a verified close handshake. The parent must drain stdout
to EOF, reject extra output, and confirm exit 0 before accepting normal completion.
EOF alone, an acknowledgment alone, a sent signal, or an unconfirmed wait does
not establish successful cleanup. See README for local-filesystem and
uninterruptible-I/O limitations.
