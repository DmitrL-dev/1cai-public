Param(
    [Parameter(Mandatory = $true)]
    [string]$Feature
)

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location ..

Write-Host "[feature-init] Creating feature scaffold for '$Feature'" -ForegroundColor Cyan
python scripts\research\init_feature.py --slug $Feature
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Error "[feature-init] init_feature.py exited with code $exitCode"
}
Pop-Location
Pop-Location
exit $exitCode

