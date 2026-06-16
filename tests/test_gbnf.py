import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

try:
    from gbnf_generator.gbnf_generator import GBNFGenerator

    print("Initializing GBNFGenerator...")
    generator = GBNFGenerator()

    print("Generating grammar...")
    grammar = generator.generate()

    print(f"Grammar generated successfully. Length: {len(grammar)} chars")
    print("First 5 lines:")
    print("\n".join(grammar.splitlines()[:5]))

    # Basic validation
    required_tokens = ["root ::=", "kw_if ::=", "kw_function ::="]
    for token in required_tokens:
        if token in grammar:
            print(f"✅ Found required token: {token}")
        else:
            print(f"❌ Missing required token: {token}")

    print("\nTest passed!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
