import sys
import logging
from fastapi.testclient import TestClient
from src.main import app

# Configure logging to stdout
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

print("Creating TestClient...")
try:
    client = TestClient(app)
    print("TestClient created.")

    print("Sending request to /...")
    response = client.get("/")
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")

    print("Sending request to /health...")
    response = client.get("/health")
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    import traceback

    traceback.print_exc()
