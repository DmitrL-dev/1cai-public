# Explicit context size for local repairs

## Purpose

Allow a new prepared profile to request a smaller Ollama context on a machine with limited memory. Existing profiles resolve to 32768. This setting changes a new request and requires new installed/native evidence; it never changes the retained C7/D9 trial.

## Contract

- Profile `context_tokens` is an integer from 8192, 16384, 32768. A missing field means 32768. JavaScript validates the numeric integer value; Python additionally requires the decoded type to be `int`, rejecting JSON forms such as `8192.0` or `8192e0` before output or model activity.
- Preparation writes the field and, when an Ollama model is selected, the matching Cline setting. Companion freezes it, journals it in each new repair request and passes an equality assertion to Python. A changed context size between activation and execution is rejected.
- The model receives this exact `num_ctx`, with existing 4096 output tokens, no reasoning by default, one model request, `keep_alive=0` and the existing timeout.
- Metrics retain `num_ctx`, serialized request byte count and SHA-256. New request/result context mismatches cannot acquire an analysis-qualified status. Legacy journal entries remain readable without a retrospective context claim.
- For reduced contexts, the complete serialized UTF-8 request must fit `context_tokens - 4096 - 512` bytes. This is a conservative client byte limit including diagnostics, escapes and both schema occurrences. It is not an exact tokenizer measurement or a guarantee for arbitrary model templates. The previous default byte limits remain compatible.

## Verification

First prove profile resolution, strict validation, exact wire options and byte-limit boundary with a local HTTP fixture. Then prove preparation/Companion propagation and mismatch refusal. Package the changed adapter reproducibly. A later native trial records the explicit selected context, fresh package/source pins and server settings; RAM/commit/VRAM admission and general model quality remain separate gates.

8192 permits only short serialized requests. A longer daily scenario must use a size whose byte guard admits its complete request; admission does not establish available RAM or VRAM.

## Scope

No new tokenizer dependency, mutable environment override, prompt truncation, production deployment or revision of old evidence. Core protocol and live recovery are unchanged.
