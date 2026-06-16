#!/usr/bin/env python3
"""
Test script for new DevOps & AI Evolution API endpoints
========================================================

Tests:
- Health check with real PostgreSQL connection
- DevOps infrastructure analysis
- Self-Evolving AI endpoints

Usage:
    python scripts/test_new_endpoints.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from rich.console import Console
from rich.table import Table

console = Console()

# API base URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8001")


async def test_health_check():
    """Test improved health check endpoint"""
    console.print("\n[bold cyan]1. Testing Health Check[/bold cyan]")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            response.raise_for_status()
            data = response.json()
            
            console.print(f"   Status: {data.get('status')}")
            console.print("   Services:")
            for service, status in data.get("services", {}).items():
                status_color = "green" if status == "healthy" else "red" if status == "unhealthy" else "yellow"
                console.print(f"     - {service}: [{status_color}]{status}[/{status_color}]")
            
            return data.get("status") == "healthy"
        except Exception as e:
            console.print(f"   [red]Error: {e}[/red]")
            return False


async def test_devops_infrastructure_status():
    """Test DevOps infrastructure status endpoint"""
    console.print("\n[bold cyan]2. Testing DevOps Infrastructure Status[/bold cyan]")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/api/v1/devops/infrastructure/status")
            response.raise_for_status()
            data = response.json()
            
            console.print(f"   Status: {data.get('status')}")
            console.print(f"   Containers found: {data.get('count', 0)}")
            
            if data.get("containers"):
                table = Table(title="Running Containers")
                table.add_column("Name", style="cyan")
                table.add_column("Image", style="magenta")
                table.add_column("Status", style="green")
                
                for container in data.get("containers", [])[:5]:  # Show first 5
                    table.add_row(
                        container.get("name", "N/A"),
                        container.get("image", "N/A"),
                        container.get("status", "N/A")
                    )
                console.print(table)
            
            return True
        except Exception as e:
            console.print(f"   [red]Error: {e}[/red]")
            return False


async def test_devops_infrastructure_analyze():
    """Test DevOps infrastructure analysis endpoint"""
    console.print("\n[bold cyan]3. Testing DevOps Infrastructure Analysis[/bold cyan]")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Try to find docker-compose file
            project_root = Path.cwd()
            compose_files = [
                project_root / "docker-compose.yml",
                project_root / "docker-compose.mvp.yml",
            ]
            
            compose_file = None
            for path in compose_files:
                if path.exists():
                    compose_file = str(path.relative_to(project_root))
                    break
            
            if not compose_file:
                console.print("   [yellow]Skipping: docker-compose.yml not found[/yellow]")
                return None
            
            response = await client.post(
                f"{API_BASE_URL}/api/v1/devops/infrastructure/analyze",
                params={"compose_file": compose_file}
            )
            response.raise_for_status()
            data = response.json()
            
            console.print(f"   Status: {data.get('status')}")
            
            static = data.get("static_analysis", {})
            console.print(f"   Services analyzed: {static.get('service_count', 0)}")
            
            security_issues = len(static.get("security_issues", []))
            perf_issues = len(static.get("performance_issues", []))
            
            if security_issues > 0:
                console.print(f"   [yellow]Security issues: {security_issues}[/yellow]")
            if perf_issues > 0:
                console.print(f"   [yellow]Performance issues: {perf_issues}[/yellow]")
            
            if security_issues == 0 and perf_issues == 0:
                console.print("   [green]No issues found![/green]")
            
            return True
        except httpx.HTTPStatusError as e:
            console.print(f"   [red]HTTP Error {e.response.status_code}: {e.response.text}[/red]")
            return False
        except Exception as e:
            console.print(f"   [red]Error: {e}[/red]")
            return False


async def test_ai_evolve_status():
    """Test Self-Evolving AI status endpoint"""
    console.print("\n[bold cyan]4. Testing Self-Evolving AI Status[/bold cyan]")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/api/v1/ai/evolve/status")
            response.raise_for_status()
            data = response.json()
            
            console.print(f"   Is evolving: {data.get('is_evolving')}")
            console.print(f"   Current stage: {data.get('current_stage')}")
            console.print(f"   Performance history: {data.get('performance_history_count', 0)} entries")
            console.print(f"   Improvements: {data.get('improvements_count', 0)}")
            
            if data.get("latest_metrics"):
                metrics = data["latest_metrics"]
                console.print("   Latest metrics:")
                console.print(f"     - Accuracy: {metrics.get('accuracy', 0) * 100:.1f}%")
                console.print(f"     - Error rate: {metrics.get('error_rate', 0) * 100:.1f}%")
                console.print(f"     - Latency: {metrics.get('latency_ms', 0)} ms")
            
            return True
        except Exception as e:
            console.print(f"   [red]Error: {e}[/red]")
            return False


async def test_ai_evolve_metrics():
    """Test Self-Evolving AI metrics endpoint"""
    console.print("\n[bold cyan]5. Testing Self-Evolving AI Metrics[/bold cyan]")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/api/v1/ai/evolve/metrics")
            response.raise_for_status()
            data = response.json()
            
            console.print(f"   Metrics history: {data.get('count', 0)} entries")
            
            return True
        except Exception as e:
            console.print(f"   [red]Error: {e}[/red]")
            return False


async def test_ai_evolve():
    """Test Self-Evolving AI evolve endpoint (may take time)"""
    console.print("\n[bold cyan]6. Testing Self-Evolving AI Evolution[/bold cyan]")
    console.print("   [yellow]This may take a while...[/yellow]")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/ai/evolve",
                json={"force": False}
            )
            response.raise_for_status()
            data = response.json()
            
            console.print(f"   Status: {data.get('status')}")
            console.print(f"   Stage: {data.get('stage')}")
            console.print(f"   Message: {data.get('message')}")
            
            if data.get("metrics"):
                metrics = data["metrics"]
                console.print("   Metrics:")
                console.print(f"     - Accuracy: {metrics.get('accuracy', 0) * 100:.1f}%")
                console.print(f"     - Error rate: {metrics.get('error_rate', 0) * 100:.1f}%")
            
            if data.get("improvements"):
                console.print(f"   Improvements generated: {len(data['improvements'])}")
            
            return True
        except httpx.HTTPStatusError as e:
            console.print(f"   [red]HTTP Error {e.response.status_code}: {e.response.text}[/red]")
            return False
        except Exception as e:
            console.print(f"   [red]Error: {e}[/red]")
            return False


async def main():
    """Run all tests"""
    console.print(f"\n[bold green]Testing API at {API_BASE_URL}[/bold green]")
    console.print("=" * 60)
    
    results = {}
    
    # Run tests
    results["health"] = await test_health_check()
    results["devops_status"] = await test_devops_infrastructure_status()
    results["devops_analyze"] = await test_devops_infrastructure_analyze()
    results["ai_status"] = await test_ai_evolve_status()
    results["ai_metrics"] = await test_ai_evolve_metrics()
    results["ai_evolve"] = await test_ai_evolve()
    
    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Test Summary[/bold cyan]")
    
    table = Table(title="Test Results")
    table.add_column("Test", style="cyan")
    table.add_column("Status", style="green")
    
    for test_name, result in results.items():
        if result is None:
            status = "[yellow]Skipped[/yellow]"
        elif result:
            status = "[green]✓ Passed[/green]"
        else:
            status = "[red]✗ Failed[/red]"
        table.add_row(test_name.replace("_", " ").title(), status)
    
    console.print(table)
    
    passed = sum(1 for r in results.values() if r is True)
    total = sum(1 for r in results.values() if r is not None)
    
    console.print(f"\n[bold]Results: {passed}/{total} tests passed[/bold]")
    
    if passed == total:
        console.print("[bold green]All tests passed! ✓[/bold green]")
    else:
        console.print("[bold yellow]Some tests failed or were skipped[/bold yellow]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Tests interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        sys.exit(1)

