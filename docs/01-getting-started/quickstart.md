# 🚀 Quick Start Guide

## Enterprise 1C AI Development Stack v4.1

### Prerequisites

- ✅ Windows 10/11 (WSL2 recommended) or Linux/macOS
- ✅ Docker Desktop installed and running
- ✅ Python 3.11 or higher
- ✅ Git
- ✅ 16GB RAM minimum (32GB recommended)
- ✅ 50GB free disk space

---

## 📦 Installation (5 minutes)

> 🎬 Нужен формат видео? См. сценарий скринкаста: [INSTALLATION_VIDEO_GUIDE.md](./INSTALLATION_VIDEO_GUIDE.md)

### Step 1: Clone Repository

```bash
git clone https://github.com/DmitrL-dev/1cai-public.git
cd 1cai-public
```

### Step 2: Configure Environment

```bash
# Copy environment template
copy env.example .env

# Edit .env file and set passwords
# Minimum required: POSTGRES_PASSWORD
notepad .env
```

**Important variables to configure:**
- `POSTGRES_PASSWORD` - PostgreSQL database password
- `GITHUB_TOKEN` - For Innovation Engine (optional now)
- `EXTERNAL_AI_API_KEY` - External AI service API key (optional)

### Step 3: Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Start Infrastructure

```bash
# Start Docker services
docker-compose up -d

# Wait ~30 seconds for services to initialize

# Check status
docker-compose ps

# Apply database migrations (one time)
docker-compose run --rm migrations
```

You should see:
- ✅ postgres (healthy)
- ✅ redis (healthy)
- ✅ nginx (running)

### Step 5: Verify Installation

```bash
# Check PostgreSQL
docker-compose exec postgres pg_isready -U admin

# Check Redis
docker-compose exec redis redis-cli ping

# Access PgAdmin (optional)
# Open browser: http://localhost:5050
# Login: admin@1c-ai.local / admin
```

---

## 📁 Prepare 1C Configurations

### Export from 1C:EDT

1. Open your configuration in 1C:EDT
2. **File → Export → Configuration to files**
3. Select XML format
4. Export to: `./1c_configurations/{CONFIG_NAME}/`

Example structure:
```
1c_configurations/
├── DO/           # Документооборот
│   ├── CommonModules/
│   ├── Documents/
│   └── Catalogs/
├── ERP/          # ERP
├── ZUP/          # Зарплата
└── BUH/          # Бухгалтерия
```

---

## ▶️ Run Parser

### Parse All Configurations

```bash
# Activate venv if not active
venv\Scripts\activate

# Run parser
python scripts/parsers/parse_edt_xml.py
```

### Parse Specific Configuration

```bash
# Parse only DO
python scripts/parsers/parse_edt_xml.py DO

# Parse only ERP
python scripts/parsers/parse_edt_xml.py ERP
```

### Check Results

```bash
# Open PgAdmin
# http://localhost:5050

# Connect to database:
# Host: postgres
# Port: 5432
# Database: knowledge_base
# User: admin
# Password: (your POSTGRES_PASSWORD from .env)

# Run query:
SELECT * FROM v_configuration_summary;
```

---

## 🔍 Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **PgAdmin** | http://localhost:5050 | admin@1c-ai.local / admin |
| **PostgreSQL** | localhost:5432 | admin / (your password) |
| **Redis** | localhost:6379 | - |
| **Health Check** | http://localhost/health | - |

---

## 📊 Verify Data

### SQL Queries to Try

```sql
-- Configuration summary
SELECT * FROM v_configuration_summary;

-- List all modules
SELECT 
    c.name as config,
    o.object_type,
    o.name as object,
    m.module_type,
    m.line_count
FROM modules m
JOIN configurations c ON c.id = m.configuration_id
LEFT JOIN objects o ON o.id = m.object_id
ORDER BY m.line_count DESC
LIMIT 20;

-- Top functions by complexity
SELECT * FROM v_complex_functions LIMIT 20;

-- Most used APIs
SELECT * FROM v_top_api_usage LIMIT 20;
```

---

## 🛠️ Common Commands

### Docker Management

```bash
# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f postgres

# Restart services
docker-compose restart

# Stop all services
docker-compose down

# Stop and remove all data (⚠️ WARNING: deletes all data!)
docker-compose down -v
```

### Database Management

```bash
# Access PostgreSQL CLI
docker-compose exec postgres psql -U admin -d knowledge_base

# Backup database
docker-compose exec postgres pg_dump -U admin knowledge_base > backup.sql

# Restore database
docker-compose exec -T postgres psql -U admin knowledge_base < backup.sql
```

---

## ❓ Troubleshooting

### Issue: Docker containers won't start

**Solution:**
```bash
# Check Docker is running
docker ps

# Check Docker Compose logs
docker-compose logs

# Restart Docker Desktop
```

### Issue: PostgreSQL connection refused

**Solution:**
```bash
# Wait 30 seconds after startup
# Check PostgreSQL is healthy
docker-compose ps

# Check logs
docker-compose logs postgres
```

### Issue: Parser fails with "module not found"

**Solution:**
```bash
# Ensure virtual environment is activated
venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Out of memory

**Solution:**
- Increase Docker memory limit in Docker Desktop settings
- Recommended: 8GB for Docker

---

## 🎯 Next Steps

After successful setup:

1. ✅ **Explore data in PgAdmin**
   - Check parsed configurations
   - Run sample queries

2. ✅ **Read documentation**
   - [Architecture Overview](../02-architecture/)
   - [Implementation Plan](../02-architecture/IMPLEMENTATION_PLAN.md)

3. ✅ **Prepare for Stage 1**
   - Review Neo4j setup (coming next)
   - Plan data migration from PostgreSQL

4. ✅ **Join community**
   - GitHub Discussions
   - Report issues

---

## 📞 Get Help

- **GitHub Issues**: [Report bugs](https://github.com/DmitrL-dev/1cai-public/issues)
- **Discussions**: [Ask questions](https://github.com/DmitrL-dev/1cai-public/discussions)
- **Documentation**: [Full docs](../)

---

## ✅ Success Checklist

- [ ] Docker services running (postgres, redis, nginx)
- [ ] PostgreSQL accessible (PgAdmin works)
- [ ] 1C configurations exported to `./1c_configurations/`
- [ ] Parser executed successfully
- [ ] Data visible in PgAdmin
- [ ] Sample queries return results

---

**Congratulations! 🎉 Your Enterprise 1C AI Development Stack is running!**

**Current Status:** Stage 0 complete (Week 1/30)  
**Next:** Stage 1 - Neo4j & Qdrant integration




