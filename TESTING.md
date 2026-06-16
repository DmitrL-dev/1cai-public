# Testing Guide for 1cAI Project

## Overview

This guide provides instructions for testing Python code in the 1cAI project, with workarounds for security restrictions that may block automated test execution.

## Prerequisites

- Python 3.11+ (recommended: 3.12.7 for better performance)
- All dependencies from `requirements.txt`

## Quick Start

### 1. Check Dependencies

First, verify all required packages are installed:

```powershell
cd c:\1cAI
python run_tests_manual.py --check-deps
```

If any packages are missing, install them:

```powershell
pip install -r requirements.txt
```

### 2. Run Simple Agent Test

Test the `DeveloperAgentEnhanced` without full pytest:

```powershell
python run_tests_manual.py --test-agent
```

This will:
- ✓ Check Python version
- ✓ Verify dependencies
- ✓ Test module imports
- ✓ Create and test DeveloperAgentEnhanced instance
- ✓ Run a simple code generation test

### 3. Run Full Test Suite

Run all tests including pytest:

```powershell
python run_tests_manual.py --all
```

### 4. Run Only Pytest Tests

If you only want to run pytest tests:

```powershell
python run_tests_manual.py --pytest-only
```

## Alternative Testing Methods

### Method 1: Using pytest directly

If the manual runner doesn't work, try pytest directly:

```powershell
# Test specific file
pytest tests/unit/test_developer_agent_enhanced.py -v

# Test all unit tests
pytest tests/unit/ -v

# Test with coverage
pytest tests/unit/ --cov=src --cov-report=html
```

### Method 2: VS Code Test Explorer

1. Open VS Code
2. Install "Python Test Explorer" extension
3. Open Testing panel (beaker icon in sidebar)
4. Click "Configure Python Tests"
5. Select "pytest"
6. Select "tests" directory
7. Run tests from the UI

### Method 3: Interactive Python REPL

For manual testing without pytest:

```powershell
python
```

Then in the Python REPL:

```python
import sys
sys.path.insert(0, 'c:/1cAI')

# Test imports
from src.ai.agents.developer_agent_enhanced import DeveloperAgentEnhanced
from src.ai.agents.base_agent import AgentCapability

# Create agent
agent = DeveloperAgentEnhanced()
print(agent.get_status())

# Test async function
import asyncio

async def test():
    result = await agent.execute(
        input_data={
            "action": "generate_code",
            "prompt": "Создай функцию для получения текущей даты"
        },
        capability=AgentCapability.CODE_GENERATION
    )
    return result

result = asyncio.run(test())
print(result)
```

### Method 4: Jupyter Notebook

Create a notebook for interactive testing:

```powershell
# Install jupyter if not installed
pip install jupyter

# Start jupyter
jupyter notebook
```

Then create a new notebook and test interactively.

## Common Issues and Solutions

### Issue 1: "Module not found" errors

**Solution:** Ensure you're in the project root directory:

```powershell
cd c:\1cAI
python run_tests_manual.py --test-agent
```

### Issue 2: Import errors for dependencies

**Solution:** Install missing dependencies:

```powershell
pip install -r requirements.txt
```

### Issue 3: Security restrictions blocking execution

**Solution:** Try these approaches in order:

1. Run PowerShell as Administrator
2. Temporarily disable antivirus (if safe to do so)
3. Use VS Code Test Explorer instead
4. Use interactive Python REPL (Method 3 above)

### Issue 4: Async test failures

**Solution:** Ensure `pytest-asyncio` is installed:

```powershell
pip install pytest-asyncio
```

### Issue 5: LLM-related import errors

**Note:** Some tests may fail if LLM components are not fully configured. This is expected behavior. The tests should still pass with placeholder/mock implementations.

## Test Structure

### Unit Tests

Located in `tests/unit/`:
- `test_developer_agent_enhanced.py` - Tests for enhanced developer agent
- `test_developer_agent_secure.py` - Tests for secure developer agent
- 92+ other unit test files

### Integration Tests

Located in `tests/integration/`:
- End-to-end workflow tests
- Component integration tests

### System Tests

Located in `tests/system/`:
- Full system tests
- Performance tests

## Running Specific Test Categories

```powershell
# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v

# Run tests with specific marker
pytest -m "unit" -v

# Run tests matching pattern
pytest -k "developer_agent" -v
```

## Coverage Reports

Generate coverage report:

```powershell
pytest tests/unit/ --cov=src --cov-report=html --cov-report=term-missing
```

View HTML report:

```powershell
start htmlcov/index.html
```

## Continuous Testing

For development, use pytest-watch:

```powershell
pip install pytest-watch
ptw tests/unit/ -- -v
```

## Troubleshooting

If all else fails:

1. **Check Python version:**
   ```powershell
   python --version
   ```
   Should be 3.11 or higher.

2. **Verify project structure:**
   ```powershell
   python run_tests_manual.py --check-deps
   ```

3. **Check for conflicting packages:**
   ```powershell
   pip list
   ```

4. **Reinstall dependencies:**
   ```powershell
   pip install -r requirements.txt --force-reinstall
   ```

5. **Create fresh virtual environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

## Getting Help

If you encounter issues not covered here:

1. Check the error message carefully
2. Look for similar issues in project documentation
3. Try the alternative testing methods above
4. Check if security software is blocking execution

## Next Steps

After successful testing:

1. Review test coverage report
2. Add new tests for uncovered code
3. Run integration tests
4. Run performance tests if needed
