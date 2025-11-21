param(
    [string]$OllamaHost = "https://ollama-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io",
    [int]$AgentPort = 8800,
    [string]$FrontendOrigin = "http://localhost:5173",
    [switch]$SkipInstalls
)

$ErrorActionPreference = 'Stop'

function Write-Section($message) {
    Write-Host "`n=== $message ===" -ForegroundColor Cyan
}

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return 'py'
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return 'python'
    }
    throw "Python executable not found. Install Python 3.10+ or ensure 'python'/'py' is on PATH."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$agentDir = Join-Path $repoRoot "agent-service" | Join-Path -ChildPath "AgentOrchestrator"
$frontendDir = Join-Path $repoRoot "frontend-service"

if (-not (Test-Path $agentDir)) {
    throw "AgentOrchestrator directory not found at $agentDir"
}
if (-not (Test-Path $frontendDir)) {
    throw "frontend-service directory not found at $frontendDir"
}

Write-Section "Preparing agent-service virtual environment"
$pythonCmd = Get-PythonCommand
$venvPath = Join-Path $agentDir ".venv"
if (-not (Test-Path (Join-Path $venvPath "Scripts\Activate.ps1"))) {
    Write-Host "Creating Python virtual environment using $pythonCmd..."
    Push-Location $agentDir
    & $pythonCmd -m venv .venv
    Pop-Location
}

if (-not $SkipInstalls) {
    Write-Host "Installing AgentOrchestrator dependencies..."
    Push-Location $agentDir
    & "$venvPath\Scripts\python.exe" -m pip install -e . --pre
    Pop-Location
}

Write-Section "Writing agent-service .env"
$agentEnvPath = Join-Path $agentDir ".env"
$agentEnvContent = @"
ORCH_OLLAMA_HOST="$OllamaHost"
ORCH_PLANNER_MODE="remote"
ORCH_ALLOWED_ORIGINS="$FrontendOrigin"
"@
Set-Content -Path $agentEnvPath -Value $agentEnvContent -Encoding UTF8

Write-Section "Preparing frontend env file"
$frontendEnvPath = Join-Path $frontendDir ".env.local"
$frontendEnvContent = @"
VITE_API_BASE_URL=http://localhost:$AgentPort
VITE_USE_MOCK=false
"@
Set-Content -Path $frontendEnvPath -Value $frontendEnvContent -Encoding UTF8

if (-not $SkipInstalls) {
    Write-Section "Installing frontend dependencies"
    Push-Location $frontendDir
    npm install
    Pop-Location
}

Write-Section "Launching services in dedicated terminals"
$agentCommand = "cd `"$agentDir`"; `"$venvPath\Scripts\Activate.ps1`"; uvicorn agent_orchestrator.api.app:app --host 0.0.0.0 --port $AgentPort --reload"
Start-Process powershell -ArgumentList "-NoExit","-Command",$agentCommand | Out-Null

$frontendCommand = "cd `"$frontendDir`"; npm run dev"
Start-Process powershell -ArgumentList "-NoExit","-Command",$frontendCommand | Out-Null

Write-Section "Done"
Write-Host "Backend running on http://localhost:$AgentPort" -ForegroundColor Green
Write-Host "Frontend running on http://localhost:5173" -ForegroundColor Green
Write-Host "Use Ctrl+C inside each spawned terminal to stop the processes." -ForegroundColor Yellow
