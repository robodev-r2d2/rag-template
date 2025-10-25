"""Update document access by calling the rag backend."""

import asyncio
import json
import logging
from urllib import request as urllib_request
from urllib.error import HTTPError

from fastapi import HTTPException, status

from admin_api_lib.api_endpoints.document_access_updater import DocumentAccessUpdater
from admin_api_lib.impl.settings.rag_api_settings import RAGAPISettings
from rag_core_lib.impl.data_types.access_control import DocumentAccessUpdate

logger = logging.getLogger(__name__)


class DefaultDocumentAccessUpdater(DocumentAccessUpdater):
    """Use the rag backend REST API to update document permissions."""

    def __init__(self, rag_settings: RAGAPISettings):
        self._settings = rag_settings

    async def update_access(self, document_id: str, update: DocumentAccessUpdate) -> None:
        url = f"{self._settings.host}/information_pieces/{document_id}/access"
        payload = json.dumps(update.model_dump()).encode("utf-8")

        def _call() -> bytes:
            req = urllib_request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib_request.urlopen(req, timeout=10) as response:
                return response.read()

        try:
            await asyncio.to_thread(_call)
        except HTTPError as exc:
            body = exc.read().decode("utf-8") if exc.fp else ""
            logger.error("Failed to update access for %s: %s", document_id, body)
            raise HTTPException(status_code=exc.code, detail=body or exc.reason) from exc
