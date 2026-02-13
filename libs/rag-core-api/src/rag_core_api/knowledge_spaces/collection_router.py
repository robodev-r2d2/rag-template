"""Mapping between logical knowledge spaces and physical vector collections."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rag_core_api.impl.settings.knowledge_space_settings import KnowledgeSpaceSettings
from rag_core_api.knowledge_spaces.models import KnowledgeSpace, KnowledgeSpaceType

if TYPE_CHECKING:
    from rag_core_api.impl.settings.vector_db_settings import VectorDatabaseSettings


class KnowledgeSpaceCollectionRouter:
    """Resolves physical collection names for logical knowledge spaces."""

    def __init__(self, settings: KnowledgeSpaceSettings, vector_settings: "VectorDatabaseSettings"):
        self._settings = settings
        self._vector_settings = vector_settings

    @property
    def strategy(self) -> str:
        """Return selected multitenancy collection strategy."""
        return self._settings.collection_strategy

    @property
    def default_collection_name(self) -> str:
        """Return default collection configured for single strategy."""
        return self._vector_settings.collection_name

    def collection_for_space(self, space: KnowledgeSpace) -> str:
        """Map space to physical collection name based on strategy."""
        if self._settings.collection_strategy == "single":
            return self._vector_settings.collection_name

        if space.type == KnowledgeSpaceType.TENANT:
            if not space.tenant_id:
                raise ValueError("Tenant knowledge space requires tenant_id.")
            return self._settings.tenant_collection_template.format(tenant_id=space.tenant_id)
        if space.type == KnowledgeSpaceType.SHARED_DOMAIN:
            if not space.domain_id:
                raise ValueError("Shared-domain knowledge space requires domain_id.")
            return self._settings.shared_domain_collection_template.format(domain_id=space.domain_id)
        if space.type == KnowledgeSpaceType.GLOBAL:
            return self._settings.global_collection_name
        raise ValueError(f"Unknown knowledge space type: {space.type}")
