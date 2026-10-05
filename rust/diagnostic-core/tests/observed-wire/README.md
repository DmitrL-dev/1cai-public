# Observed wire regression vectors

These are publicly exposable regression vectors mechanically exported from one completed synthetic v2 run. They are recorded-output regression data, not a second evaluation or fresh heldout evidence. Their future use in CI makes them public regression fixtures; do not call a later pass an independent heldout result.

Each vector contains the exact input bytes as lowercase hexadecimal, a SHA256, the recorded semantic JSON response or protocol error code, the original process exit code, stdout/stderr hashes, and every original journal occurrence. Inputs were reconstructed from frozen fixtures and the recorded observation flow; all249 request hashes and response/exit records had to match before export. Identical inputs were deduplicated only when their recorded response and exit semantics agreed. No Rust process, rule oracle, native probe, network call or new evaluation was used for this export.

Decode input_hex into bytes and call the existing diagnostic evaluate(bytes) entry point. For semantic_json, compare JSON structurally with exact JSON types; object key ordering is irrelevant and array ordering is significant. For protocol_error, require the indicated error category. process_exit_code and stdout/stderr hashes document the original CLI run; a library-level test need not spawn that CLI. The export's byte hashes do not replace independent rule-grounded evaluation.

Everything is owned synthetic data, including deliberately invalid tokens and obvious synthetic secret/path/name canaries in rejected inputs. There is no real customer information, private authoring script, internal coordination note, LLM output or copied documentation corpus here.

Shards target96KiB. A few single-vector shards exceed that size because preserved 64KiB boundary inputs require about128KiB in hexadecimal; they must not be truncated or normalized. The limits and incomplete-recall caveats of the original synthetic run remain unchanged. No production/native qualification or generalization claim follows from these vectors.
