from tools.knowledge_space_admin import readable_spaces_from_claims, writable_spaces_from_claims


def test_readable_spaces_from_claims():
    claims = {
        "tenant_id": "tenant-a",
        "allowed_tenant_ids": ["tenant-b"],
        "allowed_domain_ids": ["finance"],
    }
    assert readable_spaces_from_claims(claims) == [
        "shared_global",
        "tenant_tenant-a",
        "tenant_tenant-b",
        "shared_finance",
    ]


def test_writable_spaces_from_claims():
    claims = {
        "tenant_id": "tenant-a",
        "allowed_domain_ids": ["finance", "hr"],
        "can_write_shared_domain": True,
        "can_write_global": True,
    }
    assert writable_spaces_from_claims(claims) == [
        "tenant_tenant-a",
        "shared_finance",
        "shared_hr",
        "shared_global",
    ]
