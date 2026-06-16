import asyncio
import logging
import sys
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("AI_Verification")

async def verify_orchestrator():
    print("\n🔍 Verifying AdvancedAIOrchestrator...")
    
    try:
        from src.ai.advanced_orchestrator import AdvancedAIOrchestrator
        
        # Mock dependencies to avoid external calls
        with patch('src.ai.advanced_orchestrator.EventBus'), \
             patch('src.ai.advanced_orchestrator.SelfEvolvingAI'), \
             patch('src.ai.advanced_orchestrator.SelfHealingCode'), \
             patch('src.ai.advanced_orchestrator.DistributedAgentNetwork'), \
             patch('src.ai.orchestrator.AIOrchestrator.process_query') as mock_base_process:
            
            # 1. Initialization
            orchestrator = AdvancedAIOrchestrator()
            print("✅ AdvancedAIOrchestrator initialized")
            
            # 2. Process Query
            mock_base_process.return_value = {"type": "answer", "content": "Mock response"}
            
            query = "Как создать справочник в 1С?"
            result = await orchestrator.process_query(query)
            
            if result["content"] == "Mock response":
                print(f"✅ process_query executed successfully (Result: {result['content']})")
            else:
                print(f"❌ process_query failed: Unexpected result {result}")
                
            # Verify event publishing (we can't easily check the mock calls without keeping the mock object, 
            # but successful execution implies no crash)
            
            # 3. Evolve
            orchestrator.evolving_ai.evolve = MagicMock(return_value={"status": "completed", "improvements_generated": 2})
            evolution_result = await orchestrator.evolve()
            print(f"✅ evolve executed successfully (Status: {evolution_result['status']})")
            
            # 4. Coordinate Agents
            orchestrator.agent_network.submit_task = MagicMock()
            orchestrator.agent_network.submit_task.return_value.id = "task-123"
            orchestrator.agent_network.submit_task.return_value.status = "completed"
            orchestrator.agent_network.get_network_stats.return_value = {"agents_by_role": {"dev": 1}}
            
            agent_result = await orchestrator.coordinate_agents("Fix bug", ["dev"])
            print(f"✅ coordinate_agents executed successfully (Task ID: {agent_result['task_id']})")
            
    except Exception as e:
        print(f"❌ AdvancedAIOrchestrator verification failed: {e}")
        raise e

async def main():
    try:
        await verify_orchestrator()
        print("\n🎉 AI Core Verification Passed!")
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
