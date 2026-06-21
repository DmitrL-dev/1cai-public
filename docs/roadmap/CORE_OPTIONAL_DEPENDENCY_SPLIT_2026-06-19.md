# Core / Optional Dependency Split

Date: 2026-06-19.

## Purpose

Keep the Rentgen baseline install aligned with the product promise: local SQLite core, no mandatory cloud AI, no mandatory Neo4j/Qdrant.

## Implemented

- `requirements.txt` remains the baseline install.
- `requirements-optional.txt` now contains optional OpenAI, Qdrant, sentence-transformers and Neo4j integrations.
- `requirements-ml.txt` remains the heavy ML profile for PyTorch/scikit-learn/mlflow.
- README quick start and HANDOFF now explain the split.
- App cold import was checked with development JWT settings.

## Verification

- `python -c "from src.main import app; print('app-import-ok', app.title)"`
- Existing optional Archi health is guarded as `legacy_optional_*`.

## Product Meaning

The buyer can install and demo the core local product without accidentally pulling vector DB, Neo4j or cloud-AI client dependencies into the baseline.
