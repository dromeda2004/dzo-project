# EPIC4_TRACKER.md — DZO Food (customer ordering), backend

**Epic:** 4 — DZO Food (see `DZO_TECH_ROADMAP.md` §2)
**Goal:** Give customers everything they need on the backend to order food: an account and saved addresses, a way to find restaurants and read their menus, a checkout that prices the order on the server and places it, and a way to follow the order through the lifecycle afterwards.
**Success criterion:** A customer registers, browses the seeded pilot restaurant, places an order with modifiers, a tip and a saved address, and the order arrives as **Placed** in the restaurant's inbox (epic3.task6). The restaurant acknowledges it and the customer sees the change, with every price computed on the server and no state skipped (`AGENTS_DZO.md` §1, §3). At that point DZO Biz is receiving real orders, which unblocks epic3.task9 and epic3.task10.
**Weeks:** TBD — no target date set yet.
**Scope:** This repo's backend API only. The DZO Food iOS and Android apps (stack still [TBD] in `AGENTS_DZO.md` §1) are tracked separately once the mobile engineer picks them up. **Payments are Epic 5**, built alongside this epic (roadmap §4); checkout here goes through a payment interface so it can be built and tested before the processor account exists (open question 1).

---

## Progress at a glance

| Task | Status | Evidence |
|---|---|---|
| epic4.task1 — Customer registration | done | commit `12993a2` |
| epic4.task2 — Saved delivery addresses | done | commit `f16bfdc` |
| epic4.task3 — Restaurant availability (hours and pause) | done | commit `20cccf9` |
| epic4.task4 — Restaurant discovery and public menu | done | commit `8466935` |
| epic4.task5 — Server-side pricing (quote) | todo | |
| epic4.task6 — Place an order (checkout) | todo | |
| epic4.task7 — Order history and tracking | todo | |
| epic4.task8 — Customer cancellation | todo | depends on open question 6 |
| epic4.task9 — Payment capture at checkout | blocked | Epic 5: processor account (open question 1) |
| epic4.task10 — Notifications and receipts | blocked | push/email provider not chosen |
| epic4.task11 — Promo codes | todo | depends on open question 7 |
| epic4.task12 — Pickup orders | blocked | deferred (epic3 open question 7) |
| epic4.task13 — Loyalty, credits, referrals | blocked | post-MVP (roadmap §6) |

WIP = 1: only one row may be `active` at any time. `todo` marks tasks that are planned but not yet started.

---

## Open questions to settle before checkout (task5–task6)

Gaps found while scoping this epic, plus items carried over from the roadmap. None of them block task1–task2.

1. **How does checkout relate to payment?** No raw card data may touch DZO's servers (`AGENTS_DZO.md` §3); roadmap §3 recommends Stripe Connect. A Stripe account needs the entity-structure decision (roadmap §7) first.
   - **Proposed:** checkout calls a `PaymentProcessor` interface. A fake processor (always approves, records a fake intent id) is used in dev and tests until Epic 5 wires in Stripe. The order is created as Placed only after the payment is authorized, and captured once the restaurant acknowledges, so a restaurant cancellation voids the hold instead of refunding.
   - **Needs a decision:** is building on a fake processor acceptable, or should checkout wait for Epic 5?
2. **What does the customer pay besides food and tip?** `orders` only has `subtotal` and `tip`. Delivery fee, service fee and sales tax depend on the business model (roadmap §8) and marketplace-facilitator tax registration (roadmap §7).
   - **Proposed:** add `delivery_fee`, `service_fee`, `tax` and `total` columns in task5's migration. For the pilot: a flat delivery fee and no service fee, both set in config; tax at a single configured rate until a tax service is chosen.
   - **Needs a decision:** the actual fee amounts, and whether the pilot charges tax through DZO.
3. **When is a restaurant open?** Restaurants have no hours yet (deferred from epic3.task2).
   - **Proposed:** weekly opening hours in the restaurant's own timezone, plus a staff-controlled "pause new orders" toggle for busy nights. Orders are refused while closed or paused.
   - **Decision (2026-11-24): as proposed**, with more than one window per day allowed (e.g. lunch and dinner). Built in task3.
4. **Which addresses can a restaurant deliver to?** Nothing checks distance today, and addresses have no coordinates filled in.
   - **Proposed for the pilot:** no delivery-area check (Charlie's own restaurants, a controlled market). Geocoding and a radius check come with Epic 6, which needs coordinates anyway.
5. **Does the customer give a phone number?** The driver may need to reach the customer at the door.
   - **Proposed:** optional at registration, editable later; shown only to the claimed driver (Epic 6), never to the restaurant (epic3.task6 shows a first name only).
6. **Can the customer cancel?** The lifecycle only lets the restaurant cancel (epic3 open question 1).
   - **Proposed:** the customer can cancel only while the order is **Placed** (before the restaurant acknowledges it), with a new reason `customer_cancelled` and a full void of the payment hold. After that, they ask the restaurant or support (epic3.task10, Epic 7).
7. **Promo codes in the MVP?** Roadmap Epic 4 lists promo codes at checkout; roadmap §6 says promotions can follow once the core loop works. The `promotions` table already exists.
   - **Proposed:** leave them out of the MVP and do task11 after task7.
8. **Where does the cart live?** **Proposed:** on the phone. The server has a stateless quote endpoint (task5) and re-prices everything at checkout (task6), so a stale cart can never charge the wrong amount.
9. **Pickup** (epic3 open question 7, deferred 2026-11-04). It needs a fulfillment type on `orders`, a nullable `delivery_address_id`, a separate lifecycle path and a "collected" action for the restaurant. **Proposed:** keep it deferred until the delivery loop works end to end; task12 holds the plan.

---

## epic4.task1 — Customer registration

```json
{
  "id": "epic4.task1",
  "behavior": "Anyone can create a customer account with email, password and name, then log in with it",
  "verification": "integration tests (success, duplicate email in any case, weak password, the new user has no staff or admin rights); manual: register and log in",
  "state": "done",
  "evidence": "commit `12993a2`; tests/test_register.py; manual walk-through 2026-11-22"
}
```

**Endpoint:** `POST /auth/register` with `email`, `password`, `full_name`. Returns 201 and the same token body as login (24-hour token), so the app signs the customer straight in.

**Files:** `app/routers/auth.py`, `app/schemas/auth.py` (`RegisterRequest`; the `Email` type moved here from `app/schemas/restaurant.py` so registration and staff onboarding share it), `app/schemas/restaurant.py`, `tests/test_register.py`

**Acceptance criteria:**
- [x] A new account is created and signed in; the email is stored lowercased and the name trimmed; the password is hashed — `test_register_creates_customer_and_signs_in`, `test_registered_customer_can_log_in`
- [x] Duplicate email in any case returns 409 in the standard envelope, including a concurrent-insert race (`IntegrityError` → 409, as in epic3.task2) — `test_duplicate_email_rejected_in_any_case`
- [x] Same password rules as `POST /auth/password`; invalid email or blank name rejected — `test_weak_password_rejected`, `test_invalid_email_and_blank_name_rejected`
- [x] The new user has no staff or admin rights, and the body can't grant them — `test_registered_customer_has_no_staff_rights`, `test_cannot_register_as_admin`
- [x] `make check` equivalent passes — ruff, black, mypy clean; 260 tests pass (253 existing + 7 new)
- [x] Manual walk-through (2026-11-22, local server): registered `Walk@Through.test` with a padded name → 201; `/auth/me` showed `walk@through.test`, the trimmed name, `is_admin: false`; registering again → 409; login with different capitalization → 200; the seeded restaurant's inbox → 403. Walk-through user deleted afterwards.

**Deviations & open items:**
- **No phone number yet.** Open question 5 is still open, so registration takes email, password and name only. A phone field can be added without breaking clients.
- **No email verification** (no email provider; task10) and **no rate limiting** on this unauthenticated endpoint. Rate limiting is an Epic 8 item before public launch.
- **Registration reveals whether an email has an account** (409). Every sign-up form does this to some degree; a generic response only helps once email verification exists. Revisit with task10.
- **Mutation check:** dropping the lowercasing on `Email` makes `test_register_creates_customer_and_signs_in` fail.

---

## epic4.task2 — Saved delivery addresses

```json
{
  "id": "epic4.task2",
  "behavior": "A customer can add, list, update and delete their own delivery addresses, including delivery instructions",
  "verification": "integration tests per endpoint; another customer's address ids return 404",
  "state": "done",
  "evidence": "commit `f16bfdc`; tests/test_addresses.py; migration round-trip and manual walk-through 2026-11-23"
}
```

**Endpoints** (any logged-in user, their own addresses only):

| Endpoint | Does |
|---|---|
| `GET /me/addresses` | List saved addresses, oldest first |
| `POST /me/addresses` | Add one (201) |
| `GET /me/addresses/{id}` | Read one |
| `PATCH /me/addresses/{id}` | Edit; returns the address, which has a new id if an order used the old one |
| `DELETE /me/addresses/{id}` | Delete (204); archives it instead if an order used it |

**Decisions (2026-11-23):**
- **Used addresses are never changed.** `addresses` gets an `is_archived` flag (migration `7880f8584eb7`). Deleting an address an order used archives it. **Editing one archives it and saves the edited copy as a new address with a new id** — the tracker only covered deletes, but editing in place would change where past and active orders say they're going, including what the restaurant sees. The app should use the id in the PATCH response. Archived addresses are 404 to every endpoint here.
- **At most 20 saved addresses** per customer (409 beyond that), so one account can't fill the table.
- Text is trimmed; blank `line2` or `delivery_instructions` becomes null; `line2` and `delivery_instructions` can be cleared with null, the rest can't.
- Changing any location field clears `latitude`/`longitude`, since they belonged to the old location. Changing only the instructions keeps them.

**Files:** `app/models/address.py`, `alembic/versions/7880f8584eb7_address_archiving.py`, `app/schemas/address.py`, `app/routers/addresses.py`, `app/main.py`, `tests/test_addresses.py`

**Acceptance criteria:**
- [x] Add, list, read, edit and delete own addresses — `test_add_list_get_update_delete`, `test_list_is_oldest_first_and_only_mine`
- [x] Another customer's address ids return 404 for read, edit and delete, and are left unchanged — `test_other_customers_address_is_not_found`
- [x] Addresses used by an order are archived, not deleted or edited — `test_deleting_a_used_address_archives_it`, `test_editing_a_used_address_keeps_the_orders_copy`
- [x] Validation, limit and login — `test_validation`, `test_address_limit`, `test_requires_login`, `test_location_edit_clears_coordinates`
- [x] `make check` equivalent passes — ruff, black, mypy clean; 269 tests pass (260 existing + 9 new); `alembic downgrade -1` → `upgrade head` round-trip and `alembic check` clean
- [x] Manual walk-through (2026-11-23, local server): registered a customer, added an address with padded text and a blank `line2` (trimmed, null), added instructions (same id, unused), listed it, a second customer got 404 on it, deleted it (204, gone from the list and the table). Walk-through rows deleted afterwards.

**Deviations & open items:**
- **The edit-makes-a-new-id rule is visible to clients.** An alternative is snapshotting the address onto the order at checkout (task6), which would let edits happen in place. Revisit then; the archive flag stays useful either way.
- **Mutation check:** treating every address as unused on edit makes `test_editing_a_used_address_keeps_the_orders_copy` fail.

---

## epic4.task3 — Restaurant availability (hours and pause)

```json
{
  "id": "epic4.task3",
  "behavior": "A restaurant has weekly opening hours and a pause toggle; the API can tell whether it is accepting orders right now",
  "verification": "unit tests for the open/closed calculation, including overnight hours and DST changes in the restaurant's timezone; integration tests for the merchant endpoints",
  "state": "done",
  "evidence": "commit `20cccf9`; tests/test_availability.py, tests/test_seed_dev.py; migration round-trip and manual walk-through 2026-11-24"
}
```

This is merchant-side (DZO Biz) work, but it lives here because Epic 4 is the first thing that needs it.

**Endpoints:**

| Endpoint | Who |
|---|---|
| `GET /restaurants/{id}/availability` (hours, pause time, `is_open_now`, `accepting_orders`) | staff and up |
| `PUT /restaurants/{id}/hours` (replaces the whole weekly schedule) | manager and up |
| `PUT /restaurants/{id}/pause` with `{"paused": true}` or `false` | staff and up, including the kitchen tablet |

**Decisions (2026-11-24):**
- **Windows, not one range per day.** A `restaurant_hours` row is one window (day, `opens_at`, `closes_at`) in the restaurant's local time, and a day can have several. A `closes_at` at or before `opens_at` runs past midnight and belongs to the day it opens (Friday 17:00–01:00); equal times mean 24 hours. Overlapping windows are rejected (422); touching ones (14:00 close, 14:00 open) are fine. At most 28 windows.
- **Days are names in the API** (`"monday"`) and numbers in the database (Monday = 0, Python's `weekday()`). Times are whole minutes.
- **Wall-clock time.** "9:00–17:00" means 9 to 5 local on both sides of a DST change. On the night the clocks go back, a window covering 01:00–02:00 covers both of them; on the night they go forward, the missing hour never happens.
- **No hours means closed.** A new restaurant doesn't accept orders until a manager sets hours, so it can't receive orders by accident while it's being set up.
- **Pause** is `restaurants.orders_paused_at` (when it was paused, or null). Pausing twice keeps the first time. It doesn't expire on its own; staff resume it.
- **`accepting_orders` = active, not paused, and open now.** It's one function (`app/services/availability.is_accepting_orders`), so checkout (task6) and discovery (task4) give the same answer.
- **Seed:** the pilot restaurant is open 24 hours every day, so walk-throughs work at any hour (README updated).

**Files:** `app/models/restaurant.py` (`RestaurantHours`, `orders_paused_at`), `app/models/__init__.py`, `alembic/versions/f0b187048918_restaurant_hours.py`, `app/services/availability.py`, `app/schemas/availability.py`, `app/routers/availability.py`, `app/main.py`, `scripts/seed_dev.py`, `README.md`, `tests/test_availability.py`, `tests/test_seed_dev.py`

**Acceptance criteria:**
- [x] Open/closed calculation: a simple window, several windows a day, past midnight, Sunday-to-Monday wraparound, 24 hours, no hours, both DST changes, and the restaurant's own timezone — `test_simple_window`, `test_several_windows_in_one_day`, `test_window_past_midnight_belongs_to_the_day_it_opens`, `test_sunday_night_window_wraps_to_monday`, `test_equal_times_mean_24_hours`, `test_no_hours_means_closed`, `test_hours_are_local_time_across_daylight_saving`, `test_night_the_clocks_go_back`, `test_night_the_clocks_go_forward`, `test_timezone_is_the_restaurants`
- [x] Overlaps detected, including across midnight and the end of the week — `test_find_overlap` (7 cases, both orders), `test_overlapping_or_invalid_hours_rejected`
- [x] Accepting orders needs active, unpaused and open — `test_accepting_orders_needs_active_unpaused_and_open`
- [x] Managers set hours (replacing the old schedule); staff can't; staff pause and resume; other restaurants' staff get 403 — `test_manager_sets_hours`, `test_staff_cannot_set_hours`, `test_staff_pause_and_resume`, `test_other_restaurants_staff_are_refused`, `test_new_restaurant_has_no_hours_and_is_closed`
- [x] `make check` equivalent passes — ruff, black, mypy clean; 293 tests pass (269 existing + 24 new); migration round-trip and `alembic check` clean; a seed re-run added the 7 windows to restaurant 590
- [x] Manual walk-through (2026-11-24, restaurant 590): as `staff@dzo.test`, availability showed 7 windows, open and accepting; setting hours → 403; pause → `accepting_orders: false` with the pause time; resume → accepting again. As `manager@dzo.test`, an overlapping Monday-night/Tuesday-morning schedule → 422 naming both windows; re-saving 24 hours every day → 200.

**Deviations & open items:**
- **Times come back as `"17:00:00"`** (pydantic's default), though `"17:00"` is accepted on the way in. Harmless; trim to `HH:MM` if the app team prefers.
- **No holiday or one-off closures.** Pausing covers an unexpected closure; planned ones (e.g. Thanksgiving) can wait until a restaurant asks.
- **Closing only stops new orders.** Orders already placed carry on through the lifecycle.
- **Mutation checks:** treating every window as not wrapping past Sunday fails `test_sunday_night_window_wraps_to_monday` and the wraparound overlap case; dropping "equal times = 24 hours" fails four tests.

---

## epic4.task4 — Restaurant discovery and public menu

```json
{
  "id": "epic4.task4",
  "behavior": "Customers can list active restaurants with whether each is open now, and read a restaurant's menu with 86'd items marked unavailable",
  "verification": "integration tests: inactive restaurants and archived items never appear; 86'd items are present but unavailable; no staff-only fields leak",
  "state": "done",
  "evidence": "commit `8466935`; tests/test_food_browse.py; manual walk-through 2026-11-25"
}
```

**Endpoints** (any logged-in user):

| Endpoint | Returns |
|---|---|
| `GET /food/restaurants` | Active restaurants: id, name, address, `is_open_now`, `accepting_orders`. Those taking orders first, then by name. |
| `GET /food/restaurants/{id}/menu` | The restaurant (with timezone, hours, `is_open_now`, `accepting_orders`) and its menu: categories → items → modifiers → options, then uncategorized items |

**Decisions (2026-11-25):**
- **Under `/food/...`, not `/restaurants`** as first planned: `GET /restaurants/{id}` already belongs to staff (epic3.task2), and a separate prefix keeps customer and merchant routes from colliding. `app/main.py` had already sketched a `/food` prefix.
- **One call for the restaurant page.** The menu response includes the restaurant's details and hours, so there's no separate restaurant-detail endpoint.
- **Logged-in users only** during the pilot, so the API isn't publicly scrapeable. Opening it up means dropping one dependency on the router.
- **Inactive restaurants are 404**, the same as unknown ones. A closed or paused restaurant's menu is still readable, with `accepting_orders: false`, so customers can look ahead.
- **What customers see:** archived items never; 86'd items shown with `is_available: false`, so the menu doesn't reshuffle when something sells out; empty categories left out. Order follows the merchant's sort order, but `sort_order`, `category_id`, `is_archived` and the pause time are not exposed. The customer schemas (`app/schemas/food.py`) are separate from the merchant ones, so a field added for merchants later doesn't leak here.
- **Shared loading:** the menu query moved to `app/services/menu.load_menu`, used by both the merchant and customer menus, and hours loading to `app/services/availability.load_windows`, which loads every listed restaurant's hours in one query.

**Files:** `app/routers/food.py`, `app/schemas/food.py`, `app/services/menu.py`, `app/services/availability.py`, `app/routers/menu.py`, `app/routers/availability.py`, `app/main.py`, `tests/test_food_browse.py`

**Acceptance criteria:**
- [x] Only active restaurants are listed, those taking orders first; closed and paused ones show why — `test_list_shows_active_restaurants_accepting_first`
- [x] Archived items never appear; 86'd items appear unavailable; empty categories left out; display order kept — `test_menu_for_customers`
- [x] No merchant-only fields leak — `test_menu_hides_merchant_only_fields`, plus the exact-shape assertions in `test_menu_for_customers`
- [x] Inactive and unknown restaurants are 404; a closed restaurant's menu is readable; login required — `test_inactive_or_unknown_restaurant_is_not_found`, `test_closed_restaurant_menu_is_still_readable`, `test_browsing_requires_login`
- [x] `make check` equivalent passes — ruff, black, mypy clean; 299 tests pass (293 existing + 6 new), including the merchant menu tests after the shared-loader refactor
- [x] Manual walk-through (2026-11-25, as `customer@dzo.test`): the list showed DZO Pilot Kitchen open and accepting; its menu showed Mains/Sides/Drinks with the 86'd Fish Tacos marked unavailable and the burger's 2 modifier groups; after `staff@dzo.test` paused orders, the customer menu showed `accepting_orders: false` (resumed afterwards); logged out → 401.

**Deviations & open items:**
- **No pagination on the restaurant list.** It returns every active restaurant, which is fine for a handful of pilot restaurants. Add the `API_CONVENTIONS.md` pagination (or search and distance sorting) before opening to outside restaurants (Epic 9).
- **No search, distance sorting or photo upload** yet, as planned.
- **Mutation checks:** dropping the active-restaurant filter fails `test_list_shows_active_restaurants_accepting_first`; showing empty categories fails `test_menu_for_customers`.

---

## epic4.task5 — Server-side pricing (quote)

```json
{
  "id": "epic4.task5",
  "behavior": "Given a restaurant, items, chosen modifier options, quantities and a tip, the server validates the selection and returns the full price breakdown",
  "verification": "unit tests for the pricing service (min/max selections, options from another item, archived or 86'd items, rounding); integration test for the endpoint",
  "state": "todo",
  "evidence": null
}
```

**Depends on:** open questions 2 and 8.

**Notes:**
- One pricing function used by both the quote endpoint and checkout (task6), so the two can never disagree.
- It rejects options that belong to a different item, modifier groups outside their `min_selections`/`max_selections`, archived or 86'd items, and items from another restaurant.
- Money is `Decimal` end to end and quantized to cents, as in epic3.task3.
- Migration: the fee, tax and total columns from open question 2.

---

## epic4.task6 — Place an order (checkout)

```json
{
  "id": "epic4.task6",
  "behavior": "A customer places an order: the server re-prices it, authorizes payment through the payment interface, snapshots items and modifiers, and creates it as Placed",
  "verification": "integration tests: happy path lands in the restaurant inbox; closed or paused restaurant, someone else's address, changed prices and a declined payment are all rejected; retrying with the same idempotency key creates one order; manual walk-through through the merchant endpoints",
  "state": "todo",
  "evidence": null
}
```

**Depends on:** open questions 1–3; task2–task5.

**Notes:**
- **Idempotency:** mobile networks retry. The request carries an `Idempotency-Key` header so a retried tap never makes two orders or two charges.
- **Snapshots:** the item name is snapshotted alongside the price and modifiers. Today the restaurant sees the current menu name (noted on `OrderItemOut`), so a rename after ordering changes history.
- Everything happens in one transaction: price, payment authorization, order rows. If authorization fails, nothing is written.
- The order enters the lifecycle as Placed, so every later step goes through the epic3.task5 guard.
- This task ticks epic3's last "done when" item: Epic 4 builds against the menu and order endpoints.

---

## epic4.task7 — Order history and tracking

```json
{
  "id": "epic4.task7",
  "behavior": "A customer can list their orders and see one order's current status, items, totals, prep estimate, ready time and driver first name",
  "verification": "integration tests: another customer's orders return 404; each lifecycle state shows correctly; manual: watch an order move as the restaurant acknowledges it",
  "state": "todo",
  "evidence": null
}
```

**Notes:**
- Endpoints under `/me/orders`, using the pagination convention in `API_CONVENTIONS.md`.
- Polling for updates, same reasoning as epic3 open question 5. Push comes with task10.
- The customer sees the real lifecycle state. Turning it into friendly text ("Your order is being prepared") is the app's job, so the API never hides a state (`AGENTS_DZO.md` §3).
- A cancelled order shows the reason, but not the restaurant's free-text note, which was written for internal use.

---

## epic4.task8 — Customer cancellation

```json
{
  "id": "epic4.task8",
  "behavior": "A customer can cancel their own order while it is still Placed",
  "verification": "integration tests: allowed only from Placed; the restaurant inbox shows it cancelled; the payment hold is voided",
  "state": "todo",
  "evidence": null
}
```

**Depends on:** open question 6. Adds a `customer_cancelled` reason (enum migration, as in epic3.task5).

---

## epic4.task9 — Payment capture at checkout

```json
{
  "id": "epic4.task9",
  "behavior": "The payment interface used in task6 is backed by the real processor: authorize at checkout, capture on acknowledgment, void on cancellation",
  "verification": "TBD with Epic 5",
  "state": "blocked",
  "evidence": null
}
```

**Blocked on:** Epic 5 (a Stripe account, which needs the entity-structure decision in roadmap §7). Split payments, payouts, refunds and disputes stay in Epic 5. This row only tracks swapping the fake processor for the real one in the customer flow.

---

## epic4.task10 — Notifications and receipts

```json
{
  "id": "epic4.task10",
  "behavior": "Customers get push notifications for status changes and an emailed receipt",
  "verification": "TBD when activated",
  "state": "blocked",
  "evidence": null
}
```

**Blocked on:** choosing the push provider (roadmap §3 suggests Firebase Cloud Messaging) and an email provider. Email verification at registration (task1) comes with the email provider.

---

## epic4.task11 — Promo codes

```json
{
  "id": "epic4.task11",
  "behavior": "A customer can apply a valid promo code at quote and checkout; the discount is computed on the server and redemption limits are enforced",
  "verification": "TBD when activated",
  "state": "todo",
  "evidence": null
}
```

**Depends on:** open question 7. Who pays for the discount (DZO or the restaurant) affects the payment split, so it needs Epic 5's split rules.

---

## epic4.task12 — Pickup orders

```json
{
  "id": "epic4.task12",
  "behavior": "A customer can choose pickup; the order follows Placed → Acknowledged → Ready-time set → Picked up, with no driver, delivery fee or address",
  "verification": "TBD when activated",
  "state": "blocked",
  "evidence": null
}
```

**Blocked on:** the deferral in epic3 open question 7. The plan recorded there still applies: a fulfillment-type column, nullable `delivery_address_id`, a separate allowed path in the transition guard, and a "collected" action for the restaurant.

---

## epic4.task13 — Loyalty, credits, referrals

```json
{
  "id": "epic4.task13",
  "behavior": "TBD",
  "verification": "TBD",
  "state": "blocked",
  "evidence": null
}
```

**Blocked on:** the core ordering loop being proven in the pilot (roadmap §6).

---

## Deviations & open items (epic-level)

- **Code layout.** Same as Epic 3: organized by layer (`app/routers`, `app/schemas`, `app/services`), not the `app/food/` folder proposed in `AGENTS_DZO.md` §9.
- **Customer role.** Any logged-in user counts as a customer. Staff and drivers can order food with the same account. Revisit if that causes problems.
- **Epic 2 trigger.** Once this epic is placing real orders, the minimum viable DZO HQ (roadmap §4) has data to show.

---

## Epic 4 done when

- [ ] A customer can register, save an address and browse open restaurants and their menus (task1–task4)
- [ ] A customer can place an order whose price is computed on the server, and it reaches the restaurant inbox as Placed (task5, task6)
- [ ] The customer can follow that order through each lifecycle state the restaurant moves it to (task7)
- [ ] Open questions 1–8 are answered and recorded in this file
- [ ] Payment runs through the real processor (task9, with Epic 5)
