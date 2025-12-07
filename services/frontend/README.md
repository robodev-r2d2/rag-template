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
Seperated in 2 appilcations `chat-app` and `admin-app`

## How to run it

### Prepare

- Node : Version >22.12.0
- Fomatter : Vue-Official & Basic Ts formatter

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

With these in place, the frontends will redirect unauthenticated visitors to Keycloak, handle the callback at `/callback`, and attach the access token to API calls.

> If you enable ingress-level Basic Auth (e.g., via `shared.config.basicAuth.enabled` in the Helm values), the browser will prompt for Basic credentials before the app can reach Keycloak, and the redirect back from Keycloak will be blocked. Keep Basic Auth **disabled** for the frontend ingress when using Keycloak, or scope Basic Auth only to the backend/API hosts.

### Serve

To serve one of the application, you can run this command at the root of your workspace.

```shell
// runs the chat app on http://localhost:4200
npx nx serve chat-app:serve

// runs the admin app on http://localhost:4300
npx nx serve admin-app:serve
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
- **heroicons**: Hand-crafted SVG icons (by Tailwind CSS)
- **cypress**: End-to-end testing framework
- **vite**: Local development server

## Folder Structure
[Simple Nx Monorepo Concept](https://nx.dev/concepts/more-concepts/monorepo-nx-enterprise#scope-where-a-library-lives-who-owns-it)


- `apps/`: Base of the apps chat & administration
- `libs/`: main logic at feature-* folders, shared dumb ui components and utils. See [Library Types in Nx](https://nx.dev/concepts/more-concepts/library-types)
- `i18n`: For localization, each app has its own folder: `i18n/chat` and `i18n/admin`

## Theming

To change the theme, open the `tailwind.config.js` file and refer to the available color configuration options for DaisyUI at https://daisyui.com/docs/colors/

## Environment variables

### Application URLs
- VITE_API_URL = The URL for the backend
- VITE_ADMIN_URL = The URL where the admin frontend is running
- VITE_CHAT_URL = The URL where the chat frontend is running

### UI Customization
- VITE_BOT_NAME = The AI assistant's display name (default: "Knowledge Agent")
- VITE_UI_LOGO_PATH = Common path to the main navigation logo (default: "/assets/navigation-logo.svg"). Used as a fallback for both light/dark.
- VITE_UI_LOGO_PATH_LIGHT = Path to the logo used in light mode (fallbacks to VITE_UI_LOGO_PATH)
- VITE_UI_LOGO_PATH_DARK = Path to the logo used in dark mode (fallbacks to VITE_UI_LOGO_PATH)
- VITE_UI_THEME_DEFAULT = Default theme when user first visits (default: "dark")
- VITE_UI_THEME_OPTIONS = Available theme options, comma-separated (default: "light,dark")

For detailed UI customization instructions, see [UI Customization Guide](../../docs/UI_Customization.md).

> Important:
>
> The environment variables are not used after the docker-image is build.
> When using the `Dockerfile` to run the frontend you have to copy the build frontend from `/app/frontend` to `/usr/share/nginx/html` and run the `/app/env.sh` script.
>
> This can be done with the following command:
>
> ```bash
> cp -r /app/frontend/. /usr/share/nginx/html
> /bin/sh -c /app/env.sh
> ```
>
> This is a workaround for the inability of Vite to use env-vars at runtime.
