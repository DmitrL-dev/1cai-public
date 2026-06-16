import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.security.services.taint_analyzer import TaintAnalyzer


def verify_taint_analysis():
    print("Verifying Taint Analysis...")

    analyzer = TaintAnalyzer()

    # Code with taint flow: input -> user_input -> cmd -> os.system
    code = """
def process_request(request):
    user_input = request
    cmd = "echo " + user_input
    import os
    os.system(cmd)
    
def safe_function():
    x = "safe"
    eval(x)
    """

    print("\nAnalyzing code for taint flow...")
    vulnerabilities = analyzer.analyze(code)

    print(f"Vulnerabilities Found: {len(vulnerabilities)}")
    for v in vulnerabilities:
        print(f" - {v.type}: {v.description}")

    # Assertions
    assert len(vulnerabilities) >= 1
    assert "os.system" in vulnerabilities[0].description
    assert "request" in vulnerabilities[0].description

    print("\nTaint Analysis Verified Successfully!")


if __name__ == "__main__":
    verify_taint_analysis()
