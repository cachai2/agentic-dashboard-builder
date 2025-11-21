# MCP Shell Session Integration Guide

This document explains how to light up remote shell sessions (Model Context Protocol + Azure Container Apps session pools) inside an existing project. It covers subscription prerequisites, infrastructure deployment, azd/`azure.yaml` wiring, backend + frontend code paths, and validation tips.

## 1. Subscription & Platform Prerequisites

1. **AFEC / feature flags** – ask the ACA engineering contact to enable the following on every subscription that will host the shell session pool:
   - `Microsoft.App/SessionPoolsSupportShell`
   - `Microsoft.App/SessionPoolsSupportMCP`
   - `Microsoft.Resources/EUAPParticipation`
2. **Region restrictions** – Shell + MCP session pools are limited to East US 2 EUAP and North Central US (Stage) at the time of writing. Deploy the pool in those regions even if your Container Apps environment lives elsewhere.
3. **API version** – all ARM/Bicep interactions must use `2025-02-02-preview`.
4. **CLI tooling** – ensure the `az` CLI is on at least 2.63 and that you can run `az rest` against preview APIs. `pwsh` is recommended because the repo’s helper scripts lean on PowerShell 7 features.

## 2. Infrastructure Changes

### 2.1 Bicep parameters and module glue

The main template (`infra/main.bicep`) already exposes everything needed:

| Parameter | Purpose |
| --- | --- |
| `enableShellSessionPool` | Toggles whether the session pool module deploys. |
| `sessionPoolLocation` / `sessionPoolMaxConcurrentSessions` | Define the pool’s region and concurrency cap. |
| `mcpShellEndpoint` / `mcpShellApiKey` | When populated, these become env/secret entries on the agent service container app. Leaving them empty disables runtime integration even if the pool exists. |
| `mcpShellTimeoutSeconds` / `mcpShellSessionTtlSeconds` | Controls HTTP timeout and cached environment TTL inside the agent service. |

When `enableShellSessionPool` is `true`, `infra/modules/session-pool.bicep` provisions a `Microsoft.App/sessionPools` resource with:

- `poolManagementType: Dynamic`
- `containerType: Shell`
- Timed lifecycle w/ configurable cooldown
- `sessionNetworkConfiguration.status: EgressEnabled`
- `mcpServerSettings.isMCPServerEnabled: true`

The module outputs pool id/name so `azd env get-values` can expose them later.

### 2.2 Capturing the MCP endpoint + API key

1. After the module deploys, call `az rest` (or use the portal) to GET the session pool resource with `?api-version=2025-02-02-preview`. Note the `properties.mcpServerEndpoint` URL (e.g., `https://eastus2euap.dynamicsessions.io/.../mcp`).
2. POST to `.../fetchMCPServerCredentials?api-version=2025-02-02-preview` to retrieve a short-lived API key.
3. Feed both values to `azd` via `azd env set MCP_SHELL_ENDPOINT <url>` and `azd env set MCP_SHELL_API_KEY <key>`, or populate them inside `.azure/<env>/.env`.
4. Redeploy (`azd deploy`) so the agent service receives:
   - Env vars: `MCP_SHELL_ENDPOINT`, `MCP_SHELL_TIMEOUT_SECONDS`, `MCP_SHELL_SESSION_TTL_SECONDS`
   - Secret `mcp-shell-api-key` mounted into the Container App

### 2.3 YAML/azd notes

`azure.yaml` already synchronizes all images to the shared ACR and does not need shell-specific edits. Simply ensure the `infra.parameters.*` entries in the env file include:

```env
sessionPoolLocation="eastus2euap"
sessionPoolMaxConcurrentSessions=5
mcpShellEndpoint="https://<dynamicsessions host>/.../mcp"
mcpShellApiKey="<key>"
```

`azd env get-values` / `set` keep these synchronized.

## 3. Backend Application Wiring

Key files: `src/agent-service/app`.

1. **Configuration (`config.py`)** – `Settings` now exposes `mcp_shell_endpoint`, `mcp_shell_api_key`, timeout, and session TTL. Missing env vars cause MCP integration to be skipped but do not break the service.
2. **Service registration (`main.py`)** – during startup, if both endpoint and key exist the app instantiates `MCPShellClient`/`MCPShellService` and stores it on `app.state.shell_service`.
3. **Service implementation (`services/mcp_shell.py`)** – handles JSON-RPC orchestration:
   - Lazily calls `initialize`, then `launchShell`, caches `environmentId` for `mcp_shell_session_ttl_seconds`.
   - Provides `MCPShellService.execute()` which normalizes input (string or token array) and calls the MCP tools.
4. **API surface (`api/routes.py`)** – exposes `POST /operations/shell`. Requests map to `ShellCommandRequest` (command, optional label/mode) and responses use `ShellCommandResponse` with stdout, structured content, etc.
5. **Client responsibilities** – `services/runs.py` and other pipeline code can optionally call the shell service if they need remote diagnostics, but today only the HTTP endpoint + frontend use it.

### Expected environment variables (agent service)

| Key | Description |
| --- | --- |
| `MCP_SHELL_ENDPOINT` | Full MCP server URL from the session pool resource. |
| `MCP_SHELL_API_KEY` | API key returned by `fetchMCPServerCredentials`. Injected as a secret. |
| `MCP_SHELL_TIMEOUT_SECONDS` | Optional override (default 45). |
| `MCP_SHELL_SESSION_TTL_SECONDS` | How long to reuse the launched environment (default 240). |

## 4. Frontend / UX Hooks

Files under `src/frontend` showcase how to surface the shell from the UI:

1. **API client (`src/frontend/src/api/client.ts`)** – adds `executeShellCommand` hitting `POST /operations/shell`.
2. **Hook (`src/frontend/src/hooks/useShellCommand.ts`)** – wraps async execution state for components.
3. **Panel UI (`src/frontend/src/components/ShellCommandPanel.tsx`)** – form for pasting `curl` commands and rendering stdout/structured payloads.
4. **Layout toggle (`App.tsx`)** – `showShellPanel` flag controls whether the panel renders. When integrating into another project, gate it behind feature flags/environment detection so you can hide the UI while MCP is disabled.
5. **Shared types** – `src/frontend/src/types/shell.ts` defines the payload/response contract; keep it in sync with the FastAPI models.

## 5. Operational Scripts & Monitoring

- `scripts/monitor-session-pool.ps1` – Polls the Dynamics Sessions control plane to report sessions, cooldown, and errors.
- `scripts/warm-ollama.ps1` – unrelated to shell but often run post-provision.

Schedule the monitor script (GitHub Actions, Azure DevOps, etc.) if you need proactive alerting around session capacity.

## 6. Validation Checklist

1. **Provisioning** – `azd up` with `enableShellSessionPool=true`; confirm the new `Microsoft.App/sessionPools` resource in the portal.
2. **Endpoint/key** – run the `az rest` commands to capture endpoint + key, store them via `azd env set`.
3. **App config** – `azd deploy` then `azd env get-value MCP_SHELL_ENDPOINT` to verify the env captured the value. Also check the Container App secret blade for `mcp-shell-api-key`.
4. **API smoke test** – `curl -X POST https://<agent-app>/operations/shell -d '{"command":"echo ready"}'`. Expect JSON with stdout, command tokens, and mode.
5. **Frontend test** – enable the panel (set `showShellPanel=true` or add a feature flag) and trigger a command, ensuring results mirror the API response.
6. **Session reuse** – run two commands within `MCP_SHELL_SESSION_TTL_SECONDS` and confirm the backend log shows a single `launchShell` per TTL window.
7. **Pool monitoring** – `pwsh scripts/monitor-session-pool.ps1 -SessionPoolName <name> -ResourceGroup <rg>` to check concurrency/health.

## 7. Common Failure Modes

| Symptom | Likely fix |
| --- | --- |
| `503 MCP shell service is not configured` | Endpoint/key missing; confirm env vars exist and redeploy. |
| `HTTP 403` or `401` from MCP endpoint | API key expired; re-run `fetchMCPServerCredentials` and update `azd env`. |
| Shell panel hidden | `showShellPanel` flag still `false`; wire to environment toggle. |
| Session pool deploy fails | Subscription missing AFEC flags or using unsupported region. |
| Commands hang >45s | Increase `mcpShellTimeoutSeconds` and redeploy. |

## 8. Porting Checklist

When integrating this capability into another project, replicate the following:

1. **Infrastructure** – copy `infra/modules/session-pool.bicep` and the associated parameters/outputs. Ensure your deployment pipeline can set `mcpShellEndpoint`/`ApiKey` after the first provision.
2. **Configuration + service classes** – reuse `app/config.py` additions and `services/mcp_shell.py` along with the FastAPI route.
3. **Frontend** – bring over the hook, types, API client method, and UI panel. Wire to your own design system as needed.
4. **Docs** – provide operators with the AFEC + `az rest` instructions (you can point them to this file).
5. **Security** – store the MCP API key in your secrets manager of choice; limit exposure since it grants remote shell execution.

Following these steps should give any Container Apps-based agent portfolio the same remote shell spotlight experience showcased in Ignite demos.
