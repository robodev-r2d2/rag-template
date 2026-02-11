"""Knowledge spaces package."""

from rag_core_api.knowledge_spaces.access_service import (
    KnowledgeSpaceAccessDeniedError,
    KnowledgeSpaceAccessService,
)
from rag_core_api.knowledge_spaces.collection_router import KnowledgeSpaceCollectionRouter
from rag_core_api.knowledge_spaces.models import (
    DocumentVisibilityMetadata,
    KnowledgeSpace,
    KnowledgeSpaceType,
)

__all__ = [
    "KnowledgeSpace",
    "KnowledgeSpaceType",
    "DocumentVisibilityMetadata",
    "KnowledgeSpaceAccessService",
    "KnowledgeSpaceAccessDeniedError",
    "KnowledgeSpaceCollectionRouter",
]
