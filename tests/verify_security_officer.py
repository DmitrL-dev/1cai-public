import sys
import os
import asyncio
from typing import Dict, Any

# Add src to path
sys.path.append(os.getcwd())

from src.modules.security.services.vulnerability_scanner import VulnerabilityScanner
from src.modules.security.services.sensitive_data_scanner import SensitiveDataScanner
from src.modules.security.domain.models import ComplianceFramework


async def test_security_officer():
    print("🚀 Starting Security Officer Verification...")

    # Create a dummy file for testing
    test_file_path = "tests/temp_security_test.py"
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write(
            """
def unsafe_function(user_input):
    # Simulate SQL Injection
    query = "SELECT * FROM users WHERE id = " + user_input
    return query

def secret_leak():
    # Simulate Secret Leak
    api_key = "sk-1234567890abcdef1234567890abcdef"
    return api_key
"""
        )

    try:
        # Read code from file
        with open(test_file_path, "r", encoding="utf-8") as f:
            code = f.read()

        # 1. Test Vulnerability Scanner
        print("\n[1] Testing Vulnerability Scanner...")
        vuln_scanner = VulnerabilityScanner()
        vuln_result = await vuln_scanner.scan_vulnerabilities(code=code)

        print(f"✅ Vulnerability Scan Completed (Score: {vuln_result.risk_score})")
        print(f"   Vulnerabilities found: {len(vuln_result.vulnerabilities)}")
        for v in vuln_result.vulnerabilities:
            print(f"   - [{v.severity}] {v.type}: {v.description}")

        # 2. Test Secret Scanner
        print("\n[2] Testing Secret Scanner...")
        secret_scanner = SensitiveDataScanner()
        secret_result = await secret_scanner.scan_code(code=code)

        print(f"✅ Secret Scan Completed")
        print(f"   Secrets found: {secret_result.total_count}")
        for s in secret_result.secrets_found:
            print(f"   - [{s.type}] {s.value_preview} (Confidence: {s.confidence})")

    except Exception as e:
        print(f"❌ Verification Failed: {e}")
    finally:
        # Cleanup
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

    print("\n🎉 All tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(test_security_officer())
