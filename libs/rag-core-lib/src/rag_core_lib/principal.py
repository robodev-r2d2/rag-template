"""Principal model shared across services."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PrincipalType(StrEnum):
    """Supported principal categories."""

    AUTHENTICATED = "authenticated"
    ANONYMOUS = "anonymous"


class Principal(BaseModel):
    """Resolved identity and authorization claims for a request."""

    principal_type: PrincipalType = PrincipalType.AUTHENTICATED
    subject: str | None = None
    tenant_id: str | None = None
    allowed_tenant_ids: list[str] = Field(default_factory=list)
    allowed_domain_ids: list[str] = Field(default_factory=list)
    can_write_shared_domain: bool = False
    can_write_global: bool = False
    token_claims: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_anonymous(self) -> bool:
        """Return whether this principal is anonymous."""
        return self.principal_type == PrincipalType.ANONYMOUS

    @classmethod
    def anonymous(cls) -> "Principal":
        """Build an anonymous principal."""
        return cls(principal_type=PrincipalType.ANONYMOUS, subject="anonymous")

