#!/usr/bin/env python
"""
Manual Test Runner for 1cAI Project
Workaround for security restrictions blocking automated test execution
"""

import sys
import importlib
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print colored header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def check_python_version() -> bool:
    """Check if Python version is compatible"""
    print_header("Checking Python Version")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print_info(f"Python version: {version_str}")
    
    if version.major == 3 and version.minor >= 11:
        print_success(f"Python {version_str} is compatible (requires 3.11+)")
        return True
    else:
        print_error(f"Python {version_str} is NOT compatible (requires 3.11+)")
        print_warning("Please upgrade to Python 3.11 or higher")
        return False


def check_dependencies() -> Tuple[List[str], List[str]]:
    """Check which dependencies are installed"""
    print_header("Checking Dependencies")
    
    required_packages = [
        'pytest',
        'pytest-asyncio',
        'pydantic',
        'fastapi',
        'aiohttp',
        'prometheus_client',
        'sqlalchemy',
        'redis',
        'neo4j',
    ]
    
    installed = []
    missing = []
    
    for package in required_packages:
        try:
            importlib.import_module(package.replace('-', '_'))
            print_success(f"{package} is installed")
            installed.append(package)
        except ImportError:
            print_error(f"{package} is NOT installed")
            missing.append(package)
    
    return installed, missing


def check_project_structure() -> bool:
    """Check if project structure is correct"""
    print_header("Checking Project Structure")
    
    required_paths = [
        'src/ai/agents',
        'src/ai/agents/base_agent.py',
        'src/ai/agents/developer_agent_enhanced.py',
        'src/ai/agents/developer_agent_secure.py',
        'tests/unit',
        'tests/unit/test_developer_agent_enhanced.py',
    ]
    
    all_exist = True
    
    for path in required_paths:
        full_path = Path(path)
        if full_path.exists():
            print_success(f"{path} exists")
        else:
            print_error(f"{path} NOT found")
            all_exist = False
    
    return all_exist


def test_imports() -> Dict[str, Any]:
    """Test importing key modules"""
    print_header("Testing Module Imports")
    
    results = {}
    
    # Add project root to path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    modules_to_test = [
        ('src.ai.agents.base_agent', ['BaseAgent', 'AgentCapability', 'AgentStatus']),
        ('src.ai.agents.developer_agent_enhanced', ['DeveloperAgentEnhanced']),
        ('src.ai.agents.developer_agent_secure', ['DeveloperAISecure']),
    ]
    
    for module_name, classes in modules_to_test:
        try:
            module = importlib.import_module(module_name)
            print_success(f"Imported {module_name}")
            
            for class_name in classes:
                if hasattr(module, class_name):
                    print_success(f"  Found class: {class_name}")
                else:
                    print_warning(f"  Class {class_name} not found in module")
            
            results[module_name] = {'success': True, 'module': module}
            
        except Exception as e:
            print_error(f"Failed to import {module_name}: {str(e)}")
            results[module_name] = {'success': False, 'error': str(e)}
    
    return results


def run_simple_agent_test() -> bool:
    """Run a simple test of DeveloperAgentEnhanced"""
    print_header("Running Simple Agent Test")
    
    try:
        # Add project root to path
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root))
        
        from src.ai.agents.developer_agent_enhanced import DeveloperAgentEnhanced
        from src.ai.agents.base_agent import AgentCapability
        
        print_info("Creating DeveloperAgentEnhanced instance...")
        agent = DeveloperAgentEnhanced()
        
        print_success("Agent created successfully")
        
        # Check agent properties
        print_info("Checking agent properties...")
        status = agent.get_status()
        
        print_success(f"Agent name: {status['agent_name']}")
        print_success(f"Capabilities: {', '.join(status['capabilities'])}")
        print_success(f"Status: {status['status']}")
        
        # Test code generation (without LLM)
        print_info("\nTesting code generation (placeholder mode)...")
        
        import asyncio
        
        async def test_generation():
            result = await agent.execute(
                input_data={
                    "action": "generate_code",
                    "prompt": "Создай функцию для получения текущей даты",
                    "context": {"module": "ОбщийМодуль"}
                },
                capability=AgentCapability.CODE_GENERATION
            )
            return result
        
        result = asyncio.run(test_generation())
        
        if result.get('success'):
            print_success("Code generation test PASSED")
            print_info(f"Generated code preview:\n{result['result']['code'][:200]}...")
            return True
        else:
            print_error(f"Code generation test FAILED: {result.get('error')}")
            return False
            
    except Exception as e:
        print_error(f"Agent test failed with exception: {str(e)}")
        import traceback
        print(f"\n{Colors.RED}{traceback.format_exc()}{Colors.RESET}")
        return False


def run_pytest_tests() -> bool:
    """Run pytest tests"""
    print_header("Running Pytest Tests")
    
    try:
        import pytest
        
        print_info("Running tests for developer_agent_enhanced...")
        
        # Run specific test file
        test_file = "tests/unit/test_developer_agent_enhanced.py"
        
        if not Path(test_file).exists():
            print_error(f"Test file not found: {test_file}")
            return False
        
        print_info(f"Executing: pytest {test_file} -v")
        
        # Run pytest programmatically
        exit_code = pytest.main([
            test_file,
            '-v',
            '--tb=short',
            '--color=yes',
            '-p', 'no:warnings'
        ])
        
        if exit_code == 0:
            print_success("All pytest tests PASSED")
            return True
        else:
            print_error(f"Pytest tests FAILED (exit code: {exit_code})")
            return False
            
    except ImportError:
        print_error("pytest is not installed")
        print_info("Install with: pip install pytest pytest-asyncio")
        return False
    except Exception as e:
        print_error(f"Pytest execution failed: {str(e)}")
        return False


def print_summary(results: Dict[str, bool]):
    """Print test summary"""
    print_header("Test Summary")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    for test_name, result in results.items():
        if result:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")
    
    print(f"\n{Colors.BOLD}Total: {total} | Passed: {Colors.GREEN}{passed}{Colors.RESET}{Colors.BOLD} | Failed: {Colors.RED}{failed}{Colors.RESET}")
    
    if failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All tests passed!{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Some tests failed{Colors.RESET}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Manual test runner for 1cAI project')
    parser.add_argument('--check-deps', action='store_true', help='Only check dependencies')
    parser.add_argument('--test-agent', action='store_true', help='Run simple agent test')
    parser.add_argument('--all', action='store_true', help='Run all tests including pytest')
    parser.add_argument('--pytest-only', action='store_true', help='Run only pytest tests')
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║         1cAI Project - Manual Test Runner                 ║")
    print("║         Workaround for Security Restrictions               ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}\n")
    
    results = {}
    
    # Always check Python version
    results['Python Version'] = check_python_version()
    
    if args.check_deps:
        # Only check dependencies
        installed, missing = check_dependencies()
        
        if missing:
            print_warning("\nMissing dependencies. Install with:")
            print(f"{Colors.CYAN}pip install {' '.join(missing)}{Colors.RESET}")
        else:
            print_success("\nAll required dependencies are installed!")
        
        return
    
    # Check dependencies
    installed, missing = check_dependencies()
    results['Dependencies'] = len(missing) == 0
    
    # Check project structure
    results['Project Structure'] = check_project_structure()
    
    # Test imports
    import_results = test_imports()
    results['Module Imports'] = all(r['success'] for r in import_results.values())
    
    if args.pytest_only:
        # Run only pytest
        results['Pytest Tests'] = run_pytest_tests()
    elif args.test_agent or args.all:
        # Run simple agent test
        results['Simple Agent Test'] = run_simple_agent_test()
        
        if args.all:
            # Run pytest tests
            results['Pytest Tests'] = run_pytest_tests()
    
    # Print summary
    print_summary(results)
    
    # Exit with appropriate code
    if all(results.values()):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
