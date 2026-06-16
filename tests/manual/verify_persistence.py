import asyncio
import sys
import os
import uuid

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.modules.ai_orchestration.services.nodes import GraphNodes
from src.modules.ai_orchestration.services.graph_builder import GraphBuilder
from src.modules.ai_orchestration.infrastructure.checkpoint import PostgresCheckpointer
from src.modules.ai_orchestration.domain.models import AgentState

# Set DB URL for localhost (running from host)
os.environ["DATABASE_URL"] = "postgresql://admin:change_me_in_prod@localhost:5432/enterprise_os"


async def main():
    print("🚀 Starting Persistence Verification...")

    # 1. Initialize Checkpointer
    print("🔹 Connecting to Postgres...")
    checkpointer_wrapper = PostgresCheckpointer()
    checkpointer = await checkpointer_wrapper.get_saver()

    # 2. Initialize Graph with Checkpointer
    print("🔹 Building Graph with Persistence...")
    nodes = GraphNodes()
    builder = GraphBuilder(nodes, checkpointer=checkpointer)
    graph = builder.build()

    # 3. Define Thread ID
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    print(f"🔹 Using Thread ID: {thread_id}")

    # 4. Run Step 1
    print("\n🔹 Running Step 1 (User Input)...")
    initial_state = {
        "messages": [{"role": "user", "content": "My name is Antigravity."}],
        "context": {},
        "next_step": "reason",
        "scratchpad": {},
    }

    # We use ainvoke with config to persist state
    result1 = await graph.ainvoke(initial_state, config=config)
    print(f"Result 1: {result1['messages'][-1].content}")

    # 5. Simulate Restart / New Session
    print("\n🔹 Simulating New Session (Same Thread ID)...")
    # We don't pass messages, just the new input. The graph should load history.
    # Note: LangGraph's ainvoke loads state if thread_id is present.

    new_input = {
        "messages": [{"role": "user", "content": "What is my name?"}],
        # We don't need to pass context/scratchpad, it should be loaded
    }

    result2 = await graph.ainvoke(new_input, config=config)
    print(f"Result 2: {result2['messages'][-1].content}")

    # 6. Verify Memory
    # Since we use a MockLLM, it won't actually "remember" unless we check the state history manually
    # or if the MockLLM was smart.
    # But we can check if the state contains the previous messages.

    all_messages = result2["messages"]
    print("\n🔹 Verifying Message History in State...")
    for i, msg in enumerate(all_messages):
        content = msg.get("content") if isinstance(msg, dict) else msg.content
        print(f"  [{i}] {content}")

    if len(all_messages) >= 3:  # User1, AI1, User2, AI2...
        print("\n✅ Persistence Verified! History preserved.")
    else:
        print("\n❌ Persistence Failed! History lost.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
