import pytest
from unittest.mock import MagicMock
from rag_core_api.impl.vector_databases.qdrant_database import QdrantDatabase
from langchain_core.documents import Document

def test_qdrant_database_upload_uses_add_documents():
    # Mock dependencies
    mock_settings = MagicMock()
    mock_embedder = MagicMock()
    mock_sparse_embedder = MagicMock()
    mock_vectorstore = MagicMock()
    
    db = QdrantDatabase(
        settings=mock_settings,
        embedder=mock_embedder,
        sparse_embedder=mock_sparse_embedder,
        vectorstore=mock_vectorstore
    )
    
    documents = [Document(page_content="test", metadata={})]
    
    # Call upload
    db.upload(documents)
    
    # Verify add_documents was called
    mock_vectorstore.add_documents.assert_called_once_with(documents)
    
    # Verify from_documents was NOT called
    assert not mock_vectorstore.from_documents.called
