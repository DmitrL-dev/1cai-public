# Run local mock controls in a separate pwsh process; no real HTTP or sleeps.
param(
    [Parameter(Mandatory)][string]$HelperPath,
    [Parameter(Mandatory)][string]$MockRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not [System.IO.Path]::IsPathRooted($HelperPath) -or
    (Get-FileHash -LiteralPath $HelperPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne '1d7f911f1176d1041cb5a8c6002da530dd1888268cd7833c543b3ad2a932dfe4') {
    throw 'Exact helper Source pin required'
}
if (-not [System.IO.Path]::IsPathRooted($MockRoot) -or (Test-Path -LiteralPath $MockRoot)) {
    throw 'MockRoot must be a new absolute owned directory'
}
$script:MockRootFull = [System.IO.Path]::GetFullPath($MockRoot).TrimEnd([char[]]@('\', '/'))
$null = [System.IO.Directory]::CreateDirectory($script:MockRootFull)
. $HelperPath
$script:JavaUri = 'https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip'
$script:BslUri = 'https://github.com/1c-syntax/bsl-language-server/releases/download/v1.0.5/bsl-language-server-1.0.5-exec.jar'
$script:GoodSha = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
class MockRuntimeHttpResponseException : System.Exception {
    [System.Net.Http.HttpResponseMessage]$Response
    MockRuntimeHttpResponseException([int]$Status) : base('mock structured IWR Response') {
        $this.Response = [System.Net.Http.HttpResponseMessage]::new([System.Net.HttpStatusCode]$Status)
    }
}
$script:Assertions = 0; $script:Cases = 0
function Check([bool]$Condition, [string]$Message) {
    $script:Assertions++
    if (-not $Condition) { throw "Mock control failed: $Message" }
}
# All commands used by the helper are shadowed here; IWR never reaches the network.
function Invoke-WebRequest {
    [CmdletBinding()]
    param([uri]$Uri, [string]$OutFile, [int]$TimeoutSec, [int]$MaximumRetryCount)
    Check ($TimeoutSec -eq 120) 'per-request timeout'
    Check ($MaximumRetryCount -eq 0) 'no hidden built-in retries'
    Check ($PSBoundParameters['ErrorAction'] -eq 'Stop') 'terminating request failure'
    Check ($Uri.OriginalString -in @($script:JavaUri, $script:BslUri)) 'URL unchanged'
    Check ($script:Requests.Count -lt $script:Plan.Count) 'unexpected extra request'
    $index = $script:Requests.Count
    $script:Requests.Add([pscustomobject]@{uri=$Uri.OriginalString; file=$OutFile})
    # A prior failed attempt leaves a partial; the retry must remove it first.
    Check (-not (Test-Path -LiteralPath $OutFile)) 'stale partial reused'
    $action = $script:Plan[$index]
    if ($action -eq 'ABC') { [System.IO.File]::WriteAllBytes($OutFile, [byte[]]@(97,98,99)); return }
    if ($action -eq 'ABD') { [System.IO.File]::WriteAllBytes($OutFile, [byte[]]@(97,98,100)); return }
    if ($action -eq 'AB') { [System.IO.File]::WriteAllBytes($OutFile, [byte[]]@(97,98)); return }
    if ($action -eq 'HTML') {
        [System.IO.File]::WriteAllText($OutFile, '<!doctype html><title>Unicorn</title>')
        return
    }
    [System.IO.File]::WriteAllBytes($OutFile, [byte[]]@(112))
    if ($action.StartsWith('RESPONSE')) {
        $exception = [MockRuntimeHttpResponseException]::new([int]$action.Substring(8))
    } elseif ($action.StartsWith('HTTP')) {
        $exception = [System.Net.Http.HttpRequestException]::new(
            'mock structured HTTP failure', $null, [System.Net.HttpStatusCode][int]$action.Substring(4))
    } elseif ($action -eq 'TIMEOUT') {
        $exception = [System.TimeoutException]::new('mock network timeout')
    } elseif ($action -eq 'CANCEL') {
        $exception = [System.Threading.Tasks.TaskCanceledException]::new('mock cancellation without timeout')
    } else {
        $exception = [System.IO.IOException]::new('mock unknown failure')
    }
    $script:Thrown.Add($exception)
    throw $exception
}
function Start-Sleep {
    [CmdletBinding()] param([int]$Seconds)
    $script:Sleeps.Add($Seconds)
    if ($script:FailSleep) { throw [System.InvalidOperationException]::new('mock sleep F') }
}
function Remove-Item {
    [CmdletBinding()] param([string]$LiteralPath)
    $resolved = [System.IO.Path]::GetFullPath($LiteralPath)
    Check ($resolved.StartsWith($script:MockRootFull + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase)) 'delete outside owned MockRoot'
    Check ([System.IO.Path]::GetFileName($resolved) -in @('jdk.zip','bsl-language-server.jar')) 'unknown delete target'
    $script:Deletes.Add($resolved)
    if ($script:FailDelete) { throw [System.InvalidOperationException]::new('mock delete F') }
    Microsoft.PowerShell.Management\Remove-Item -LiteralPath $resolved -ErrorAction Stop
}
function Begin-Case([string[]]$Plan, [bool]$TwoAssets = $false, [bool]$FailDelete = $false, [bool]$FailSleep = $false) {
    $script:Cases++
    $script:CaseDir = Join-Path $script:MockRootFull ('case-' + $script:Cases)
    $null = [System.IO.Directory]::CreateDirectory($script:CaseDir)
    $script:Plan = $Plan; $script:TwoAssets = $TwoAssets
    $script:FailDelete = $FailDelete; $script:FailSleep = $FailSleep
    $script:Requests = [System.Collections.Generic.List[object]]::new()
    $script:Sleeps = [System.Collections.Generic.List[int]]::new()
    $script:Deletes = [System.Collections.Generic.List[string]]::new()
    $script:Thrown = [System.Collections.Generic.List[object]]::new()
    $script:Failure = $null; $script:AfterPins = $false
    $script:Receipt = [ordered]@{schema=1; java_warmup=$false; downloaded=$false; hashes_verified=$false; error=$null}
    # Independent caller boundary: real size/SHA over known tiny fixture bytes.
    # These test-only pins do not claim to be the production Java/JAR assets.
    try {
        $archive = Join-Path $script:CaseDir 'jdk.zip'
        $jar = Join-Path $script:CaseDir 'bsl-language-server.jar'
        Invoke-PinnedRuntimeDownload -Uri $script:JavaUri -OutFile $archive -Asset java -Receipt $script:Receipt
        if ($TwoAssets) {
            Invoke-PinnedRuntimeDownload -Uri $script:BslUri -OutFile $jar -Asset bsl -Receipt $script:Receipt
        }
        $script:Receipt.downloaded = $true
        if ((Get-Item -LiteralPath $archive).Length -ne 3 -or
            (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $script:GoodSha) {
            throw 'Pinned Java archive differs'
        }
        if ($TwoAssets -and ((Get-Item -LiteralPath $jar).Length -ne 3 -or
            (Get-FileHash -LiteralPath $jar -Algorithm SHA256).Hash.ToLowerInvariant() -ne $script:GoodSha)) {
            throw 'Pinned BSL JAR differs'
        }
        $script:Receipt.hashes_verified = $true
        $script:AfterPins = $true
    } catch {
        $script:Failure = $_
        $script:Receipt.error = $_.Exception.Message
    }
}
function Check-Primary {
    Check ($null -ne $script:Failure -and $script:Thrown.Count -gt 0) 'expected request P'
    $wanted = $script:Thrown[$script:Thrown.Count - 1]
    $exception = $script:Failure.Exception; $found = $false
    for ($depth = 0; $null -ne $exception -and $depth -lt 16; $depth++) {
        if ([object]::ReferenceEquals($wanted, $exception)) { $found = $true; break }
        $exception = $exception.InnerException
    }
    Check $found 'request P replaced by retry preparation F'
    Check (-not $script:Receipt.downloaded -and -not $script:Receipt.hashes_verified -and -not $script:AfterPins) 'failed acquisition crossed caller gate'
}
foreach ($status in @(408,429,500,502,503,504)) {
    Begin-Case -Plan @(('HTTP' + $status), 'ABC')
    Check ($null -eq $script:Failure -and $script:AfterPins) "HTTP$status recovered"
    Check ($script:Requests.Count -eq 2 -and $script:Sleeps.Count -eq 1 -and $script:Sleeps[0] -eq 2) 'single retry bound'
    Check ($script:Receipt.download_attempts.Count -eq 2 -and $script:Receipt.download_attempts[0].status -eq $status) 'structured status recorded'
}
Begin-Case -Plan @('RESPONSE502','ABC')
Check ($null -eq $script:Failure -and $script:AfterPins -and $script:Requests.Count -eq 2 -and $script:Receipt.download_attempts[0].status -eq 502) 'IWR Response.StatusCode adapter'
Begin-Case -Plan @('TIMEOUT','ABC')
Check ($null -eq $script:Failure -and $script:AfterPins -and $script:Receipt.download_attempts[0].timeout) 'network timeout retry'
Begin-Case -Plan @('HTTP502','HTTP503','ABC')
Check ($null -eq $script:Failure -and $script:AfterPins -and $script:Requests.Count -eq 3) 'third attempt success'
Check (($script:Sleeps -join ',') -eq '2,5') 'exact bounded backoff'
Begin-Case -Plan @('HTTP502','HTTP502','HTTP502')
Check-Primary
Check ($script:Requests.Count -eq 3 -and ($script:Sleeps -join ',') -eq '2,5') 'exhaustion cap'
Check ($script:Receipt.download_attempts.Count -eq 3 -and -not $script:Receipt.download_attempts[2].retry) 'final attempt not retried'
foreach ($action in @('HTTP403','HTTP404','HTTP501','UNKNOWN','CANCEL')) {
    Begin-Case -Plan @($action)
    Check-Primary
    Check ($script:Requests.Count -eq 1 -and $script:Sleeps.Count -eq 0 -and $script:Deletes.Count -eq 0) "$action must not retry"
}
foreach ($action in @('ABD','AB','HTML')) {
    Begin-Case -Plan @($action)
    Check ($null -ne $script:Failure -and $script:Failure.Exception.Message -eq 'Pinned Java archive differs') 'pin failure retained'
    Check ($script:Requests.Count -eq 1 -and $script:Sleeps.Count -eq 0 -and $script:Deletes.Count -eq 0) 'successful corrupt response not retried'
    Check ($script:Receipt.downloaded -and -not $script:Receipt.hashes_verified -and -not $script:AfterPins) 'no pin bypass'
}
Begin-Case -Plan @('ABC','HTTP503','ABC') -TwoAssets $true
Check ($null -eq $script:Failure -and $script:AfterPins) 'two assets complete'
Check (@($script:Requests | Where-Object {$_.uri -eq $script:JavaUri}).Count -eq 1) 'completed Java not redownloaded'
Check (@($script:Requests | Where-Object {$_.uri -eq $script:BslUri}).Count -eq 2) 'JAR only retry'
Check ($script:Receipt.download_attempts.Count -eq 3) 'shared bounded ledger'
Begin-Case -Plan @('HTTP502') -FailDelete $true
Check-Primary
Check ($script:Requests.Count -eq 1 -and $script:Sleeps.Count -eq 0 -and $null -ne $script:Receipt.download_attempts[0].retry_preparation_error) 'delete F retains P and stops'
Begin-Case -Plan @('HTTP502') -FailSleep $true
Check-Primary
Check ($script:Requests.Count -eq 1 -and $script:Sleeps.Count -eq 1 -and $null -ne $script:Receipt.download_attempts[0].retry_preparation_error) 'sleep F retains P and stops'
[pscustomobject]@{
    scope='local-mock-only'; cases=$script:Cases; assertions=$script:Assertions
    actual_network=$false; actual_sleep=$false; production_assets_verified=$false
    original_Main56_reclassified=$false; helper_sha256='1d7f911f1176d1041cb5a8c6002da530dd1888268cd7833c543b3ad2a932dfe4'
} | ConvertTo-Json -Compress
