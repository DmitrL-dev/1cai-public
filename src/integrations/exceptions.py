

class IntegrationError(RuntimeError):
    """Base error for integration failures."""


class IntegrationConfigError(IntegrationError):
    """Raised when integration configuration is missing or invalid."""
