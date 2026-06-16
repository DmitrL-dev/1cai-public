import sys
import os
import asyncio
from datetime import datetime

# Add src to path
sys.path.append(os.getcwd())

from src.modules.scenario_hub.services import ScenarioEngine
from src.modules.scenario_hub.domain.models import Scenario, ScenarioStep, ScenarioStatus

async def test_scenario_hub():
    print("🚀 Starting Scenario Hub Verification...")
    
    engine = ScenarioEngine()
    
    # 1. Register a Scenario
    print("\n[1] Registering Scenario...")
    scenario = Scenario(
        id="deploy-app",
        name="Deploy Application",
        description="Simulates an application deployment pipeline",
        steps=[
            ScenarioStep(id="build", action="log", parameters={"message": "Building application..."}),
            ScenarioStep(id="test", action="wait", parameters={"seconds": 0.5}),
            ScenarioStep(id="deploy", action="log", parameters={"message": "Deploying to production..."}),
            ScenarioStep(id="verify", action="log", parameters={"message": "Health check passed!"})
        ]
    )
    engine.register_scenario(scenario)
    print(f"✅ Registered scenario: {scenario.name} ({len(scenario.steps)} steps)")

    # 2. Execute Scenario
    print("\n[2] Executing Scenario...")
    execution = await engine.execute_scenario("deploy-app")
    
    print(f"✅ Execution started: {execution.id}")
    print(f"   Status: {execution.status}")
    
    # Verify results
    assert execution.status == ScenarioStatus.COMPLETED, f"Execution failed: {execution.error}"
    assert len(execution.step_executions) == 4, "Should have executed 4 steps"
    
    print("\n[3] Verifying Execution Log...")
    for step_exec in execution.step_executions:
        status_icon = "✅" if step_exec.status == "completed" else "❌"
        print(f"   {status_icon} Step {step_exec.step_id}: {step_exec.status}")
        if step_exec.logs:
            for log in step_exec.logs:
                print(f"      📝 Log: {log}")

    print("\n🎉 All tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_scenario_hub())
