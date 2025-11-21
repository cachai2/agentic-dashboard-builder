# MCP Load-Test Tool Specification

This document extends `mcpshellsessions.md` with the concrete feature work needed to ship the **`run_load_test`** MCP shell tool. The existing guide already covers how MCP shell sessions are provisioned (session pool module, env vars such as `MCP_SHELL_ENDPOINT` and `MCP_SHELL_API_KEY`, FastAPI wiring, frontend panel hooks, etc.). The spec below treats that infrastructure as given and focuses on the new load-test capability: what to build, how to expose it as an MCP tool, and how to narrate it in the Ignite demo.

---

## 1. Goal & Demo Narrative

- **Goal:** Add a single MCP tool named `run_load_test` that hits the agent service's `/dashboard/plan` endpoint with a short `curl` burst, summarizes success rate + latency, and feeds the result back through the agent.
- **Demo story:** The agent that builds dashboards can also self-validate performance. During the demo you ask, "Run a quick load test against the planner and tell me how many requests succeeded and the average latency." The agent invokes `run_load_test`, receives a JSON summary, and replies with a natural-language recap while ACA serverless GPU scaling is shown in the portal.

Dependencies are identical to those outlined in `mcpshellsessions.md`:

| Item | Notes |
| --- | --- |
| MCP shell endpoint + API key | Already delivered by the session pool module. Stored in `MCP_SHELL_ENDPOINT` / `MCP_SHELL_API_KEY`. |
| Agent base URL | New env var `AGENT_BASE_URL` (e.g., `https://agent-ignite-demo-...azurecontainerapps.io`). Provide via `azd env set AGENT_BASE_URL <url>` so the MCP server can reach `/dashboard/plan`. |
| Timeout/TTL | Reuse `MCP_SHELL_TIMEOUT_SECONDS` / `MCP_SHELL_SESSION_TTL_SECONDS`; no changes required. |

---

## 2. Tool Contract

Register a single MCP tool in the shell server:

```json
{
  "name": "run_load_test",
  "description": "Run a short curl-based load test against the dashboard planner endpoint and summarize results.",
  "parameters": {
    "type": "object",
    "properties": {
      "requests": {
        "type": "integer",
        "default": 20,
        "minimum": 1,
        "maximum": 100,
        "description": "Total number of requests to send"
      },
      "concurrency": {
        "type": "integer",
        "default": 5,
        "minimum": 1,
        "maximum": 20,
        "description": "Parallel curl workers"
      }
    }
  }
}
```

Return payload (tool result) must be the JSON summary consumed by the agent:

```json
{
  "total_requests": 20,
  "success_count": 20,
  "failure_count": 0,
  "average_latency_seconds": 0.43
}
```

---

## 3. MCP Shell Implementation

### 3.1 Environment expectations

- `AGENT_BASE_URL` – base HTTPS URL for the deployed agent Container App. Add this to `.azure/<env>/.env` via `azd env set`.
- Existing MCP env vars from `mcpshellsessions.md` (`MCP_SHELL_ENDPOINT`, `MCP_SHELL_API_KEY`, timeouts, TTLs) remain unchanged.

### 3.2 Command template

Use a fixed shell command (no user-provided fragments) that prints `HTTP_STATUS LATENCY_SECONDS` per line. Two variants depending on HTTP verb; the agent's `/dashboard/plan` is POST, so include a minimal JSON body.

```bash
seq 1 "${REQUESTS}" | xargs -n1 -P"${CONCURRENCY}" bash -c '
  curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "{\"profile_summary\":{}}" \
    -o /dev/null \
    -w "%{http_code} %{time_total}\n" \
    "${LOAD_TEST_URL}"
'
```

Notes:
- Replace the dummy `profile_summary` with a lightweight payload that satisfies the API contract (e.g., include a minimal valid request object or reuse a canned JSON blob from `app/agent-service/AgentOrchestrator/artifacts/plan.json`). Keeping the payload static ensures deterministic timing.
- All variables (`REQUESTS`, `CONCURRENCY`, `LOAD_TEST_URL`) are interpolated server-side; the user cannot inject shell content.

### 3.3 MCP server pseudo-code

```python
import os
import statistics
import subprocess
from typing import Any, Dict

DEFAULT_REQUESTS = 20
DEFAULT_CONCURRENCY = 5


def run_load_test(requests: int = DEFAULT_REQUESTS, concurrency: int = DEFAULT_CONCURRENCY) -> Dict[str, Any]:
    base_url = os.environ["AGENT_BASE_URL"].rstrip("/")
    url = f"{base_url}/dashboard/plan"

    cmd = [
        "bash",
        "-lc",
        (
            f"seq 1 {requests} | xargs -n1 -P{concurrency} bash -c '"
            "curl -s -X POST -H \"Content-Type: application/json\" "
            "-d \"{\\\"profile_summary\\\":{}}\" -o /dev/null "
            "-w \"%{{http_code}} %{{time_total}}\\n\" "
            f"\"{url}\"'"
        ),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    statuses = []
    latencies = []

    for line in proc.stdout.strip().splitlines():
        status_str, latency_str = line.split()
        statuses.append(int(status_str))
        latencies.append(float(latency_str))

    total = len(statuses)
    success = sum(1 for s in statuses if 200 <= s < 300)
    failure = total - success
    avg_latency = statistics.mean(latencies) if latencies else None

    return {
        "total_requests": total,
        "success_count": success,
        "failure_count": failure,
        "average_latency_seconds": avg_latency,
    }
```

Edge cases:
- If curl fails entirely, `proc.returncode` will be non-zero. Surface a structured error so the LLM can report "load test failed; curl exit code 6".
- Skip malformed lines defensively.

### 3.4 Backend/Frontend glue

- **FastAPI** – no changes; the MCP server already talks directly to the agent via HTTPS. Ensure CORS/ACLs allow the MCP session pool to reach the public agent endpoint.
- **Frontend shell panel** – optional. If you want a quick shortcut button, add a preset command that asks the agent, "Run a quick load test..." as described in the narrative.

---

## 4. Agent Runtime Integration

1. **Tool registration (LLM side)** – add `run_load_test` to your agent framework (e.g., `PersistentAgentsClient`). Update the system prompt with guidance: _"You can call `run_load_test` to benchmark the planner service; do so when the user asks about performance, load, or autoscale."_
2. **Telemetry** – log each invocation (requests, concurrency, summary) to Application Insights so you can correlate with ACA metrics.
3. **Safety** – enforce min/max bounds server-side to avoid unintentional large bursts. The values above (1–100 requests, 1–20 concurrency) are safe for a live demo.

---

## 5. Demo Script

1. **Set the stage** (after showing dashboard generation):
   - "Same agent can validate its own backend via a shell tool."
2. **Prompt the agent** with the exact wording you plan to use: _"Run a quick load test against the planner and tell me how many requests succeeded and the average latency."_
3. **Agent response path**:
   - LLM calls `run_load_test` → MCP shell executes the command → JSON summary → LLM natural-language recap.
4. **Show ACA scaling**:
   - Flip to the ACA portal (planner Container App) and display the metrics/revisions blade with autoscale events.
5. **Tie-back**:
   - Highlight MCP tooling for ops plus ACA serverless GPU autoscale.

---

## 6. Implementation Checklist

| Step | Details |
| --- | --- |
| 1. Env setup | `azd env set AGENT_BASE_URL https://agent-...azurecontainerapps.io` (keep in `.azure/<env>/.env`). |
| 2. MCP tool code | Add `run_load_test` implementation to the MCP shell server plus schema entry. |
| 3. Command payload | Create or reuse a minimal valid `/dashboard/plan` JSON body stored on disk; reference it in the curl `-d @payload.json` if easier. |
| 4. Agent registration | Update agent framework config and system prompt to describe when to use the tool. |
| 5. Testing | Run the tool locally (`python run_load_test.py`) against a dev agent before wiring into MCP. Validate success/failure handling. |
| 6. Demo prep | Pre-open ACA planner metrics tab; optionally prepare a shortcut in the UI to issue the prompt. |

---

## 7. Future Enhancements (Optional)

- Accept a parameter to choose between `/dashboard/plan` and another endpoint (e.g., `/dashboard/view`).
- Emit percentile latency (P95) in addition to average.
- Stream load-test output back to the user as structured content so they can inspect each individual request.

With this specification and the existing MCP shell wiring documented in `mcpshellsessions.md`, you have a complete blueprint for implementing and demoing the `run_load_test` capability without introducing new Azure resources.
