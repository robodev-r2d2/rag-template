# RAG - Frontend

## Table of Contents

 - [Introduction](#introduction)
 - [How to run it](#how-to-run-it)
    - [Prepare](#prepare)
    - [Serve](#serve)
    - [Test](#test)
 - [Dependencies](#dependencies)
 - [Folder Structure](#folder-structure)
 - [Theming](#theme)
 - [Environment variables](#env)

## Introduction

This repository contains the frontend applications built using Vue 3 within an NX monorepo architecture.
Separated into two applications: `chat-app` and `admin-app`.

## How to run it

### Prepare

- Node: >=18.0.0 (see `package.json` engines)
- Formatter: Vue-Official & Basic TS formatter

Install all dependencies for both apps
```shell
npm install
```

### Keycloak setup (once)

The chat and admin apps expect Keycloak to issue tokens. Create a client for the frontends and a user that can log in:

1. Sign in to Keycloak admin (e.g. `http://keycloak.rag.localhost/auth/`).
2. Create (or reuse) the realm you target (default in `values.yaml` is `rag`).
3. Create a new client:
   - Client type: **Public**
   - Client ID: **rag-frontend** (matches `VITE_KEYCLOAK_CLIENT_ID`)
   - Root URL: `http://rag.localhost`
   - Valid redirect URIs: add `http://rag.localhost/*` and `http://admin.rag.localhost/*` (the apps redirect to `/callback` after login).
   - Web origins: add `http://rag.localhost` and `http://admin.rag.localhost` (or `*` for local dev only).
   - Standard flow: **ON**; Direct access grants: **OFF** (default for public SPA clients).
4. Create a test user in the realm and set a password (disable “Temporary” so you can log in).
5. Ensure the frontend env matches Keycloak:
   - `VITE_KEYCLOAK_AUTHORITY` → `http://keycloak.rag.localhost/auth/realms/rag`
   - `VITE_KEYCLOAK_CLIENT_ID` → `rag-frontend`

With these in place:

- `admin-app` redirects unauthenticated visitors to Keycloak.
- `chat-app` is accessible without login and attaches access token automatically when the user signs in.
- Both apps handle the callback at `/callback`.

> If you enable ingress-level Basic Auth (e.g., via `shared.config.basicAuth.enabled` in the Helm values), the browser will prompt for Basic credentials before the app can reach Keycloak, and the redirect back from Keycloak will be blocked. Keep Basic Auth **disabled** for the frontend ingress when using Keycloak, or scope Basic Auth only to the backend/API hosts.

### Use an existing Keycloak deployment

You do not need to deploy the bundled Keycloak chart.

1. Set `features.keycloak.enabled: false` in your Helm values override.
2. Set `VITE_KEYCLOAK_AUTHORITY` to your external realm issuer.
3. Keep `VITE_KEYCLOAK_CLIENT_ID` aligned with your external public client (default `rag-frontend`).
4. Configure backend/admin keycloak envs (`KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM_NAME`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`, `KEYCLOAK_ALLOWED_ISSUERS`) to the same external realm.

For full backend + security details (trusted issuer allowlist, `tenant_id` mapper, and client setup), see [Keycloak usage](../../docs/Keycloak.md).

### Keycloak setup for backend APIs (rag-backend)

The backend services use client credentials to talk to Keycloak (service account flow). Create a confidential client:

1. In Keycloak admin, same realm (default `rag`), go to **Clients → Create**.
2. Client type: **Confidential**, Client ID: **rag-backend** (matches `KEYCLOAK_CLIENT_ID` in values).
3. Enable:
   - **Client authentication**: ON
   - **Service accounts**: ON
4. Credentials: generate/set a secret (e.g., `rag-backend-client-secret`), and keep it in sync with:
   - `backend.envs.keycloak.KEYCLOAK_CLIENT_SECRET`
   - `adminBackend.envs.keycloak.KEYCLOAK_CLIENT_SECRET` (admin-backend also uses client credentials)
   - `backend.envs.keycloak.KEYCLOAK_ALLOWED_ISSUERS` and `adminBackend.envs.keycloak.KEYCLOAK_ALLOWED_ISSUERS`
     should include the public realm issuer (for example `http://keycloak.rag.localhost/auth/realms/rag`)
     and optionally the in-cluster issuer (for example `http://rag-keycloak-http:80/auth/realms/rag`)
5. Tokens: leave defaults unless you need longer TTLs. Scope: ensure realm roles/scopes required by your APIs are assigned to this client’s service account.

If the secret or client type don’t match, calls like `/api/upload_file` will fail with `invalid_client`.

### Serve

To serve one of the application, you can run this command at the root of your workspace.

```shell
# runs the chat app on http://localhost:4200
npm run chat:serve

# runs the admin app on http://localhost:4300
npm run admin:serve
```

### Live updates with Tilt

When running via Tilt, the frontend containers use Nginx and Tilt syncs the built assets (Vite `dist/`) directly into `/usr/share/nginx/html` inside the pod. For live updates while editing code, run a build in watch mode and Tilt will sync changes automatically:

```bash
# From services/frontend
npx nx run admin-app:build --watch
npx nx run chat-app:build --watch
```

### Test

To run unit test, you can run this command at the root of your workspace.

```shell
npm run test
```

## Dependencies

- **@vueuse/core**: Utility functions
- **pinia**: State management
- **vue-i18n**: Internationalization
- **vue-router**: Routing
- **daisyUI**: Tailwind based CSS framework
- **@sit-onyx/icons**: Icon set (used via `OnyxIcon`)
- **cypress**: End-to-end testing framework
- **vite**: Local development server

## Folder Structure
[Simple Nx Monorepo Concept](https://nx.dev/concepts/more-concepts/monorepo-nx-enterprise#scope-where-a-library-lives-who-owns-it)


- `apps/`: Base of the apps chat & administration
- `libs/`: main logic at feature-* folders, shared dumb ui components and utils. See [Library Types in Nx](https://nx.dev/concepts/more-concepts/library-types)
- `i18n`: For localization, each app has its own folder: `i18n/chat` and `i18n/admin`

## Theming

To change the theme, edit `libs/ui-styles/src/tailwind.css` (Tailwind v4 + daisyUI v5 via CSS `@plugin` blocks).

## Environment variables

### Application URLs
- VITE_API_URL = The URL for the backend
- VITE_ADMIN_URL = The URL where the admin frontend is running
- VITE_CHAT_URL = The URL where the chat frontend is running

### Authentication
- VITE_AUTH_USERNAME = Basic auth username used by the frontend
- VITE_AUTH_PASSWORD = Basic auth password used by the frontend
- VITE_CHAT_AUTH_ENABLED = Enable the auth prompt in the chat app (true/false)
- VITE_ENABLE_SPACE_SELECTOR_IN_CHAT = Show optional knowledge-space selector in chat (true/false)
- VITE_ENABLE_UPLOAD_SHARING_TARGET = Show optional upload target selector in admin for shared/global writes (true/false)

### UI Customization
- VITE_BOT_NAME = The AI assistant's display name (default: "Knowledge Agent")
- VITE_UI_LOGO_PATH = Common path to the main navigation logo (fallback for both light/dark, default: "/assets/navigation-logo.svg")
- VITE_UI_LOGO_PATH_LIGHT = Path to the logo used in light mode (fallbacks to VITE_UI_LOGO_PATH, default: "/assets/navigation-logo-light.svg")
- VITE_UI_LOGO_PATH_DARK = Path to the logo used in dark mode (fallbacks to VITE_UI_LOGO_PATH, default: "/assets/navigation-logo-dark.svg")
- VITE_UI_THEME_DEFAULT = Default theme when user first visits (default: "dark")
- VITE_UI_THEME_OPTIONS = Available theme options, comma-separated (default: "light,dark")

For detailed UI customization instructions, see [UI Customization Guide](../../docs/UI_Customization.md).

> Important:
>
> Vite `VITE_*` env vars are build-time by default. The provided Docker images (see `apps/chat-app/Dockerfile` and `apps/admin-app/Dockerfile`) use placeholder replacement at runtime via `env.sh`.
> To apply runtime env vars, copy the built files from `/app/frontend` to `/usr/share/nginx/html` and run `/app/env.sh` before nginx serves the files.
>
> This can be done with the following command:
>
> ```bash
> cp -r /app/frontend/. /usr/share/nginx/html
> /bin/sh /app/env.sh
> ```
>
> This is a workaround for the inability of Vite to use env-vars at runtime.
