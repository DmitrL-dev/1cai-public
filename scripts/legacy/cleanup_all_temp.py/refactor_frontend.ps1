# Create target directory
New-Item -ItemType Directory -Force -Path "frontend-portal/src/services"

# Move TypeScript files
Get-ChildItem -Path "src/services" -Filter "*.ts" | ForEach-Object {
    Move-Item -Path $_.FullName -Destination "frontend-portal/src/services" -Force
    Write-Host "Moved $($_.Name)"
}

Write-Host "Frontend refactoring complete."
