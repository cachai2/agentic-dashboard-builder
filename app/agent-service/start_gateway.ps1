Set-Location "C:\Users\cachai\demos\ignite-25-fresh\app\agent-service\OllamaStructuredJson"
$env:PYTHONPATH = "C:\Users\cachai\demos\ignite-25-fresh\app\agent-service"
$env:OLLAMA_MODE = "remote"
$env:OLLAMA_HOST = "https://ollama-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io"
$env:OLLAMA_MODEL = "llama3.1:8b"
$env:OLLAMA_TIMEOUT_SECONDS = "120"
$env:PLAN_SCHEMA_PATH = "C:\Users\cachai\demos\ignite-25-fresh\app\agent-service\schemas\dashboard_plan.schema.json"
& "C:\Python313\python.exe" -m uvicorn app.service:app --host 0.0.0.0 --port 8801 --log-level debug