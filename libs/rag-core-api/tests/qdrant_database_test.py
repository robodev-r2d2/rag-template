import pytest
from unittest.mock import MagicMock

from langchain_core.documents import Document

from rag_core_api.impl.vector_databases.qdrant_database import QdrantDatabase
from rag_core_api.knowledge_spaces.models import KnowledgeSpace, KnowledgeSpaceType
from rag_core_lib.context import clear_principal, clear_target_space_id


@pytest.fixture(autouse=True)
def reset_context():
    clear_principal()
    clear_target_space_id()
    yield
    clear_principal()
    clear_target_space_id()


def test_qdrant_database_upload_uses_add_documents_and_stamps_visibility_metadata():
    # Mock dependencies
    mock_settings = MagicMock()
    mock_settings.validate_collection_config = False
    mock_settings.retrieval_mode = MagicMock()
    mock_settings.collection_name = "rag-db"
    mock_embedder = MagicMock()
    mock_sparse_embedder = MagicMock()
    mock_vectorstore = MagicMock()
    mock_vectorstore.collection_name = "rag-db"

    mock_access_service = MagicMock()
    mock_access_service.resolve_upload_target.return_value = KnowledgeSpace(
        id="tenant_tenant-a",
        type=KnowledgeSpaceType.TENANT,
        tenant_id="tenant-a",
        display_name="Tenant tenant-a",
        enabled=True,
    )
    mock_collection_router = MagicMock()
    mock_collection_router.collection_for_space.return_value = "rag-db"
    mock_collection_router.strategy = "single"
    mock_collection_router.default_collection_name = "rag-db"

    db = QdrantDatabase(
        settings=mock_settings,
        embedder=mock_embedder,
        sparse_embedder=mock_sparse_embedder,
        vectorstore=mock_vectorstore,
        access_service=mock_access_service,
        collection_router=mock_collection_router,
    )

    documents = [Document(page_content="test", metadata={})]

    # Call upload
    db.upload(documents)

    # Verify add_documents was called
    mock_vectorstore.add_documents.assert_called_once_with(documents)
    assert documents[0].metadata["visibility"] == KnowledgeSpaceType.TENANT.value
    assert documents[0].metadata["space_id"] == "tenant_tenant-a"
    assert documents[0].metadata["tenant_id"] == "tenant-a"


def test_single_strategy_acl_filter_contains_legacy_tenant_fallback():
    mock_settings = MagicMock()
    mock_settings.validate_collection_config = False
    mock_settings.retrieval_mode = MagicMock()
    mock_settings.collection_name = "rag-db"
    mock_vectorstore = MagicMock()
    mock_vectorstore.collection_name = "rag-db"

    db = QdrantDatabase(
        settings=mock_settings,
        embedder=MagicMock(),
        sparse_embedder=MagicMock(),
        vectorstore=mock_vectorstore,
        access_service=MagicMock(),
        collection_router=MagicMock(),
    )

    acl_filter = db._build_single_strategy_acl_filter(
        [
            KnowledgeSpace(
                id="tenant_tenant-a",
                type=KnowledgeSpaceType.TENANT,
                tenant_id="tenant-a",
                display_name="Tenant tenant-a",
                enabled=True,
            )
        ]
    )

    tenant_conditions = [condition for condition in acl_filter.should if condition.key == "metadata.tenant_id"]
    assert tenant_conditions
    assert tenant_conditions[0].match.value == "tenant-a"


def test_get_documents_by_ids_resolves_across_scope_collections_in_hybrid_strategy():
    mock_settings = MagicMock()
    mock_settings.validate_collection_config = False
    mock_settings.retrieval_mode = MagicMock()
    mock_settings.collection_name = "rag-db"
    mock_embedder = MagicMock()
    mock_sparse_embedder = MagicMock()
    mock_vectorstore = MagicMock()
    mock_vectorstore.collection_name = "rag-db"

    tenant_space = KnowledgeSpace(
        id="tenant_tenant-a",
        type=KnowledgeSpaceType.TENANT,
        tenant_id="tenant-a",
        display_name="Tenant tenant-a",
        enabled=True,
    )
    shared_space = KnowledgeSpace(
        id="shared_finance",
        type=KnowledgeSpaceType.SHARED_DOMAIN,
        domain_id="finance",
        display_name="Shared finance",
        enabled=True,
    )

    mock_collection_router = MagicMock()
    mock_collection_router.strategy = "hybrid"
    mock_collection_router.default_collection_name = "rag-db"
    mock_collection_router.collection_for_space.side_effect = lambda space: space.id

    db = QdrantDatabase(
        settings=mock_settings,
        embedder=mock_embedder,
        sparse_embedder=mock_sparse_embedder,
        vectorstore=mock_vectorstore,
        access_service=MagicMock(),
        collection_router=mock_collection_router,
    )
    db._resolve_read_scope = MagicMock(return_value=[tenant_space, shared_space])  # noqa: SLF001
    db._collection_exists = MagicMock(return_value=True)  # noqa: SLF001

    tenant_hit = MagicMock(payload={"page_content": "tenant doc", "metadata": {"id": "doc-tenant"}})
    shared_hit = MagicMock(payload={"page_content": "shared doc", "metadata": {"id": "doc-shared"}})

    def scroll_side_effect(*, collection_name, scroll_filter):
        document_id = scroll_filter.must[0].match.value
        if collection_name == "tenant_tenant-a" and document_id == "doc-tenant":
            return ([tenant_hit], None)
        if collection_name == "shared_finance" and document_id == "doc-shared":
            return ([shared_hit], None)
        return ([], None)

    mock_vectorstore.client.scroll.side_effect = scroll_side_effect

    documents = db.get_documents_by_ids(["doc-tenant", "doc-shared"])

    assert {doc.metadata["id"] for doc in documents} == {"doc-tenant", "doc-shared"}
    assert {doc.metadata["_collection_name"] for doc in documents} == {"tenant_tenant-a", "shared_finance"}
