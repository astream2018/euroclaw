.PHONY: install install-dev test test-unit test-integration lint format run-orchestrator run-worker deploy-compose deploy-helm

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

format:
	python -m black euroclaw tests

lint:
	python -m black --check euroclaw tests
	python -m flake8 euroclaw tests
	python -m bandit -c pyproject.toml --severity-level medium -r euroclaw/ -x euroclaw/connectors/templates.py

test-unit:
	pytest tests/unit/ --cov=euroclaw --cov-report=term-missing

test-integration:
	docker compose -f docker-compose.yml up -d
	sleep 10
	pytest tests/integration/
	docker compose -f docker-compose.yml down

test: test-unit

run-orchestrator:
	python -m euroclaw

run-worker:
	celery -A euroclaw.worker celery_app worker --loglevel=info --concurrency=4

deploy-compose:
	docker compose -f deploy/docker-compose.yml up -d --build

deploy-helm:
	helm upgrade --install euroclaw helm/euroclaw -f helm/euroclaw/values-production.yaml
