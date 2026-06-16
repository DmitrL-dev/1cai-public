import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.shared_memory.infrastructure.vector_memory import VectorMemoryService


async def verify_memory():
    print("Verifying Shared Memory (Vector)...")

    memory = VectorMemoryService()

    # 1. Add memories
    print("Adding memories...")
    await memory.add("Python is a programming language.", {"topic": "tech"})
    await memory.add("The sky is blue.", {"topic": "nature"})
    await memory.add("Machine learning uses statistics.", {"topic": "tech"})

    # 2. Search
    print("Searching for 'programming'...")
    results = await memory.search("programming")  # Should match Python

    print(f"Found {len(results)} results:")
    for res in results:
        print(f"- {res.item.content} (Score: {res.score:.4f})")

    # Check relevance
    assert len(results) > 0
    assert "Python" in results[0].item.content

    print("\nSearching for 'sky'...")
    results = await memory.search("sky")  # Should match sky

    print(f"Found {len(results)} results:")
    for res in results:
        print(f"- {res.item.content} (Score: {res.score:.4f})")

    assert len(results) > 0
    assert "sky" in results[0].item.content

    print("\nShared Memory Verified Successfully!")


if __name__ == "__main__":
    asyncio.run(verify_memory())
