# Frontend Agent Playground

Prototype the upload → reasoning → dashboard experience without relying on the full backend. The app is built with Vite + React + TypeScript, ships reusable components, exposes feature flags, and includes Playwright smoke tests plus a mock API server so designers can iterate offline.

## Highlights

- **CSV → dashboard loop**: drag/drop uploader, orchestrator status timeline, KPI grid, and Plotly/iframe dashboard preview. All state flows through `usePlannerSession` which can swap between the real REST bridge and the local mock.
- **Mock planner + API server**: the UI uses `services/mockPlanner.ts`, while `npm run mock-api` hosts the `/upload`, `/dashboard/status`, `/dashboard/view` endpoints expected from `app/main.py`.
- **Component gallery**: append `?gallery=1` or tap the hero toggle to explore documented components (Uploader, StatusTimeline, MetricsGrid, ErrorBanner, DashboardViewer) without Storybook overhead.
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
| `VITE_USE_MOCK` | `true` | Switch between the in-app mock planner and REST client. |
| `VITE_API_BASE_URL` | `http://localhost:8800` | REST endpoint base for `/upload`, `/dashboard/status`, `/dashboard/view`. |
| `VITE_ENABLE_AGENT_FRAMEWORK` | `false` | Surfaces a hero badge to show when the Agent Framework integration is live. |
| `VITE_ENABLE_APP_INSIGHTS` | `false` | Enables the Application Insights hook (wire the SDK + connection string when ready). |

Feature flag values are rendered in the hero pill so demo crews always know what data source is backing the UI.

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
