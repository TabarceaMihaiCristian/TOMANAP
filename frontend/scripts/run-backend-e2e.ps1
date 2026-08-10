$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$backendRoot = Join-Path $repositoryRoot "backend"
$databasePath = Join-Path $env:TEMP "tomanap-frontend-e2e.db"
$python = Join-Path $backendRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend virtual environment is missing. Run 'uv sync' in the backend directory."
}

$env:TOMANAP_ENVIRONMENT = "test"
$env:TOMANAP_DATABASE_URL = "sqlite+aiosqlite:///$($databasePath.Replace('\', '/'))"
$env:TOMANAP_DEADLINE_WORKER_ENABLED = "false"
$env:TOMANAP_OUTBOX_WORKER_ENABLED = "false"
$env:TOMANAP_MAINTENANCE_WORKER_ENABLED = "false"

Push-Location $backendRoot
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Database migration failed."
    }
    & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}
