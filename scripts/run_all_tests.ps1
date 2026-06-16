# PowerShell version of run_all_tests.sh
# Run All Tests - Comprehensive Testing Suite

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Enterprise 1C AI Stack - Full Test Suite" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$PASSED = 0
$FAILED = 0

Write-Host "Installing test dependencies..." -ForegroundColor Yellow
pip install -q pytest pytest-asyncio pytest-cov pytest-mock radon vulture coverage psutil
Write-Host ""

Write-Host "Starting Test Suite..." -ForegroundColor Cyan
Write-Host ""

# 1. Unit Tests
Write-Host "[1/9] Running Unit Tests..." -ForegroundColor Yellow
if (pytest tests/unit/ -v --cov=src --cov-report=term-missing) {
    Write-Host " Unit tests passed" -ForegroundColor Green
    $PASSED++
} else {
    Write-Host " Unit tests failed" -ForegroundColor Red
    $FAILED++
}
Write-Host ""

# 2. Integration Tests
Write-Host "[2/9] Running Integration Tests..." -ForegroundColor Yellow
if (pytest tests/integration/ -v) {
    Write-Host " Integration tests passed" -ForegroundColor Green
    $PASSED++
} else {
    Write-Host " Integration tests failed" -ForegroundColor Red
    $FAILED++
}
Write-Host ""

# 3. System Tests
Write-Host "[3/9] Running System Tests..." -ForegroundColor Yellow
if (pytest tests/system/ -v) {
    Write-Host " System tests passed" -ForegroundColor Green
    $PASSED++
} else {
    Write-Host " System tests failed" -ForegroundColor Red
    $FAILED++
}
Write-Host ""

# 4. Performance Tests
Write-Host "[4/9] Running Performance Tests..." -ForegroundColor Yellow
if (pytest tests/performance/ -v -s) {
    Write-Host " Performance tests passed" -ForegroundColor Green
    $PASSED++
} else {
    Write-Host " Performance tests failed" -ForegroundColor Red
    $FAILED++
}
Write-Host ""

# 5. Security Tests
Write-Host "[5/9] Running Security Tests..." -ForegroundColor Yellow
if (pytest tests/security/ -v) {
    Write-Host " Security tests passed" -ForegroundColor Green
    $PASSED++
} else {
    Write-Host " Security tests failed" -ForegroundColor Red
    $FAILED++
}
Write-Host ""

# 6. Acceptance Tests
Write-Host "[6/9] Running Acceptance Tests..." -ForegroundColor Yellow
if (pytest tests/acceptance/ -v) {
    Write-Host " Acceptance tests passed" -ForegroundColor Green
    $PASSED++
} else {
    Write-Host " Acceptance tests failed" -ForegroundColor Red
    $FAILED++
}
Write-Host ""

# 7. White-box Tests
Write-Host "[7/9] Running White-box Tests..." -ForegroundColor Yellow
if (pytest tests/whitebox/ -v -s) {
    Write-Host " White-box tests passed" -ForegroundColor Green
    $PASSED++
} else {
    Write-Host " White-box tests failed" -ForegroundColor Red
    $FAILED++
}
Write-Host ""

# 8. Coverage Report
Write-Host "[8/9] Generating Coverage Report..." -ForegroundColor Yellow
pytest tests/unit/ tests/integration/ --cov=src --cov-report=html --cov-report=term-missing
Write-Host " Coverage report: htmlcov/index.html" -ForegroundColor Green
Write-Host ""

# 9. Load Tests
Write-Host "[9/9] Running Load Tests (K6)..." -ForegroundColor Yellow
if (Get-Command k6 -ErrorAction SilentlyContinue) {
    k6 run tests/load/k6_load_test.js
    Write-Host " Load tests completed" -ForegroundColor Green
    $PASSED++
} else {
    Write-Host " K6 not installed - skipping" -ForegroundColor Yellow
}
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Total suites: $($PASSED + $FAILED)"
Write-Host "Passed: $PASSED" -ForegroundColor Green
Write-Host "Failed: $FAILED" -ForegroundColor Red
Write-Host ""

if ($FAILED -eq 0) {
    Write-Host " ALL TESTS PASSED!" -ForegroundColor Green
    exit 0
} else {
    Write-Host " SOME TESTS FAILED" -ForegroundColor Red
    exit 1
}


