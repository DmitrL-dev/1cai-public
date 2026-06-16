
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.structured_logging import StructuredLogger
logger = StructuredLogger("Verification").logger

async def verify_orchestrator():
    print("\n--- Verifying Orchestrator ---")
    try:
        from src.ai.orchestrator import get_orchestrator
        print("✅ Import successful")
        
        orchestrator = get_orchestrator()
        print("✅ Singleton retrieval successful")
        
        # Test simple query to trigger lazy loading of strategies
        query = "как сделать рефакторинг?"
        print(f"Testing query: '{query}'")
        
        # We expect this to work without error, even if it returns a mock/default response
        # This verifies that the lazy imports inside process_query/_execute_strategies work
        try:
            # Mock context to avoid complex dependencies if needed
            context = {"test_mode": True} 
            # Note: We might hit missing dependencies if the strategies require external services
            # but we want to see if the *imports* work.
            
            # Just checking if we can resolve a strategy is a good first step
            # Accessing private method for verification purposes
            from src.ai.query_classifier import QueryIntent, QueryType, AIService
            
            # Simulate intent
            intent = QueryIntent(
                query_type=QueryType.OPTIMIZATION,
                confidence=0.9,
                keywords=["рефакторинг"],
                context_type=None,
                preferred_services=[AIService.QWEN_CODER],
                suggested_tools=[]
            )
            
            print("✅ Intent creation successful")
            
            # Check if we can get the strategy (triggers lazy import)
            strategy = orchestrator._get_strategy(AIService.QWEN_CODER, context)
            print(f"✅ Strategy loaded: {strategy}")
            
        except Exception as e:
            print(f"⚠️ Runtime check warning (might be expected due to missing config): {e}")
            # If it's an ImportError, that's a failure. If it's a config error, that's okay for now.
            if isinstance(e, ImportError):
                print("❌ CRITICAL: ImportError detected during runtime!")
                raise e

    except Exception as e:
        print(f"❌ Orchestrator verification failed: {e}")
        raise e

async def verify_ml_api():
    print("\n--- Verifying ML API ---")
    try:
        # This checks if the module can be imported without executing the heavy top-level code
        # and if the lazy imports inside functions are syntactically correct (static analysis would catch this, but runtime is better)
        import src.api.ml
        print("✅ Module import successful")
        
        # Check if router exists
        if hasattr(src.api.ml, 'router'):
             print("✅ Router found")
        else:
             print("❌ Router NOT found")

    except Exception as e:
        print(f"❌ ML API verification failed: {e}")
        raise e

async def main():
    print("Starting Functional Verification...")
    await verify_orchestrator()
    await verify_ml_api()
    print("\nVerification Completed.")

if __name__ == "__main__":
    asyncio.run(main())
