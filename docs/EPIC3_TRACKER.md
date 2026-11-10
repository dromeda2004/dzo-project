# EPIC3_TRACKER.md — DZO Biz (restaurant & merchant portal), backend

**Epic:** 3 — DZO Biz (see `DZO_TECH_ROADMAP.md` §2)
**Goal:** Give a restaurant everything it needs on the backend to take part in the order lifecycle: an account and staff, a menu customers can order from, and the API to receive orders, acknowledge them with a prep-time estimate, and signal the ready-time to the claimed driver.
**Success criterion:** For a seeded pilot restaurant, a merchant can manage the full menu and walk a seeded order from **Placed** through **Acknowledged → Open for claim**, then (once a driver has claimed it) **Ready-time set**, with every transition enforced server-side and no state skipped (`AGENTS_DZO.md` §1, §3). That is the point where Epic 4 (DZO Food) has something real to order from.
**Weeks:** TBD — no target date set yet.
**Scope:** This repo's backend API only. The DZO Biz web portal (frontend, stack still [TBD] in `AGENTS_DZO.md` §1) is tracked separately once a frontend engineer picks it up. Since the pilot restaurants are Charlie's own, the roadmap (§4) is explicit that this doesn't need to be a polished self-serve portal yet.

---

## Progress at a glance

| Task | Status | Evidence |
|---|---|---|
| epic3.task1 — Per-restaurant merchant authorization | done | commit `581c709` |
| epic3.task2 — Restaurant onboarding (admin-driven) | done | commit `f76ef99` |
| epic3.task3 — Menu management | done | commit `277c7e9` |
| epic3.task4 — Dev seed data for manual walk-throughs | todo | — |
| epic3.task5 — Order state machine (transition guard) | todo | — |
| epic3.task6 — Order inbox for merchants | todo | — |
| epic3.task7 — Acknowledge order with prep-time estimate | todo | — |
| epic3.task8 — Ready-time signal | todo | — |
| epic3.task9 — Merchant analytics & reporting | blocked | needs real orders, i.e. Epic 4 |
| epic3.task10 — Merchant-side customer service tools | blocked | needs real customers, i.e. Epic 4 |

WIP = 1: no task should be marked `active` until it's the single thing actually being worked on. Only one row above may be `active` at any time.

`todo` marks tasks that are planned but not yet activated. `AGENTS_DZO.md` §7 only lists `active | done | blocked`, which covers tasks once work has started.

---

## Open questions to settle before the order tasks (task5–task8)

Carried over from `DZO_TECH_ROADMAP.md` §3 and §11, plus gaps found while scoping this epic. None of them block task1–task4.

1. **Can a restaurant reject or cancel an order?** The seven-state lifecycle has no rejected/cancelled state, but a restaurant will sometimes need one (item 86'd after the order was placed, kitchen closing, a customer calling to cancel). Adding a state changes the shared source of truth across all four products, so this needs Charlie's sign-off, not a quiet addition (`AGENTS_DZO.md` §4). Proposed: a terminal `cancelled` state reachable from Placed/Acknowledged/Open for claim, with a reason field; refunds handled once Epic 5 exists.
2. **How do Acknowledged and Open for claim relate?** The roadmap says acknowledgment "opens the order up" to drivers. Proposed: `POST .../acknowledge` moves Placed → Acknowledged → Open for claim in one transaction, through the task5 guard, recording `acknowledged_at`. Without an `order_status_events` table (epic1.task2 decision), Acknowledged is never observable on its own. If something needs to happen between the two (e.g. a delay before drivers see it), they become separate steps.
3. **Can the restaurant signal the ready-time before a driver has claimed?** The lifecycle puts Ready-time set after Claimed. If food is nearly done and nobody has claimed it, that's the unclaimed-order fallback question from roadmap §3, still open. Proposed for MVP: ready-time can only be set on a Claimed order; the unclaimed case is escalated through HQ later.
4. **Manual or automatic ready-time?** Roadmap §3 recommends manual (staff tap a button) for MVP and puts automatic prediction in Epic 9. This tracker assumes manual.
5. **How do merchants learn about new orders?** Polling the order inbox (task6) is the simplest MVP. Push/WebSocket delivery depends on the real-time stack decision (`AGENTS_DZO.md` §1) and likely FCM. Proposed: polling for now.
6. **How does the claimed driver get notified of the ready-time?** Task8 records it and changes the state; delivering the notification to the driver's phone belongs to Epic 6 (DZO Ride) and the push provider decision.
7. **Pickup orders** (feedback 2026-11-02). Customers should be able to choose pickup instead of delivery. Roadmap §3 proposes a pickup path: Placed → Acknowledged → Ready-time set → Picked up, with no driver states. This affects the restaurant side directly:
   - **Schema:** `orders` needs a fulfillment type (pickup/delivery), and `delivery_address_id` must become nullable for pickup orders. Best done in task3's migration or its own migration before task5.
   - **task5:** the transition guard needs a separate allowed path per fulfillment type.
   - **task7:** acknowledging a pickup order goes to Acknowledged only, never to Open for claim.
   - **task8:** for pickup orders, ready-time can be set straight from Acknowledged (no driver to wait for), and the customer is notified rather than a driver.
   - **New action:** the restaurant marks a pickup order as collected (Ready-time set → Picked up). Proposed as part of task8.
   - **Decision (2026-11-04): pickup is deferred.** It was left out of task3's migration. When it comes back it needs its own migration (fulfillment type, nullable `delivery_address_id`) before task5.

---

## epic3.task1 — Per-restaurant merchant authorization

```json
{
  "id": "epic3.task1",
  "behavior": "Merchant endpoints are authorized per restaurant: a user can only act on restaurants they're on the staff of, and owner/manager/staff roles limit what they can do there",
  "verification": "integration tests: staff of restaurant A get 403 on restaurant B; each restaurant staff role's allowed/denied actions covered",
  "state": "done",
  "evidence": "commit `581c709`; tests/test_restaurant_auth.py"
}
```

**Why first:** `require_role(Role.MERCHANT)` from epic1.task3 only checks that a user works at *some* restaurant. Every Biz endpoint below needs "works at *this* restaurant, with at least this role."

**Files:** `app/core/auth.py` (`require_restaurant_role(min_role)`, `RESTAURANT_ROLE_RANK`), `tests/test_restaurant_auth.py`

**Design decision:** `require_restaurant_role(min_role)` reads `restaurant_id` from the route path and returns the `Restaurant`, so routes get the loaded row for free. It reuses the staff memberships `get_current_user` already loads, so the check adds one query (the restaurant lookup). Inactive restaurants still pass, so an owner can set up a menu before the restaurant goes live.

**Acceptance criteria:**
- [x] A dependency resolves the current user's `RestaurantStaff` row for the path's `restaurant_id`, returning 403 if there is none and 404 if the restaurant doesn't exist — `test_staff_of_another_restaurant_rejected`, `test_non_staff_user_rejected`, `test_unknown_restaurant_returns_404`
- [x] Role ordering owner > manager > staff is enforced — `test_role_hierarchy` covers all 9 combinations of staff role and minimum role
- [x] Internal admins (`is_admin`) can act on any restaurant — `test_admin_allowed_at_any_restaurant`. The check goes through `user_roles()`, the one place `is_admin` is read, so it's a single change once HQ users get permission levels (feedback 2026-11-02, see roadmap Epic 2)
- [x] `make check` passes — ruff, black, mypy clean; 32 tests pass (18 existing + 14 new)

**Deviations & open items:**
- The per-action defaults (staff run orders and the 86 toggle, managers also edit the menu, only owners manage staff) aren't applied here, since no menu, order, or staff endpoints exist yet. Each later task picks the `min_role` for its routes using those defaults.
- Tests mount the dependency on a throwaway FastAPI app rather than the real one, since adding a placeholder route would be dead code (same reasoning as epic1.task4).
- Mutation check: replacing the membership's restaurant match with `True` makes `test_staff_of_another_restaurant_rejected` fail, so the cross-restaurant check is actually covered.
- Checking a restaurant that doesn't exist returns 404 even to non-staff. Restaurant existence isn't secret (customers will browse restaurants in Epic 4), so this leaks nothing.

---

## epic3.task2 — Restaurant onboarding (admin-driven)

```json
{
  "id": "epic3.task2",
  "behavior": "An internal admin can create a restaurant and its owner account; an owner can add and remove staff at their restaurant",
  "verification": "integration tests for each endpoint, including role denials; manual: create a restaurant + owner, log in as the owner",
  "state": "done",
  "evidence": "commit `f76ef99`; tests/test_restaurants.py, tests/test_auth.py; manual walk-through 2026-11-03"
}
```

**Design note:** Pilot restaurants are Charlie's own (roadmap §4), so onboarding is admin-driven rather than self-serve sign-up. This also partly closes epic1.task3's open item that no user-creation endpoint exists. Customer self-registration stays with Epic 4.

**Decisions (agreed 2026-11-03, before starting):**
- **First password:** there's no email service yet, so invite or reset links aren't possible. The admin (or an owner, for staff) sets a temporary password and passes it on directly. A `POST /auth/password` endpoint lets the user change it. Invite/reset links wait until an email provider exists.
- **Existing accounts:** adding staff by an email that already has an account attaches that user rather than creating a duplicate (e.g. Charlie may already be an admin or customer).
- **Who manages staff:** owners add and remove staff and can make someone a co-owner. The last owner can't be removed or demoted. Removing someone only removes their staff link, not their account.
- **Which admins:** any `is_admin` user for now, until HQ permission levels are designed (roadmap Epic 2).
- **Removing a restaurant:** deactivate via `is_active`, never delete, since orders and payouts reference it.
- **Missing restaurant fields** (phone, opening hours, coordinates): not added here. Epic 4 needs hours and Epic 6 needs coordinates; add them when there's a feature to check them against.

**Files:** `app/routers/restaurants.py`, `app/schemas/restaurant.py`, `app/routers/auth.py` (`POST /auth/password`, case-insensitive login), `app/schemas/auth.py` (password rules), `app/main.py`, `tests/test_restaurants.py`, `tests/test_auth.py`, `tests/conftest.py`, `pyproject.toml` + `uv.lock` (`tzdata`)

**Endpoints:**

| Endpoint | Who |
|---|---|
| `POST /restaurants` | admin |
| `GET /restaurants/{id}` | staff and up |
| `PATCH /restaurants/{id}` (incl. `is_active`) | admin |
| `GET /restaurants/{id}/staff` | owner |
| `POST /restaurants/{id}/staff` (attach existing account, or create one with a temporary password) | owner |
| `PATCH /restaurants/{id}/staff/{user_id}` (change role) | owner |
| `DELETE /restaurants/{id}/staff/{user_id}` | owner |
| `POST /auth/password` | any logged-in user |

Admins pass every owner check (epic3.task1), so an admin onboards a restaurant with `POST /restaurants`, then `POST /restaurants/{id}/staff` with `role: owner`.

**Acceptance criteria:**
- [x] Admin: create/update a restaurant (name, address, timezone, `is_active`) — `test_admin_creates_restaurant`, `test_admin_updates_and_deactivates_restaurant`; non-admins get 403 (`test_non_admin_cannot_create_restaurant`, `test_owner_cannot_update_restaurant`); timezones are validated against the IANA database (`test_unknown_timezone_rejected`)
- [x] Admin: create a user and attach them as the restaurant's owner — `test_admin_onboards_new_owner_who_can_then_log_in`; existing accounts are attached, not duplicated (`test_existing_account_is_attached_not_duplicated`)
- [x] Owner: list, add, and remove staff and change their role; an owner can't remove the last owner — `test_owner_changes_staff_role`, `test_last_owner_cannot_be_demoted`, `test_owner_can_be_demoted_when_another_owner_exists`, `test_last_owner_cannot_be_removed`, `test_removing_staff_keeps_their_account`, `test_manager_cannot_add_staff`
- [x] Passwords are hashed with the existing bcrypt helper; email uniqueness errors come back in the standard error envelope — new-account test checks the stored hash; duplicate cases return 409 in the envelope (`test_existing_account_with_password_rejected`, `test_adding_existing_staff_member_rejected`), as do concurrent-insert races (`IntegrityError` → 409)
- [x] PII handling (emails, names) is covered by tests — password hashes never appear in responses, the staff list returns exactly `user_id/email/full_name/role` and is owner-only (`test_staff_list_is_owner_only_and_hides_password_hashes`)
- [x] `make check` passes — ruff, black, mypy clean; 56 tests pass (32 existing + 24 new)
- [x] Manual walk-through against a running server (2026-11-03): admin created a restaurant and added a new owner; the owner logged in with the temporary password, changed it (old password then 401, new 200), added a cook, listed staff; removing themselves as last owner returned 409 and deactivating the restaurant returned 403. Walk-through rows deleted afterwards.

**Deviations & open items:**
- **Test fixture change:** this is the first task whose routes commit. `tests/conftest.py`'s `db_session` now runs inside an outer transaction with `join_transaction_mode="create_savepoint"`, so a route's `commit()` only releases a savepoint and each test still rolls back fully. Checked: row counts in `users`/`restaurants`/`restaurant_staff` are 0 before and after the full suite.
- **Login is now case-insensitive.** New accounts store emails lowercased so "Owner@Example.com" finds an existing owner@example.com. Login had to match, or an owner typing their email with capitals would be locked out. The unique index on `users.email` is still case-sensitive, so two accounts differing only by case could exist if created outside these endpoints; a `lower(email)` unique index would close that (needs a migration — fold into task3's).
- **Email existence is visible to owners:** adding staff by email reveals whether that email has an account (attach vs. "full_name and password required"). Acceptable for a small pilot of trusted owners; revisit before Biz is opened to outside merchants (roadmap Epic 9).
- **Changing a password doesn't log out other sessions.** Tokens are stateless JWTs with a 24h expiry and no revocation (epic1.task3). Fine for now; matters if an account is ever compromised.
- **Email validation is a loose pattern**, not `pydantic.EmailStr`, to avoid a new dependency for a check that can't prove an address works anyway. Real verification comes with an email provider.
- **`tzdata` added as a dependency.** Windows (and slim container images, relevant to epic1.task6's Cloud Run plan) have no system timezone database, so `zoneinfo` couldn't validate timezones without it.
- **Mutation check:** loosening the last-owner guard (`<= 1` → `<= 0`) makes both last-owner tests fail.

---

## epic3.task3 — Menu management

```json
{
  "id": "epic3.task3",
  "behavior": "Merchants can create, update, and list their restaurant's menu: categories, items (price, description, photo URL), the 86 availability toggle, and modifier groups with options",
  "verification": "integration tests per endpoint and per role; manual: build a small menu for a seeded restaurant and read it back",
  "state": "done",
  "evidence": "commit `277c7e9`; tests/test_menu.py, tests/test_models.py, tests/test_restaurants.py; migration round-trip and manual walk-through 2026-11-04"
}
```

**Schema gaps to close in this task** (needs a new Alembic migration, with a downgrade → upgrade round-trip as in epic1.task2):
- **Categories.** Roadmap Epic 3 lists categories, but epic1.task2's schema has none. Proposed: a `menu_categories` table (restaurant_id, name, sort order) and a nullable `category_id` on `menu_items`.
- **Modifier selection limits.** `menu_item_modifiers` only has `is_required`. Most real modifiers need "choose up to N" (e.g. toppings). Proposed: `min_selections` / `max_selections`, replacing or derived from `is_required`.
- **Deleting items that have been ordered.** `order_items` references `menu_items`, so a hard delete breaks order history. Proposed: soft-delete (an `is_archived` flag) rather than `DELETE`.

**Photos:** this task stores a `photo_url` only. Upload/storage (e.g. a Cloud Storage bucket on GCP) waits for epic1.task6.

**Files (expected):** `app/models/menu.py`, `alembic/versions/*`, `app/routers/menu.py`, `app/schemas/menu.py`, `tests/test_menu.py`

**Acceptance criteria:**
**Decisions (made 2026-11-04 when starting; pickup deferred per open question 7):**
- **Categories are optional.** `menu_items.category_id` is nullable with `ON DELETE SET NULL`: deleting a category leaves its items on the menu, uncategorized. Categories are hard-deleted (nothing references them historically).
- **Selection limits replace `is_required`.** `min_selections` (default 0) and `max_selections` (NULL = no limit), enforced by check constraints and the schemas. The migration maps `is_required = true` to `min_selections = 1`, and back on downgrade. "Size" is min 1 / max 1; "up to 3 toppings" is min 0 / max 3.
- **Sort order** on categories, items, modifiers, and options (`sort_order`, then `id`), so merchants control the order customers see.
- **Items are archived, never deleted** (`DELETE` sets `is_archived`). Archived items are 404 to every menu endpoint. Modifiers and options are hard-deleted, since `order_items.selected_modifiers` snapshots them instead of referencing them.
- **Who can do what:** owners and managers edit the menu; any staff member can read it and use the 86 toggle.
- **Money** is `Decimal` in and out, serialized as a string (`"12.50"`), rejected if negative, over 10 digits, or more than 2 decimal places, and quantized to cents so create responses match stored values. Option `price_delta` is also non-negative: sizes are modelled as the base price plus add-ons from the smallest.
- **Case-insensitive email uniqueness** (carried over from task2): `users.email`'s unique index is replaced by a unique index on `lower(email)`.

**Files:** `app/models/menu.py`, `app/models/user.py`, `app/models/restaurant.py`, `alembic/versions/e244c811d626_menu_management.py`, `app/routers/menu.py`, `app/schemas/menu.py`, `app/schemas/base.py` (`PatchModel`), `app/schemas/restaurant.py`, `app/main.py`, `tests/test_menu.py`, `tests/factories.py` (helpers moved out of `tests/test_restaurants.py`), `tests/test_models.py`, `tests/test_restaurants.py`

**Endpoints** (all under `/restaurants/{id}/menu`):

| Endpoint | Who |
|---|---|
| `GET ""` (full menu: categories → items → modifiers → options, then uncategorized items) | staff and up |
| `POST /categories`, `PATCH /categories/{category_id}`, `DELETE /categories/{category_id}` | manager and up |
| `POST /items` (optionally with nested modifiers and options), `PATCH /items/{item_id}`, `DELETE /items/{item_id}` (archives) | manager and up |
| `PUT /items/{item_id}/availability` (the 86 toggle) | staff and up |
| `POST /items/{item_id}/modifiers`, `PATCH /modifiers/{modifier_id}`, `DELETE /modifiers/{modifier_id}` | manager and up |
| `POST /modifiers/{modifier_id}/options`, `PATCH /options/{option_id}`, `DELETE /options/{option_id}` | manager and up |

**Acceptance criteria:**
- [x] CRUD for categories, items, modifiers, and options, scoped to the merchant's own restaurant via task1 — `test_manager_builds_menu_and_reads_it_back`, `test_update_item_category_and_price`, `test_deleting_category_keeps_its_items`, `test_add_update_and_delete_modifiers_and_options`; every lookup filters on `restaurant_id`, so another restaurant's ids return 404 (`test_ids_from_another_restaurant_are_not_found`, `test_item_cannot_use_another_restaurants_category`, `test_other_restaurants_staff_cannot_read_menu`)
- [x] 86 toggle is its own endpoint usable by `staff` — `test_staff_can_read_and_86_but_not_edit` (staff get 403 on every edit endpoint)
- [x] Prices are `Decimal` end to end, rejecting negatives — `test_invalid_prices_rejected`, `test_price_is_stored_exactly`
- [x] A full menu read (categories → items → modifiers → options) in one call, ready for Epic 4 to reuse — `GET /restaurants/{id}/menu`, ordering checked by `test_menu_follows_sort_order`
- [x] Archived items disappear from the menu but existing `order_items` still resolve — `test_archived_item_leaves_menu_but_order_history_resolves`
- [x] Migration round-trips cleanly; `make check` passes — `alembic upgrade head` → `downgrade -1` → `upgrade head` clean, and `alembic check` finds no drift; ruff, black, mypy clean; 74 tests pass (56 existing + 16 menu tests + 2 regression tests below)
- [x] Manual walk-through against a running server (2026-11-04): admin created a restaurant and added a manager, cook, and owner; the manager (logging in with a capitalized email) built Mains and Drinks, a Burger with Size (min 1 / max 1) and Toppings (up to 3), and Lemonade, then archived an item; the cook 86'd the Burger, was refused a price change (403), and read the menu back in the right order, with the Burger unavailable and the archived item gone. Walk-through rows deleted afterwards.

**Deviations & open items:**
- **`PatchModel` (new in `app/schemas/base.py`):** PATCH bodies reject an explicit `null` for NOT NULL fields (422). Before this, `PATCH /restaurants/{id}` with `{"name": null}` reached the database and returned a 500; `RestaurantUpdate` now uses it too (`test_restaurant_name_cannot_be_nulled`). Fields that may be cleared opt in via `clearable`.
- **Lowercase email index** — `test_user_email_unique_ignoring_case`. The migration would fail if two existing accounts differed only in case; there are none outside local dev data.
- **No restore for archived items.** Archiving is one-way through the API for now; restoring needs a direct DB change. Add an endpoint if merchants ask for it.
- **Options can't be 86'd on their own** (e.g. out of avocado but the burger is fine). Only whole items have `is_available`. Easy to add later as a column on `modifier_options`.
- **`min_selections` isn't checked against the number of options** (a "choose 2" group with one option can be saved). Epic 4's order validation must check selections against the limits anyway, so it's left there.
- **Menu reads are merchant-only.** Customers reading a menu (and hiding 86'd items) is Epic 4; it can reuse `MenuOut`.
- **Mutation checks:** removing the `restaurant_id` filter from any of the item, modifier, option, or category lookups, dropping the archived filter, or loosening the PATCH limit check each makes at least one test fail.

---

## epic3.task4 — Dev seed data for manual walk-throughs

```json
{
  "id": "epic3.task4",
  "behavior": "One command populates a local DB with a pilot restaurant, its staff, a menu, a customer, a driver, and orders in the Placed state",
  "verification": "manual: run the seed against a fresh DB, log in as each seeded user",
  "state": "todo",
  "evidence": null
}
```

**Why:** Orders can't be created through the API until Epic 4 exists, but the Definition of Done (`AGENTS_DZO.md` §6) needs a manual walk-through of each state transition for task6–task8. A repeatable seed replaces hand-written SQL.

**Files (expected):** `scripts/seed_dev.py`, `Makefile` (`seed` target), `README.md`

**Acceptance criteria:**
- [ ] Idempotent: running it twice doesn't duplicate data
- [ ] Refuses to run unless the database URL points at a local DB
- [ ] Seeded passwords are obviously dev-only and documented in the README
- [ ] `make check` passes

---

## epic3.task5 — Order state machine (transition guard)

```json
{
  "id": "epic3.task5",
  "behavior": "All order status changes go through one function that only allows the transitions in the seven-state lifecycle, sets the matching timestamp, and rejects anything else",
  "verification": "unit tests covering every allowed transition and a representative set of illegal ones (skips, backwards moves, repeats)",
  "state": "todo",
  "evidence": null
}
```

**Why its own task:** "No order-lifecycle state transition is skipped or faked" is a hard constraint (`AGENTS_DZO.md` §3). Biz (task7, task8), Ride (Epic 6), and HQ will all change order status. One guard used by all of them is how that constraint is enforced, rather than each endpoint checking it separately.

**Files (expected):** `app/services/order_lifecycle.py` (new `services` package), `tests/test_order_lifecycle.py`

**Acceptance criteria:**
- [ ] Allowed transitions for delivery orders are exactly Placed → Acknowledged → Open for claim → Claimed → Ready-time set → Picked up → Delivered, plus whatever open question 1 decides about cancellation
- [ ] Pickup orders follow their own path (open question 7), and the guard rejects driver states for them
- [ ] Each transition sets its timestamp (`acknowledged_at`, `claimed_at`, `ready_time`, `picked_up_at`, `delivered_at`)
- [ ] Concurrent transitions on the same order can't both succeed (row lock or a conditional `UPDATE ... WHERE status = ...`). This matters most for Epic 6's claim race, but the guard should handle it from the start
- [ ] Illegal transitions return 409 in the standard error envelope
- [ ] `make check` passes

---

## epic3.task6 — Order inbox for merchants

```json
{
  "id": "epic3.task6",
  "behavior": "Restaurant staff can list their restaurant's orders filtered by status and view one order with its items, modifiers, delivery address, and claimed driver",
  "verification": "integration tests including cross-restaurant denial; manual: view the seeded orders",
  "state": "todo",
  "evidence": null
}
```

**Files (expected):** `app/routers/merchant_orders.py`, `app/schemas/order.py`, `tests/test_merchant_orders.py`

**Acceptance criteria:**
- [ ] List endpoint filters by status (default: active orders, i.e. not Delivered), newest first, paginated
- [ ] Detail shows each item's `price_at_order_time` and `selected_modifiers` snapshot, not today's menu prices
- [ ] Only the minimum customer PII needed to fulfil the order is exposed (proposed: first name and delivery address, no email or phone)
- [ ] `make check` passes

---

## epic3.task7 — Acknowledge order with prep-time estimate

```json
{
  "id": "epic3.task7",
  "behavior": "A restaurant acknowledges a Placed order with a prep-time estimate, which moves it to Open for claim so drivers can see it",
  "verification": "integration tests + manual walk-through on a seeded order (AGENTS_DZO.md §6 lifecycle row)",
  "state": "todo",
  "evidence": null
}
```

**Lifecycle states touched:** 1 Placed → 2 Acknowledged → 3 Open for claim. Depends on open question 2.

**Files (expected):** `app/routers/merchant_orders.py`, `tests/test_merchant_orders.py`

**Acceptance criteria:**
- [ ] `prep_time_estimate_minutes` is required and within sane bounds (proposed 1–180)
- [ ] Goes through the task5 guard; acknowledging twice returns 409
- [ ] `make check` passes; manual walk-through recorded here

---

## epic3.task8 — Ready-time signal

```json
{
  "id": "epic3.task8",
  "behavior": "A restaurant sets the ready-time on a Claimed order, moving it to Ready-time set",
  "verification": "integration tests + manual walk-through on a seeded order with a seeded driver claim",
  "state": "todo",
  "evidence": null
}
```

**Lifecycle states touched:** 4 Claimed → 5 Ready-time set. Depends on open questions 3, 4, and 6.

**Files (expected):** `app/routers/merchant_orders.py`, `tests/test_merchant_orders.py`

**Acceptance criteria:**
- [ ] Accepts either "ready now" or a future time; rejects past times
- [ ] Rejected with 409 unless the order is Claimed (per the proposed answer to open question 3)
- [ ] Driver notification is out of scope (Epic 6), but the stored `ready_time` is what Epic 6 will read
- [ ] `make check` passes; manual walk-through recorded here

---

## epic3.task9 — Merchant analytics & reporting

```json
{
  "id": "epic3.task9",
  "behavior": "Merchants can see sales totals and item performance for their restaurant over a date range",
  "verification": "TBD when activated",
  "state": "blocked",
  "evidence": null
}
```

**Blocked on:** real order data, which only exists once Epic 4 (DZO Food) is placing orders. Building reports against seed data only would mean designing them blind. Scope it when Epic 4 is live, alongside the minimum viable DZO HQ (roadmap §4).

---

## epic3.task10 — Merchant-side customer service tools

```json
{
  "id": "epic3.task10",
  "behavior": "Merchants can handle customer issues on their orders (e.g. missing item, refund request)",
  "verification": "TBD when activated",
  "state": "blocked",
  "evidence": null
}
```

**Blocked on:** Epic 4 (customers) and Epic 5 (refunds go through the payment processor). Also depends on open question 1, since a cancellation is the simplest customer-service action.

---

## Deviations & open items (epic-level)

- **Code layout.** `AGENTS_DZO.md` §9 proposes `app/biz/`, but the repo built in Epic 1 is organized by layer (`app/routers`, `app/schemas`, `app/models`). This tracker follows the existing layout and adds `app/services/` for task5. Revisit if the monorepo decision changes things.
- **Epic 2 trigger.** Per roadmap §4, a minimum viable DZO HQ (restaurant/menu/order list) starts once this epic is producing real data, roughly at the end of task3 and task6.

---

## Epic 3 done when

- [ ] Restaurants can be onboarded and staff are authorized per restaurant (task1, task2)
- [ ] A complete menu can be managed and read back, including categories, modifiers, and the 86 toggle (task3)
- [ ] A seeded order can be walked through Placed → Acknowledged → Open for claim and Claimed → Ready-time set via the API, with illegal transitions rejected (task4–task8)
- [ ] Open questions 1–3 and 7 (pickup) are answered and recorded in this file
- [ ] If pickup is confirmed: a seeded pickup order can be walked through Placed → Acknowledged → Ready-time set → Picked up
- [ ] Epic 4 (DZO Food) can build customer ordering against the menu and order endpoints
