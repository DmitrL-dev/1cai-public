import json

# Read pylint results with auto-detected encoding
# Try different encodings
encodings = ['utf-16le', 'utf-16', 'utf-8', 'utf-8-sig']
data = None

for enc in encodings:
    try:
        with open('pylint_results_final.json', 'r', encoding=enc) as f:
            data = json.load(f)
        print(f"Successfully read with encoding: {enc}")
        break
    except:
        continue

if data is None:
    print("ERROR: Could not read file with any encoding")
    exit(1)

# Find E0001 errors
e0001_errors = [x for x in data if x.get('message-id') == 'E0001']

print(f"\nTotal E0001 errors: {len(e0001_errors)}\n")

for error in e0001_errors:
    print(f"File: {error.get('path')}")
    print(f"Line: {error.get('line')}")
    print(f"Message: {error.get('message')}")
    print()
