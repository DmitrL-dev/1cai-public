import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.infrastructure.event_bus import EventBus, EventType, Event
from src.modules.security.services.vulnerability_scanner import VulnerabilityScanner
from src.modules.technical_writer.services.ast_doc_generator import ASTUserGuideGenerator
from src.modules.technical_writer.domain.models import Audience


class MockEventBus(EventBus):
    def __init__(self):
        super().__init__()
        self.published_events = []

    async def publish(self, event: Event) -> None:
        self.published_events.append(event)
        await super().publish(event)


async def verify_integration():
    print("Verifying Event Bus Integration...")

    # 1. Setup Mock Event Bus
    mock_bus = MockEventBus()
    await mock_bus.start()

    # 2. Verify Security Officer
    print("\nTesting Security Officer...")
    scanner = VulnerabilityScanner(event_bus=mock_bus)
    code_with_vuln = 'import os; os.system("rm -rf /")'

    await scanner.scan_vulnerabilities(code_with_vuln)

    # Check if VULNERABILITY_FOUND event was published
    vuln_events = [e for e in mock_bus.published_events if e.type == EventType.VULNERABILITY_FOUND]
    print(f"Vulnerability Events Published: {len(vuln_events)}")
    assert len(vuln_events) > 0
    assert vuln_events[0].source == "security_officer"

    # 3. Verify Technical Writer
    print("\nTesting Technical Writer...")
    # Clear events
    mock_bus.published_events.clear()

    generator = ASTUserGuideGenerator(event_bus=mock_bus)
    code_doc = "class MyClass: pass"

    await generator.generate(code_doc, "MyFeature", Audience.DEVELOPER)

    # Check if DOC_GENERATED event was published
    doc_events = [e for e in mock_bus.published_events if e.type == EventType.DOC_GENERATED]
    print(f"Doc Events Published: {len(doc_events)}")
    assert len(doc_events) == 1
    assert doc_events[0].source == "technical_writer"

    await mock_bus.stop()
    print("\nEvent Bus Integration Verified Successfully!")


if __name__ == "__main__":
    asyncio.run(verify_integration())
