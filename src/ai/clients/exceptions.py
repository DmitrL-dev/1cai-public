

class LLMNotConfiguredError(RuntimeError):
    """Raised when an LLM client is not configured with credentials."""


class LLMCallError(RuntimeError):
    """Raised when an LLM call fails."""
