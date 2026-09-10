$ErrorActionPreference = 'Stop'
$profileData = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'profile.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$vsix = Join-Path $PSScriptRoot 'assets/cline.vsix'
if ((Get-FileHash -LiteralPath $vsix -Algorithm SHA256).Hash.ToLowerInvariant() -ne $profileData.cline_sha256) {
    throw 'Cline VSIX changed; installation refused.'
}
$companion = Join-Path $PSScriptRoot 'assets/rentgen-companion.vsix'
if ((Get-FileHash -LiteralPath $companion -Algorithm SHA256).Hash.ToLowerInvariant() -ne $profileData.companion_sha256) {
    throw 'Rentgen companion VSIX changed; installation refused.'
}
$editorCli = $profileData.editor_cli
if (-not (Test-Path -LiteralPath $editorCli -PathType Leaf)) { throw 'Editor CLI was not found.' }
$priorElectron = $env:ELECTRON_RUN_AS_NODE
try {
    $env:ELECTRON_RUN_AS_NODE = '1'
    & $profileData.editor $editorCli --user-data-dir (Join-Path $PSScriptRoot 'editor') --extensions-dir (Join-Path $PSScriptRoot 'extensions') --install-extension $vsix | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Cline installation failed.' }
    & $profileData.editor $editorCli --user-data-dir (Join-Path $PSScriptRoot 'editor') --extensions-dir (Join-Path $PSScriptRoot 'extensions') --install-extension $companion | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Rentgen companion installation failed.' }
} finally {
    $env:ELECTRON_RUN_AS_NODE = $priorElectron
}
