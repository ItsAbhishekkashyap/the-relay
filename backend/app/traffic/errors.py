"""Exception hierarchy for the asynchronous traffic manager."""

from typing import Optional, Dict, Any
from app.providers.base import RateLimitError
from app.providers.schemas import ErrorCategory


class TrafficManagerError(Exception):
    """Base exception for all traffic-manager operations and policies."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Return serializable representation of error details."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class QueueFullError(TrafficManagerError):
    """Raised immediately when the FIFO waiting queue has reached maximum capacity."""

    def __init__(
        self,
        message: str = "Traffic manager request queue is full",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)


class RequestTimeoutError(TrafficManagerError):
    """Base exception for deadline expirations within the traffic management pipeline."""

    def __init__(
        self,
        message: str,
        phase: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.phase = phase  # "queue" or "execution"


class QueueTimeoutError(RequestTimeoutError):
    """Raised when a request deadline expires while waiting in the FIFO queue before admission."""

    def __init__(
        self,
        message: str = "Request deadline expired while waiting in queue",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, phase="queue", details=details)


class ExecutionTimeoutError(RequestTimeoutError):
    """Raised when a request deadline expires during provider execution."""

    def __init__(
        self,
        message: str = "Request deadline expired during provider execution",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, phase="execution", details=details)


class LocalRateLimitError(TrafficManagerError, RateLimitError):
    """Raised when local rate admission constraints (RPM, TPM, daily budget) are exceeded.

    Inherits from both TrafficManagerError and RateLimitError to maintain seamless
    compatibility with provider error categorizers and upstream retry handlers.
    """

    def __init__(
        self,
        message: str = "Local rate limit exceeded",
        status_code: int = 429,
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[float] = None,
    ):
        TrafficManagerError.__init__(self, message, details)
        RateLimitError.__init__(
            self,
            message=message,
            status_code=status_code,
            provider_name="traffic_manager",
            details=details,
            retry_after=retry_after,
        )


class StreamAlreadyStartedError(TrafficManagerError):
    """Raised when a stream encounters an unrecoverable failure after tokens were already delivered.

    Streams must never be transparently restarted once partial content has reached the caller.
    """

    def __init__(
        self,
        message: str = "Stream failed after partial content was already emitted to the caller",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)


class TrafficManagerClosedError(TrafficManagerError):
    """Raised when a request is submitted to a closed or shutting-down traffic manager."""

    def __init__(
        self,
        message: str = "Traffic manager is closed and cannot accept new requests",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)

