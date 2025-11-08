"""Default implementation for updating document access metadata."""

from fastapi import HTTPException, status

from rag_core_api.api_endpoints.document_access_manager import DocumentAccessManager
from rag_core_api.vector_databases.vector_database import VectorDatabase
from rag_core_lib.impl.settings.access_control_settings import AccessControlSettings


class DefaultDocumentAccessManager(DocumentAccessManager):
    """Persist access control information inside the vector database."""

    def __init__(self, vector_database: VectorDatabase, access_settings: AccessControlSettings):
        self._vector_database = vector_database
        self._settings = access_settings

    def update_access(self, document_id: str, access_groups: list[str]) -> None:
        try:
            sanitized = [group for group in dict.fromkeys(access_groups) if group]
            if not sanitized:
                sanitized = [self._settings.default_group]
            self._vector_database.update_access_groups(document_id, sanitized, self._settings.metadata_key)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update document access: {exc}",
            ) from exc
