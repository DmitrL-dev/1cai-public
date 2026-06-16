<#
  security-audit.ps1 - Полный security-аудит для Windows окружения.

  Повторяет make security-audit:
    - python scripts/audit/check_hidden_dirs.py --fail-new
    - python scripts/audit/check_secrets.py --json > analysis/secret_scan_report.json
    - python scripts/audit/check_git_safety.py
    - python scripts/audit/comprehensive_project_audit.py

  Запуск:
    pwsh scripts/windows/security-audit.ps1
#>

param(
    [string]$PythonExe = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "=== Security audit (hidden dirs, secrets, git safety, comprehensive) ===" -ForegroundColor Cyan

Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    # Проверка скрытых директорий
    Write-Host "`n[1/4] check_hidden_dirs.py --fail-new" -ForegroundColor Yellow
    & $PythonExe "scripts/audit/check_hidden_dirs.py" "--fail-new"

    # Поиск возможных секретов
    Write-Host "`n[2/4] check_secrets.py --json > analysis/secret_scan_report.json" -ForegroundColor Yellow
    if (-not (Test-Path "analysis")) {
        New-Item -ItemType Directory -Path "analysis" | Out-Null
    }
    & $PythonExe "scripts/audit/check_secrets.py" "--json" | Set-Content -Path "analysis/secret_scan_report.json" -Encoding UTF8

    # Проверка git safety
    Write-Host "`n[3/4] check_git_safety.py" -ForegroundColor Yellow
    & $PythonExe "scripts/audit/check_git_safety.py"

    # Полный аудит
    Write-Host "`n[4/4] comprehensive_project_audit.py" -ForegroundColor Yellow
    & $PythonExe "scripts/audit/comprehensive_project_audit.py"

    Write-Host "`nSecurity audit completed successfully." -ForegroundColor Green
    Write-Host " - Secret report: analysis/secret_scan_report.json"
    Write-Host " - Comprehensive audit: output/audit/comprehensive_audit.json"
}
finally {
    Pop-Location
}


