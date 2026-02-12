# Keycloak usage

This template assumes Keycloak is the OIDC provider that issues JWT access tokens for every component. The backend middlewares (`libs/rag-core-api`, `libs/admin-api-lib`) verify JWTs locally and reject requests that do not contain a `tenant_id` claim.

## What must be configured in Keycloak

- **Realm**: use a single realm (default: `rag`). Enable **Realm settings → General → Unmanaged attributes** so custom claims like `tenant_id` can be added.
- **Client scope for `tenant_id` (required)**  
  1. Create a client scope (e.g., `tenant-id`).  
  2. Add a mapper (type: *User Attribute*; name/user attribute/token claim name: `tenant_id`; JSON type: `String`; add to access token: ON).  
  3. Attach the scope to every client the services use (`rag-frontend`, `rag-backend`, and any others) under **Clients → <client> → Client scopes → Assigned default client scopes**.  
  4. Set the user attribute per user: **Users → <user> → Attributes → tenant_id=<slug>**.  
     - If the **Attributes** tab is missing, enable unmanaged attributes (above) or define `tenant_id` under **Realm settings → User profile → Attributes**.  
  5. Validate a token (copy from **Clients → Service account** or impersonate a user) and ensure it contains `"tenant_id": "<slug>"`. Requests without it return `403 Missing tenant_id claim in token`.  
  More detail and CLI alternatives: `docs/KeycloakTenantSetup.md`.
- **Frontend client (`rag-frontend`, public)**  
  - Client type: Public.  
  - Redirect URIs: `http://rag.localhost/*`, `http://admin.rag.localhost/*` (add your domains).  
  - Web origins: the same hosts (or `*` for local dev only).  
  - Standard flow: ON; Direct access grants: OFF.
- **Backend/admin client (`rag-backend`, confidential)**  
  - Client type: Confidential; **Client authentication: ON**; **Service accounts: ON**.  
  - Generate a secret and keep it in sync with the Helm values `backend.envs.keycloak.KEYCLOAK_CLIENT_SECRET` and `adminBackend.envs.keycloak.KEYCLOAK_CLIENT_SECRET`.  
  - Assign whatever realm roles/scopes your APIs need to this client’s service account if you add RBAC.
- **Keycloak deployment defaults** (Helm `infrastructure/rag/values.yaml`):  
  - Admin user: `admin` / `admin` (dev only).  
  - Internal URL for services: `http://rag-keycloak-http:80/auth/`.  
  - Public ingress: `http://keycloak.rag.localhost/auth/`.

## Using an existing Keycloak deployment

Using an external Keycloak is fully supported and is the recommended production setup.

1) Disable the bundled Keycloak chart  
   - In your Helm values override, set `features.keycloak.enabled: false`.
2) Point frontends to your external realm issuer  
   - Set `frontend.envs.vite.VITE_KEYCLOAK_AUTHORITY` to your realm issuer, for example `https://sso.example.com/realms/rag` or `https://sso.example.com/auth/realms/rag` (must match your Keycloak base path).
   - Keep `frontend.envs.vite.VITE_KEYCLOAK_CLIENT_ID` aligned with your public SPA client (default: `rag-frontend`).
3) Point backends to your external Keycloak base URL  
   - Set `backend.envs.keycloak.KEYCLOAK_SERVER_URL` and `adminBackend.envs.keycloak.KEYCLOAK_SERVER_URL` to the base auth URL (for example `https://sso.example.com/` or `https://sso.example.com/auth/`).
   - Set `KEYCLOAK_REALM_NAME`, `KEYCLOAK_CLIENT_ID`, and `KEYCLOAK_CLIENT_SECRET` for the confidential client used by backend/admin-backend (default client ID: `rag-backend`).
4) Restrict trusted token issuers  
   - Set `backend.envs.keycloak.KEYCLOAK_ALLOWED_ISSUERS` and `adminBackend.envs.keycloak.KEYCLOAK_ALLOWED_ISSUERS` to a comma-separated list of exact trusted `iss` values.
   - Include every issuer format you intentionally accept (for example public ingress issuer and optional in-cluster issuer), but do not use wildcards.
5) Keep required realm/client setup  
   - Ensure the `tenant_id` mapper/client-scope is attached as described above.
   - Ensure both clients exist: `rag-frontend` (public) and `rag-backend` (confidential + service account enabled).

Quick validation after deployment:
- Open login from frontend and confirm token `iss` equals one entry in `KEYCLOAK_ALLOWED_ISSUERS`.
- Call an authenticated API and confirm no `401 Invalid token` due to issuer mismatch.
- Confirm token includes `tenant_id`, otherwise requests will be rejected with `403`.

## Application settings that must match Keycloak

- **Backend (`services/rag-backend`)**: `KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM_NAME`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`. Defaults come from Helm under `backend.envs.keycloak` and point to `rag-backend` in realm `rag`.
- **Admin backend (`services/admin-backend`)**: same variables under `adminBackend.envs.keycloak`; uses the same `rag-backend` confidential client for client-credential calls to other services.
- **Frontends (`services/frontend`)**:  
  - `VITE_KEYCLOAK_AUTHORITY` → `http://keycloak.rag.localhost/auth/realms/rag`  
  - `VITE_KEYCLOAK_CLIENT_ID` → `rag-frontend`  
  Tokens from the SPA are sent as Bearer tokens to the APIs; the APIs only accept them if `tenant_id` is present.
- **Automation (optional)**: `tools/setup_keycloak.py` can bootstrap a dev realm, `rag-frontend`/`rag-backend` clients, and a demo user. Override creds/URLs via `KEYCLOAK_URL`, `KEYCLOAK_ADMIN_USERNAME`, `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_REALM`.

## Using groups and roles

- Groups are supported in Keycloak and can be mapped into tokens, but tenancy in this codebase is enforced **only** via the `tenant_id` claim. Group membership does not substitute for `tenant_id`.
- To include groups in tokens: for each client, add a mapper (**Client → Client scopes/Mappers → Create → Group membership**; add to access token = ON). The claim will appear as `groups: ["/team/a", ...]`.
- If you want RBAC by group/role, add realm or client roles and map them to users/groups, then enforce them in your APIs (currently the middleware only checks signature + `tenant_id`; any role checks must be added where you authorize actions).

## Using other identity providers (IdP) through Keycloak (recommended)

Use Keycloak as an **identity broker**. External IdPs (OIDC/SAML/social) authenticate the user, and Keycloak still issues the final access token that the services verify. To keep the `tenant_id` claim present for federated users:

1) Configure the external IdP in Keycloak  
   - **Identity providers → Add provider** (OIDC/SAML/others).  
   - Set client ID/secret, endpoints, and (for OIDC) scopes such as `profile email`. Test login.

2) Import or set `tenant_id` on the federated user  
   - Preferred: map an IdP claim/attribute to the Keycloak user attribute `tenant_id`.  
     - For OIDC: **Identity providers → <provider> → Mappers → Add mapper → Claim to user attribute**, set `claim=tenant_id` (or any IdP claim you trust), `user attribute=tenant_id`.  
     - For SAML: use an Attribute Importer mapper with `Attribute name=tenant_id`, `Friendly name` optional, `User attribute=tenant_id`.  
   - If the IdP does not provide a tenant, use a **Hardcoded attribute** mapper on the provider to set `tenant_id=<value>` for all users coming from that IdP.  
   - For per-tenant routing via different IdPs, configure one provider per tenant, each with its own hardcoded `tenant_id`.

3) Keep the `tenant-id` client scope attached  
   - The existing `tenant-id` client scope and mapper (see above) will include the `tenant_id` user attribute in access tokens for `rag-frontend` and `rag-backend`. No code changes are needed.

4) First-broker-login flow (optional)  
   - If you need to enforce user creation rules, add a post-broker login flow to set/validate `tenant_id` before granting access (e.g., check a whitelist and set the attribute). This is optional; a mapper is usually enough.

Result: Users authenticating through external IdPs still receive a Keycloak-issued token with `tenant_id`, and the services work unchanged.

## Replacing Keycloak entirely

- The services expect OIDC JWT access tokens with `tenant_id` and a JWKS endpoint. They also call `KeycloakOpenID.token(...)` for client credentials. A different IdP would require:
  - Matching or reconfiguring JWKS discovery (currently assumes `<issuer>/protocol/openid-connect/certs`).
  - A client-credential flow alternative.
  - Guaranteeing `tenant_id` is issued.  
  This is feasible but needs code/config changes; Keycloak-as-broker is the simplest path.

## Quick checks

- Decode an access token (jwt.io or `python -m jwt`) and confirm `iss` points to your realm, signature verifies, and `tenant_id` is present.
- If you get `Invalid token`, verify `KEYCLOAK_*` URLs match how the service reaches Keycloak (internal service name vs. ingress host).
- If you get `Missing tenant_id claim in token`, add the `tenant_id` mapper/scope and set the user attribute, then reissue the token.
