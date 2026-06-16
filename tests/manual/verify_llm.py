import asyncio
import sys
import os
from langchain_core.messages import HumanMessage

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.modules.ai_orchestration.services.nodes import GraphNodes
from src.modules.ai_orchestration.domain.models import AgentState

async def main():
    print("🚀 Starting Real LLM Verification...")

    # Check for API Key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ OPENAI_API_KEY not found. Skipping real LLM call.")
        print("Please set OPENAI_API_KEY in your environment to verify real integration.")
        return

    # 1. Initialize Nodes (uses LLMFactory -> ChatOpenAI by default)
    print("🔹 Initializing Nodes with Real LLM...")
    nodes = GraphNodes() 

    # 2. Define State
    state: AgentState = {
        "messages": [HumanMessage(content="What is the capital of France? Reply in one word.")],
        "context": {},
        "next_step": "reason",
        "scratchpad": {}
    }

    # 3. Test Reason Node
    print("🔹 Testing reason_node...")
    try:
        result = await nodes.reason_node(state)
        response = result['messages'][0]
        
        print(f"✅ LLM Response: {response.content}")
        print(f"Next Step: {result['next_step']}")
        
        if "Paris" in response.content:
            print("✅ Verification Successful: Correct answer received.")
        else:
            print("⚠️ Verification Warning: Unexpected answer.")
            
    except Exception as e:
        print(f"❌ Verification Failed: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
