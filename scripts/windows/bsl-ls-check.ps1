Param(
    [string]$ServerUrl = "http://localhost:8081"
)

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location ..

Write-Host "[bsl-ls-check] Running health and parse check against $ServerUrl" -ForegroundColor Cyan
$env:BSL_LANGUAGE_SERVER_URL = $ServerUrl
python scripts\parsers\check_bsl_language_server.py
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Error "[bsl-ls-check] Health check failed with code $exitCode"
}
Pop-Location
Pop-Location
exit $exitCode

