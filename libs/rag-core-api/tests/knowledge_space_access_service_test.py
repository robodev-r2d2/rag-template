import json

import pytest

from rag_core_api.impl.settings.knowledge_space_settings import KnowledgeSpaceSettings
from rag_core_api.knowledge_spaces.access_service import (
    KnowledgeSpaceAccessDeniedError,
    KnowledgeSpaceAccessService,
)
from rag_core_lib.principal import Principal, PrincipalType


def _principal() -> Principal:
    return Principal(
        principal_type=PrincipalType.AUTHENTICATED,
        subject="user-a",
        tenant_id="tenant-a",
        allowed_tenant_ids=["tenant-a", "tenant-b"],
        allowed_domain_ids=["finance", "hr"],
        can_write_shared_domain=True,
        can_write_global=True,
        token_claims={},
    )


def test_anonymous_principal_reads_global_only():
    service = KnowledgeSpaceAccessService(KnowledgeSpaceSettings())
    spaces = service.resolve_readable_spaces(Principal.anonymous())
    assert [space.id for space in spaces] == ["shared_global"]


def test_effective_scope_intersection():
    service = KnowledgeSpaceAccessService(KnowledgeSpaceSettings())
    principal = _principal()
    effective = service.resolve_effective_scope(principal, ["tenant_tenant-b", "shared_global"])
    assert [space.id for space in effective] == ["tenant_tenant-b", "shared_global"]


def test_effective_scope_rejects_unauthorized_space():
    service = KnowledgeSpaceAccessService(KnowledgeSpaceSettings())
    principal = _principal()
    with pytest.raises(KnowledgeSpaceAccessDeniedError):
        service.resolve_effective_scope(principal, ["tenant_other"])


def test_upload_target_defaults_to_my_tenant():
    service = KnowledgeSpaceAccessService(KnowledgeSpaceSettings())
    principal = _principal()
    target = service.resolve_upload_target(principal, None)
    assert target.id == "tenant_tenant-a"


def test_upload_target_requires_permission():
    service = KnowledgeSpaceAccessService(KnowledgeSpaceSettings())
    principal = Principal(
        principal_type=PrincipalType.AUTHENTICATED,
        subject="user-b",
        tenant_id="tenant-b",
        allowed_tenant_ids=["tenant-b"],
        allowed_domain_ids=[],
        can_write_shared_domain=False,
        can_write_global=False,
        token_claims={},
    )
    with pytest.raises(KnowledgeSpaceAccessDeniedError):
        service.resolve_upload_target(principal, "shared_global")


def test_disabled_spaces_are_excluded_from_read_and_write(tmp_path):
    state_file = tmp_path / "knowledge-spaces-state.json"
    state_file.write_text(
        json.dumps(
            {
                "spaces": {
                    "tenant_tenant-a": {"enabled": False},
                    "shared_finance": {"enabled": False},
                }
            }
        )
    )

    service = KnowledgeSpaceAccessService(
        KnowledgeSpaceSettings(knowledge_spaces_state_file=str(state_file))
    )
    principal = _principal()

    readable_ids = [space.id for space in service.resolve_readable_spaces(principal)]
    assert "tenant_tenant-a" not in readable_ids
    assert "shared_finance" not in readable_ids
    assert "tenant_tenant-b" in readable_ids
    assert "shared_hr" in readable_ids
    assert "shared_global" in readable_ids

    writable_ids = [space.id for space in service.resolve_writable_spaces(principal)]
    assert "tenant_tenant-a" not in writable_ids
    assert "shared_finance" not in writable_ids
    assert "shared_hr" in writable_ids
    assert "shared_global" in writable_ids


def test_effective_scope_rejects_disabled_space(tmp_path):
    state_file = tmp_path / "knowledge-spaces-state.json"
    state_file.write_text(
        json.dumps(
            {
                "spaces": {
                    "shared_finance": {"enabled": False},
                }
            }
        )
    )

    service = KnowledgeSpaceAccessService(
        KnowledgeSpaceSettings(knowledge_spaces_state_file=str(state_file))
    )
    principal = _principal()
    with pytest.raises(KnowledgeSpaceAccessDeniedError):
        service.resolve_effective_scope(principal, ["shared_finance"])


def test_explicit_upload_target_rejects_disabled_space(tmp_path):
    state_file = tmp_path / "knowledge-spaces-state.json"
    state_file.write_text(
        json.dumps(
            {
                "spaces": {
                    "tenant_tenant-a": {"enabled": False},
                }
            }
        )
    )

    service = KnowledgeSpaceAccessService(
        KnowledgeSpaceSettings(knowledge_spaces_state_file=str(state_file))
    )
    principal = _principal()
    with pytest.raises(KnowledgeSpaceAccessDeniedError):
        service.resolve_upload_target(principal, "my_tenant")


def test_anonymous_has_no_read_scope_if_global_disabled(tmp_path):
    state_file = tmp_path / "knowledge-spaces-state.json"
    state_file.write_text(
        json.dumps(
            {
                "spaces": {
                    "shared_global": {"enabled": False},
                }
            }
        )
    )

    service = KnowledgeSpaceAccessService(
        KnowledgeSpaceSettings(knowledge_spaces_state_file=str(state_file))
    )
    spaces = service.resolve_readable_spaces(Principal.anonymous())
    assert spaces == []
