# DEMO.md — How to demo what exists so far

Covers `epic1.task1` (repo skeleton) and `epic1.task2` (core DB schema) — see
`docs/EPIC1_TRACKER.md` for full task detail. There's no CRUD API yet
(`epic1.task4`) and no auth yet (`epic1.task3`), so this is a backend/schema
demo, not a user-facing product walkthrough.

## 1. App boots (epic1.task1)

```
make db-up          # start local Postgres
make run             # start FastAPI
curl localhost:8000/health          # {"status": "ok"}
```

Open `http://localhost:8000/docs` in a browser for the interactive Swagger
UI — it currently only shows the `/health` route.

## 2. Schema exists and is migrated (epic1.task2)

```
make migrate                         # alembic upgrade head
docker compose exec db psql -U dzo -d dzo -c "\dt"       # list all 16 tables
docker compose exec db psql -U dzo -d dzo -c "\d orders" # show FKs, indexes, the order_status enum
```

## 3. Constraints are real, not just declared

```
pytest -v
```

Shows 5 passing tests: `users.email` uniqueness, `driver_profiles`' 1:1 with
`users`, `restaurant_staff`'s per-user/restaurant uniqueness, and `orders`
defaulting to `PLACED` status with `tip` defaulting to 0.

## 4. The order lifecycle works end-to-end

The most convincing part for a non-engineer audience — a sample order
stepping through all seven states from `docs/AGENTS_DZO.md` section 1
(placed → acknowledged → open_for_claim → claimed → ready_time_set →
picked_up → delivered):

```
python scripts/demo_order_lifecycle.py
```

Creates a customer, restaurant, address, and order, prints the status at
each lifecycle step, then rolls back — no demo data is left in the database.
