"""
Custom exception hierarchy for LLM API utilities.

All exceptions carry the originating provider name and, where available,
an HTTP status code so callers can branch on specific failure modes.
"""

from __future__ import annotations

from typing import Optional


class APIError(Exception):
    """Base class for all LLM API errors.

    Attributes:
        message:    Human-readable description.
        provider:   The provider that raised the error ("openai", "claude",
                    "gemini", or "unknown").
        status_code: HTTP status if available, else None.
    """

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"provider={self.provider!r}, "
            f"status_code={self.status_code}, "
            f"message={self.message!r})"
        )


class APIKeyError(APIError):
    """Raised when the API key is missing or rejected (HTTP 401/403)."""


class APIRateLimitError(APIError):
    """Raised when the provider returns a rate-limit response (HTTP 429)."""


class APIConnectionError(APIError):
    """Raised on network-level failures (DNS, timeout, connection refused)."""


class APIResponseError(APIError):
    """Raised when the provider returns an unexpected or malformed payload."""


class APIValidationError(APIError):
    """Raised when the request itself is invalid before it is sent
    (e.g. missing required fields, unsupported model name)."""


# ---------------------------------------------------------------------------
# Helper used by provider adapters to convert SDK exceptions
# ---------------------------------------------------------------------------

def handle_openai_error(exc: Exception, provider: str = "openai") -> APIError:
    """Map an openai SDK exception to the appropriate APIError subclass."""
    try:
        import openai
    except ImportError:
        return APIError(str(exc), provider)

    if isinstance(exc, openai.AuthenticationError):
        return APIKeyError(str(exc), provider, status_code=401)
    if isinstance(exc, openai.PermissionDeniedError):
        return APIKeyError(str(exc), provider, status_code=403)
    if isinstance(exc, openai.RateLimitError):
        return APIRateLimitError(str(exc), provider, status_code=429)
    if isinstance(exc, openai.APIConnectionError):
        return APIConnectionError(str(exc), provider)
    if isinstance(exc, openai.BadRequestError):
        return APIValidationError(str(exc), provider, status_code=400)
    if isinstance(exc, openai.APIStatusError):
        return APIResponseError(str(exc), provider, status_code=exc.status_code)
    return APIError(str(exc), provider)


def handle_anthropic_error(exc: Exception, provider: str = "claude") -> APIError:
    """Map an anthropic SDK exception to the appropriate APIError subclass."""
    try:
        import anthropic
    except ImportError:
        return APIError(str(exc), provider)

    if isinstance(exc, anthropic.AuthenticationError):
        return APIKeyError(str(exc), provider, status_code=401)
    if isinstance(exc, anthropic.PermissionDeniedError):
        return APIKeyError(str(exc), provider, status_code=403)
    if isinstance(exc, anthropic.RateLimitError):
        return APIRateLimitError(str(exc), provider, status_code=429)
    if isinstance(exc, anthropic.APIConnectionError):
        return APIConnectionError(str(exc), provider)
    if isinstance(exc, anthropic.BadRequestError):
        return APIValidationError(str(exc), provider, status_code=400)
    if isinstance(exc, anthropic.APIStatusError):
        return APIResponseError(str(exc), provider, status_code=exc.status_code)
    return APIError(str(exc), provider)


def handle_google_error(exc: Exception, provider: str = "gemini") -> APIError:
    """Map a google-generativeai / google-genai exception to APIError."""
    exc_str = str(exc)
    exc_type = type(exc).__name__

    # google.api_core.exceptions use status codes in the message
    if "401" in exc_str or "UNAUTHENTICATED" in exc_type or "UNAUTHENTICATED" in exc_str:
        return APIKeyError(exc_str, provider, status_code=401)
    if "403" in exc_str or "PERMISSION_DENIED" in exc_type or "PERMISSION_DENIED" in exc_str:
        return APIKeyError(exc_str, provider, status_code=403)
    if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_type or "RESOURCE_EXHAUSTED" in exc_str:
        return APIRateLimitError(exc_str, provider, status_code=429)
    if "ServiceUnavailable" in exc_type or "DeadlineExceeded" in exc_type:
        return APIConnectionError(exc_str, provider)
    if "InvalidArgument" in exc_type or "400" in exc_str:
        return APIValidationError(exc_str, provider, status_code=400)
    return APIError(exc_str, provider)
