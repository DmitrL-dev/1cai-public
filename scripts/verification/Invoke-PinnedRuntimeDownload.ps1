# Retry structured transient download failures within a fixed attempt budget.
# The caller verifies exact size and SHA256 before extraction.
function Invoke-PinnedRuntimeDownload {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][uri]$Uri,
        [Parameter(Mandatory)][string]$OutFile,
        [Parameter(Mandatory)][ValidateSet('java', 'bsl')][string]$Asset,
        [Parameter(Mandatory)][System.Collections.IDictionary]$Receipt
    )
    if (-not [System.IO.Path]::IsPathRooted($OutFile)) {
        throw 'Runtime download destination must be absolute'
    }
    if ($null -eq $Receipt['download_attempts']) {
        $Receipt['download_attempts'] = [System.Collections.Generic.List[object]]::new()
    }
    $attempts = $Receipt['download_attempts']
    if ($attempts -isnot [System.Collections.Generic.List[object]]) {
        throw 'Invalid runtime download attempt ledger'
    }
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        if ($attempts.Count -ge 6) { throw 'Runtime download attempt ledger is full' }
        $record = [ordered]@{
            asset = $Asset; attempt = $attempt; status = $null
            exception_type = $null; timeout = $false; succeeded = $false
            retry = $false; delay_seconds = 0; retry_preparation_error = $null
        }
        $attempts.Add($record)
        try {
            # Disable implicit IWR retries; this wrapper owns the entire cap.
            $null = Invoke-WebRequest -Uri $Uri -OutFile $OutFile -TimeoutSec 120 -MaximumRetryCount 0 -ErrorAction Stop
            $record.succeeded = $true
            return
        } catch {
            $requestError = $_
            $record.exception_type = $requestError.Exception.GetType().FullName
            $status = $null; $timeout = $false; $classificationFailed = $false
            try {
                $exception = $requestError.Exception
                for ($depth = 0; $null -ne $exception -and $depth -lt 16; $depth++) {
                    $response = $exception.PSObject.Properties['Response']
                    if ($null -eq $status -and $null -ne $response -and $null -ne $response.Value) {
                        $code = $response.Value.PSObject.Properties['StatusCode']
                        if ($null -ne $code -and $null -ne $code.Value) { $status = [int]$code.Value }
                    }
                    if ($null -eq $status -and $exception -is [System.Net.Http.HttpRequestException] -and $null -ne $exception.StatusCode) {
                        $status = [int]$exception.StatusCode
                    }
                    if ($exception -is [System.TimeoutException] -or
                        ($exception -is [System.Net.WebException] -and $exception.Status -eq [System.Net.WebExceptionStatus]::Timeout)) {
                        $timeout = $true
                    }
                    $exception = $exception.InnerException
                }
            } catch { $classificationFailed = $true }
            $record.status = $status; $record.timeout = $timeout
            $transient = -not $classificationFailed -and $(if ($null -ne $status) {
                $status -in @(408, 429, 500, 502, 503, 504)
            } else { $timeout })
            if (-not $transient -or $attempt -eq 3) {
                $PSCmdlet.ThrowTerminatingError($requestError)
            }
            $record.retry = $true
            $record.delay_seconds = $(if ($attempt -eq 1) { 2 } else { 5 })
            try {
                # The caller passes exactly its known owned asset path.
                # Remove a failed partial file only; never recurse or enumerate.
                if (Test-Path -LiteralPath $OutFile -PathType Leaf) {
                    Remove-Item -LiteralPath $OutFile -ErrorAction Stop
                }
                Start-Sleep -Seconds $record.delay_seconds
            } catch {
                $record.retry = $false
                $record.retry_preparation_error = $_.Exception.GetType().FullName
                $PSCmdlet.ThrowTerminatingError($requestError)
            }
        }
    }
}
