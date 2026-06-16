import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.security.services.vulnerability_scanner import VulnerabilityScanner
from src.modules.security.domain.models import VulnerabilityType

async def verify_security_enhancements():
    print("Verifying Security Officer Enhancements...")
    
    scanner = VulnerabilityScanner()
    
    # Test Code with vulnerabilities
    unsafe_code = """
import os
import subprocess

def run_command(cmd):
    # Regex should catch this (maybe)
    os.system(cmd) 
    
    # AST should definitely catch this
    eval("print('hack')")
    
    # AST should catch this
    import telnetlib
    """
    
    print("\nScanning unsafe code...")
    result = await scanner.scan_vulnerabilities(unsafe_code, language="python")
    
    print(f"Risk Score: {result.risk_score}")
    print(f"Found {len(result.vulnerabilities)} vulnerabilities:")
    
    found_types = [v.type for v in result.vulnerabilities]
    
    for v in result.vulnerabilities:
        print(f" - [{v.severity}] {v.type}: {v.description} (Line {v.line_number})")
        
    # Assertions
    assert VulnerabilityType.COMMAND_INJECTION in found_types # os.system
    assert VulnerabilityType.CODE_INJECTION in found_types # eval
    assert VulnerabilityType.INSECURE_PROTOCOL in found_types # telnetlib
    
    print("\nSecurity Enhancements Verified!")

if __name__ == "__main__":
    asyncio.run(verify_security_enhancements())
