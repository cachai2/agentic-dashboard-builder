# Frontend Agent Playground

Prototype the upload → reasoning → dashboard experience without relying on the full backend. The app is built with Vite + React + TypeScript, ships reusable components, exposes feature flags, and includes Playwright smoke tests plus a mock API server so designers can iterate offline.

## Status snapshot · Nov 19 2025

- `npm run dev` is the primary Ignite demo path (optimized for a 15" Surface projecting to stage displays).
- Single CSV ingest story is live with the mock planner by default; flip `VITE_USE_MOCK=false` once the real orchestrator is online.
- Latest UX polish: 3-step flow indicator, dashboard skeleton that animates only while generation is running, and a reactive drag/drop uploader hover state.
- Quality gates: `npm run test:e2e` last ran on 2025-11-19 (pass) and `npm run build` previously succeeded after the latest UI sweep.

## Highlights

- **CSV → dashboard loop**: drag/drop uploader, orchestrator status timeline, KPI grid, and Plotly/iframe dashboard preview. All state flows through `usePlannerSession` which can swap between the real REST bridge and the local mock.
- **Mock planner + API server**: the UI uses `services/mockPlanner.ts`, while `npm run mock-api` hosts the `/upload`, `/dashboard/status`, `/dashboard/view` endpoints expected from `app/main.py`.
- **Component gallery**: append `?gallery=1` or tap the hero toggle to explore documented components (Uploader, StatusTimeline, MetricsGrid, ErrorBanner, DashboardViewer) without Storybook overhead.
- **Guided story arc**: the 3-step indicator, idle + active dashboard placeholder states, and gated animation keep demo audiences oriented from upload to insights.
- **Reactive uploader**: the drag/drop surface now pulses on hover and lifts during drag to telegraph that files can be dropped safely.
- **Smoke coverage**: Playwright tests exercise upload success, validation errors, and retry/reset flows with the dev server auto-booted.
- **Debug + telemetry hooks**: `window.DashboardDemo` exposes the latest session + plan, and `trackEvent` is wired for Application Insights once a connection string is provided.

## Getting Started

```powershell
cd Playground/FrontendAgent
npm install
npm run dev
```

- Visit `http://localhost:5173` for the playground.
- Toggle the component gallery from the hero or load `http://localhost:5173?gallery=1`.

### Mock API server (optional)

```powershell
npm run mock-api
```

The mock service listens on `http://localhost:8800` and mirrors the backend contracts. Set `VITE_API_BASE_URL=http://localhost:8800` in `.env.local` to force the frontend to talk to it instead of the in-browser mock client.

### Environment flags

| Env var | Default | Purpose |
| --- | --- | --- |
| `VITE_USE_MOCK` | `false` (prod) | Switch between the in-app mock planner and REST client. Set to `true` only for offline demos. |
| `VITE_API_BASE_URL` | `https://agent-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io` (prod) | REST endpoint base for `/upload`, `/dashboard/status`, `/dashboard/view`. Local fallback remains `http://localhost:8800`. |
| `VITE_ENABLE_AGENT_FRAMEWORK` | `false` | Surfaces a hero badge to show when the Agent Framework integration is live. |
| `VITE_ENABLE_APP_INSIGHTS` | `false` | Enables the Application Insights hook (wire the SDK + connection string when ready). |

Feature flag values are rendered in the hero pill so demo crews always know what data source is backing the UI.

- `.env.production` pins the planner to the Azure agent (`VITE_API_BASE_URL`) and keeps `VITE_USE_MOCK=false`.
- `.env.local.example` mirrors those settings—copy it to `.env.local` when you want local dev to speak to Azure.
- Override `VITE_USE_MOCK=true` in `.env.local` whenever you need the in-browser mock planner for offline demos.

## Azure deployment checklist

1. **Frontend env vars** – deploy `VITE_API_BASE_URL=https://agent-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io` and `VITE_USE_MOCK=false` via your Container App/App Service config (matching `.env.production`).
2. **Agent CORS** – ensure `ORCH_ALLOWED_ORIGINS` (or the defaults baked into `agent_orchestrator.api.app`) include both the Azure frontend URL and `http://localhost:5173` for local smoke tests.
3. **Agent → Ollama** – configure `ORCH_OLLAMA_HOST=https://planner-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io` (or your preferred host) and any required credentials on the agent container.
4. **Restart containers** – bounce the Azure frontend, agent, and Ollama apps after changing env vars so settings reload.
5. **Smoke test** – upload a CSV from the Azure frontend and confirm `/upload` calls hit the Azure agent domain without CORS/network errors.

## Testing & quality

- **Lint**: `npm run lint`
- **Build**: `npm run build`
- **Playwright smoke tests** (auto-starts the dev server on port 4173):

  ```powershell
  npm run test:e2e
  ```

  Use `npm run test:e2e:headed` for visual debugging. Fixtures live under `tests/fixtures/` and cover happy path upload, validation errors, and retry/resets.

## Project layout

```text
src/
  components/         Reusable UI building blocks (Uploader, StatusTimeline, etc.)
  config/             UI copy + feature flags
  hooks/              Planner/session hooks + telemetry
  pages/              Playground + component gallery views
  services/           Mock planner + REST planner client
  styles/             Tokens + global styles
public/sample-dashboard.html  static iframe dashboard for demos
tests/e2e/            Playwright smoke tests + fixtures
mock/server.mjs       Express mock API matching backend contracts
```

## Debug & instrumentation

- Run `window.DashboardDemo` in DevTools to inspect the latest session id, metrics, and Plotly configs that were generated.
- `trackEvent` logs telemetry to the console by default and is ready for an Application Insights connection string when we have one.

## Next steps

- Wire the REST client to the real orchestrator once available (types already mirror `/upload`, `/dashboard/status`, `/dashboard/view`).
- Drop in the official Application Insights SDK inside `trackEvent` when the instrumentation key lands.
- Explore optimistic UI for uploads by surfacing the CSV preview returned from `services/mockPlanner.ts`.

Feel free to grab the component gallery for documentation demos until Storybook is required.
