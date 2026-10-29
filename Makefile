.PHONY: setup lock-upgrade db-up db-down test lint check migrate run

setup:
	uv sync --locked --extra dev
	@echo "Now: cp .env.example .env, then 'make db-up' and 'make migrate'"

# Re-resolve uv.lock to the newest versions pyproject.toml allows. Commit the
# updated uv.lock; CI installs exactly what it pins.
lock-upgrade:
	uv lock --upgrade

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
