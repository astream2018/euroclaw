.PHONY: install-dev test lint format up-test

install-dev:
	pip install -r requirements.txt -r requirements-dev.txt

format:
	python -m black src plugins tests

lint:
	python -m black --check src plugins tests
	python -m flake8 src plugins tests
	python -m bandit -r src/ plugins/

test-unit:
	pytest tests/unit/ --cov=src --cov=plugins --cov-report=term-missing

# Spins up the environment before running heavy integration tests
test-integration:
	docker-compose -f docker-compose.yml up -d
	sleep 10 # Wait for OpenTelemetry collectors / databases to boot
	pytest tests/integration/
	docker-compose -f docker-compose.yml down