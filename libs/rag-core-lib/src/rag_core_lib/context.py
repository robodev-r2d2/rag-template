"""Module for managing execution context."""

from contextvars import ContextVar
from typing import Optional

from rag_core_lib.principal import Principal

_tenant_id_ctx_var: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
_principal_ctx_var: ContextVar[Optional[Principal]] = ContextVar("principal", default=None)
_requested_space_ids_ctx_var: ContextVar[list[str]] = ContextVar("requested_space_ids", default=[])
_target_space_id_ctx_var: ContextVar[Optional[str]] = ContextVar("target_space_id", default=None)


def get_tenant_id() -> Optional[str]:
    """Get the current tenant ID."""
    principal = get_principal()
    if principal and principal.tenant_id:
        return principal.tenant_id
    return _tenant_id_ctx_var.get()


def set_tenant_id(tenant_id: str) -> None:
    """Set the current tenant ID."""
    _tenant_id_ctx_var.set(tenant_id)


def clear_tenant_id() -> None:
    """Clear the current tenant ID."""
    _tenant_id_ctx_var.set(None)


def get_principal() -> Optional[Principal]:
    """Get the current principal."""
    return _principal_ctx_var.get()


def set_principal(principal: Principal) -> None:
    """Set the current principal."""
    _principal_ctx_var.set(principal)


def clear_principal() -> None:
    """Clear the current principal."""
    _principal_ctx_var.set(None)


def get_requested_space_ids() -> list[str]:
    """Get requested space identifiers for current request."""
    return _requested_space_ids_ctx_var.get()


def set_requested_space_ids(space_ids: list[str]) -> None:
    """Set requested space identifiers for current request."""
    _requested_space_ids_ctx_var.set(space_ids)


def clear_requested_space_ids() -> None:
    """Clear requested space identifiers for current request."""
    _requested_space_ids_ctx_var.set([])


def get_target_space_id() -> Optional[str]:
    """Get target upload/delete space id for current request."""
    return _target_space_id_ctx_var.get()


def set_target_space_id(space_id: str | None) -> None:
    """Set target upload/delete space id for current request."""
    _target_space_id_ctx_var.set(space_id)


def clear_target_space_id() -> None:
    """Clear target upload/delete space id for current request."""
    _target_space_id_ctx_var.set(None)
