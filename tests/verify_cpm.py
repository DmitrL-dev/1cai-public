import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.project_manager.services.critical_path_analyzer import CriticalPathAnalyzer
from src.modules.project_manager.domain.models import Task, TaskPriority, TaskStatus


def verify_cpm():
    print("Verifying Critical Path Method (CPM)...")

    analyzer = CriticalPathAnalyzer()

    # Define tasks for a simple project graph
    # A (3) -> B (2) -> D (4)
    # A (3) -> C (5) -> D (4)
    # Path 1: A-B-D = 3+2+4 = 9
    # Path 2: A-C-D = 3+5+4 = 12 (Critical Path)

    tasks = [
        Task(id="A", title="Task A", description="Start", story_points=3, dependencies=[]),
        Task(id="B", title="Task B", description="Middle 1", story_points=2, dependencies=["A"]),
        Task(id="C", title="Task C", description="Middle 2", story_points=5, dependencies=["A"]),
        Task(id="D", title="Task D", description="End", story_points=5, dependencies=["B", "C"]),
    ]

    print("\nCalculating Critical Path...")
    critical_path = analyzer.calculate_critical_path(tasks)

    print(f"Critical Path Length: {len(critical_path)}")
    path_ids = [t.id for t in critical_path]
    print(f"Path: {' -> '.join(path_ids)}")

    # Assertions
    assert len(critical_path) == 3
    assert path_ids == ["A", "C", "D"]

    print("\nCPM Verified Successfully!")


if __name__ == "__main__":
    verify_cpm()
