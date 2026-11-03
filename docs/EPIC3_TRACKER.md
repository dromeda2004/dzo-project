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
| epic3.task1 — Per-restaurant merchant authorization | todo | — |
| epic3.task2 — Restaurant onboarding (admin-driven) | todo | — |
| epic3.task3 — Menu management | todo | — |
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

---

## epic3.task1 — Per-restaurant merchant authorization

```json
{
  "id": "epic3.task1",
  "behavior": "Merchant endpoints are authorized per restaurant: a user can only act on restaurants they're on the staff of, and owner/manager/staff roles limit what they can do there",
  "verification": "integration tests: staff of restaurant A get 403 on restaurant B; each restaurant staff role's allowed/denied actions covered",
  "state": "todo",
  "evidence": null
}
```

**Why first:** `require_role(Role.MERCHANT)` from epic1.task3 only checks that a user works at *some* restaurant. Every Biz endpoint below needs "works at *this* restaurant, with at least this role."

**Files (expected):** `app/core/auth.py` (new dependency, e.g. `require_restaurant_role(min_role)` reading `restaurant_id` from the path), `tests/test_restaurant_auth.py`

**Acceptance criteria:**
- [ ] A dependency resolves the current user's `RestaurantStaff` row for the path's `restaurant_id`, returning 403 if there is none and 404 if the restaurant doesn't exist
- [ ] Role ordering owner > manager > staff is enforced; proposed defaults: staff can run the order flow and toggle availability, managers can also edit the menu, only owners manage staff
- [ ] Internal admins (`is_admin`) can act on any restaurant (needed for onboarding and for HQ later)
- [ ] `make check` passes

---

## epic3.task2 — Restaurant onboarding (admin-driven)

```json
{
  "id": "epic3.task2",
  "behavior": "An internal admin can create a restaurant and its owner account; an owner can add and remove staff at their restaurant",
  "verification": "integration tests for each endpoint, including role denials; manual: create a restaurant + owner, log in as the owner",
  "state": "todo",
  "evidence": null
}
```

**Design note:** Pilot restaurants are Charlie's own (roadmap §4), so onboarding is admin-driven rather than self-serve sign-up. This also partly closes epic1.task3's open item that no user-creation endpoint exists. Customer self-registration stays with Epic 4.

**Files (expected):** `app/routers/restaurants.py`, `app/schemas/restaurant.py`, `tests/test_restaurants.py`

**Acceptance criteria:**
- [ ] Admin: create/update a restaurant (name, address, timezone, `is_active`)
- [ ] Admin: create a user and attach them as the restaurant's owner
- [ ] Owner: list, add, and remove staff and change their role; an owner can't remove the last owner
- [ ] Passwords are hashed with the existing bcrypt helper; email uniqueness errors come back in the standard error envelope (`docs/API_CONVENTIONS.md`)
- [ ] PII handling (emails, names) is covered by tests (`AGENTS_DZO.md` §3)
- [ ] `make check` passes

---

## epic3.task3 — Menu management

```json
{
  "id": "epic3.task3",
  "behavior": "Merchants can create, update, and list their restaurant's menu: categories, items (price, description, photo URL), the 86 availability toggle, and modifier groups with options",
  "verification": "integration tests per endpoint and per role; manual: build a small menu for a seeded restaurant and read it back",
  "state": "todo",
  "evidence": null
}
```

**Schema gaps to close in this task** (needs a new Alembic migration, with a downgrade → upgrade round-trip as in epic1.task2):
- **Categories.** Roadmap Epic 3 lists categories, but epic1.task2's schema has none. Proposed: a `menu_categories` table (restaurant_id, name, sort order) and a nullable `category_id` on `menu_items`.
- **Modifier selection limits.** `menu_item_modifiers` only has `is_required`. Most real modifiers need "choose up to N" (e.g. toppings). Proposed: `min_selections` / `max_selections`, replacing or derived from `is_required`.
- **Deleting items that have been ordered.** `order_items` references `menu_items`, so a hard delete breaks order history. Proposed: soft-delete (an `is_archived` flag) rather than `DELETE`.

**Photos:** this task stores a `photo_url` only. Upload/storage (e.g. a Cloud Storage bucket on GCP) waits for epic1.task6.

**Files (expected):** `app/models/menu.py`, `alembic/versions/*`, `app/routers/menu.py`, `app/schemas/menu.py`, `tests/test_menu.py`

**Acceptance criteria:**
- [ ] CRUD for categories, items, modifiers, and options, scoped to the merchant's own restaurant via task1
- [ ] 86 toggle is its own endpoint usable by `staff` (the most frequent action during service)
- [ ] Prices are `Decimal` end to end, rejecting negatives
- [ ] A full menu read (categories → items → modifiers → options) in one call, ready for Epic 4 to reuse
- [ ] Archived items disappear from the menu but existing `order_items` still resolve
- [ ] Migration round-trips cleanly; `make check` passes

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
- [ ] Allowed transitions are exactly Placed → Acknowledged → Open for claim → Claimed → Ready-time set → Picked up → Delivered, plus whatever open question 1 decides about cancellation
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
- [ ] Open questions 1–3 are answered and recorded in this file
- [ ] Epic 4 (DZO Food) can build customer ordering against the menu and order endpoints
