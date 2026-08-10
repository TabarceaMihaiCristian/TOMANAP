param(
    [string]$Target = "http://host.docker.internal:58000",
    [string]$ReportDirectory = "",
    [int]$SpiderMinutes = 1
)

$ErrorActionPreference = "Stop"
$backendRoot = Split-Path -Parent $PSScriptRoot
if (-not $ReportDirectory) {
    $ReportDirectory = Join-Path $backendRoot "work\zap"
}
New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null
$resolvedReports = (Resolve-Path -LiteralPath $ReportDirectory).Path

docker run --rm `
    --volume "${resolvedReports}:/zap/wrk/:rw" `
    ghcr.io/zaproxy/zaproxy:stable `
    zap-baseline.py `
    -t $Target `
    -m $SpiderMinutes `
    -s `
    -J tomanap-zap.json `
    -r tomanap-zap.html

$scanExitCode = $LASTEXITCODE
if ($scanExitCode -eq 1) {
    throw "OWASP ZAP reported at least one configured failure"
}
if ($scanExitCode -eq 3) {
    throw "OWASP ZAP could not complete the scan"
}
if ($scanExitCode -eq 2) {
    Write-Warning "OWASP ZAP completed with warnings that require triage"
}

Write-Output "ZAP reports: $resolvedReports"
