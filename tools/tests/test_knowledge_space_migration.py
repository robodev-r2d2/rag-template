from tools.knowledge_space_migration import (
    build_collection_plan,
    infer_visibility_patch,
    run_backfill,
)


class _Point:
    def __init__(self, point_id, payload):
        self.id = point_id
        self.payload = payload


class _FakeClient:
    def __init__(self, points):
        self._points = points
        self.payload_updates = []
        self._returned = False

    def scroll(self, **_kwargs):
        if self._returned:
            return [], None
        self._returned = True
        return self._points, None

    def set_payload(self, **kwargs):
        self.payload_updates.append(kwargs)


def test_build_collection_plan_single():
    plan = build_collection_plan(
        strategy="single",
        base_collection="rag-db",
        tenant_ids=["tenant-a"],
        domain_ids=["finance"],
        tenant_template="tenant_{tenant_id}",
        shared_domain_template="shared_{domain_id}",
        global_collection="shared_global",
    )
    assert plan == ["rag-db"]


def test_build_collection_plan_hybrid():
    plan = build_collection_plan(
        strategy="hybrid",
        base_collection="rag-db",
        tenant_ids=["tenant-a"],
        domain_ids=["finance"],
        tenant_template="tenant_{tenant_id}",
        shared_domain_template="shared_{domain_id}",
        global_collection="shared_global",
    )
    assert sorted(plan) == ["rag-db", "shared_finance", "shared_global", "tenant_tenant-a"]


def test_infer_visibility_patch_for_legacy_tenant_payload():
    patch = infer_visibility_patch({"tenant_id": "tenant-a"})
    assert patch == {
        "space_id": "tenant_tenant-a",
        "visibility": "tenant",
        "space_type": "tenant",
        "owner_tenant_id": "tenant-a",
    }


def test_run_backfill_dry_run_reports_expected_counts():
    points = [
        _Point(1, {"metadata": {"tenant_id": "tenant-a"}}),
        _Point(2, {"metadata": {"space_id": "shared_global", "visibility": "global"}}),
        _Point(3, {"metadata": {"foo": "bar"}}),
    ]
    client = _FakeClient(points)
    report = run_backfill(client=client, collection_name="rag-db", apply=False)
    assert report.scanned == 3
    assert report.patched == 1
    assert report.unresolved == 0
    assert client.payload_updates == []


def test_run_backfill_apply_updates_payload():
    points = [_Point(1, {"metadata": {"tenant_id": "tenant-a"}})]
    client = _FakeClient(points)
    report = run_backfill(client=client, collection_name="rag-db", apply=True)
    assert report.patched == 1
    assert len(client.payload_updates) == 1
