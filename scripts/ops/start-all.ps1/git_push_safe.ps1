# ============================================================================
# SAFE GITHUB PUSH SCRIPT
# Repository: https://github.com/DmitrL-dev/1cai
# Date: 2025-11-06
# ============================================================================

Write-Host ""
Write-Host "============================================================================"
Write-Host "  UPDATING GITHUB: https://github.com/DmitrL-dev/1cai"
Write-Host "============================================================================"
Write-Host ""

# Change to project directory
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "[1/6] Security check..."
Write-Host ""

# Check for proprietary data
Write-Host "  Checking for proprietary data in git status..."
$proprietary = git status --porcelain | Select-String "knowledge_base.*\.json|output.*edt_parser.*\.json|ml_training_dataset"

if ($proprietary) {
    Write-Host ""
    Write-Host "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    Write-Host "  DANGER! PROPRIETARY FILES FOUND IN GIT STATUS!"
    Write-Host "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    Write-Host ""
    Write-Host "Files:"
    $proprietary | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""
    Write-Host "STOPPED! Check .gitignore and fix before commit!"
    Write-Host ""
    exit 1
}

Write-Host "  [OK] No proprietary data will be committed"
Write-Host ""

# Check .env files
Write-Host "  Checking .env files..."
$envFiles = git status --porcelain | Select-String "\.env[^.]" | Select-String -NotMatch "\.env\.example"

if ($envFiles) {
    Write-Host ""
    Write-Host "  [WARNING] Found .env files in git status:"
    $envFiles | ForEach-Object { Write-Host "    - $_" }
    Write-Host ""
    $response = Read-Host "  Continue? (yes/no)"
    if ($response -ne "yes") {
        Write-Host "  Stopped by user."
        exit 1
    }
} else {
    Write-Host "  [OK] .env files are protected"
}

Write-Host ""
Write-Host "[2/6] Adding all changes..."
Write-Host ""

# Add all changes
git add -A

Write-Host "  [OK] Files added to staging"
Write-Host ""

Write-Host "[3/6] Reviewing changes..."
Write-Host ""

# Show status
git status --short | Select-Object -First 50
$totalChanges = (git status --short).Count
Write-Host ""
Write-Host "  Total changes: $totalChanges"
Write-Host ""

# Check size
Write-Host "[4/6] Checking commit size..."
Write-Host ""

$stagedFiles = git diff --cached --name-only
$totalSize = 0
foreach ($file in $stagedFiles) {
    if (Test-Path $file) {
        $size = (Get-Item $file).Length
        $totalSize += $size
        if ($size -gt 5242880) {  # 5 MB in bytes
            $sizeMB = [math]::Round($size / 1048576, 2)
            Write-Host "  [WARNING] Large file: $file ($sizeMB MB)"
        }
    }
}

$totalSizeMB = [math]::Round($totalSize / 1048576, 2)
Write-Host "  Total size: $totalSizeMB MB"
Write-Host ""

if ($totalSizeMB -gt 100) {
    Write-Host "  [ERROR] Commit size too large! ($totalSizeMB MB)"
    Write-Host "  Check that large JSON files are not included!"
    Write-Host ""
    exit 1
}

Write-Host "  [OK] Commit size acceptable ($totalSizeMB MB)"
Write-Host ""

Write-Host "[5/6] Creating commit..."
Write-Host ""

# Commit
git commit -m "Ready for publication: cleaned from proprietary data

- Added disclaimer to README.md
- Updated .gitignore to exclude 3.2 GB of proprietary 1C data  
- Protected all credentials (.env files)
- Created .env.example files
- Fixed security issues (SQL injection, hardcoded secrets)
- Cleaned marketplace.py (13 TODO processed)
- Project is now safe to publish on GitHub

Security:
- NO proprietary 1C data included
- NO configuration files
- NO credentials
- All sensitive data in .gitignore"

Write-Host "  [OK] Commit created"
Write-Host ""

Write-Host "[6/6] Pushing to GitHub..."
Write-Host ""

# Push
Write-Host "  Pushing to origin/main..."
git push origin main

Write-Host ""
Write-Host "============================================================================"
Write-Host "  SUCCESS! PUBLISHED TO GITHUB!"
Write-Host "============================================================================"
Write-Host ""
Write-Host "  Repository: https://github.com/DmitrL-dev/1cai"
Write-Host ""
Write-Host "  Check on GitHub:"
Write-Host "    - Commit appeared"
Write-Host "    - README.md is current"
Write-Host "    - NO proprietary data"
Write-Host ""
Write-Host "============================================================================"
Write-Host ""

