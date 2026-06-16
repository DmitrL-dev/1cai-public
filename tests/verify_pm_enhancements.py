import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.project_manager.services import RiskAnalyzer, ResourceAllocator, SprintPlanner
from src.modules.project_manager.domain.models import Task, TaskPriority, TaskStatus, RiskStrategy

async def verify_project_manager_enhancements():
    print("Verifying Project Manager Enhancements...")
    
    # 1. Verify Risk Analyzer
    print("\n[1] Verifying Risk Analyzer...")
    analyzer = RiskAnalyzer()
    
    # Critical Risk
    risk1 = analyzer.analyze_risk("Database crash", 5, 5) # 25
    print(f"Risk 1 (5x5): Score={risk1.score}, Level={risk1.level}, Strategy={risk1.strategy}")
    assert risk1.strategy == RiskStrategy.MITIGATE
    
    # Low Risk
    risk2 = analyzer.analyze_risk("Typo in docs", 1, 2) # 2
    print(f"Risk 2 (1x2): Score={risk2.score}, Level={risk2.level}, Strategy={risk2.strategy}")
    assert risk2.strategy == RiskStrategy.ACCEPT
    
    print("Risk Analyzer Verified!")

    # 2. Verify Resource Allocator
    print("\n[2] Verifying Resource Allocator...")
    allocator = ResourceAllocator()
    
    task_python = Task(id="t1", title="Implement Backend API", description="Use Python FastAPI", tags=["backend"])
    task_sql = Task(id="t2", title="Optimize SQL Query", description="Fix slow join", tags=["database"])
    
    agent1 = allocator.get_best_agent_for_task(task_python)
    print(f"Task: {task_python.title} -> Agent: {agent1.name} (Skills: {agent1.skills})")
    assert "PYTHON" in [s.value for s in agent1.skills]
    
    agent2 = allocator.get_best_agent_for_task(task_sql)
    print(f"Task: {task_sql.title} -> Agent: {agent2.name} (Skills: {agent2.skills})")
    assert "SQL" in [s.value for s in agent2.skills]
    
    print("Resource Allocator Verified!")

    # 3. Verify Sprint Planner with Resource Allocation
    print("\n[3] Verifying Sprint Planner (with Allocation)...")
    planner = SprintPlanner(resource_allocator=allocator)
    
    backlog = [
        Task(id="b1", title="Fix Bug", description="Critical bug", priority=TaskPriority.MUST, story_points=5, tags=["python"]),
        Task(id="b2", title="Write Docs", description="User guide", priority=TaskPriority.SHOULD, story_points=3, tags=["docs"]),
    ]
    
    from datetime import date
    sprint = planner.plan_sprint("Sprint 1", date.today(), 2, 20, backlog)
    
    print(f"Sprint Planned: {len(sprint.tasks)} tasks")
    for t in sprint.tasks:
        print(f" - {t.title} ({t.story_points} SP) -> Assigned to: {t.assignee_id}")
        assert t.assignee_id is not None # Should be assigned
        
    print("Sprint Planner Verified!")
    
    print("\nALL CHECKS PASSED")

if __name__ == "__main__":
    asyncio.run(verify_project_manager_enhancements())
