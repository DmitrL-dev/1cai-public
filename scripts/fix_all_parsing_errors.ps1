# Master Script: Fix All Parsing Errors
# This script fixes all 172 parsing/indentation errors in the codebase

Write-Host "=" * 80
Write-Host "MASTER SCRIPT: FIX ALL PARSING ERRORS"
Write-Host "=" * 80
Write-Host ""

$SRC_DIR = "c:\1cAI\src"
$RESULTS_FILE = "c:\1cAI\pylint_results_after_fixes.json"
$LOG_FILE = "c:\1cAI\PARSING_FIXES_LOG.txt"

# Initialize log
"Parsing Errors Fix Log - $(Get-Date)" | Out-File $LOG_FILE
"=" * 80 | Out-File $LOG_FILE -Append
"" | Out-File $LOG_FILE -Append

Write-Host "Step 1: Analyzing parsing errors..."
Write-Host ""

# Read pylint results
$results = Get-Content $RESULTS_FILE -Raw | ConvertFrom-Json

# Find all parsing errors
$parsingErrors = $results | Where-Object { $_.'message-id' -eq 'E0001' }

Write-Host "Found $($parsingErrors.Count) parsing errors"
"Found $($parsingErrors.Count) parsing errors" | Out-File $LOG_FILE -Append
"" | Out-File $LOG_FILE -Append

# Group by file
$fileErrors = @{}
foreach ($error in $parsingErrors) {
    $file = $error.path
    if (-not $fileErrors.ContainsKey($file)) {
        $fileErrors[$file] = @()
    }
    $fileErrors[$file] += $error
}

Write-Host "Affected files: $($fileErrors.Count)"
Write-Host ""

# Fix each file
$fixedCount = 0
$failedCount = 0

Write-Host "Step 2: Fixing files..."
Write-Host ""

foreach ($file in $fileErrors.Keys | Sort-Object) {
    $errorCount = $fileErrors[$file].Count
    $fileName = Split-Path $file -Leaf
    
    Write-Host "Processing: $fileName ($errorCount errors)"
    "Processing: $file ($errorCount errors)" | Out-File $LOG_FILE -Append
    
    # Construct full path
    $fullPath = if ($file.StartsWith("src\") -or $file.StartsWith("src/")) {
        Join-Path $SRC_DIR ($file.Substring(4))
    } else {
        Join-Path $SRC_DIR $file
    }
    
    if (-not (Test-Path $fullPath)) {
        Write-Host "  [SKIP] File not found: $fullPath" -ForegroundColor Yellow
        "  [SKIP] File not found" | Out-File $LOG_FILE -Append
        $failedCount++
        continue
    }
    
    # Try to fix with autopep8
    try {
        $output = autopep8 --in-place --aggressive --aggressive $fullPath 2>&1
        
        # Verify file is now valid Python
        $syntaxCheck = python -c "import py_compile; py_compile.compile('$fullPath', doraise=True)" 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] Fixed successfully" -ForegroundColor Green
            "  [OK] Fixed successfully" | Out-File $LOG_FILE -Append
            $fixedCount++
        } else {
            Write-Host "  [PARTIAL] autopep8 ran but syntax errors remain" -ForegroundColor Yellow
            "  [PARTIAL] Syntax errors remain: $syntaxCheck" | Out-File $LOG_FILE -Append
            
            # Show first error for manual review
            $firstError = $fileErrors[$file][0]
            Write-Host "    Line $($firstError.line): $($firstError.message.Substring(0, [Math]::Min(60, $firstError.message.Length)))" -ForegroundColor Gray
            
            $failedCount++
        }
    }
    catch {
        Write-Host "  [ERROR] Failed to fix: $_" -ForegroundColor Red
        "  [ERROR] $_" | Out-File $LOG_FILE -Append
        $failedCount++
    }
    
    "" | Out-File $LOG_FILE -Append
}

Write-Host ""
Write-Host "=" * 80
Write-Host "SUMMARY"
Write-Host "=" * 80
Write-Host "Total files:     $($fileErrors.Count)"
Write-Host "Fixed:           $fixedCount" -ForegroundColor Green
Write-Host "Failed/Partial:  $failedCount" -ForegroundColor Yellow
Write-Host ""

"" | Out-File $LOG_FILE -Append
"=" * 80 | Out-File $LOG_FILE -Append
"SUMMARY" | Out-File $LOG_FILE -Append
"=" * 80 | Out-File $LOG_FILE -Append
"Total files:     $($fileErrors.Count)" | Out-File $LOG_FILE -Append
"Fixed:           $fixedCount" | Out-File $LOG_FILE -Append
"Failed/Partial:  $failedCount" | Out-File $LOG_FILE -Append

Write-Host "Step 3: Re-running pylint to verify..."
Write-Host ""

# Re-run pylint
pylint src/ --output-format=json 2>$null | Out-File -FilePath "pylint_results_final.json" -Encoding utf8

Write-Host "Step 4: Comparing results..."
Write-Host ""

# Compare results
$finalResults = Get-Content "pylint_results_final.json" -Raw | ConvertFrom-Json
$finalParsingErrors = $finalResults | Where-Object { $_.'message-id' -eq 'E0001' }

$improvement = $parsingErrors.Count - $finalParsingErrors.Count

Write-Host "=" * 80
Write-Host "FINAL RESULTS"
Write-Host "=" * 80
Write-Host "Before:      $($parsingErrors.Count) parsing errors"
Write-Host "After:       $($finalParsingErrors.Count) parsing errors"
Write-Host "Improvement: $improvement errors fixed ($([Math]::Round($improvement / $parsingErrors.Count * 100, 1))%)" -ForegroundColor Green
Write-Host ""
Write-Host "Log saved to: $LOG_FILE"
Write-Host "=" * 80

"" | Out-File $LOG_FILE -Append
"FINAL RESULTS" | Out-File $LOG_FILE -Append
"Before:      $($parsingErrors.Count) parsing errors" | Out-File $LOG_FILE -Append
"After:       $($finalParsingErrors.Count) parsing errors" | Out-File $LOG_FILE -Append
"Improvement: $improvement errors fixed" | Out-File $LOG_FILE -Append
