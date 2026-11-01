# dzo-backend

Shared backend for DZO Food, Ride, Biz, and HQ — Epic 1 (core platform: auth, DB, API layer). See `docs/DZO_TECH_ROADMAP.md` and `docs/AGENTS_DZO.md` for the full plan; this repo is the starting skeleton, not a finished product.

## Stack

Python 3.11+, FastAPI, PostgreSQL, SQLAlchemy (async), Alembic.

## Getting started

```bash
git clone <this repo>
cd dzo-backend
make setup              # creates .venv, installs the exact versions in uv.lock (needs uv: https://docs.astral.sh/uv/)
cp .env.example .env    # then edit if needed
make db-up               # starts a local Postgres via Docker
make migrate             # runs Alembic migrations (none yet — schema TBD)
make run                 # starts the API at http://localhost:8000
```

Visit `http://localhost:8000/health` — should return `{"status": "ok"}`. Interactive API docs are at `http://localhost:8000/docs`.

### Tracing (OpenTelemetry)

`make db-up` also starts a local Jaeger. To send traces to it, set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` in `.env`, restart the API, make a request, and open `http://localhost:16686` (service `dzo-backend`). Each request shows up as a trace with its SQL queries as child spans. Leave the variable unset to turn export off — tests and CI run that way.

## Everyday commands

```bash
make test    # run tests
make lint    # ruff + black --check + mypy
make check   # lint + test — required before any commit, per docs/AGENTS_DZO.md
```

### Dependencies

`uv.lock` pins every package (including indirect ones) for all platforms, and CI installs exactly what it pins. After editing dependencies in `pyproject.toml`, run `uv lock` and commit `uv.lock` too. CI fails if the two are out of sync. To pick up newer versions within the ranges `pyproject.toml` allows, run `make lock-upgrade`, then `make check`, then commit.

## Layout

```
app/
├── main.py          # FastAPI app entrypoint
├── core/            # config, DB session setup — shared by everything
├── models/          # SQLAlchemy ORM models (empty — schema not drafted yet)
├── schemas/         # Pydantic request/response schemas
├── routers/         # shared/top-level routes (currently just /health)
├── food/            # DZO Food domain logic (Epic 4)
├── ride/            # DZO Ride domain logic (Epic 6)
├── biz/             # DZO Biz domain logic (Epic 3)
├── hq/              # DZO HQ domain logic (Epic 2)
└── payments/        # Payments domain logic (Epic 5)
alembic/             # DB migrations
tests/               # pytest suite
```

## Status

This is a bare-bones skeleton: the app boots and has one working endpoint (`/health`) and a passing test, but there's no real schema, no auth, and no domain logic yet. Next steps per the roadmap: sketch the DB schema (users, restaurants, menus, orders, deliveries, drivers, payments, ratings, promotions), then start `EPIC1_TRACKER.md` to track the real task breakdown.
