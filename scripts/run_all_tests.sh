#!/bin/bash
# Run All Tests - Comprehensive Testing Suite

set -e

echo "========================================"
echo "Enterprise 1C AI Stack - Full Test Suite"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

echo "📦 Installing test dependencies..."
pip install -q pytest pytest-asyncio pytest-cov pytest-mock \
    radon vulture coverage psutil

echo ""
echo "🧪 Starting Test Suite..."
echo ""

# 1. Unit Tests
echo -e "${YELLOW}[1/9]${NC} Running Unit Tests..."
if pytest tests/unit/ -v --cov=src --cov-report=term-missing; then
    echo -e "${GREEN}✓ Unit tests passed${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}✗ Unit tests failed${NC}"
    ((FAILED_TESTS++))
fi
echo ""

# 2. Integration Tests
echo -e "${YELLOW}[2/9]${NC} Running Integration Tests..."
if pytest tests/integration/ -v; then
    echo -e "${GREEN}✓ Integration tests passed${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}✗ Integration tests failed${NC}"
    ((FAILED_TESTS++))
fi
echo ""

# 3. System Tests
echo -e "${YELLOW}[3/9]${NC} Running System Tests..."
if pytest tests/system/ -v; then
    echo -e "${GREEN}✓ System tests passed${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}✗ System tests failed${NC}"
    ((FAILED_TESTS++))
fi
echo ""

# 4. Performance Tests
echo -e "${YELLOW}[4/9]${NC} Running Performance Tests..."
if pytest tests/performance/ -v -s; then
    echo -e "${GREEN}✓ Performance tests passed${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}✗ Performance tests failed${NC}"
    ((FAILED_TESTS++))
fi
echo ""

# 5. Security Tests
echo -e "${YELLOW}[5/9]${NC} Running Security Tests..."
if pytest tests/security/ -v; then
    echo -e "${GREEN}✓ Security tests passed${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}✗ Security tests failed${NC}"
    ((FAILED_TESTS++))
fi
echo ""

# 6. Acceptance Tests
echo -e "${YELLOW}[6/9]${NC} Running Acceptance Tests..."
if pytest tests/acceptance/ -v; then
    echo -e "${GREEN}✓ Acceptance tests passed${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}✗ Acceptance tests failed${NC}"
    ((FAILED_TESTS++))
fi
echo ""

# 7. White-box Tests
echo -e "${YELLOW}[7/9]${NC} Running White-box Tests..."
if pytest tests/whitebox/ -v -s; then
    echo -e "${GREEN}✓ White-box tests passed${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}✗ White-box tests failed${NC}"
    ((FAILED_TESTS++))
fi
echo ""

# 8. Code Coverage Report
echo -e "${YELLOW}[8/9]${NC} Generating Coverage Report..."
pytest tests/unit/ tests/integration/ --cov=src --cov-report=html --cov-report=term-missing
echo -e "${GREEN}✓ Coverage report: htmlcov/index.html${NC}"
echo ""

# 9. Load Testing (K6 - if available)
echo -e "${YELLOW}[9/9]${NC} Running Load Tests (K6)..."
if command -v k6 &> /dev/null; then
    k6 run tests/load/k6_load_test.js
    echo -e "${GREEN}✓ Load tests completed${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${YELLOW}⚠ K6 not installed - skipping load tests${NC}"
    echo "Install: https://k6.io/docs/getting-started/installation"
fi
echo ""

# Summary
echo "========================================"
echo "Test Summary"
echo "========================================"
echo ""
echo -e "Total test suites: $((PASSED_TESTS + FAILED_TESTS))"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    exit 1
fi


