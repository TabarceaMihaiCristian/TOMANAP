# TOMANAP frontend

Responsive Romanian game client built with React, TypeScript, Vite, TanStack Query, and a generated OpenAPI contract.

## Architecture

```text
src/
├── api/                 # The only HTTP boundary and generated API types
├── app/                 # Composition root, providers, routing, shell, global styles
├── features/            # Home, lobby, game, review, realtime, and session slices
├── shared/              # Reusable presentational UI and framework-independent helpers
└── test/                # Test renderer and isolated browser shims
e2e/                     # Desktop/mobile journeys and optional live-backend contract test
scripts/                 # Local integration-test infrastructure
```

Features depend on `ApiClient`; components do not call `fetch` directly. The backend remains the authority for rooms, sessions, timers, rounds, scoring, and realtime events. `openapi.json` is exported from FastAPI and generates `src/api/schema.d.ts`, preventing the two applications from silently drifting.

## Local development

Prerequisites: a supported Node.js release, npm, `uv`, and the backend virtual environment.

```powershell
npm ci
npm run dev
```

The client opens at `http://127.0.0.1:5173` and uses `http://127.0.0.1:8000` by default. Override the API origin with a local, uncommitted `.env.local` file:

```dotenv
VITE_API_URL=http://127.0.0.1:8000
```

## Contract generation

After changing backend routes or schemas:

```powershell
npm run api:generate
```

Review both `openapi.json` and `src/api/schema.d.ts` with the backend change.

## Quality gates

```powershell
npm run check
npm run format:check
npm run test:e2e
```

`npm run test:e2e` covers the responsive UI with Chromium desktop and Pixel 7 profiles. The live-backend test is opt-in:

```powershell
# Terminal 1
npm run backend:e2e

# Terminal 2
$env:TOMANAP_E2E_BACKEND = "1"
npm run test:e2e:backend
```

The integration database is an isolated SQLite file in the operating-system temporary directory.

To run the complete live suite, including refresh/token rotation and a
three-round game with two independent browser sessions:

```powershell
# Terminal 1
npm run backend:e2e

# Terminal 2
$env:TOMANAP_E2E_BACKEND = "1"
npm run test:e2e:live
```

## Resilience

- A central session provider rotates credentials on refresh before protected
  routes or realtime connections are allowed to load.
- Invalid reconnect credentials are cleared, while transient failures retain
  the reconnect token and expose an explicit retry.
- Room routes share consistent restoring, retry, and session-lost states.
- Realtime events invalidate only the affected authoritative query scopes.
- Definitively rejected realtime sessions stop reconnecting and clear local
  credentials.
- Zone-less backend timestamps are interpreted as UTC; malformed deadlines
  fail closed.
- Unexpected render errors, unknown routes, and offline browser state have
  dedicated, sanitized user interfaces.

## Security choices

- Session and reconnect credentials are tab-scoped in `sessionStorage`, never local storage or URLs.
- Requests omit ambient credentials and referrer data.
- Unexpected server bodies are not displayed to users.
- Backend-provided HTML is never injected into the DOM.
- Realtime authentication uses short-lived one-time tickets and bounded reconnection.
- Strict TypeScript, typed ESLint, accessibility linting, dependency auditing, and lockfile installs are mandatory gates.

Deployment configuration is intentionally deferred. At deployment time, set the production API origin, frontend security headers, asset caching, observability, and the backend CORS allowlist together.

Before deployment, also add frontend error-reporting transport, enforce bundle
and Core Web Vitals budgets in CI, connect real game sound cues to the stored
sound preference, and fail CI when regenerated OpenAPI artifacts drift.
