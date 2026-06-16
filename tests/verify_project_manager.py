import sys
import os
from datetime import date

# Add src to path
sys.path.append(os.getcwd())

from src.modules.project_manager.domain.models import Task, TaskPriority, TaskStatus
from src.modules.project_manager.services import TaskDecomposer, EffortEstimator, SprintPlanner

def test_project_manager():
    print("🚀 Starting Project Manager Verification...")
    
    # 1. Test Task Decomposer
    print("\n[1] Testing Task Decomposer...")
    decomposer = TaskDecomposer()
    parent_task = Task(
        id="T-1",
        title="Implement User Profile",
        description="Create backend API and frontend UI for user profile management",
        priority=TaskPriority.MUST
    )
    subtasks = decomposer.decompose(parent_task)
    print(f"✅ Decomposed into {len(subtasks)} subtasks:")
    for t in subtasks:
        print(f"   - {t.title} ({t.id})")
    assert len(subtasks) >= 2, "Should have at least frontend and backend subtasks"

    # 2. Test Effort Estimator
    print("\n[2] Testing Effort Estimator...")
    estimator = EffortEstimator()
    t1 = Task(id="T-2", title="Fix Typo", description="Fix typo in README", priority=TaskPriority.COULD)
    t2 = Task(id="T-3", title="Migrate DB", description="Migrate entire database architecture to Neo4j", priority=TaskPriority.MUST)
    
    est1 = estimator.estimate(t1)
    est2 = estimator.estimate(t2)
    
    print(f"✅ 'Fix Typo' estimated as: {est1} SP")
    print(f"✅ 'Migrate DB' estimated as: {est2} SP")
    
    assert est1 <= 2, "Typo should be low effort"
    assert est2 >= 5, "Migration should be high effort"

    # 3. Test Sprint Planner
    print("\n[3] Testing Sprint Planner...")
    planner = SprintPlanner()
    backlog = [
        Task(id="B-1", title="Critical Bug", description="Fix crash", priority=TaskPriority.MUST, story_points=8),
        Task(id="B-2", title="Nice Feature", description="Add dark mode", priority=TaskPriority.COULD, story_points=5),
        Task(id="B-3", title="Important Feature", description="Add login", priority=TaskPriority.SHOULD, story_points=5),
    ]
    
    sprint = planner.plan_sprint(
        sprint_name="Sprint 1",
        start_date=date.today(),
        duration_weeks=2,
        capacity=10, # Limited capacity
        backlog=backlog
    )
    
    print(f"✅ Sprint '{sprint.name}' planned with {len(sprint.tasks)} tasks.")
    print(f"   Total Points: {sprint.total_points} / {sprint.capacity}")
    for t in sprint.tasks:
        print(f"   - {t.title} ({t.priority.value}, {t.story_points} SP)")
        
    assert len(sprint.tasks) == 1, "Should only fit the MUST task (8 SP)"
    assert sprint.tasks[0].id == "B-1", "Should select the MUST task"

    print("\n🎉 All tests passed successfully!")

if __name__ == "__main__":
    test_project_manager()
