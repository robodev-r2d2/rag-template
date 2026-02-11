"""Helpers for building request principals from JWT claims."""

from __future__ import annotations

from typing import Any

from rag_core_lib.principal import Principal, PrincipalType


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None and str(item).strip()]
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return []
        if "," in trimmed:
            return [item.strip() for item in trimmed.split(",") if item.strip()]
        return [trimmed]
    return [str(value)]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def principal_from_claims(claims: dict[str, Any]) -> Principal:
    """Build an authenticated principal from decoded JWT claims."""
    tenant_id = claims.get("tenant_id")
    allowed_tenant_ids = _as_list(claims.get("allowed_tenant_ids"))
    if tenant_id and tenant_id not in allowed_tenant_ids:
        allowed_tenant_ids.insert(0, str(tenant_id))

    return Principal(
        principal_type=PrincipalType.AUTHENTICATED,
        subject=claims.get("sub") or claims.get("preferred_username"),
        tenant_id=str(tenant_id) if tenant_id else None,
        allowed_tenant_ids=allowed_tenant_ids,
        allowed_domain_ids=_as_list(claims.get("allowed_domain_ids")),
        can_write_shared_domain=_as_bool(claims.get("can_write_shared_domain")),
        can_write_global=_as_bool(claims.get("can_write_global")),
        token_claims=claims,
    )
