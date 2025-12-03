"""Module for managing execution context."""

from contextvars import ContextVar
from typing import Optional

_tenant_id_ctx_var: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)


def get_tenant_id() -> Optional[str]:
    """Get the current tenant ID."""
    return _tenant_id_ctx_var.get()


def set_tenant_id(tenant_id: str) -> None:
    """Set the current tenant ID."""
    _tenant_id_ctx_var.set(tenant_id)


def clear_tenant_id() -> None:
    """Clear the current tenant ID."""
    _tenant_id_ctx_var.set(None)
