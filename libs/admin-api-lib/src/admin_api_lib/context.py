"""Context helpers for admin-api-lib."""

from contextvars import ContextVar
from typing import Optional

_token_ctx: ContextVar[Optional[str]] = ContextVar("current_token", default=None)


def set_current_token(token: Optional[str]) -> None:
    """Store the current bearer token in context."""
    _token_ctx.set(token)


def get_current_token() -> Optional[str]:
    """Retrieve the current bearer token from context."""
    return _token_ctx.get()


def clear_current_token() -> None:
    """Clear the stored bearer token."""
    _token_ctx.set(None)
