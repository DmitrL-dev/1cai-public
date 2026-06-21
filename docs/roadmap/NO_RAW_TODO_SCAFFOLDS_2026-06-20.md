# No Raw TODO Scaffolds - 2026-06-20

## Why

Several developer-facing fallback paths could still show `TODO` placeholders:

- BSL editor default sample;
- legacy Copilot completion fallback;
- Python/Jest test generators;
- grounded BSL generation.

For a buyer demo this reads as unfinished tooling. For a developer it also weakens trust in local/offline
generation because the output looks like a generic scaffold instead of a controlled engineering artifact.

## Implemented

- Replaced the BSL editor default `TODO` sample line with a `RENTGEN-GUARD` instruction.
- Replaced local Copilot fallback `// TODO` suggestions with guarded branch/loop snippets.
- Added UTF-8 BSL keyword coverage for real `Если`, `Для Каждого`, `Запрос` and `Результат` lines in fallback completions.
- Replaced Python/Jest `TODO: Add specific assertions` with concrete baseline assertions.
- Added regression tests covering completion snippets, Python/Jest generated tests and the BSL editor source.

## Buyer Impact

Developers no longer see raw unfinished placeholders when they touch fallback generation paths.
The local product story becomes more credible: even offline suggestions carry explicit guardrails and runnable
baseline checks.

## Verification

- `python -m py_compile src/services/rentgen/grounded_codegen.py src/modules/copilot/services/completion_service.py src/modules/copilot/services/copilot_service.py src/modules/copilot/application/service.py src/modules/test_generation/services/generators/python_generator.py src/modules/test_generation/services/generators/js_generator.py`
- `pytest tests/unit/test_no_todo_scaffolds.py tests/unit/test_grounded_codegen.py -q`
