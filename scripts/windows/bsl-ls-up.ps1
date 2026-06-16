Param(
    [string]$ComposeFile = "docker-compose.dev.yml"
)

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location ..

Write-Host "[bsl-ls-up] Starting bsl-language-server via $ComposeFile..." -ForegroundColor Cyan
docker-compose -f $ComposeFile up -d bsl-language-server
if ($LASTEXITCODE -ne 0) {
    Write-Error "[bsl-ls-up] docker-compose exited with code $LASTEXITCODE"
    Pop-Location
    Pop-Location
    exit $LASTEXITCODE
}

Write-Host "[bsl-ls-up] Service is starting; check logs with scripts/windows/bsl-ls-logs.ps1" -ForegroundColor Green
Pop-Location
Pop-Location

