import socket
import sys

services = [
    ("PostgreSQL", "localhost", 5432),
    ("Redis", "localhost", 6379),
    ("MCP Server", "localhost", 6001),
    ("Qdrant", "localhost", 6333)
]

print("Checking service connectivity...")
all_success = True
for name, host, port in services:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        if result == 0:
            print(f"✅ {name}: Accessible ({host}:{port})")
        else:
            print(f"❌ {name}: Not accessible ({host}:{port})")
            all_success = False
        sock.close()
    except Exception as e:
        print(f"❌ {name}: Error {e}")
        all_success = False

if not all_success:
    sys.exit(1)
