#!/usr/bin/env python3
"""Migrate and backfill knowledge-space collections and metadata in Qdrant."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Iterable


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_collection_plan(
    strategy: str,
    base_collection: str,
    tenant_ids: Iterable[str],
    domain_ids: Iterable[str],
    tenant_template: str,
    shared_domain_template: str,
    global_collection: str,
) -> list[str]:
    collections = {base_collection}
    if strategy == "single":
        return sorted(collections)
    collections.update(tenant_template.format(tenant_id=tenant_id) for tenant_id in tenant_ids)
    collections.update(shared_domain_template.format(domain_id=domain_id) for domain_id in domain_ids)
    collections.add(global_collection)
    return sorted(collections)


def infer_visibility_patch(metadata: dict) -> dict | None:
    """Infer required visibility metadata for legacy points."""
    if metadata.get("space_id") and metadata.get("visibility"):
        return None

    tenant_id = metadata.get("tenant_id")
    if tenant_id:
        return {
            "space_id": f"tenant_{tenant_id}",
            "visibility": "tenant",
            "space_type": "tenant",
            "owner_tenant_id": tenant_id,
        }

    if metadata.get("space_id") == "shared_global" or metadata.get("visibility") == "global":
        return {
            "space_id": "shared_global",
            "visibility": "global",
            "space_type": "global",
        }
    return None


@dataclass
class BackfillReport:
    scanned: int = 0
    patched: int = 0
    unresolved: int = 0


def run_backfill(client, collection_name: str, apply: bool, limit: int = 256) -> BackfillReport:
    report = BackfillReport()
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            with_payload=True,
            with_vectors=False,
            offset=offset,
            limit=limit,
        )
        if not points:
            break

        for point in points:
            report.scanned += 1
            payload = point.payload or {}
            metadata = payload.get("metadata", {})
            if not isinstance(metadata, dict):
                report.unresolved += 1
                continue
            patch = infer_visibility_patch(metadata)
            if not patch:
                continue

            report.patched += 1
            if apply:
                updated_metadata = {**metadata, **patch}
                client.set_payload(
                    collection_name=collection_name,
                    points=[point.id],
                    payload={"metadata": updated_metadata},
                )

        if offset is None:
            break
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Knowledge-space migration helper for Qdrant.")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--qdrant-api-key", default=None)
    parser.add_argument("--strategy", default="single", choices=["single", "hybrid", "isolated"])
    parser.add_argument("--base-collection", default="rag-db")
    parser.add_argument("--tenant-ids", default="")
    parser.add_argument("--domain-ids", default="")
    parser.add_argument("--tenant-collection-template", default="tenant_{tenant_id}")
    parser.add_argument("--shared-domain-collection-template", default="shared_{domain_id}")
    parser.add_argument("--global-collection", default="shared_global")
    parser.add_argument("--backfill", action="store_true", help="Backfill legacy points with visibility metadata.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default mode is dry-run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tenant_ids = parse_csv(args.tenant_ids)
    domain_ids = parse_csv(args.domain_ids)

    plan = build_collection_plan(
        strategy=args.strategy,
        base_collection=args.base_collection,
        tenant_ids=tenant_ids,
        domain_ids=domain_ids,
        tenant_template=args.tenant_collection_template,
        shared_domain_template=args.shared_domain_collection_template,
        global_collection=args.global_collection,
    )
    print(json.dumps({"action": "collection-plan", "strategy": args.strategy, "collections": plan}, indent=2))

    try:
        from qdrant_client import QdrantClient
    except Exception as exc:  # pragma: no cover - CLI runtime guard
        print(f"qdrant-client is required for apply mode: {exc}")
        return 2

    client = QdrantClient(url=args.qdrant_url, api_key=args.qdrant_api_key)
    if args.strategy != "single":
        base_info = client.get_collection(args.base_collection)
        for collection_name in plan:
            if client.collection_exists(collection_name):
                continue
            if not args.apply:
                print(f"[dry-run] would create collection: {collection_name}")
                continue
            print(f"creating collection: {collection_name}")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=base_info.config.params.vectors,
                sparse_vectors_config=base_info.config.params.sparse_vectors,
            )

    if args.backfill:
        report = run_backfill(client=client, collection_name=args.base_collection, apply=args.apply)
        print(
            json.dumps(
                {
                    "action": "backfill",
                    "collection": args.base_collection,
                    "apply": args.apply,
                    "scanned": report.scanned,
                    "patched": report.patched,
                    "unresolved": report.unresolved,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
