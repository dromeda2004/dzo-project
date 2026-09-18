.PHONY: setup db-up db-down test lint check migrate run

setup:
	python -m venv .venv
	. .venv/bin/activate; pip install -e ".[dev]"
	@echo "Now: cp .env.example .env, then 'make db-up' and 'make migrate'"

db-up:
	docker compose up -d

db-down:
	docker compose down

migrate:
	alembic upgrade head

run:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check .
	black --check .
	mypy app

check: lint test
	@echo "All checks passed."
