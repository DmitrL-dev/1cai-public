
#!/usr/bin/env python3
"""
Seed Demo Data Script
Creates realistic demo data for development and demos
"""

import asyncio
import os
import random
from datetime import datetime, timedelta

import asyncpg

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/enterprise_1c_ai')

async def seed_demo_data():
    """Create realistic demo data"""
    
    print("🌱 Seeding demo data...")
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # 1. Create demo tenant
        print("  Creating demo tenant...")
        tenant_id = await conn.fetchval(
            """
            INSERT INTO tenants (name, plan, active, created_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (name) DO UPDATE
            SET plan = EXCLUDED.plan
            RETURNING id
            """,
            "Demo Company",
            "professional",
            True,
            datetime.now() - timedelta(days=365)
        )
        print(f"  ✅ Tenant created: {tenant_id}")
        
        # 2. Create users
        print("  Creating demo users...")
        users = []
        user_names = [
            ("Alice Johnson", "developer"),
            ("Bob Smith", "pm"),
            ("Carol White", "qa"),
            ("David Brown", "developer"),
            ("Eve Wilson", "ba")
        ]
        
        for name, role in user_names:
            user_id = await conn.fetchval(
                """
                INSERT INTO users (email, role, created_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (email) DO UPDATE
                SET role = EXCLUDED.role
                RETURNING id
                """,
                f"{name.lower().replace(' ', '.')}@demo.com",
                role,
                datetime.now() - timedelta(days=random.randint(30, 365))
            )
            users.append((user_id, name, role))
        print(f"  ✅ {len(users)} users created")
        
        # 3. Create transactions (revenue data)
        print("  Creating transactions...")
        for month_offset in range(12, 0, -1):
            # Create 3-10 transactions per month
            for _ in range(random.randint(3, 10)):
                base_amount = 10000 + (12 - month_offset) * 1000
                amount = base_amount + random.randint(-2000, 3000)
                
                created_date = datetime.now() - timedelta(days=30 * month_offset + random.randint(0, 28))
                
                await conn.execute(
                    """
                    INSERT INTO transactions 
                    (tenant_id, amount, currency, type, status, description, created_at, completed_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    tenant_id,
                    amount,
                    'EUR',
                    random.choice(['subscription', 'one_time']),
                    'completed',
                    f"Payment for {created_date.strftime('%B %Y')}",
                    created_date,
                    created_date + timedelta(hours=1)
                )
        print("  ✅ Transactions created")
        
        # 4. Create projects
        print("  Creating projects...")
        projects = [
            ("ERP Modernization", "Upgrading legacy ERP system", "active", 60, "Sprint 3"),
            ("Mobile App", "Customer-facing mobile application", "active", 90, "Final QA"),
            ("API Gateway", "New API gateway implementation", "active", 25, "Design"),
            ("Database Migration", "Move to cloud database", "completed", 100, "Done"),
            ("UI Redesign", "Modern UI overhaul", "paused", 45, "On Hold")
        ]
        
        project_ids = []
        for name, desc, status, progress, phase in projects:
            start_date = datetime.now() - timedelta(days=random.randint(60, 180))
            project_id = await conn.fetchval(
                """
                INSERT INTO projects 
                (tenant_id, name, description, status, progress, current_phase, start_date, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                tenant_id, name, desc, status, progress, phase, start_date, start_date
            )
            if project_id:
                project_ids.append(project_id)
        print(f"  ✅ {len(project_ids)} projects created")
        
        # 5. Create tasks
        print("  Creating tasks...")
        statuses = ['todo', 'in_progress', 'review', 'completed', 'blocked']
        priorities = ['low', 'medium', 'high', 'critical']
        
        for project_id in project_ids:
            for i in range(random.randint(5, 15)):
                assignee = random.choice([u[0] for u in users])
                status = random.choice(statuses)
                
                await conn.execute(
                    """
                    INSERT INTO tasks 
                    (tenant_id, project_id, title, description, status, priority, assignee_id, 
                     due_date, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    tenant_id,
                    project_id,
                    f"Task #{i+1}: Implementation work",
                    f"Detailed description of task {i+1}",
                    status,
                    random.choice(priorities),
                    assignee,
                    datetime.now() + timedelta(days=random.randint(1, 30)),
                    datetime.now() - timedelta(days=random.randint(1, 30))
                )
        print("  ✅ Tasks created")
        
        # 6. Create activities
        print("  Creating activities...")
        activity_types = [
            ('task_completed', 'Completed task: {}'),
            ('task_started', 'Started working on: {}'),
            ('pr_opened', 'Opened pull request: {}'),
            ('deployment', 'Deployed to: {}'),
            ('new_customer', 'New customer signed up: {}'),
        ]
        
        for i in range(20):
            act_type, template = random.choice(activity_types)
            user_id, user_name, _ = random.choice(users)
            
            await conn.execute(
                """
                INSERT INTO activities 
                (tenant_id, actor_id, actor_name, type, description, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                tenant_id,
                user_id,
                user_name,
                act_type,
                template.format(f"Item {i+1}"),
                datetime.now() - timedelta(hours=random.randint(1, 72))
            )
        print("  ✅ Activities created")
        
        # 7. Create team members
        print("  Creating team members...")
        for user_id, name, role in users:
            await conn.execute(
                """
                INSERT INTO team_members 
                (tenant_id, user_id, name, role, workload, tasks_count, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (tenant_id, user_id) DO UPDATE
                SET workload = EXCLUDED.workload, tasks_count = EXCLUDED.tasks_count
                """,
                tenant_id,
                user_id,
                name,
                role,
                random.randint(40, 100),
                random.randint(3, 12),
                datetime.now() - timedelta(days=random.randint(30, 365))
            )
        print("  ✅ Team members created")
        
        # 8. Create objectives
        print("  Creating objectives...")
        objectives = [
            ("Q1 2025: Launch Multi-Tenant SaaS", 80, "on_track"),
            ("Q1 2025: Acquire 100 Customers", 35, "behind"),
            ("Q2 2025: €50K MRR", 10, "on_track"),
            ("Q2 2025: Expand to 3 Countries", 5, "ahead")
        ]
        
        for title, progress, status in objectives:
            await conn.execute(
                """
                INSERT INTO objectives 
                (tenant_id, title, progress, status, target_date, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT DO NOTHING
                """,
                tenant_id,
                title,
                progress,
                status,
                datetime.now() + timedelta(days=random.randint(30, 180)),
                datetime.now() - timedelta(days=random.randint(10, 60))
            )
        print("  ✅ Objectives created")
        
        print("\n🎉 Demo data seeded successfully!")
        print(f"   Tenant: {tenant_id}")
        print(f"   Users: {len(users)}")
        print(f"   Projects: {len(project_ids)}")
        print(f"   Revenue data: Last 12 months")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_demo_data())


