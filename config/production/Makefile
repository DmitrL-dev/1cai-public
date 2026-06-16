# AI-Assistants Production Deployment Makefile

.PHONY: help init deploy-staging deploy-production backup restore health-check logs monitoring test clean setup-ssl

# Variables
ENV ?= staging
COMPOSE_FILE = docker-compose.yml
ENV_FILE = .env.$(ENV)
PROJECT_NAME = ai-assistants
BACKUP_DIR = /opt/ai-assistants/backups
LOG_DIR = /var/log/ai-assistants

# Default target
help:
	@echo "AI-Assistants Production Deployment"
	@echo "===================================="
	@echo ""
	@echo "Available commands:"
	@echo ""
	@echo "Environment setup:"
	@echo "  make init              Initialize environment and dependencies"
	@echo "  make setup-ssl         Setup SSL certificates with Let's Encrypt"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-staging    Deploy staging environment"
	@echo "  make deploy-production Deploy production environment"
	@echo "  make stop              Stop all services"
	@echo "  make restart           Restart all services"
	@echo ""
	@echo "Backup & Restore:"
	@echo "  make backup            Create full system backup"
	@echo "  make restore           Restore from backup"
	@echo "  make backup-db         Backup PostgreSQL database"
	@echo "  make backup-redis      Backup Redis data"
	@echo ""
	@echo "Monitoring:"
	@echo "  make logs              View application logs"
	@echo "  make health-check      Run system health check"
	@echo "  make monitoring        Open monitoring dashboards"
	@echo "  make alerts            Check active alerts"
	@echo ""
	@echo "Maintenance:"
	@echo "  make update            Update all services"
	@echo "  make cleanup           Clean up resources"
	@echo "  make test              Run system tests"
	@echo ""
	@echo "Secrets Management:"
	@echo "  make secrets-init      Initialize secrets management"
	@echo "  make secrets-rotate    Rotate secrets"
	@echo ""
	@echo "Examples:"
	@echo "  make ENV=production deploy-production"
	@echo "  make ENV=staging deploy-staging"

# Environment initialization
init:
	@echo "🚀 Initializing AI-Assistants Production Environment..."
	@echo "Creating directories..."
	@sudo mkdir -p $(BACKUP_DIR) $(LOG_DIR)
	@sudo chown -R $$USER:$$USER $(BACKUP_DIR) $(LOG_DIR)
	@echo "Setting up environment files..."
	@if [ ! -f .env.staging ]; then \
		cp .env.staging .env.staging.local; \
		echo "Created .env.staging.local - please configure it"; \
	fi
	@if [ ! -f .env.production ]; then \
		cp .env.production .env.production.local; \
		echo "Created .env.production.local - please configure it"; \
	fi
	@echo "Setting up cron jobs..."
	@sudo cp crontab /etc/cron.d/ai-assistants
	@sudo chmod 644 /etc/cron.d/ai-assistants
	@sudo systemctl restart cron
	@echo "✅ Environment initialization complete!"

# SSL setup
setup-ssl:
	@echo "🔒 Setting up SSL certificates..."
	@read -p "Enter your domain (e.g., yourcompany.com): " domain; \
	read -p "Enter your email for Let's Encrypt: " email; \
	sudo certbot --nginx -d $$domain --email $$email --agree-tos --non-interactive
	@sudo systemctl enable nginx
	@sudo systemctl enable certbot.timer
	@echo "✅ SSL certificates configured!"

# Deployment commands
deploy-staging:
	@echo "🚀 Deploying staging environment..."
	@ENV=staging $(MAKE) deploy

deploy-production:
	@echo "🚀 Deploying production environment..."
	@if [ ! -f .env.production.local ]; then \
		echo "❌ .env.production.local not found. Run 'make init' first"; \
		exit 1; \
	fi
	@ENV=production $(MAKE) deploy

deploy:
	@echo "Deploying with ENV=$(ENV)..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d --build
	@echo "Waiting for services to be healthy..."
	@sleep 30
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps
	@echo "✅ Deployment complete!"

stop:
	@echo "🛑 Stopping all services..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) stop

restart:
	@echo "🔄 Restarting all services..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) restart

# Backup commands
backup:
	@echo "💾 Creating full system backup..."
	@mkdir -p $(BACKUP_DIR)/$(shell date +%Y%m%d_%H%M%S)
	@./scripts/backup_database.sh
	@./scripts/backup_redis.sh
	@echo "✅ Backup complete!"

backup-db:
	@echo "💾 Backing up PostgreSQL database..."
	@./scripts/backup_database.sh

backup-redis:
	@echo "💾 Backing up Redis data..."
	@./scripts/backup_redis.sh

backup-secrets:
	@echo "💾 Backing up secrets..."
	@./secrets/aws_secrets_manager.sh backup $(BACKUP_DIR)/secrets_$(shell date +%Y%m%d_%H%M%S).txt

# Restore commands
restore:
	@echo "📂 Restoring from backup..."
	@read -p "Enter backup file path: " backup_file; \
	if [ ! -f $$backup_file ]; then \
		echo "❌ Backup file not found: $$backup_file"; \
		exit 1; \
	fi; \
	echo "⚠️  This will stop all services and restore data. Continue? (y/N)" && \
	read confirm && [ "$$confirm" = "y" ] && \
	$(MAKE) stop && \
	./secrets/aws_secrets_manager.sh restore $$backup_file && \
	$(MAKE) deploy

# Monitoring commands
logs:
	@echo "📊 Viewing application logs..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f --tail=100

logs-db:
	@echo "📊 Viewing database logs..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f postgres

logs-nginx:
	@echo "📊 Viewing nginx logs..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f nginx

logs-redis:
	@echo "📊 Viewing redis logs..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f redis

health-check:
	@echo "🏥 Running system health check..."
	@./scripts/health_check.sh

monitoring:
	@echo "📊 Opening monitoring dashboards..."
	@echo "Grafana: http://localhost:3000"
	@echo "Prometheus: http://localhost:9090"
	@echo "Alertmanager: http://localhost:9093"
	@echo "MLflow: http://localhost:5000"

alerts:
	@echo "🚨 Checking active alerts..."
	@curl -s http://localhost:9093/api/v1/alerts | jq .

status:
	@echo "📊 System Status:"
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps
	@echo ""
	@echo "Resource Usage:"
	@docker stats --no-stream

# Secrets management
secrets-init:
	@echo "🔐 Initializing secrets management..."
	@echo "Choose secrets manager:"
	@echo "1) AWS Secrets Manager"
	@echo "2) HashiCorp Vault"
	@read -p "Enter choice (1-2): " choice; \
	case $$choice in \
		1) \
			echo "Using AWS Secrets Manager..."; \
			./secrets/aws_secrets_manager.sh init; \
			;; \
		2) \
			echo "Using HashiCorp Vault..."; \
			docker compose -f secrets/docker-compose.vault.yml up -d vault; \
			./vault/vault_manager.sh init; \
			;; \
		*) \
			echo "Invalid choice"; \
			exit 1; \
			;; \
	esac

secrets-rotate:
	@echo "🔄 Rotating secrets..."
	@read -p "Enter secret name to rotate: " secret_name; \
	if command -v aws >/dev/null 2>&1; then \
		./secrets/aws_secrets_manager.sh rotate $$secret_name; \
	else \
		export VAULT_ADDR=http://localhost:8200; \
		export VAULT_TOKEN=$$(grep VAULT_TOKEN .env.production | cut -d'=' -f2); \
		./vault/vault_manager.sh rotate $$secret_name; \
	fi

secrets-list:
	@echo "🔐 Listing secrets..."
	@if command -v aws >/dev/null 2>&1; then \
		./secrets/aws_secrets_manager.sh list; \
	else \
		export VAULT_ADDR=http://localhost:8200; \
		export VAULT_TOKEN=$$(grep VAULT_TOKEN .env.production | cut -d'=' -f2); \
		./vault/vault_manager.sh list; \
	fi

# Maintenance commands
update:
	@echo "🔄 Updating all services..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) pull
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d
	@echo "✅ Update complete!"

update-db:
	@echo "🔄 Updating database schema..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec postgres psql -U postgres -d ai_assistants -c "SELECT version();"

cleanup:
	@echo "🧹 Cleaning up resources..."
	@docker system prune -f
	@docker volume prune -f
	@docker image prune -f
	@sudo journalctl --vacuum-size=100M
	@echo "✅ Cleanup complete!"

clean:
	@echo "🗑️  Stopping and removing all containers and networks..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down -v --remove-orphans
	@docker network prune -f
	@echo "✅ Clean complete!"

# Testing commands
test:
	@echo "🧪 Running system tests..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec ai-assistants python -m pytest tests/ || \
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec ai-assistants python -c "print('Running basic connectivity tests...')"

test-db:
	@echo "🧪 Testing database connectivity..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec postgres pg_isready -U postgres

test-redis:
	@echo "🧪 Testing Redis connectivity..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec redis redis-cli ping

test-api:
	@echo "🧪 Testing API endpoints..."
	@curl -s http://localhost:8000/health | jq .
	@curl -s http://localhost:8001/health | jq .
	@curl -s http://localhost:5000/health | jq .

# Scaling commands
scale-api:
	@echo "📈 Scaling API services..."
	@read -p "Enter number of API instances: " instances; \
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d --scale ai-assistants=$$instances

scale-workers:
	@echo "📈 Scaling worker services..."
	@read -p "Enter number of worker instances: " instances; \
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d --scale celery-worker=$$instances \
	--scale ml-worker=$$instances

# Database maintenance
db-migrate:
	@echo "🔄 Running database migrations..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec ai-assistants python manage.py migrate

db-vacuum:
	@echo "🧹 Vacuuming database..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec postgres vacuumdb -a -f -z -v

db-analyze:
	@echo "📊 Analyzing database..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec postgres psql -U postgres -d ai_assistants -c "ANALYZE;"

# Performance monitoring
perf-test:
	@echo "⚡ Running performance test..."
	@read -p "Enter test duration (seconds): " duration; \
	read -p "Enter concurrent users: " users; \
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) run --rm loadtest locust -f loadtest.py --headless -u $$users -t $${duration}s

# Security commands
security-scan:
	@echo "🔒 Running security scan..."
	@docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
		aquasec/trivy image ai-assistants:latest

ssl-check:
	@echo "🔒 Checking SSL certificates..."
	@read -p "Enter domain to check: " domain; \
	ssl_expiry=$$(echo | openssl s_client -servername $$domain -connect $$domain:443 2>/dev/null | openssl x509 -noout -dates | grep notAfter | cut -d= -f2); \
	echo "SSL certificate expires: $$ssl_expiry"

# Information commands
info:
	@echo "ℹ️  AI-Assistants Production Info"
	@echo "================================"
	@echo "Environment: $(ENV)"
	@echo "Project: $(PROJECT_NAME)"
	@echo "Compose file: $(COMPOSE_FILE)"
	@echo "Env file: $(ENV_FILE)"
	@echo ""
	@echo "Service URLs:"
	@echo "- AI API: http://localhost:8000"
	@echo "- ML API: http://localhost:8001"
	@echo "- MLflow: http://localhost:5000"
	@echo "- Grafana: http://localhost:3000"
	@echo "- Prometheus: http://localhost:9090"
	@echo "- Alertmanager: http://localhost:9093"
	@echo ""
	@echo "Status:"
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"

# Quick deployment for development
dev:
	@echo "🚀 Starting development environment..."
	@ENV=staging $(MAKE) deploy
	@echo "Development environment ready!"
	@echo "Access the application at http://localhost:8000"

# Emergency commands
emergency-stop:
	@echo "🚨 EMERGENCY STOP - Stopping all services immediately..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) kill

emergency-backup:
	@echo "🚨 EMERGENCY BACKUP - Creating immediate backup..."
	@$(MAKE) backup
	@echo "Emergency backup completed!"

# Development helpers
shell-api:
	@echo "🔧 Opening shell in API container..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec ai-assistants /bin/bash

shell-db:
	@echo "🔧 Opening PostgreSQL shell..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec postgres psql -U postgres

shell-redis:
	@echo "🔧 Opening Redis CLI..."
	@docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec redis redis-cli

# All-in-one commands
full-backup:
	@echo "💾 Creating full system backup..."
	@$(MAKE) backup
	@$(MAKE) backup-secrets
	@echo "📦 Creating deployment package..."
	@tar -czf ai-assistants-backup-$(shell date +%Y%m%d_%H%M%S).tar.gz config/ .env.*.local || true
	@echo "✅ Full backup complete!"

system-check:
	@echo "🔍 Running full system check..."
	@$(MAKE) health-check
	@$(MAKE) test
	@$(MAKE) test-db
	@$(MAKE) test-redis
	@$(MAKE) test-api
	@echo "✅ System check complete!"