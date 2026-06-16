import asyncio
import sys
import os
import logging
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.infrastructure.event_bus_nats import NATSEventBus
from src.infrastructure.event_bus import Event, EventType
from src.modules.ai_orchestration.infrastructure.event_bus import AIOrchestratorConsumer


async def main():
    print("🚀 Starting NATS Integration Verification...")

    # Mock LLM to avoid API Key errors
    mock_llm = MagicMock()

    # Define an async function for the mock to return
    async def mock_ainvoke(*args, **kwargs):
        return AIMessage(content="NATS Verification Mock Response")

    # Assign the async function to ainvoke
    mock_llm.ainvoke = mock_ainvoke

    # Patch LLMFactory.create to return our mock
    with patch("src.modules.ai_orchestration.infrastructure.llm.LLMFactory.create", return_value=mock_llm):
        # 1. Initialize NATS Bus
        # Note: Requires NATS to be running (docker-compose up -d nats)
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        print(f"🔹 Connecting to NATS at {nats_url}...")

        try:
            bus = NATSEventBus(nats_url=nats_url, stream_name="test_events")
            await bus.start()
        except Exception as e:
            print(f"❌ Failed to connect to NATS: {e}")
            print("Ensure NATS is running: docker-compose up -d nats")
            return

        # 2. Register Consumer
        print("🔹 Registering AIOrchestratorConsumer...")
        consumer = AIOrchestratorConsumer()
        bus.subscribe(EventType.AI_AGENT_STARTED, consumer)

        # 3. Publish Event
        print("🔹 Publishing AI_AGENT_STARTED event...")
        event = Event(
            type=EventType.AI_AGENT_STARTED, payload={"message": "Triggered via NATS", "thread_id": "nats-test-1"}
        )
        await bus.publish(event)

        # 4. Wait for processing
        print("🔹 Waiting for event processing (5s)...")
        await asyncio.sleep(5)

        # 5. Cleanup
        await bus.stop()
        print("\n✅ Verification Complete (Check logs for 'Workflow completed')")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
