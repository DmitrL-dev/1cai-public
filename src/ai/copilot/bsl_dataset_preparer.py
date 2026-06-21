"""BSL dataset preparation helpers for local copilot training data."""

from typing import Dict


class BSLDatasetPreparer:
    """Builds instruction-tuning samples from BSL snippets."""

    def prepare_single_sample(self, code: str, description: str) -> Dict[str, str]:
        return {
            "instruction": description.strip()
            or "Generate or explain the supplied 1C BSL code.",
            "input": code.strip(),
            "output": code.strip(),
        }


__all__ = ["BSLDatasetPreparer"]
