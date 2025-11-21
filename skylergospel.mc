Skyler Gospel – Build & Operate Guidance

1. Build the project with clearly separated folders for each app or microservice so copilots can focus on their own surface area.
2. Run copilots in parallel: one Codex instance driving the backend, another owning the frontend, or scope prompts tightly per concern.
3. Ask for outline plans plus pressure-testing steps while other work executes to keep agents coordinated.
4. Prefer Azure CLI commands over `azd up`; create a single `deploy-2-azure.sh` helper that performs the full deployment.
5. Lean into structured outputs and tool calling—they reinforce each other. Enable strict mode in system prompts so responses adhere to JSON.
6. Reference OpenAI tool/function-calling docs (the “copy/paste” example shows how to build a ReAct loop agent) and reuse that blueprint to bootstrap agents quickly.
7. Experiment with the `gpt-oss20b` model—it’s comparable to o3 for this workload.
8. Start with mvp with a llm for orchestration
9. If need be take azd up scaffolding from codex project to use