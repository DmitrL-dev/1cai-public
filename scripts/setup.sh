#!/bin/bash

# Enterprise 1C AI Development Stack
# Initial Setup Script

set -e  # Exit on error

echo "=================================================="
echo "  Enterprise 1C AI Development Stack"
echo "  Initial Setup"
echo "=================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "Checking prerequisites..."

# Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker Desktop.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker installed${NC}"

# Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose installed${NC}"

# Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found.${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} installed${NC}"

# Git
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git not found.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Git installed${NC}"

echo ""
echo "Creating project structure..."

# Create directories
mkdir -p 1c_configurations/{DO,ERP,ZUP,BUH}
mkdir -p knowledge_base
mkdir -p logs
mkdir -p db/init
mkdir -p nginx/ssl
mkdir -p src/{api,ai,parsers,services,utils}
mkdir -p edt-plugin/src
mkdir -p innovation-engine/{discovery,analysis,reporting}
mkdir -p k8s/{deployments,services,configmaps,secrets}
mkdir -p terraform
mkdir -p docs/{architecture,deployment,user-guide,api-reference}
mkdir -p tests/{unit,integration,e2e}

# Create .gitkeep files
find . -type d -empty -exec touch {}/.gitkeep \;

echo -e "${GREEN}✓ Project structure created${NC}"

# Setup .env
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp env.example .env
    echo -e "${YELLOW}⚠ Please edit .env file and configure your credentials${NC}"
fi

# Python virtual environment
echo ""
echo "Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate venv and install dependencies
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null

echo "Installing Python dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Docker setup
echo ""
echo "Starting Docker services..."

docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

# Check service health
echo ""
echo "Checking service health..."

# PostgreSQL
if docker-compose exec -T postgres pg_isready -U admin > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
else
    echo -e "${YELLOW}⚠ PostgreSQL might need more time to initialize${NC}"
fi

# Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis is ready${NC}"
else
    echo -e "${YELLOW}⚠ Redis might need more time${NC}"
fi

echo ""
echo "=================================================="
echo -e "${GREEN}✓ Setup completed successfully!${NC}"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env file with your credentials"
echo "  2. Run: source venv/bin/activate"
echo "  3. Place 1C configurations in ./1c_configurations/"
echo "  4. Run parser: python parse_edt_xml.py"
echo ""
echo "Access services:"
echo "  - PostgreSQL: localhost:5432"
echo "  - PgAdmin: http://localhost:5050"
echo "  - Redis: localhost:6379"
echo ""
echo "View logs: docker-compose logs -f"
echo "Stop services: docker-compose down"
echo ""







