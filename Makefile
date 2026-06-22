# Makefile for Enterprise 1C AI Development Stack
# Quick commands for common tasks

.PHONY: help install install-dev prod-up prod-down prod-logs test docker-up docker-down migrate clean train-ml eval-ml train-ml-demo eval-ml-demo scrape-its render-uml render-uml-svg adr-new test-bsl export-context generate-docs bsl-ls-up bsl-ls-down bsl-ls-logs feature-init feature-validate release-notes release-tag release-push smoke-tests check-runtime kind-up kind-down helm-deploy terraform-apply terraform-destroy policy-check gitops-apply gitops-sync ba-extract audit-hidden-dirs audit-secrets security-audit validate-standards

CONFIG ?= ERPCPM
EPOCHS ?=
LIMIT ?= 20
BASE_MODEL ?=
ITS_START_URL ?= https://its.1c.ru/db/cabinetdoc
ITS_OUTPUT ?= output/its-scraper
ITS_FORMATS ?= json markdown
ITS_CONCURRENCY ?=
ITS_SLEEP ?=
ITS_PROXY ?=
ITS_USER_AGENT_FILE ?=

help:
	@echo "Enterprise 1C AI Development Stack - Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make install          - Install Python dependencies"
	@echo "  make install-dev      - Install dev dependencies + main"
	@echo "  make check-runtime    - Ensure Python 3.11 runtime is available"
	@echo "  make kind-up          - Start local kind cluster (infrastructure/kind/cluster.yaml)"
	@echo "  make kind-down        - Delete local kind cluster"
	@echo "  make helm-deploy      - Deploy 1cai via Helm chart (infrastructure/helm/1cai-stack)"
	@echo "  make helm-observability- Deploy observability stack (prometheus+loki+tempo+grafana)"
	@echo "  make terraform-apply  - Apply Terraform stack (namespace + Helm release)"
	@echo "  make terraform-destroy - Destroy Terraform resources"
	@echo "  make policy-check     - Run policy-as-code checks (Conftest + Semgrep)"
	@echo "  make gitops-apply     - Apply Argo CD manifests (Kustomize)"
	@echo "  make gitops-sync      - Trigger Argo CD sync (requires argocd CLI/token)"
	@echo "  make mesh-istio-apply - Apply IstioOperator profile via kubectl"
	@echo "  make chaos-litmus-run - Apply Litmus chaos experiment (pod-delete, EXPERIMENT=network для latency)"
	@echo "  make preflight        - Run self-control checklist before deploy"
	@echo "  make vault-csi-apply  - Apply Vault CSI SecretProviderClass + example"
	@echo "  make linkerd-install  - Install Linkerd control plane"
	@echo "  make finops-slack     - Send AWS/Azure cost reports to Slack/Teams"
	@echo "  make azure-keyvault   - Provision Azure Key Vault via Terraform"
	@echo "  make vault-test       - Validate Vault/Kubernetes secrets"
	@echo ""
	@echo "Docker:"
	@echo "  make prod-up          - Build & start production rentgen app (docker-compose.prod.yml)"
	@echo "  make prod-down        - Stop production rentgen app"
	@echo "  make prod-logs        - Tail production rentgen logs"
	@echo "  make docker-up        - Start all Docker services"
	@echo "  make docker-down      - Stop all Docker services"
	@echo "  make docker-logs      - View Docker logs"
	@echo "  make docker-clean     - Remove all Docker volumes (⚠️  deletes data!)"
	@echo "  make bsl-ls-up        - Start the bsl-language-server (docker-compose.dev.yml)"
	@echo "  make bsl-ls-down      - Stop the bsl-language-server"
	@echo "  make bsl-ls-logs      - Tail logs from bsl-language-server"
	@echo "  make bsl-ls-check     - Run health/parse check against bsl-language-server"
	@echo ""
	@echo "Migration:"
	@echo "EDT Plugin:"
	@echo "  make plugin-build     - Build EDT plugin"
	@echo "  make plugin-install   - Build and install to EDT"
	@echo ""
	@echo "AI Models:"
	@echo "  make ollama-pull      - Download Qwen3-Coder model"
	@echo "  make ollama-list      - List installed models"
	@echo ""
	@echo "ML:"
	@echo "  make train-ml         - Train neural pipeline (CONFIG=$(CONFIG), EPOCHS=$(if $(EPOCHS),$(EPOCHS),default))"
	@echo "  make eval-ml          - Evaluate dataset (CONFIG=$(CONFIG), LIMIT=$(LIMIT))"
	@echo ""
	@echo "ML Demos:"
	@echo "  make train-ml-demo    - Run demo training preset (DEMO)"
	@echo "  make eval-ml-demo     - Evaluate demo preset (DEMO)"
	@echo ""
	@echo "Utilities:"
	@echo "  make status           - Show project status"
	@echo "  make clean            - Clean temporary files"
	@echo "  make audit-hidden-dirs- Report tracked hidden directories (.folder rule)"
	@echo "  make audit-secrets    - Run lightweight secret scan (scripts/audit/check_secrets.py)"
	@echo "  make security-audit   - Run full security audit (hidden dirs, secrets, git safety, comprehensive audit)"
	@echo "  make validate-standards - Validate Scenario DSL / Autonomy Policy schemas against example data"
	@echo "  make scrape-its       - Run ITS scraper (ITS_START_URL, ITS_OUTPUT, ITS_FORMATS, ITS_CONCURRENCY, ITS_SLEEP, ITS_PROXY, ITS_USER_AGENT_FILE)"
	@echo "  make render-uml       - Render all PlantUML diagrams to PNG"
	@echo "  make render-uml-svg   - Render PlantUML diagrams to PNG + SVG"
	@echo "  make ba-extract FILE=path [OUTPUT=out.json DOC_TYPE=tz] - Extract requirements via BA агент"
	@echo "  make adr-new SLUG=... - Create a new Architecture Decision Record"
	@echo "  make feature-init FEATURE=slug - Create spec-driven feature scaffold"
	@echo "  make feature-validate [FEATURE=slug] - Validate filled spec-driven documents"
	@echo "  make release-notes VERSION=vX.Y.Z - Generate release notes"

feature-validate:
ifdef FEATURE
	python scripts/research/check_feature.py --feature $(FEATURE)
else
	python scripts/research/check_feature.py
endif

release-notes:
ifndef VERSION
	$(error VERSION is required, e.g. make release-notes VERSION=v5.2.0)
endif
	python scripts/release/create_release.py --version $(VERSION)

release-tag: release-notes
	python scripts/release/create_release.py --version $(VERSION) --tag

release-push: release-notes
	python scripts/release/create_release.py --version $(VERSION) --tag --push

smoke-tests:
	python scripts/testing/smoke_healthcheck.py

smoke-up:
	docker compose up -d smoke-api
	@echo "Waiting for smoke-api to become healthy..."
	docker compose wait smoke-api
	@echo "Smoke API ready on http://localhost:8080/health"

smoke-down:
	docker compose down smoke-api

observability-up:
	docker compose -f observability/docker-compose.observability.yml up -d
	docker compose -f observability/docker-compose.observability.yml ps
	@echo "Prometheus: http://localhost:9090, Grafana: http://localhost:3000 (user: admin, password: admin)"

observability-down:
	docker compose -f observability/docker-compose.observability.yml down

kind-up:
	kind create cluster --config infrastructure/kind/cluster.yaml || true

kind-down:
	kind delete cluster --name 1cai-devops || true

helm-deploy:
	helm upgrade --install 1cai infrastructure/helm/1cai-stack \
	  --namespace 1cai --create-namespace \
	  -f infrastructure/helm/1cai-stack/values.yaml

helm-observability:
	helm upgrade --install observability infrastructure/helm/observability-stack \
	  --namespace observability --create-namespace \
	  -f infrastructure/helm/observability-stack/values.yaml

terraform-apply:
	cd infrastructure/terraform && terraform init && terraform apply -auto-approve

terraform-destroy:
	cd infrastructure/terraform && terraform destroy -auto-approve

policy-check:
	bash scripts/security/run_policy_checks.sh

gitops-apply:
	bash scripts/gitops/apply.sh

gitops-sync:
	bash scripts/gitops/sync.sh

ba-extract:
ifndef FILE
	$(error FILE is required, e.g. make ba-extract FILE=docs/sample.docx)
endif
	python -m scripts.ba.requirements_cli extract $(FILE) $(if $(DOC_TYPE),--document-type $(DOC_TYPE),) $(if $(OUTPUT),--output $(OUTPUT),)

mesh-istio-apply:
	kubectl apply -k infrastructure/service-mesh/istio

chaos-litmus-run:
	bash scripts/chaos/run_litmus.sh

preflight:
	bash scripts/checklists/preflight.sh

vault-csi-apply:
	bash scripts/secrets/apply_vault_csi.sh

linkerd-install:
	linkerd install | kubectl apply -f -
	linkerd viz install | kubectl apply -f -

finops-slack:
	pip install --quiet boto3 requests azure-identity azure-mgmt-costmanagement >/dev/null
	SLACK_WEBHOOK_URL=$(SLACK_WEBHOOK_URL) TEAMS_WEBHOOK_URL=$(TEAMS_WEBHOOK_URL) \
	AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY) \
	python scripts/finops/aws_cost_to_slack.py || true
	SLACK_WEBHOOK_URL=$(SLACK_WEBHOOK_URL) TEAMS_WEBHOOK_URL=$(TEAMS_WEBHOOK_URL) \
	AZURE_TENANT_ID=$(AZURE_TENANT_ID) AZURE_CLIENT_ID=$(AZURE_CLIENT_ID) \
	AZURE_CLIENT_SECRET=$(AZURE_CLIENT_SECRET) AZURE_SUBSCRIPTION_ID=$(AZURE_SUBSCRIPTION_ID) \
	python scripts/finops/azure_cost_to_slack.py || true
	if [ -n "$(AWS_BUDGET_NAMES)" ]; then \
	  SLACK_WEBHOOK_URL=$(SLACK_WEBHOOK_URL) TEAMS_WEBHOOK_URL=$(TEAMS_WEBHOOK_URL) \
	  AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY) \
	  AWS_ACCOUNT_ID=$(AWS_ACCOUNT_ID) AWS_BUDGET_NAMES=$(AWS_BUDGET_NAMES) \
	  python scripts/finops/aws_budget_check.py || true; fi

azure-keyvault:
	cd infrastructure/terraform/azure-keyvault && terraform init && terraform apply -auto-approve \
	  -var="subscription_id=$(AZURE_SUBSCRIPTION_ID)" \
	  -var="tenant_id=$(AZURE_TENANT_ID)" \
	  -var="resource_group_name=$(AZURE_KV_RG)" \
	  -var="location=$(AZURE_KV_LOCATION)" \
	  -var="key_vault_name=$(AZURE_KV_NAME)"

vault-test:
	VAULT_ADDR=$(VAULT_ADDR) VAULT_TOKEN=$(VAULT_TOKEN) bash scripts/secrets/test_vault_sync.sh

linkerd-smoke:
	bash scripts/service_mesh/linkerd/ci_smoke.sh

linkerd-rotate-certs:
	bash scripts/service_mesh/linkerd/rotate_certs.sh

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# Production deploy — single rentgen app service (SQLite product path)
prod-up:
	docker compose -f docker-compose.prod.yml up -d --build

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f

validate-standards:
	python scripts/validation/validate_scenarios_against_schema.py
	python scripts/validation/check_conformance_report.py
	python scripts/validation/validate_code_graph_against_schema.py

# CLI Tools
CLI_BASE_URL ?= http://localhost:8000

cli-query:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) query "$(TEXT)"

cli-scenarios:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) scenarios

cli-recommend:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) recommend "$(QUERY)" --max $(MAX)

cli-impact:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) impact $(NODE_IDS) --max-depth $(MAX_DEPTH)

cli-health:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) health

cli-cache-metrics:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) cache metrics

cli-cache-invalidate:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) cache invalidate --clear-all

cli-llm-providers:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) llm-providers list

cli-llm-select:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) llm-providers select $(QUERY_TYPE) --max-cost $(MAX_COST) --max-latency $(MAX_LATENCY) --compliance $(COMPLIANCE) --risk-level $(RISK_LEVEL)

# Docker
docker-up:
	docker-compose -f docker-compose.yml up -d
	@echo "Waiting for services to start..."
	@sleep 10
	docker-compose ps

docker-down:
	docker-compose -f docker-compose.yml down

docker-logs:
	docker-compose -f docker-compose.yml logs -f

docker-clean:
	docker-compose -f docker-compose.yml down -v
	@echo "⚠️  All data deleted!"


# bsl-language-server helpers
bsl-ls-up:
	docker-compose -f docker-compose.dev.yml up -d bsl-language-server

bsl-ls-down:
	docker-compose -f docker-compose.dev.yml stop bsl-language-server

bsl-ls-logs:
	docker-compose -f docker-compose.dev.yml logs -f bsl-language-server

bsl-ls-check:
	python scripts/parsers/check_bsl_language_server.py

# Migration
migrate: migrate-pg migrate-neo4j migrate-qdrant

migrate-pg:
	python migrate_json_to_postgres.py

migrate-neo4j:
	python migrate_postgres_to_neo4j.py

migrate-qdrant:
	python migrate_to_qdrant.py

# Testing
test:
	pytest

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v -m integration

coverage:
	pytest --cov=src --cov-report=html --cov-report=term
	@echo "Coverage report: htmlcov/index.html"

# Code Quality
format:
	black src/ tests/
	isort src/ tests/

lint:
	flake8 src/ tests/ --max-line-length=120
	mypy src/ --ignore-missing-imports

quality: format lint test

# API Servers
api:
	python -m uvicorn src.api.graph_api:app --host 0.0.0.0 --port 8080 --reload

mcp:
	python -m uvicorn src.ai.mcp_server:app --host 0.0.0.0 --port 6001 --reload

servers:
	@echo "Starting API servers in background..."
	python -m uvicorn src.api.graph_api:app --host 0.0.0.0 --port 8080 &
	python -m uvicorn src.ai.mcp_server:app --host 0.0.0.0 --port 6001 &

# EDT Plugin
plugin-build:
	cd edt-plugin && mvn clean package

plugin-install: plugin-build
	@echo "Install manually: Help → Install New Software → Local → edt-plugin/target/repository"

# AI Models
ollama-pull:
	docker-compose exec ollama ollama pull qwen2.5-coder:7b

ollama-pull-large:
	docker-compose exec ollama ollama pull qwen2.5-coder:32b

ollama-list:
	docker-compose exec ollama ollama list

# Utilities
status:
	@echo "=== Docker Services ==="
	@docker-compose ps
	@echo ""
	@echo "=== PostgreSQL ==="
	@docker-compose exec postgres pg_isready -U admin || echo "Not running"
	@echo ""
	@echo "=== Neo4j ==="
	@curl -s http://localhost:7474 > /dev/null && echo "✓ Running" || echo "✗ Not running"
	@echo ""
	@echo "=== Qdrant ==="
	@curl -s http://localhost:6333/readyz > /dev/null && echo "✓ Running" || echo "✗ Not running"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	rm -rf htmlcov/ coverage.xml .coverage
	@echo "✓ Cleaned temporary files"

scrape-its:
	python -m integrations.its_scraper scrape $(ITS_START_URL) --output $(ITS_OUTPUT) $(foreach fmt,$(ITS_FORMATS), --format $(fmt)) $(if $(ITS_CONCURRENCY), --concurrency $(ITS_CONCURRENCY),) $(if $(ITS_SLEEP), --sleep $(ITS_SLEEP),) $(if $(ITS_PROXY), --proxy $(ITS_PROXY),) $(if $(ITS_USER_AGENT_FILE), --user-agent-file $(ITS_USER_AGENT_FILE),)

render-uml:
	python scripts/docs/render_uml.py --fail-on-missing

render-uml-svg:
	python scripts/docs/render_uml.py --format png --format svg --fail-on-missing

adr-new:
ifndef SLUG
	$(error "Usage: make adr-new SLUG=my-decision")
endif
	python scripts/docs/create_adr.py $(SLUG)

test-bsl:
	python scripts/tests/run_bsl_tests.py

export-context:
	python scripts/context/export_platform_context.py

generate-docs:
	python scripts/context/generate_docs.py

audit-hidden-dirs:
	python scripts/audit/check_hidden_dirs.py --fail-new

audit-secrets:
	@mkdir -p analysis 2>/dev/null || true
	python scripts/audit/check_secrets.py --json > analysis/secret_scan_report.json

security-audit: audit-hidden-dirs audit-secrets
	python scripts/audit/check_git_safety.py
	python scripts/audit/comprehensive_project_audit.py

train-ml:
	@python scripts/ml/config_utils.py --info $(CONFIG)
	python scripts/run_neural_training.py $(if $(EPOCHS),--epochs $(EPOCHS),)

eval-ml:
	python scripts/eval/eval_model.py --config-name $(CONFIG) --limit $(LIMIT)
python scripts/validation/validate_scenarios_against_schema.py
python scripts/validation/check_conformance_report.py
python scripts/validation/validate_code_graph_against_schema.py

# CLI Tools
CLI_BASE_URL ?= http://localhost:8000

cli-query:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) query "$(TEXT)"

cli-scenarios:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) scenarios

cli-recommend:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) recommend "$(QUERY)" --max $(MAX)

cli-impact:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) impact $(NODE_IDS) --max-depth $(MAX_DEPTH)

cli-health:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) health

cli-cache-metrics:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) cache metrics

cli-cache-invalidate:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) cache invalidate --clear-all

cli-llm-providers:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) llm-providers list

cli-llm-select:
	@python scripts/cli/1cai_cli.py --base-url $(CLI_BASE_URL) llm-providers select $(QUERY_TYPE) --max-cost $(MAX_COST) --max-latency $(MAX_LATENCY) --compliance $(COMPLIANCE) --risk-level $(RISK_LEVEL)

# Docker
docker-up:
	docker-compose -f docker-compose.yml up -d
	@echo "Waiting for services to start..."
	@sleep 10
	docker-compose ps

docker-down:
	docker-compose -f docker-compose.yml down

docker-logs:
	docker-compose -f docker-compose.yml logs -f

docker-clean:
	docker-compose -f docker-compose.yml down -v
	@echo "⚠️  All data deleted!"


# bsl-language-server helpers
bsl-ls-up:
	docker-compose -f docker-compose.dev.yml up -d bsl-language-server

bsl-ls-down:
	docker-compose -f docker-compose.dev.yml stop bsl-language-server

bsl-ls-logs:
	docker-compose -f docker-compose.dev.yml logs -f bsl-language-server

bsl-ls-check:
	python scripts/parsers/check_bsl_language_server.py

# Migration
migrate: migrate-pg migrate-neo4j migrate-qdrant

migrate-pg:
	python migrate_json_to_postgres.py

migrate-neo4j:
	python migrate_postgres_to_neo4j.py

migrate-qdrant:
	python migrate_to_qdrant.py

# Testing
test:
	pytest

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v -m integration

coverage:
	pytest --cov=src --cov-report=html --cov-report=term
	@echo "Coverage report: htmlcov/index.html"

# Code Quality
format:
	black src/ tests/
	isort src/ tests/

lint:
	flake8 src/ tests/ --max-line-length=120
	mypy src/ --ignore-missing-imports

quality: format lint test

# API Servers
api:
	python -m uvicorn src.api.graph_api:app --host 0.0.0.0 --port 8080 --reload

mcp:
	python -m uvicorn src.ai.mcp_server:app --host 0.0.0.0 --port 6001 --reload

servers:
	@echo "Starting API servers in background..."
	python -m uvicorn src.api.graph_api:app --host 0.0.0.0 --port 8080 &
	python -m uvicorn src.ai.mcp_server:app --host 0.0.0.0 --port 6001 &

# EDT Plugin
plugin-build:
	cd edt-plugin && mvn clean package

plugin-install: plugin-build
	@echo "Install manually: Help → Install New Software → Local → edt-plugin/target/repository"

# AI Models
ollama-pull:
	docker-compose exec ollama ollama pull qwen2.5-coder:7b

ollama-pull-large:
	docker-compose exec ollama ollama pull qwen2.5-coder:32b

ollama-list:
	docker-compose exec ollama ollama list

# Utilities
status:
	@echo "=== Docker Services ==="
	@docker-compose ps
	@echo ""
	@echo "=== PostgreSQL ==="
	@docker-compose exec postgres pg_isready -U admin || echo "Not running"
	@echo ""
	@echo "=== Neo4j ==="
	@curl -s http://localhost:7474 > /dev/null && echo "✓ Running" || echo "✗ Not running"
	@echo ""
	@echo "=== Qdrant ==="
	@curl -s http://localhost:6333/readyz > /dev/null && echo "✓ Running" || echo "✗ Not running"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	rm -rf htmlcov/ coverage.xml .coverage
	@echo "✓ Cleaned temporary files"

scrape-its:
	python -m integrations.its_scraper scrape $(ITS_START_URL) --output $(ITS_OUTPUT) $(foreach fmt,$(ITS_FORMATS), --format $(fmt)) $(if $(ITS_CONCURRENCY), --concurrency $(ITS_CONCURRENCY),) $(if $(ITS_SLEEP), --sleep $(ITS_SLEEP),) $(if $(ITS_PROXY), --proxy $(ITS_PROXY),) $(if $(ITS_USER_AGENT_FILE), --user-agent-file $(ITS_USER_AGENT_FILE),)

render-uml:
	python scripts/docs/render_uml.py --fail-on-missing

render-uml-svg:
	python scripts/docs/render_uml.py --format png --format svg --fail-on-missing

adr-new:
ifndef SLUG
	$(error "Usage: make adr-new SLUG=my-decision")
endif
	python scripts/docs/create_adr.py $(SLUG)

test-bsl:
	python scripts/tests/run_bsl_tests.py

export-context:
	python scripts/context/export_platform_context.py

generate-docs:
	python scripts/context/generate_docs.py

audit-hidden-dirs:
	python scripts/audit/check_hidden_dirs.py --fail-new

audit-secrets:
	@mkdir -p analysis 2>/dev/null || true
	python scripts/audit/check_secrets.py --json > analysis/secret_scan_report.json

security-audit: audit-hidden-dirs audit-secrets
	python scripts/audit/check_git_safety.py
	python scripts/audit/comprehensive_project_audit.py

train-ml:
	@python scripts/ml/config_utils.py --info $(CONFIG)
	python scripts/run_neural_training.py $(if $(EPOCHS),--epochs $(EPOCHS),)

eval-ml:
	python scripts/eval/eval_model.py --config-name $(CONFIG) --limit $(LIMIT)

train-ml-demo:
	$(MAKE) train-ml CONFIG=DEMO EPOCHS=1

eval-ml-demo:
	$(MAKE) eval-ml CONFIG=DEMO LIMIT=10

check-runtime:
	python scripts/setup/check_runtime.py

# Revolutionary Components
revolutionary-up:
	@echo "🚀 Starting Revolutionary Components..."
	@bash scripts/start_revolutionary.sh --with-monitoring

revolutionary-down:
	@echo "🛑 Stopping Revolutionary Components..."
	@docker-compose --profile revolutionary down

revolutionary-status:
	@echo "📊 Revolutionary Components Status:"
	@echo ""
	@echo "NATS:"
	@curl -s http://localhost:8222/healthz > /dev/null && echo "  ✅ Running" || echo "  ❌ Not running"
	@echo ""
	@echo "Prometheus:"
	@curl -s http://localhost:9090/-/healthy > /dev/null && echo "  ✅ Running" || echo "  ❌ Not running"
	@echo ""
	@echo "Grafana:"
	@curl -s http://localhost:3001/api/health > /dev/null && echo "  ✅ Running" || echo "  ❌ Not running"
	@echo ""
	@echo "Revolutionary API:"
	@curl -s http://localhost:8000/api/v1/revolutionary/health > /dev/null && echo "  ✅ Running" || echo "  ❌ Not running"
