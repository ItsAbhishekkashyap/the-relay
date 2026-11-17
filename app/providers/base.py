"""Abstract base class and exception hierarchy for model providers."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any

from app.providers.schemas import (
    ErrorCategory,
    GenerationRequest,
    GenerationResponse,
    StreamChunk,
)


class ModelProviderError(Exception):
    """Base exception for all model provider errors."""

    def __init__(
        self,
        message: str,
        error_category: ErrorCategory,
        status_code: Optional[int] = None,
        provider_name: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[float] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_category = error_category
        self.status_code = status_code
        self.provider_name = provider_name
        self.details = details or {}
        self.retry_after = retry_after

    def to_dict(self) -> Dict[str, Any]:
        """Return serializable representation of error details (safe for logging/responses)."""
        data: Dict[str, Any] = {
            "error_category": self.error_category.value,
            "message": self.message,
            "provider_name": self.provider_name,
            "status_code": self.status_code,
        }
        if self.retry_after is not None:
            data["retry_after"] = self.retry_after
        if self.details:
            data["details"] = self.details
        return data


class RateLimitError(ModelProviderError):
    """Raised when rate limits (RPM, TPM, or daily quota) are exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        status_code: int = 429,
        provider_name: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[float] = None,
    ):
        super().__init__(
            message=message,
            error_category=ErrorCategory.RATE_LIMITED,
            status_code=status_code,
            provider_name=provider_name,
            details=details,
            retry_after=retry_after,
        )


class AuthenticationError(ModelProviderError):
    """Raised when API credentials are missing, invalid, or forbidden."""

    def __init__(
        self,
        message: str = "Authentication failed",
        status_code: int = 401,
        provider_name: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_category=ErrorCategory.AUTHENTICATION_FAILURE,
            status_code=status_code,
            provider_name=provider_name,
            details=details,
        )


class TimeoutError(ModelProviderError):
    """Raised when a request or stream times out."""

    def __init__(
        self,
        message: str = "Provider request timed out",
        status_code: int = 408,
        provider_name: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_category=ErrorCategory.TIMEOUT,
            status_code=status_code,
            provider_name=provider_name,
            details=details,
        )


class ProviderServerError(ModelProviderError):
    """Raised when the upstream provider experiences internal server errors (5xx)."""

    def __init__(
        self,
        message: str = "Provider server error",
        status_code: int = 500,
        provider_name: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_category=ErrorCategory.SERVER_ERROR,
            status_code=status_code,
            provider_name=provider_name,
            details=details,
        )


class ConnectionError(ModelProviderError):
    """Raised when network connection or transport fails."""

    def __init__(
        self,
        message: str = "Failed to connect to provider",
        status_code: Optional[int] = None,
        provider_name: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_category=ErrorCategory.CONNECTION_FAILURE,
            status_code=status_code,
            provider_name=provider_name,
            details=details,
        )


class InvalidResponseError(ModelProviderError):
    """Raised when the provider returns a malformed or 4xx bad request response."""

    def __init__(
        self,
        message: str = "Invalid response from provider",
        status_code: int = 400,
        provider_name: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_category=ErrorCategory.INVALID_RESPONSE,
            status_code=status_code,
            provider_name=provider_name,
            details=details,
        )


class BaseModelProvider(ABC):
    """Common interface for model providers (Groq and Simulator)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier name of the provider."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Default model name used by this provider."""
        ...

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate a complete chat completion."""
        ...

    @abstractmethod
    async def stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        """Stream chunks of chat completion."""
        ...

