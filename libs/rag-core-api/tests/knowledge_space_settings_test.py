import pytest
from pydantic import ValidationError
from types import SimpleNamespace

from rag_core_api.impl.settings.knowledge_space_settings import KnowledgeSpaceSettings
from rag_core_api.knowledge_spaces.collection_router import KnowledgeSpaceCollectionRouter
from rag_core_api.knowledge_spaces.models import KnowledgeSpace, KnowledgeSpaceType


def test_knowledge_space_settings_defaults():
    settings = KnowledgeSpaceSettings()
    assert settings.collection_strategy == "single"
    assert settings.tenant_collection_template == "tenant_{tenant_id}"
    assert settings.shared_domain_collection_template == "shared_{domain_id}"
    assert settings.global_collection_name == "shared_global"
    assert settings.knowledge_spaces_state_file == "infrastructure/rag/knowledge-spaces-state.json"
    assert settings.enable_space_selector_in_chat is False
    assert settings.enable_upload_sharing_target is False


def test_invalid_tenant_template_rejected(monkeypatch):
    monkeypatch.setenv("MULTITENANCY_TENANT_COLLECTION_TEMPLATE", "tenant_{foo}")
    with pytest.raises(ValidationError):
        KnowledgeSpaceSettings()


def test_invalid_shared_template_rejected(monkeypatch):
    monkeypatch.setenv("MULTITENANCY_SHARED_DOMAIN_COLLECTION_TEMPLATE", "shared_{foo}")
    with pytest.raises(ValidationError):
        KnowledgeSpaceSettings()


def test_invalid_global_collection_name_rejected(monkeypatch):
    monkeypatch.setenv("MULTITENANCY_GLOBAL_COLLECTION_NAME", "{global}")
    with pytest.raises(ValidationError):
        KnowledgeSpaceSettings()


def test_collection_router_uses_default_collection_in_single_strategy():
    knowledge_settings = KnowledgeSpaceSettings(collection_strategy="single")
    vector_settings = SimpleNamespace(collection_name="rag-db")
    router = KnowledgeSpaceCollectionRouter(settings=knowledge_settings, vector_settings=vector_settings)

    space = KnowledgeSpace(
        id="tenant_tenant-a",
        type=KnowledgeSpaceType.TENANT,
        tenant_id="tenant-a",
        display_name="Tenant tenant-a",
        enabled=True,
    )
    assert router.collection_for_space(space) == "rag-db"


def test_collection_router_uses_templates_for_hybrid_strategy():
    knowledge_settings = KnowledgeSpaceSettings(collection_strategy="hybrid")
    vector_settings = SimpleNamespace(collection_name="rag-db")
    router = KnowledgeSpaceCollectionRouter(settings=knowledge_settings, vector_settings=vector_settings)

    tenant_space = KnowledgeSpace(
        id="tenant_tenant-a",
        type=KnowledgeSpaceType.TENANT,
        tenant_id="tenant-a",
        display_name="Tenant tenant-a",
        enabled=True,
    )
    domain_space = KnowledgeSpace(
        id="shared_finance",
        type=KnowledgeSpaceType.SHARED_DOMAIN,
        domain_id="finance",
        display_name="Shared finance",
        enabled=True,
    )
    global_space = KnowledgeSpace(
        id="shared_global",
        type=KnowledgeSpaceType.GLOBAL,
        display_name="Global",
        enabled=True,
    )

    assert router.collection_for_space(tenant_space) == "tenant_tenant-a"
    assert router.collection_for_space(domain_space) == "shared_finance"
    assert router.collection_for_space(global_space) == "shared_global"
