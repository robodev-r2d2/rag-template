"""Base interface for document access updates."""

from abc import ABC, abstractmethod


class DocumentAccessManager(ABC):
    """API endpoint abstraction for updating document access metadata."""

    @abstractmethod
    def update_access(self, document_id: str, access_groups: list[str]) -> None:
        """Persist access groups for the given document identifier."""

        raise NotImplementedError()
