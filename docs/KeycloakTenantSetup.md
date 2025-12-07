# Keycloak tenant_id setup

The services now enforce a `tenant_id` claim on every access token. If it is missing, requests are rejected with `403 Missing tenant_id claim in token`.

## Configure Keycloak

1) Keep one realm (e.g., `rag`) and point the services to it via `KEYCLOAK_REALM_NAME`.

1a) Enable unmanaged attributes (needed to add custom attributes like `tenant_id`):
   - **Realm settings** → **General** → enable **Unmanaged attributes** → Save.

2) Create a client scope that carries `tenant_id` (recommended, so multiple clients can reuse it):
   - Open Keycloak Admin UI → pick your realm (left sidebar).
   - Go to **Client scopes** → **Create client scope**.
   - Name: `tenant-id` (or similar). Save.
   - Open the new scope → **Mappers** tab → **Create**:
     - Mapper type: **User Attribute**
     - Name: `tenant_id`
     - User Attribute: `tenant_id`
     - Token Claim Name: `tenant_id`
     - Claim JSON Type: `String`
     - Add to access token: ON
     - Add to ID token / userinfo: optional
   - Save.

3) Attach the scope to the clients the services use (e.g., `rag-backend`, `admin-backend`):
   - **Clients** → pick the client → **Client scopes** tab.
   - Under **Assigned default client scopes**, click **Add client scope** and add `tenant-id`.
     - If you prefer optional scopes, add it under **Assigned optional client scopes**, but then clients must request it explicitly via `scope=...`. For backend tokens, default is simpler.

4) Set the `tenant_id` value per user (Admin UI):
   - Go to **Users** → select the user.
   - In the top tab bar you should see **Details | Attributes | Credentials | Role mapping | ...**. Open **Attributes**.
   - Click **Add attribute** → Key `tenant_id`, Value `<your-tenant-slug>` (e.g., `tenant-a`) → Save.
   - If you don’t see an **Attributes** tab:
     - First, ensure **Realm settings → General → Unmanaged attributes** is enabled, then reload.
     - If it’s still missing, click the kebab (⋮) → **Switch to old console**, then open **Attributes**.
     - Or define `tenant_id` as a managed profile attribute: **Realm settings → User profile → Attributes → Add attribute** (`name=tenant_id`, required=false), then set it per user under **Users → user → Profile**.
     - Or use the CLI (see below).
   - Repeat for each user.

   CLI alternative (if the UI tab is missing):
   ```bash
   kcadm.sh config credentials --server https://<kc-host>/auth --realm master --user <admin> --password <pwd>
   kcadm.sh update users/<user-id> -r <realm> -s 'attributes.tenant_id=["tenant-a"]'
   ```

5) (Optional) If you prefer roles to control who can call the backend, add realm roles and map them separately. Tenancy enforcement itself depends on the `tenant_id` claim.

6) Test a token:
   - In **Clients** → select your client → **Service accounts** (for client credentials) or use **Users** → **Impersonate** / **Account Console** for user tokens.
   - Copy an access token and decode at jwt.io (or `jq` after `jwt decode`) and confirm it contains `"tenant_id": "<your-tenant-slug>"`.

7) Restart/redeploy services with correct Keycloak settings if needed (env vars `KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM_NAME`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`).

Notes:
- Groups can still be used for RBAC, but tenancy is enforced only via the `tenant_id` claim.
- If a request arrives without `tenant_id`, the services return 403.

Groups remain optional for your own RBAC, but they are no longer used to infer tenancy. Every request must carry the explicit `tenant_id` claim.
