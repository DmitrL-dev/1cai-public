$ErrorActionPreference = 'Stop'
$profileData = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'profile.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$priorData = $env:CLINE_DATA_DIR
$priorDir = $env:CLINE_DIR
$priorBundle = $env:CLINE_BUNDLE_OVERRIDE
$priorProfile = $env:RENTGEN_EDITOR_PROFILE
try {
    $env:RENTGEN_EDITOR_PROFILE = $PSScriptRoot
    $env:CLINE_BUNDLE_OVERRIDE = 'legacy'
    $env:CLINE_DIR = Join-Path $PSScriptRoot 'cline'
    $env:CLINE_DATA_DIR = Join-Path $PSScriptRoot 'cline/data'
    & $profileData.editor --user-data-dir (Join-Path $PSScriptRoot 'editor') --extensions-dir (Join-Path $PSScriptRoot 'extensions') --new-window (Join-Path $PSScriptRoot 'rentgen.code-workspace')
} finally {
    $env:CLINE_DATA_DIR = $priorData
    $env:CLINE_DIR = $priorDir
    $env:CLINE_BUNDLE_OVERRIDE = $priorBundle
    $env:RENTGEN_EDITOR_PROFILE = $priorProfile
}
