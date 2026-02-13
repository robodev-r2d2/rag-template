#!/usr/bin/env python3
"""Operational helpers for managing logical knowledge spaces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"spaces": {}}
    return json.loads(path.read_text())


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def to_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        if "," in value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return [value] if value.strip() else []
    return []


def readable_spaces_from_claims(claims: dict[str, Any]) -> list[str]:
    spaces = ["shared_global"]
    tenant_ids = to_list(claims.get("allowed_tenant_ids"))
    tenant_id = claims.get("tenant_id")
    if tenant_id and tenant_id not in tenant_ids:
        tenant_ids.insert(0, tenant_id)
    spaces.extend([f"tenant_{tenant}" for tenant in tenant_ids if tenant])
    spaces.extend([f"shared_{domain}" for domain in to_list(claims.get("allowed_domain_ids")) if domain])
    return list(dict.fromkeys(spaces))


def writable_spaces_from_claims(claims: dict[str, Any]) -> list[str]:
    spaces = []
    tenant_id = claims.get("tenant_id")
    if tenant_id:
        spaces.append(f"tenant_{tenant_id}")
    if to_bool(str(claims.get("can_write_shared_domain", "false"))):
        spaces.extend([f"shared_{domain}" for domain in to_list(claims.get("allowed_domain_ids")) if domain])
    if to_bool(str(claims.get("can_write_global", "false"))):
        spaces.append("shared_global")
    return list(dict.fromkeys(spaces))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Knowledge-space operational helper.")
    parser.add_argument("--state-file", default="infrastructure/rag/knowledge-spaces-state.json")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-shared-domain-space")
    create.add_argument("--domain-id", required=True)
    create.add_argument("--display-name", default=None)

    toggle = sub.add_parser("set-space-state")
    toggle.add_argument("--space-id", required=True)
    toggle.add_argument("--enabled", required=True, choices=["true", "false"])

    sub.add_parser("list-spaces")

    audit = sub.add_parser("audit-access")
    audit.add_argument("--claims-json", required=True, help="Raw JSON string with JWT claims.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_path = Path(args.state_file)
    state = load_state(state_path)
    spaces = state.setdefault("spaces", {})

    if args.command == "create-shared-domain-space":
        space_id = f"shared_{args.domain_id}"
        spaces[space_id] = {
            "id": space_id,
            "type": "shared_domain",
            "domain_id": args.domain_id,
            "display_name": args.display_name or f"Shared ({args.domain_id})",
            "enabled": True,
        }
        save_state(state_path, state)
        print(json.dumps({"created": spaces[space_id]}, indent=2))
        return 0

    if args.command == "set-space-state":
        if args.space_id not in spaces:
            print(json.dumps({"error": f"space '{args.space_id}' not found"}, indent=2))
            return 1
        spaces[args.space_id]["enabled"] = args.enabled == "true"
        save_state(state_path, state)
        print(json.dumps({"updated": spaces[args.space_id]}, indent=2))
        return 0

    if args.command == "list-spaces":
        print(json.dumps({"spaces": list(spaces.values())}, indent=2))
        return 0

    if args.command == "audit-access":
        claims = json.loads(args.claims_json)
        readable = readable_spaces_from_claims(claims)
        writable = writable_spaces_from_claims(claims)
        disabled = {space_id for space_id, space in spaces.items() if not space.get("enabled", True)}
        print(
            json.dumps(
                {
                    "readable_spaces": [space_id for space_id in readable if space_id not in disabled],
                    "writable_spaces": [space_id for space_id in writable if space_id not in disabled],
                    "disabled_spaces": sorted(disabled),
                },
                indent=2,
            )
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
