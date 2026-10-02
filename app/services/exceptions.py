"""Service-layer exceptions with HTTP status codes."""


class ServiceError(Exception):
    """Predictable failure surfaced as structured API error."""

    def __init__(self, message: str, code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
