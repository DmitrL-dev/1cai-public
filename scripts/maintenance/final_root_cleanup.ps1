# Final Root Cleanup Script
# Removes all .md files from root EXCEPT README.md, CHANGELOG.md, CONTRIBUTING.md

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Final Root Cleanup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Files to KEEP in root
$KeepFiles = @(
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md"
)

# Get all .md files in root
$AllMdFiles = Get-ChildItem -Path . -Filter "*.md" -File

Write-Host "`nTotal .md files in root: $($AllMdFiles.Count)" -ForegroundColor Yellow
Write-Host "Files to keep: $($KeepFiles.Count)" -ForegroundColor Green
Write-Host "Files to delete: $($AllMdFiles.Count - $KeepFiles.Count)" -ForegroundColor Red

Write-Host "`nStarting cleanup..." -ForegroundColor Cyan

$DeletedCount = 0
$KeptCount = 0

foreach ($File in $AllMdFiles) {
    if ($KeepFiles -contains $File.Name) {
        Write-Host "[KEEP] $($File.Name)" -ForegroundColor Green
        $KeptCount++
    } else {
        try {
            Remove-Item $File.FullName -Force
            Write-Host "[DELETE] $($File.Name)" -ForegroundColor Gray
            $DeletedCount++
        } catch {
            Write-Host "[ERROR] Failed to delete $($File.Name)" -ForegroundColor Red
        }
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Cleanup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Kept: $KeptCount files" -ForegroundColor Green
Write-Host "Deleted: $DeletedCount files" -ForegroundColor Gray
Write-Host "`nRoot now contains only essential files!" -ForegroundColor Green


