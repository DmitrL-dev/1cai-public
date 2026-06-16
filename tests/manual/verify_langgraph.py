import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.modules.ai_orchestration.services.nodes import GraphNodes
from src.modules.ai_orchestration.services.graph_builder import GraphBuilder
from src.modules.ai_orchestration.domain.models import AgentState


async def main():
    print("🚀 Starting LangGraph Verification...")

    # 1. Initialize Nodes
    print("🔹 Initializing Nodes...")
    nodes = GraphNodes()  # Uses MockLLM by default

    # 2. Build Graph
    print("🔹 Building Graph...")
    builder = GraphBuilder(nodes)
    graph = builder.build()

    # 3. Define Initial State
    initial_state: AgentState = {
        "messages": [{"role": "user", "content": "Hello, AI!"}],
        "context": {"thread_id": "test-thread-1"},
        "next_step": "reason",
        "scratchpad": {},
    }

    # 4. Run Graph
    print("🔹 Running Graph...")
    try:
        # invoke is sync, ainvoke is async. LangGraph compiles to Runnable.
        result = await graph.ainvoke(initial_state)

        print("\n✅ Graph Execution Successful!")
        print("Final State:")
        for msg in result["messages"]:
            content = msg.get("content") if isinstance(msg, dict) else msg.content
            print(f"  - {content}")

        print(f"Next Step: {result.get('next_step')}")

    except Exception as e:
        print(f"\n❌ Graph Execution Failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
