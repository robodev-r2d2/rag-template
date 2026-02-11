"""Module containing the QdrantDatabase class."""

from __future__ import annotations

import asyncio
import logging

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore, SparseEmbeddings
from qdrant_client.http import models
from qdrant_client.models import FieldCondition, Filter, MatchValue

from rag_core_api.embeddings.embedder import Embedder
from rag_core_api.impl.settings.vector_db_settings import VectorDatabaseSettings
from rag_core_api.knowledge_spaces.access_service import KnowledgeSpaceAccessService
from rag_core_api.knowledge_spaces.collection_router import KnowledgeSpaceCollectionRouter
from rag_core_api.knowledge_spaces.models import (
    DocumentVisibilityMetadata,
    KnowledgeSpace,
    KnowledgeSpaceType,
)
from rag_core_api.vector_databases.vector_database import VectorDatabase
from rag_core_lib.context import get_principal, get_requested_space_ids, get_target_space_id
from rag_core_lib.principal import Principal

logger = logging.getLogger(__name__)


class QdrantDatabase(VectorDatabase):
    """
    A class representing the interface to the Qdrant database.

    Inherits from VectorDatabase.
    """

    def __init__(
        self,
        settings: VectorDatabaseSettings,
        embedder: Embedder,
        sparse_embedder: SparseEmbeddings,
        vectorstore: QdrantVectorStore,
        access_service: KnowledgeSpaceAccessService,
        collection_router: KnowledgeSpaceCollectionRouter,
    ):
        """
        Initialize the Qdrant database.

        Parameters
        ----------
        settings : VectorDatabaseSettings
            The settings for the vector database.
        embedder : Embedder
            The embedder used to convert chunks into vector representations.
        vectorstore : QdrantVectorStore
            The default Qdrant vector store instance.
        access_service : KnowledgeSpaceAccessService
            Service resolving readable and writable logical spaces.
        collection_router : KnowledgeSpaceCollectionRouter
            Router that maps logical spaces to physical collections.
        """
        super().__init__(
            settings=settings,
            embedder=embedder,
            vectorstore=vectorstore,
            sparse_embedder=sparse_embedder,
        )
        self._access_service = access_service
        self._collection_router = collection_router
        self._vectorstores: dict[str, QdrantVectorStore] = {vectorstore.collection_name: vectorstore}

    @property
    def collection_available(self):
        """
        Check if at least one relevant collection is available and has points.

        Returns
        -------
        bool
            True if at least one relevant collection exists and has points, False otherwise.
        """
        if self._collection_router.strategy == "single":
            if self._vectorstore.collection_name in [c.name for c in self.get_collections()]:
                collection = self._vectorstore.client.get_collection(self._vectorstore.collection_name)
                return collection.points_count > 0
            return False

        try:
            spaces = self._resolve_read_scope()
        except Exception:
            return False
        for space in spaces:
            collection_name = self._collection_router.collection_for_space(space)
            if not self._collection_exists(collection_name):
                continue
            collection = self._vectorstore.client.get_collection(collection_name)
            if collection.points_count > 0:
                return True
        return False

    @staticmethod
    def _metadata_conditions(filter_kwargs: dict | None) -> list[models.Condition]:
        if not filter_kwargs:
            return []
        return [
            models.FieldCondition(key="metadata." + key, match=models.MatchValue(value=value))
            for key, value in filter_kwargs.items()
        ]

    @staticmethod
    def _merge_filters(
        filter_kwargs: dict | None,
        acl_filter: models.Filter | None = None,
        extra_conditions: list[models.Condition] | None = None,
    ) -> models.Filter | None:
        must_conditions: list[models.Condition] = QdrantDatabase._metadata_conditions(filter_kwargs)
        if extra_conditions:
            must_conditions.extend(extra_conditions)
        if acl_filter:
            must_conditions.append(acl_filter)
        if not must_conditions:
            return None
        return models.Filter(must=must_conditions)

    @staticmethod
    def _search_kwargs_builder(
        search_kwargs: dict,
        filter_kwargs: dict | None,
        acl_filter: models.Filter | None = None,
        extra_conditions: list[models.Condition] | None = None,
    ):
        """Build search kwargs with proper Qdrant filter format."""
        merged_filter = QdrantDatabase._merge_filters(
            filter_kwargs=filter_kwargs, acl_filter=acl_filter, extra_conditions=extra_conditions
        )
        if not merged_filter:
            return search_kwargs
        return {**search_kwargs, "filter": merged_filter}

    def _build_single_strategy_acl_filter(self, spaces: list[KnowledgeSpace]) -> models.Filter | None:
        should_conditions: list[models.Condition] = []
        for space in spaces:
            if space.type == KnowledgeSpaceType.TENANT:
                should_conditions.append(
                    models.FieldCondition(key="metadata.space_id", match=models.MatchValue(value=space.id))
                )
                if space.tenant_id:
                    # Backward compatibility for legacy chunks without visibility/space_id metadata.
                    should_conditions.append(
                        models.FieldCondition(key="metadata.tenant_id", match=models.MatchValue(value=space.tenant_id))
                    )
            elif space.type == KnowledgeSpaceType.SHARED_DOMAIN:
                should_conditions.append(
                    models.FieldCondition(key="metadata.space_id", match=models.MatchValue(value=space.id))
                )
                if space.domain_id:
                    should_conditions.append(
                        models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="metadata.visibility",
                                    match=models.MatchValue(value=KnowledgeSpaceType.SHARED_DOMAIN.value),
                                ),
                                models.FieldCondition(
                                    key="metadata.domain_id",
                                    match=models.MatchValue(value=space.domain_id),
                                ),
                            ]
                        )
                    )
            elif space.type == KnowledgeSpaceType.GLOBAL:
                should_conditions.append(
                    models.FieldCondition(key="metadata.space_id", match=models.MatchValue(value=space.id))
                )
                should_conditions.append(
                    models.FieldCondition(
                        key="metadata.visibility", match=models.MatchValue(value=KnowledgeSpaceType.GLOBAL.value)
                    )
                )

        if not should_conditions:
            return None
        return models.Filter(should=should_conditions)

    def _resolve_read_scope(self) -> list[KnowledgeSpace]:
        principal = get_principal()
        requested_scope = get_requested_space_ids()
        return self._access_service.resolve_effective_scope(principal, requested_scope)

    def _resolve_upload_target(self) -> KnowledgeSpace:
        principal = get_principal()
        target_space_id = get_target_space_id()
        return self._access_service.resolve_upload_target(principal, target_space_id)

    def _resolve_delete_scope(self) -> list[KnowledgeSpace]:
        principal = get_principal()
        target_space_id = get_target_space_id()
        return self._access_service.resolve_delete_scope(principal, target_space_id)

    def _collection_exists(self, collection_name: str) -> bool:
        return self._vectorstore.client.collection_exists(collection_name)

    def _ensure_collection_exists(self, collection_name: str) -> None:
        if self._collection_exists(collection_name):
            return

        default_collection = self._collection_router.default_collection_name
        if self._collection_exists(default_collection):
            info = self._vectorstore.client.get_collection(default_collection)
            vectors_config = info.config.params.vectors
            sparse_vectors_config = info.config.params.sparse_vectors
        else:
            try:
                dim = len(self._embedder.embed_query("health check"))
            except Exception:
                dim = 1536
            vectors_config = models.VectorParams(size=dim, distance=models.Distance.COSINE)
            sparse_vectors_config = {
                "langchain-sparse": models.SparseVectorParams(index=models.SparseIndexParams(on_disk=False)),
                "text-sparse": models.SparseVectorParams(index=models.SparseIndexParams(on_disk=False)),
            }

        self._vectorstore.client.create_collection(
            collection_name=collection_name,
            vectors_config=vectors_config,
            sparse_vectors_config=sparse_vectors_config,
        )

    def _get_vectorstore_for_collection(self, collection_name: str, create_if_missing: bool = False) -> QdrantVectorStore:
        if collection_name in self._vectorstores:
            return self._vectorstores[collection_name]

        if create_if_missing:
            self._ensure_collection_exists(collection_name)
        elif not self._collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist.")

        vectorstore = QdrantVectorStore(
            client=self._vectorstore.client,
            collection_name=collection_name,
            embedding=self._embedder,
            sparse_embedding=self._sparse_embedder,
            validate_collection_config=self._settings.validate_collection_config,
            retrieval_mode=self._settings.retrieval_mode,
        )
        self._vectorstores[collection_name] = vectorstore
        return vectorstore

    async def _asearch_collection(self, collection_name: str, query: str, search_params: dict) -> list[Document]:
        vectorstore = self._get_vectorstore_for_collection(collection_name)
        retriever = vectorstore.as_retriever(query=query, search_kwargs=search_params)
        return await retriever.ainvoke(query)

    @staticmethod
    def _annotate_document_space(document: Document, space: KnowledgeSpace, collection_name: str) -> None:
        document.metadata.setdefault("space_id", space.id)
        document.metadata.setdefault("space_type", space.type.value)
        document.metadata.setdefault("visibility", space.type.value)
        if space.domain_id:
            document.metadata.setdefault("domain_id", space.domain_id)
        if space.tenant_id:
            document.metadata.setdefault("tenant_id", space.tenant_id)
        document.metadata["_collection_name"] = collection_name

    def _annotate_single_mode_document(self, document: Document, spaces: list[KnowledgeSpace], collection_name: str) -> None:
        if "space_id" in document.metadata:
            document.metadata.setdefault("space_type", document.metadata.get("visibility", "tenant"))
            document.metadata["_collection_name"] = collection_name
            return

        tenant_id = document.metadata.get("tenant_id")
        if tenant_id:
            tenant_space = self._access_service.tenant_space(str(tenant_id))
            self._annotate_document_space(document, tenant_space, collection_name)
            return

        space_ids = {space.id: space for space in spaces}
        global_space_id = self._access_service.global_space().id
        if global_space_id in space_ids:
            self._annotate_document_space(document, space_ids[global_space_id], collection_name)
        else:
            document.metadata["_collection_name"] = collection_name

    @staticmethod
    def _dedupe_documents(documents: list[Document]) -> list[Document]:
        deduped: list[Document] = []
        seen: set[str] = set()
        for document in documents:
            key = str(document.metadata.get("id") or document.page_content)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(document)
        return deduped

    async def asearch(self, query: str, search_kwargs: dict, filter_kwargs: dict | None = None) -> list[Document]:
        """
        Asynchronously search for documents based on a query and optional filters.

        Parameters
        ----------
        query : str
            The search query string.
        search_kwargs : dict
            Additional keyword arguments for the search.
        filter_kwargs : dict, optional
            Optional filter keyword arguments to refine the search (default is None).

        Returns
        -------
        list[Document]
            A list of documents that match the search query and filters, including related documents.
        """
        try:
            spaces = self._resolve_read_scope()
            if not spaces:
                return []

            if self._collection_router.strategy == "single":
                collection_name = self._collection_router.default_collection_name
                acl_filter = self._build_single_strategy_acl_filter(spaces)
                search_params = self._search_kwargs_builder(
                    search_kwargs=search_kwargs, filter_kwargs=filter_kwargs, acl_filter=acl_filter
                )
                results = await self._asearch_collection(collection_name=collection_name, query=query, search_params=search_params)
                for result in results:
                    self._annotate_single_mode_document(result, spaces=spaces, collection_name=collection_name)

                related_results: list[Document] = []
                for result in results:
                    related_results.extend(
                        self._get_related(
                            result.metadata.get("related", []),
                            collection_name=collection_name,
                            acl_filter=acl_filter,
                        )
                    )
                for result in related_results:
                    self._annotate_single_mode_document(result, spaces=spaces, collection_name=collection_name)
                return self._dedupe_documents(results + related_results)

            search_tasks: list[asyncio.Task[list[Document]]] = []
            task_spaces: list[tuple[KnowledgeSpace, str]] = []
            for space in spaces:
                collection_name = self._collection_router.collection_for_space(space)
                if not self._collection_exists(collection_name):
                    continue
                space_condition = models.FieldCondition(
                    key="metadata.space_id",
                    match=models.MatchValue(value=space.id),
                )
                search_params = self._search_kwargs_builder(
                    search_kwargs=search_kwargs,
                    filter_kwargs=filter_kwargs,
                    extra_conditions=[space_condition],
                )
                search_tasks.append(
                    asyncio.create_task(
                        self._asearch_collection(collection_name=collection_name, query=query, search_params=search_params)
                    )
                )
                task_spaces.append((space, collection_name))

            if not search_tasks:
                return []

            grouped_results = await asyncio.gather(*search_tasks)
            results: list[Document] = []
            related_results: list[Document] = []
            for (space, collection_name), docs in zip(task_spaces, grouped_results):
                for result in docs:
                    self._annotate_document_space(result, space=space, collection_name=collection_name)
                results.extend(docs)

                scope_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="metadata.space_id",
                            match=models.MatchValue(value=space.id),
                        )
                    ]
                )
                space_related_results: list[Document] = []
                for result in docs:
                    space_related_results.extend(
                        self._get_related(
                            result.metadata.get("related", []),
                            collection_name=collection_name,
                            acl_filter=scope_filter,
                        )
                    )
                for result in space_related_results:
                    self._annotate_document_space(result, space=space, collection_name=collection_name)
                related_results.extend(space_related_results)

            return self._dedupe_documents(results + related_results)

        except Exception:
            logger.exception("Search failed")
            raise

    def get_specific_document(
        self,
        document_id: str,
        collection_name: str | None = None,
        acl_filter: models.Filter | None = None,
    ) -> list[Document]:
        """
        Retrieve a specific document from the vector database using the document ID.

        Parameters
        ----------
        document_id : str
            The ID of the document to retrieve.
        collection_name : str, optional
            Collection to query. Defaults to currently configured default collection.
        acl_filter : models.Filter, optional
            Additional ACL filter to ensure related-document expansion does not bypass scope checks.

        Returns
        -------
        list[Document]
            A list containing the requested document as a Document object. If the document is not found,
            an empty list is returned.
        """
        target_collections = self._resolve_document_lookup_collections(collection_name=collection_name)
        if not target_collections:
            return []

        results: list[Document] = []
        for target_collection in target_collections:
            if not self._collection_exists(target_collection):
                continue

            must_conditions: list[models.Condition] = [
                FieldCondition(
                    key="metadata.id",
                    match=MatchValue(value=document_id),
                )
            ]
            if acl_filter:
                must_conditions.append(acl_filter)

            requested = self._vectorstore.client.scroll(
                collection_name=target_collection,
                scroll_filter=Filter(must=must_conditions),
            )
            points = requested[0] if requested else []
            for search_result in points:
                metadata = search_result.payload.get("metadata", {})
                if isinstance(metadata, dict):
                    metadata = dict(metadata)
                else:
                    metadata = {"raw_metadata": metadata}
                metadata.setdefault("_collection_name", target_collection)
                results.append(
                    Document(
                        page_content=search_result.payload["page_content"],
                        metadata=metadata,
                    )
                )

        if collection_name is None:
            return self._dedupe_documents(results)
        return results

    def _resolve_document_lookup_collections(self, collection_name: str | None) -> list[str]:
        """Resolve candidate collections for document-id lookup."""
        if collection_name:
            return [collection_name]

        if self._collection_router.strategy == "single":
            return [self._vectorstore.collection_name]

        try:
            spaces = self._resolve_read_scope()
        except Exception:
            logger.exception("Failed to resolve readable scope for document lookup.")
            return []

        collections: list[str] = []
        seen: set[str] = set()
        for space in spaces:
            target_collection = self._collection_router.collection_for_space(space)
            if target_collection in seen:
                continue
            seen.add(target_collection)
            collections.append(target_collection)
        return collections

    def get_documents_by_ids(
        self,
        document_ids: list[str],
        collection_name: str | None = None,
        acl_filter: models.Filter | None = None,
    ) -> list[Document]:
        """Batch fetch multiple documents by their IDs."""
        if not document_ids:
            return []

        results: list[Document] = []
        for doc_id in document_ids:
            results.extend(
                self.get_specific_document(document_id=doc_id, collection_name=collection_name, acl_filter=acl_filter)
            )
        return self._dedupe_documents(results)

    def _stamp_visibility_metadata(self, doc: Document, target_space: KnowledgeSpace, principal: Principal | None) -> None:
        visibility = DocumentVisibilityMetadata(
            visibility=target_space.type,
            tenant_id=target_space.tenant_id if target_space.type == KnowledgeSpaceType.TENANT else None,
            domain_id=target_space.domain_id,
            space_id=target_space.id,
            owner_tenant_id=principal.tenant_id if principal else None,
        )
        doc.metadata["visibility"] = visibility.visibility.value
        doc.metadata["space_id"] = visibility.space_id
        doc.metadata["space_type"] = target_space.type.value
        doc.metadata["owner_tenant_id"] = visibility.owner_tenant_id

        if visibility.tenant_id:
            doc.metadata["tenant_id"] = visibility.tenant_id
        else:
            doc.metadata.pop("tenant_id", None)

        if visibility.domain_id:
            doc.metadata["domain_id"] = visibility.domain_id
        else:
            doc.metadata.pop("domain_id", None)

    def upload(self, documents: list[Document]) -> None:
        """
        Save the given documents to the Qdrant database.

        Parameters
        ----------
        documents : list[Document]
            The list of documents to be stored.

        Returns
        -------
        None
        """
        target_space = self._resolve_upload_target()
        principal = get_principal()
        collection_name = self._collection_router.collection_for_space(target_space)
        vectorstore = self._get_vectorstore_for_collection(collection_name, create_if_missing=True)

        for doc in documents:
            self._stamp_visibility_metadata(doc=doc, target_space=target_space, principal=principal)
            doc.metadata["_collection_name"] = collection_name

        vectorstore.add_documents(documents)

    def delete(self, delete_request: dict) -> None:
        """
        Delete all points associated with a specific document from the Qdrant database.

        Parameters
        ----------
        delete_request : dict
            A dictionary containing the conditions to match the points to be deleted.

        Returns
        -------
        None
        """
        delete_scope = self._resolve_delete_scope()

        if self._collection_router.strategy == "single":
            acl_filter = self._build_single_strategy_acl_filter(delete_scope)
            merged_filter = self._merge_filters(filter_kwargs=delete_request, acl_filter=acl_filter)
            if merged_filter is None:
                raise ValueError("No delete filter generated.")

            points_selector = models.FilterSelector(filter=merged_filter)
            self._vectorstore.client.delete(
                collection_name=self._settings.collection_name,
                points_selector=points_selector,
            )
            return

        for space in delete_scope:
            collection_name = self._collection_router.collection_for_space(space)
            if not self._collection_exists(collection_name):
                continue
            space_condition = models.FieldCondition(
                key="metadata.space_id",
                match=models.MatchValue(value=space.id),
            )
            merged_filter = self._merge_filters(filter_kwargs=delete_request, extra_conditions=[space_condition])
            if merged_filter is None:
                continue
            points_selector = models.FilterSelector(filter=merged_filter)
            self._vectorstore.client.delete(
                collection_name=collection_name,
                points_selector=points_selector,
            )

    def get_collections(self) -> list[str]:
        """
        Get all collection names from the vector database.

        Returns
        -------
        list[str]
            A list of collection names from the vector database.
        """
        return self._vectorstore.client.get_collections().collections

    def _get_related(
        self,
        related_ids: list[str],
        collection_name: str | None = None,
        acl_filter: models.Filter | None = None,
    ) -> list[Document]:
        result: list[Document] = []
        for document_id in related_ids or []:
            result.extend(
                self.get_specific_document(
                    document_id=document_id,
                    collection_name=collection_name,
                    acl_filter=acl_filter,
                )
            )
        return result
