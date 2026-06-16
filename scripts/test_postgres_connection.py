#!/usr/bin/env python3
"""
Test PostgreSQL Connection
==========================

Проверяет подключение к PostgreSQL разными способами:
1. Через PostgreSQLSaver
2. Через asyncpg напрямую
3. Через psycopg2 напрямую
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table

console = Console()

def test_postgres_saver():
    """Test PostgreSQLSaver connection"""
    console.print("\n[bold cyan]1. Testing PostgreSQLSaver[/bold cyan]")
    try:
        from src.db.postgres_saver import PostgreSQLSaver
        
        pg_saver = PostgreSQLSaver()
        console.print(f"   Initialized with host: {pg_saver.conn_params['host']}")
        console.print(f"   Database: {pg_saver.conn_params['database']}")
        console.print(f"   User: {pg_saver.conn_params['user']}")
        
        if pg_saver.connect():
            console.print("   [green]✓ connect() returned True[/green]")
            if pg_saver.is_connected():
                console.print("   [green]✓ is_connected() returned True[/green]")
                return True
            else:
                console.print("   [red]✗ is_connected() returned False[/red]")
                return False
        else:
            console.print("   [red]✗ connect() returned False[/red]")
            return False
    except ValueError as e:
        console.print(f"   [red]✗ Error: {e}[/red]")
        return False
    except Exception as e:
        console.print(f"   [red]✗ Unexpected error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False

async def test_asyncpg():
    """Test asyncpg direct connection"""
    console.print("\n[bold cyan]2. Testing asyncpg (direct)[/bold cyan]")
    try:
        import asyncpg
        from urllib.parse import urlparse
        
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = int(os.getenv("POSTGRES_PORT", "5432"))
            database = os.getenv("POSTGRES_DB", "knowledge_base")
            user = os.getenv("POSTGRES_USER", "admin")
            password = os.getenv("POSTGRES_PASSWORD")
        else:
            parsed = urlparse(db_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            database = parsed.path.lstrip("/") or "knowledge_base"
            user = parsed.username or "admin"
            password = parsed.password or os.getenv("POSTGRES_PASSWORD")
        
        console.print(f"   Connecting to: {user}@{host}:{port}/{database}")
        
        if not password:
            console.print("   [red]✗ Password not provided[/red]")
            return False
        
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            timeout=5.0,
        )
        
        result = await conn.fetchval("SELECT 1")
        await conn.close()
        
        if result == 1:
            console.print("   [green]✓ Connection successful[/green]")
            return True
        else:
            console.print(f"   [red]✗ Unexpected result: {result}[/red]")
            return False
    except Exception as e:
        console.print(f"   [red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False

def test_psycopg2():
    """Test psycopg2 direct connection"""
    console.print("\n[bold cyan]3. Testing psycopg2 (direct)[/bold cyan]")
    try:
        import psycopg2
        from urllib.parse import urlparse
        
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = int(os.getenv("POSTGRES_PORT", "5432"))
            database = os.getenv("POSTGRES_DB", "knowledge_base")
            user = os.getenv("POSTGRES_USER", "admin")
            password = os.getenv("POSTGRES_PASSWORD")
        else:
            parsed = urlparse(db_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            database = parsed.path.lstrip("/") or "knowledge_base"
            user = parsed.username or "admin"
            password = parsed.password or os.getenv("POSTGRES_PASSWORD")
        
        console.print(f"   Connecting to: {user}@{host}:{port}/{database}")
        
        if not password:
            console.print("   [red]✗ Password not provided[/red]")
            return False
        
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=5,
        )
        
        cur = conn.cursor()
        cur.execute("SELECT 1")
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result[0] == 1:
            console.print("   [green]✓ Connection successful[/green]")
            return True
        else:
            console.print(f"   [red]✗ Unexpected result: {result}[/red]")
            return False
    except Exception as e:
        console.print(f"   [red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False

def show_env_vars():
    """Show relevant environment variables"""
    console.print("\n[bold cyan]Environment Variables:[/bold cyan]")
    table = Table()
    table.add_column("Variable", style="cyan")
    table.add_column("Value", style="magenta")
    
    vars_to_check = [
        "DATABASE_URL",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    
    for var in vars_to_check:
        value = os.getenv(var, "NOT SET")
        if "PASSWORD" in var and value != "NOT SET":
            value = "***" if value else "NOT SET"
        table.add_row(var, value)
    
    console.print(table)

async def main():
    """Run all tests"""
    console.print("\n[bold green]PostgreSQL Connection Test[/bold green]")
    console.print("=" * 60)
    
    show_env_vars()
    
    results = {}
    results["postgres_saver"] = test_postgres_saver()
    
    results["asyncpg"] = await test_asyncpg()
    results["psycopg2"] = test_psycopg2()
    
    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Test Summary[/bold cyan]")
    
    table = Table(title="Connection Test Results")
    table.add_column("Method", style="cyan")
    table.add_column("Status", style="green")
    
    for method, result in results.items():
        status = "[green]✓ Passed[/green]" if result else "[red]✗ Failed[/red]"
        table.add_row(method.replace("_", " ").title(), status)
    
    console.print(table)
    
    if all(results.values()):
        console.print("\n[bold green]All connection methods work! ✓[/bold green]")
    else:
        console.print("\n[bold yellow]Some connection methods failed[/bold yellow]")

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)

