param(
    [Parameter(Mandatory = $true)][string]$Login,
    [Parameter(Mandatory = $true)][string]$Password,
    [string]$BaseUrl = 'http://localhost:5678',
    [string]$OutputFile = './n8n_cookies.txt'
)

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$body = @{ emailOrLdapLoginId = $Login; password = $Password } | ConvertTo-Json
$response = Invoke-RestMethod -Uri "$BaseUrl/rest/login" -Method Post -Body $body -ContentType 'application/json' -WebSession $session
$session.Cookies.GetCookies($BaseUrl) |
    ForEach-Object { $_.Name + '=' + $_.Value } |
    Set-Content -Encoding ascii $OutputFile
$response | ConvertTo-Json
