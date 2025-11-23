# Makefile for mymeta

.PHONY: help install test run clean docker-build docker-run

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s
", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test: ## Run tests
	pytest

test-cov: ## Run tests with coverage
	pytest --cov=app --cov-report=html

run: ## Run the application
	uvicorn app.main:app --reload

run-prod: ## Run the application in production mode
	uvicorn app.main:app --host 0.0.0.0 --port 8000

clean: ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage

docker-build: ## Build Docker image
	docker build -t mymeta .

docker-run: ## Run Docker container
	docker run -p 8000:8000 mymeta

docker-compose-up: ## Start services with Docker Compose
	docker-compose up -d

docker-compose-down: ## Stop services with Docker Compose
	docker-compose down

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create new migration
	alembic revision --autogenerate -m "$(message)"

format: ## Format code with black
	black app/ tests/

lint: ## Lint code with flake8
	flake8 app/ tests/

type-check: ## Type check with mypy
	mypy app/