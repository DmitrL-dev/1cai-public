# Archive and cleanup 1c_configurations
# Saves ~12-14 GB of disk space

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "1C Configurations Archive & Cleanup Script" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Paths
$sourcePath = ".\1c_configurations"
$archivePath = ".\1c_configurations_backup.zip"

# Check if source exists
if (-Not (Test-Path $sourcePath)) {
    Write-Host "[ERROR] Source path not found: $sourcePath" -ForegroundColor Red
    exit 1
}

# Get size before
$sizeBefore = (Get-ChildItem -Path $sourcePath -Recurse -File | Measure-Object -Property Length -Sum).Sum
$sizeBeforeMB = [math]::Round($sizeBefore / 1MB, 2)
$sizeBeforeGB = [math]::Round($sizeBefore / 1GB, 2)

Write-Host "[INFO] Source folder: $sourcePath" -ForegroundColor Green
Write-Host "[INFO] Size: $sizeBeforeGB GB ($sizeBeforeMB MB)" -ForegroundColor Green
Write-Host ""

# Confirm
Write-Host "This will:" -ForegroundColor Yellow
Write-Host "  1. Create archive: $archivePath" -ForegroundColor Yellow
Write-Host "  2. DELETE original folder: $sourcePath" -ForegroundColor Yellow
Write-Host ""
$confirmation = Read-Host "Continue? (yes/no)"

if ($confirmation -ne 'yes') {
    Write-Host "[CANCELLED] No changes made." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "[STEP 1/3] Creating archive..." -ForegroundColor Cyan

try {
    # Create archive
    Compress-Archive -Path $sourcePath -DestinationPath $archivePath -Force
    Write-Host "[OK] Archive created: $archivePath" -ForegroundColor Green
    
    # Check archive size
    $archiveSize = (Get-Item $archivePath).Length
    $archiveSizeMB = [math]::Round($archiveSize / 1MB, 2)
    $archiveSizeGB = [math]::Round($archiveSize / 1GB, 2)
    $compressionRatio = [math]::Round(($archiveSize / $sizeBefore) * 100, 1)
    
    Write-Host "[INFO] Archive size: $archiveSizeGB GB ($archiveSizeMB MB)" -ForegroundColor Green
    Write-Host "[INFO] Compression: $compressionRatio%" -ForegroundColor Green
    
} catch {
    Write-Host "[ERROR] Failed to create archive: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[STEP 2/3] Testing archive..." -ForegroundColor Cyan

try {
    # Test archive integrity
    $testResult = Test-Path $archivePath
    if ($testResult) {
        Write-Host "[OK] Archive is valid" -ForegroundColor Green
    } else {
        throw "Archive test failed"
    }
} catch {
    Write-Host "[ERROR] Archive validation failed: $_" -ForegroundColor Red
    Write-Host "[WARNING] NOT deleting original folder!" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "[STEP 3/3] Removing original folder..." -ForegroundColor Cyan

try {
    # Delete original folder
    Remove-Item -Path $sourcePath -Recurse -Force
    Write-Host "[OK] Original folder deleted" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to delete folder: $_" -ForegroundColor Red
    Write-Host "[WARNING] Archive is safe at: $archivePath" -ForegroundColor Yellow
    exit 1
}

# Calculate space saved
$spaceSaved = $sizeBefore - $archiveSize
$spaceSavedMB = [math]::Round($spaceSaved / 1MB, 2)
$spaceSavedGB = [math]::Round($spaceSaved / 1GB, 2)

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "SUMMARY" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Original size:  $sizeBeforeGB GB" -ForegroundColor White
Write-Host "Archive size:   $archiveSizeGB GB" -ForegroundColor White
Write-Host "Space saved:    $spaceSavedGB GB" -ForegroundColor Green
Write-Host "Compression:    $compressionRatio%" -ForegroundColor Green
Write-Host ""
Write-Host "[SUCCESS] Cleanup completed!" -ForegroundColor Green
Write-Host "Archive location: $archivePath" -ForegroundColor Cyan
Write-Host ""
Write-Host "To restore:" -ForegroundColor Yellow
Write-Host "  Expand-Archive -Path '$archivePath' -DestinationPath '.'" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan


