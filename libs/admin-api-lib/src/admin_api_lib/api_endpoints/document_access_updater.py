"""Interface for updating document access configuration."""

from abc import ABC, abstractmethod

from rag_core_lib.impl.data_types.access_control import DocumentAccessUpdate


class DocumentAccessUpdater(ABC):
    """Update access groups for managed documents."""

    @abstractmethod
    async def update_access(self, document_id: str, update: DocumentAccessUpdate) -> None:
        """Persist access changes for a document."""

        raise NotImplementedError()
