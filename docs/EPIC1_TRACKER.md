# EPIC1_TRACKER.md — Core Platform & Backend Foundations

**Epic:** 1 — Core platform & backend foundations (see `DZO_TECH_ROADMAP.md` §2)
**Goal:** Stand up the shared backend spine (DB, auth, API layer, infra) that DZO Food, Ride, Biz, and HQ all build on top of.
**Success criterion:** A running FastAPI service with the full core DB schema migrated, working auth/session handling with role-based access, CI enforcing `make check` on every change, and basic dev/staging/prod environments provisioned — ready for Epic 3 (DZO Biz) to start building real domain logic against it.
**Weeks:** TBD — no target date set yet.

---

## Progress at a glance

| Task | Status | Evidence |
|---|---|---|
| epic1.task1 — Repo skeleton & tooling | done | commit `65982d7` |
| epic1.task2 — Core DB schema | done | commit `0565bfe` |
| epic1.task3 — Auth & role-based access | done | commit `c895152` |
| epic1.task4 — API layer conventions & integration scaffolding | done | commit `1993dbb` |
| epic1.task5 — CI/CD pipeline | active | — |
| epic1.task6 — Cloud infra & environments (dev/staging/prod) | blocked | blocked on cloud provider decision, see `DZO_TECH_ROADMAP.md` §11 |
| epic1.task7 — Observability (OpenTelemetry) | todo | — |

WIP = 1: no task should be marked `active` until it's the single thing actually being worked on. Only one row above may be `active` at any time.

---

## epic1.task1 — Repo skeleton & tooling

```json
{
  "id": "epic1.task1",
  "behavior": "FastAPI app boots, has a working /health endpoint, and the repo has make setup/test/lint/check wired up",
  "verification": "manual: make run + curl /health; automated: tests/test_health.py",
  "state": "done",
  "evidence": "commit 65982d7"
}
```

**Files:** `app/main.py`, `app/core/config.py`, `app/core/database.py`, `app/routers/health.py`, `tests/test_health.py`, `Makefile`, `pyproject.toml`, `docker-compose.yml`, `.env.example`

**Acceptance criteria:**
- [x] `/health` returns `{"status": "ok"}`
- [x] `tests/test_health.py` passes
- [x] `make setup` / `make test` / `make lint` / `make check` all defined
- [x] Local Postgres via `docker-compose.yml`

**Deviations & open items:** None.

---

## epic1.task2 — Core DB schema

```json
{
  "id": "epic1.task2",
  "behavior": "SQLAlchemy models exist for the finalized core schema (users, driver_profiles, restaurant_staff, restaurants, menu_items, menu_item_modifiers/modifier_options, addresses, orders, order_items, driver_locations, payments, payouts, driver_subscriptions, ratings, promotions), matching the seven-state order lifecycle in AGENTS_DZO.md section 1, with a first Alembic migration applied",
  "verification": "alembic upgrade head runs clean against a fresh DB; unit tests confirm each model's constraints (uniqueness, FKs, required fields)",
  "state": "done",
  "evidence": "commits 0565bfe (models + migration), 0a18e9c (tests)"
}
```

**Files (expected):** `app/models/*.py` (per-domain files, replacing the placeholder in `app/models/base.py`), `alembic/versions/*`

**Finalized schema** (brainstormed 2026-09-19):

| Table | Notes |
|---|---|
| `users` | One shared table for all roles (customer/driver/merchant/admin), not per-role tables — a person can be both customer and driver |
| `driver_profiles` | 1:1 with `users` where role=driver — vehicle info, background-check status, online/offline |
| `restaurant_staff` | Join table: `users` ↔ `restaurants`, with owner/manager/staff role |
| `restaurants` | name, address, status, timezone |
| `menu_items` | restaurant_id, name, price, description, photo_url, is_available (the "86" toggle) |
| `menu_item_modifiers` / `modifier_options` | Customizable items (size, add-ons) |
| `addresses` | Reusable customer delivery addresses |
| `orders` | customer_id, restaurant_id, driver_id (nullable), status, prep_time_estimate, ready_time, subtotal, tip, promo_id (nullable), delivery_address_id, **plus delivery fields folded in directly**: `claimed_at`, `picked_up_at`, `delivered_at`, `proof_of_delivery` |
| `order_items` | order_id, menu_item_id, quantity, selected modifiers, price_at_order_time |
| `driver_locations` | Last-known location (or a ping history table if a location trail is wanted later) |
| `payments` | One row per order, linked to processor's payment intent, split into platform/restaurant/driver amounts |
| `payouts` | Restaurant and driver payout batches |
| `driver_subscriptions` | Tracks the $99/month plan and 30-day trial window (roadmap §8) |
| `ratings` | order_id, rater_id, ratee_id, rater_role, score, comment — one table covering all three rating directions (customer↔restaurant, customer↔driver, restaurant↔driver) rather than three separate tables |
| `promotions` | code, discount type/amount, valid dates, usage limits |

**Explicitly decided against, for now:**
- No `order_status_events` audit table — `orders.status` alone is the source of truth. Revisit if the "no state transition skipped or faked" hard constraint (`AGENTS_DZO.md` §3) turns out to need a real audit trail (e.g. for HQ analytics or dispute resolution).
- No separate `deliveries` table — delivery fields live directly on `orders` since every delivery maps 1:1 to a Food order at launch. Revisit and extract into its own table if/when DZO Ride needs to serve non-Food logistics (roadmap Epic 9).

**TDD checklist:**
- [x] Write failing tests for each model's core constraints before implementing — models were written first here (brainstorm → schema → models), tests written and run immediately after against a real local Postgres rather than strict test-first; see deviation note below
- [x] `User`, `DriverProfile`, `RestaurantStaff` models
- [x] `Restaurant`, `MenuItem`, `MenuItemModifier`/`ModifierOption` models
- [x] `Address` model
- [x] `Order` model with status field covering all seven lifecycle states (`AGENTS_DZO.md` §1) and delivery fields folded in
- [x] `OrderItem` model
- [x] `DriverLocation` model
- [x] `Payment`, `Payout`, `DriverSubscription` models (references only, no raw card data — `AGENTS_DZO.md` §3)
- [x] `Rating`, `Promotion` models
- [x] First Alembic migration generated and applied

**Acceptance criteria:**
- [x] `alembic upgrade head` runs clean on a fresh DB — verified with a full upgrade → downgrade → upgrade round-trip against local Postgres
- [x] All model groups in the finalized schema table above exist with tests passing — `tests/test_models.py` covers unique-email, driver_profile 1:1, restaurant_staff uniqueness, and order default status/tip
- [x] Order status field can represent all seven lifecycle states, no shortcuts
- [x] `make check` passes

**Deviations & open items:**
- Delivery fields were folded into `orders` instead of a separate `deliveries` table, and no `order_status_events` audit table was built — both explicit scope decisions made during brainstorming (2026-09-19), not oversights. See "Explicitly decided against" above.
- `pyproject.toml` was missing `psycopg2-binary`, needed by Alembic's `env.py` for its sync migration connection — added as part of this task.
- The autogenerated migration's `downgrade()` didn't drop the Postgres ENUM types it created (`op.drop_table()` doesn't do this), which broke a downgrade → upgrade round-trip with "type already exists" — fixed by adding explicit `sa.Enum(...).drop()` calls at the end of `downgrade()`. Worth remembering for any future migration that adds new enum columns.
- Test-first (write failing tests, then implement) wasn't followed literally for this task — the models were designed and written first (following the brainstormed schema), then `tests/test_models.py` was added and verified against real Postgres immediately after, before this task was marked done. Acceptance criteria (tests passing, migration round-trip, `make check`) were all verified before closing this out.
- `tests/conftest.py`'s `db_session` fixture uses its own `NullPool` engine rather than the app's pooled one in `app.core.database`, because pytest-asyncio's per-test event loop can't reuse a pooled asyncpg connection from a prior test's loop.

---

## epic1.task3 — Auth & role-based access

```json
{
  "id": "epic1.task3",
  "behavior": "Users can authenticate and requests are authorized by role (customer, driver, merchant, internal admin/staff)",
  "verification": "unit + integration tests covering login, token validation, and role-gated endpoint access",
  "state": "done",
  "evidence": "commit `c895152`"
}
```

**Files:** `app/core/security.py` (bcrypt hashing), `app/core/auth.py` (JWT issuance/validation, `Role` enum, `get_current_user`, `require_role`), `app/schemas/auth.py`, `app/routers/auth.py` (`POST /auth/login`, `GET /auth/me`), `app/routers/admin.py` (`GET /admin/ping` — minimal role-gated example), `tests/test_auth.py`, `tests/conftest.py` (`client` fixture)

**Design decision:** Roles are derived from a user's existing data rather than stored as a single column — `is_admin` flag, presence of `driver_profile`, presence of `restaurant_staff_memberships` — consistent with epic1.task2's decision that one person can hold more than one role (e.g. a driver who also orders as a customer). `user_roles(user)` in `app/core/auth.py` computes the set of roles for a given request.

**TDD checklist:**
- [x] Depends on `User` model from epic1.task2
- [x] Session/token issuance and validation
- [x] Role-based access control dependency for route handlers
- [x] Tests for each of the four roles' access boundaries

**Acceptance criteria:**
- [x] A user can authenticate and receive a valid session/token — `POST /auth/login`
- [x] Role-gated endpoints reject requests from the wrong role — `GET /admin/ping` returns 403 for non-admins, 200 for admins; verified via `tests/test_auth.py` and a live `curl` smoke test against a running server
- [x] `make check` passes

**Deviations & open items:**
- No registration/user-creation endpoint exists yet — out of scope for this task, which assumes users already exist. Tests seed users directly via `db_session`. Worth revisiting when `epic1.task4` designs the general API layer, or whenever DZO Food/Biz need customer/merchant sign-up.
- Token expiry is a flat 24h with no refresh-token flow — reasonable for an MVP-stage single access token, revisit if session length becomes a real product concern.
- `SECRET_KEY` defaults to an intentionally obvious placeholder (`dev-insecure-secret-change-in-production`) in `app/core/config.py` and `.env.example` — must be overridden per environment before any real deployment (ties into `epic1.task6`/`epic1.task8` launch prep).

---

## epic1.task4 — API layer conventions & integration scaffolding

```json
{
  "id": "epic1.task4",
  "behavior": "Consistent API conventions (request/response schemas, error handling, versioning) are established, with scaffolding in place for third-party integrations (payments, maps, push)",
  "verification": "a second real endpoint (beyond /health) follows the convention and has passing tests",
  "state": "done",
  "evidence": "commit `1993dbb`"
}
```

**Files:** `app/schemas/base.py` (`ORMBase`), `app/schemas/errors.py` (`ErrorDetail`/`ErrorResponse`), `app/core/error_handlers.py` (`register_exception_handlers`), `app/core/config.py` (integration key stubs), `docs/API_CONVENTIONS.md`, `tests/test_error_handlers.py`

**Design decision:** Rather than a parallel custom exception class, `register_exception_handlers(app)` intercepts FastAPI/Starlette's own `HTTPException` and `RequestValidationError` and envelopes them as `{"error": {"code", "message", "fields"?}}`. Every existing and future route that just does `raise HTTPException(...)` gets the convention for free — see `docs/API_CONVENTIONS.md` for the full shape and Pydantic naming conventions.

**TDD checklist:**
- [x] Standard error-response schema
- [x] Pydantic request/response schema conventions documented
- [x] Config scaffolding for Stripe/maps/FCM keys (values pending stack confirmation in `DZO_TECH_ROADMAP.md` §5)

**Acceptance criteria:**
- [x] At least one non-health endpoint demonstrates the convention end to end — `/auth/*` and `/admin/ping` (existing from epic1.task3) now return the standard error envelope; `UserOut` retrofitted onto `ORMBase`. Verified via `tests/test_error_handlers.py` and a live smoke test against a running server.
- [x] `make check` passes

**Deviations & open items:**
- No new demo endpoint was built — the existing auth/admin routes from epic1.task3 were retrofitted onto the new conventions instead, since building a throwaway endpoint just to prove the convention would be dead code.
- Versioning: documented as "none yet" in `docs/API_CONVENTIONS.md` rather than implemented — no external consumers exist yet to version against. Revisit before DZO Biz is sold standalone or DZO Ride serves non-Food logistics (roadmap Epic 9).
- Integration config fields (`stripe_secret_key`, `google_maps_api_key`, `fcm_server_key`) are unused stubs — real values and actual SDK wiring wait for roadmap Epic 5 (payments) / Epic 6 (DZO Ride) once the provider decisions in `DZO_TECH_ROADMAP.md` §5 are made.

---

## epic1.task5 — CI/CD pipeline

```json
{
  "id": "epic1.task5",
  "behavior": "make check (lint + test) runs automatically on every push/PR, blocking merge on failure",
  "verification": "a deliberately failing PR is blocked by CI; a passing PR is allowed to merge",
  "state": "active",
  "evidence": null
}
```

**Files (expected):** `.github/workflows/*.yml` or equivalent, depending on where the repo ends up hosted

**Acceptance criteria:**
- [ ] CI runs `make check` on every push
- [ ] Failing checks block merge
- [ ] Secret scanning included per `AGENTS_DZO.md` §11 Level 1

**Deviations & open items:** None yet.

---

## epic1.task6 — Cloud infra & environments (dev/staging/prod)

```json
{
  "id": "epic1.task6",
  "behavior": "dev/staging/prod environments exist with a managed Postgres instance and the API deployed to at least dev",
  "verification": "manual: hit /health on the deployed dev environment",
  "state": "blocked",
  "evidence": null
}
```

**Blocked on:** cloud provider decision (`DZO_TECH_ROADMAP.md` §11 — open question, being discussed with a coworker as of 2026-09-18) and the monorepo/multirepo decision, since deploy tooling and repo layout are coupled.

**Deviations & open items:** Cannot start until the cloud provider is chosen.

---

## epic1.task7 — Observability (OpenTelemetry)

```json
{
  "id": "epic1.task7",
  "behavior": "OpenTelemetry instrumentation is wired into the FastAPI app for traces/metrics/logs",
  "verification": "manual: a request produces a visible trace in whatever backend is configured",
  "state": "todo",
  "evidence": null
}
```

**Files (expected):** `app/core/telemetry.py` or similar, `app/main.py` (instrumentation hook)

**Acceptance criteria:**
- [ ] Requests produce traces
- [ ] `make check` passes

**Deviations & open items:** Depends on where telemetry data is sent, likely coupled to the cloud provider decision (epic1.task6).

---

## Epic 1 done when

- [ ] Core DB schema (epic1.task2) fully migrated and tested
- [ ] Auth & role-based access (epic1.task3) working for all four roles
- [ ] API conventions and integration scaffolding (epic1.task4) established
- [ ] CI/CD (epic1.task5) enforcing `make check` on every change
- [ ] Dev environment (epic1.task6) live and reachable
- [ ] Observability (epic1.task7) producing traces
- [ ] Epic 3 (DZO Biz) can start building real domain logic against this backend
