import asyncio
import sys
import os
import json
import websockets

# Add project root to path
sys.path.append(os.getcwd())

async def test_collab_service():
    print("Starting Collab Service WebSocket Test...")
    uri = "ws://localhost:8002/ws/test-room"

    async with websockets.connect(uri) as client1:
        print("Client 1 connected.")
        
        async with websockets.connect(uri) as client2:
            print("Client 2 connected.")
            
            # Client 1 sends a message
            test_message = "Hello from Client 1"
            await client1.send(test_message)
            print(f"Client 1 sent: {test_message}")
            
            # Client 2 should receive it
            response = await client2.recv()
            print(f"Client 2 received: {response}")
            
            assert response == test_message
            print("SUCCESS: Message broadcast verified.")

if __name__ == "__main__":
    try:
        asyncio.run(test_collab_service())
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)
