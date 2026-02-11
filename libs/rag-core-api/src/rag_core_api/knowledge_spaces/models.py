"""Knowledge space domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class KnowledgeSpaceType(StrEnum):
    """Logical knowledge space types."""

    TENANT = "tenant"
    SHARED_DOMAIN = "shared_domain"
    GLOBAL = "global"


class KnowledgeSpace(BaseModel):
    """Logical knowledge space definition."""

    id: str
    type: KnowledgeSpaceType
    domain_id: str | None = None
    tenant_id: str | None = None
    display_name: str
    enabled: bool = True


class DocumentVisibilityMetadata(BaseModel):
    """Metadata fields stored on vector documents for ACL and attribution."""

    visibility: KnowledgeSpaceType
    tenant_id: str | None = None
    domain_id: str | None = None
    space_id: str
    owner_tenant_id: str | None = None
