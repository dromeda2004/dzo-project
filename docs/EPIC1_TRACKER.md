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
| epic1.task2 — Core DB schema | todo | — |
| epic1.task3 — Auth & role-based access | todo | — |
| epic1.task4 — API layer conventions & integration scaffolding | todo | — |
| epic1.task5 — CI/CD pipeline | todo | — |
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
  "behavior": "SQLAlchemy models exist for users, restaurants, menus/items, orders, deliveries, drivers, payments, ratings, and promotions, matching the seven-state order lifecycle in AGENTS_DZO.md section 1, with a first Alembic migration applied",
  "verification": "alembic upgrade head runs clean against a fresh DB; unit tests confirm each model's constraints (uniqueness, FKs, required fields)",
  "state": "todo",
  "evidence": null
}
```

**Files (expected):** `app/models/*.py` (per-domain files, replacing the placeholder in `app/models/base.py`), `alembic/versions/*`

**TDD checklist:**
- [ ] Write failing tests for each model's core constraints before implementing
- [ ] `User` model (role: customer/driver/merchant/admin per epic1.task3's needs)
- [ ] `Restaurant`, `MenuItem` models
- [ ] `Order` model with status field covering all seven lifecycle states (`AGENTS_DZO.md` §1)
- [ ] `Delivery`, `Driver` models
- [ ] `Payment` model (references only, no raw card data — `AGENTS_DZO.md` §3)
- [ ] `Rating`, `Promotion` models
- [ ] First Alembic migration generated and applied

**Acceptance criteria:**
- [ ] `alembic upgrade head` runs clean on a fresh DB
- [ ] All nine model groups above exist with tests passing
- [ ] Order status field can represent all seven lifecycle states, no shortcuts
- [ ] `make check` passes

**Deviations & open items:** None yet.

---

## epic1.task3 — Auth & role-based access

```json
{
  "id": "epic1.task3",
  "behavior": "Users can authenticate and requests are authorized by role (customer, driver, merchant, internal admin/staff)",
  "verification": "unit + integration tests covering login, token validation, and role-gated endpoint access",
  "state": "todo",
  "evidence": null
}
```

**Files (expected):** `app/core/auth.py` (or similar), `app/schemas/auth.py`, tests under `tests/`

**TDD checklist:**
- [ ] Depends on `User` model from epic1.task2
- [ ] Session/token issuance and validation
- [ ] Role-based access control dependency for route handlers
- [ ] Tests for each of the four roles' access boundaries

**Acceptance criteria:**
- [ ] A user can authenticate and receive a valid session/token
- [ ] Role-gated endpoints reject requests from the wrong role
- [ ] `make check` passes

**Deviations & open items:** None yet.

---

## epic1.task4 — API layer conventions & integration scaffolding

```json
{
  "id": "epic1.task4",
  "behavior": "Consistent API conventions (request/response schemas, error handling, versioning) are established, with scaffolding in place for third-party integrations (payments, maps, push)",
  "verification": "a second real endpoint (beyond /health) follows the convention and has passing tests",
  "state": "todo",
  "evidence": null
}
```

**Files (expected):** `app/schemas/*.py`, `app/routers/*.py`, `app/core/config.py` (integration credentials via env)

**TDD checklist:**
- [ ] Standard error-response schema
- [ ] Pydantic request/response schema conventions documented
- [ ] Config scaffolding for Stripe/maps/FCM keys (values pending stack confirmation in `DZO_TECH_ROADMAP.md` §5)

**Acceptance criteria:**
- [ ] At least one non-health endpoint demonstrates the convention end to end
- [ ] `make check` passes

**Deviations & open items:** None yet.

---

## epic1.task5 — CI/CD pipeline

```json
{
  "id": "epic1.task5",
  "behavior": "make check (lint + test) runs automatically on every push/PR, blocking merge on failure",
  "verification": "a deliberately failing PR is blocked by CI; a passing PR is allowed to merge",
  "state": "todo",
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
