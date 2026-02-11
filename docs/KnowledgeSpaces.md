# Knowledge Spaces

This project supports logical **knowledge spaces** for multitenant retrieval and ingestion.

## Space Model

Each logical space has:

- `id`
- `type`: `tenant`, `shared_domain`, `global`
- `tenant_id` (tenant spaces)
- `domain_id` (shared-domain spaces)
- `display_name`
- `enabled`

Chunk metadata now uses:

- `visibility`
- `space_id`
- `space_type`
- `tenant_id` (tenant-private content)
- `domain_id` (domain-shared content)
- `owner_tenant_id` (uploader tenant)

Legacy points without `space_id`/`visibility` are still readable in `single` strategy by `tenant_id`.

## Collection Strategies

Configure with `MULTITENANCY_COLLECTION_STRATEGY`:

- `single` (default): one physical collection (`VECTOR_DB_COLLECTION_NAME`) with ACL metadata filters.
- `hybrid`: per-tenant collections + shared-domain collections + global collection.
- `isolated`: same physical separation as `hybrid`, intended for stricter enterprise isolation policies.

Naming templates:

- `MULTITENANCY_TENANT_COLLECTION_TEMPLATE` (default `tenant_{tenant_id}`)
- `MULTITENANCY_SHARED_DOMAIN_COLLECTION_TEMPLATE` (default `shared_{domain_id}`)
- `MULTITENANCY_GLOBAL_COLLECTION_NAME` (default `shared_global`)
- `KNOWLEDGE_SPACES_STATE_FILE` (default `infrastructure/rag/knowledge-spaces-state.json`)

## Auth Claims

JWT claims used by access resolution:

- `tenant_id`
- `allowed_tenant_ids`
- `allowed_domain_ids`
- `can_write_shared_domain`
- `can_write_global`

Anonymous chat is controlled by `ALLOW_ANONYMOUS_CHAT`:

- `false` (default): chat still requires auth.
- `true`: chat allows anonymous requests and restricts retrieval to global space only.

## API Behavior

New optional query parameters:

- `POST /chat/{session_id}`: `scope` (repeatable)
- `POST /information_pieces/upload`: `target_space_id`
- `POST /information_pieces/remove`: `target_space_id`
- `POST /api/upload_file`: `target_space_id`
- `POST /api/upload_source`: `target_space_id`

Defaults:

- Upload target defaults to caller tenant space.
- Chat scope defaults to all readable spaces.

Supported target aliases:

- `my_tenant` (or `tenant`)
- `shared_<domain>`
- `shared_global` (or `global`)

## Migration / Backfill

Use the migration helper:

```bash
python tools/knowledge_space_migration.py \
  --strategy hybrid \
  --base-collection rag-db \
  --tenant-ids tenant-a,tenant-b \
  --domain-ids finance,hr
```

Dry-run is default. Add `--apply` to execute changes.

Backfill legacy metadata:

```bash
python tools/knowledge_space_migration.py \
  --strategy single \
  --base-collection rag-db \
  --backfill \
  --apply
```

## Ops Commands

Manage logical shared-domain spaces state:

```bash
python tools/knowledge_space_admin.py create-shared-domain-space --domain-id finance
python tools/knowledge_space_admin.py set-space-state --space-id shared_finance --enabled false
python tools/knowledge_space_admin.py list-spaces
python tools/knowledge_space_admin.py audit-access --claims-json '{"tenant_id":"tenant-a","allowed_domain_ids":["finance"],"can_write_shared_domain":true}'
```

Disabled spaces in the state file are enforced at runtime for read/write/delete authorization.

## Security Notes

- ACL checks are enforced server-side for upload/search/delete.
- Anonymous requests are limited to global knowledge even if clients send broader scopes.
- Apply API gateway rate limiting if anonymous chat is enabled.
- Emit audit logs at ingress/service level for scope selection and upload target usage.
