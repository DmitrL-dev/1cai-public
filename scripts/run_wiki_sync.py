import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.services.wiki.service import WikiService
from src.services.wiki.sync_worker import CodeSyncService


async def main():
    print("Initializing CodeSync...")
    
    # Point to src/ directory
    root_path = os.path.join(os.getcwd(), "src")
    
    wiki_service = WikiService()
    syncer = CodeSyncService(root_path, wiki_service)
    
    print(f"Scanning {root_path}...")
    await syncer.sync_all()
    print("Sync complete.")

if __name__ == "__main__":
    asyncio.run(main())
