Param(
    [string]$Feature
)

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location ..

if ([string]::IsNullOrWhiteSpace($Feature)) {
    Write-Host "[feature-validate] Validating all features" -ForegroundColor Cyan
    python scripts\research\check_feature.py
} else {
    Write-Host "[feature-validate] Validating feature '$Feature'" -ForegroundColor Cyan
    python scripts\research\check_feature.py --feature $Feature
}
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Error "[feature-validate] Validation failed with code $exitCode"
}
Pop-Location
Pop-Location
exit $exitCode

