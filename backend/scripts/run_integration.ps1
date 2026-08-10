$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $backendRoot "compose.test.yml"
$projectName = "tomanap-integration"

Push-Location $backendRoot
try {
    docker compose -p $projectName -f $composeFile up -d --wait
    $env:TOMANAP_TEST_DATABASE_URL = (
        "postgresql+asyncpg://tomanap_test:tomanap_test_only@" +
        "127.0.0.1:55432/tomanap_test"
    )
    $env:TOMANAP_TEST_REDIS_URL = "redis://127.0.0.1:56379/0"
    $env:TOMANAP_DATABASE_URL = $env:TOMANAP_TEST_DATABASE_URL

    uv run python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Alembic upgrade failed" }
    uv run python -m alembic check
    if ($LASTEXITCODE -ne 0) { throw "Alembic schema check failed" }
    uv run python -m alembic downgrade base
    if ($LASTEXITCODE -ne 0) { throw "Alembic downgrade failed" }
    uv run python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Alembic round-trip upgrade failed" }
    uv run python -m pytest tests/integration -m "postgres or redis" -q -W error
    if ($LASTEXITCODE -ne 0) { throw "Integration tests failed" }
}
finally {
    docker compose -p $projectName -f $composeFile down --volumes --remove-orphans
    Pop-Location
}
