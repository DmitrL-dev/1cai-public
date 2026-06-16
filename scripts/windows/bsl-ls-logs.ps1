Param(
    [string]$ComposeFile = "docker-compose.dev.yml"
)

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location ..

Write-Host "[bsl-ls-logs] Tailing logs for bsl-language-server..." -ForegroundColor Cyan
docker-compose -f $ComposeFile logs -f bsl-language-server
$exitCode = $LASTEXITCODE
Pop-Location
Pop-Location
exit $exitCode

