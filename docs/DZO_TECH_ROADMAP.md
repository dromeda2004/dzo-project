# DZO Food / DZO Ride / DZO Biz / DZO HQ — Technology Roadmap

## 0. What DZO actually is

DZO is not one app — it's **four connected products sharing one platform**:

1. **DZO Food** — restaurant ordering, pickup, and delivery (the customer-facing product; launches first).
2. **DZO Ride** — driver and delivery logistics (dispatch, routing, driver app; the engine that could eventually serve more than just DZO Food orders).
3. **DZO Biz** — restaurant and merchant technology (the portal/tools restaurants use to run their side of the business; could eventually be sold as its own product to merchants outside the DZO network).
4. **DZO HQ** — the internal admin and operations console Charlie and staff use to see and manage everything happening across Food, Ride, and Biz from one place. Unlike the other three, this one has no external users (no customers, drivers, or merchants) — it's purely for the DZO team itself.

The launch strategy is deliberately de-risked: start with restaurants Charlie owns, operates, or has relationships with, so the platform gets tested in a controlled market before opening to outside restaurants or drivers. That's a real advantage over a cold-start marketplace — worth designing the MVP around (see section 6).

Because DZO Ride, DZO Biz, and DZO HQ are each named as products in their own right, it's worth treating them as separate services/domains from day one at the architecture level (even if they launch as features inside one app), rather than building one monolith and trying to split it apart later once DZO Ride needs to serve non-Food logistics or DZO Biz needs to be sold standalone.

---

## 1. Project management structure

A lightweight but effective system for tracking engineering work:

- **`AGENTS_DZO.md`** (constitution) — Project Overview / Stack / Core loop, Quick Start commands, Hard Constraints, Work Rules, Session Routines (clock-in/clock-out), Definition of Done table, Repository Layout tree, Validation Hierarchy, Init/Exit checklists.
- **`EPICn_TRACKER.md`** per epic — Header (Epic / Goal / Success criterion / Weeks) → "Progress at a glance" table → per-task sections with Files / TDD checklist / Acceptance criteria / **Deviations & open items** → "Epic N done when" checklist.
- **`WEEK1_CHECKLIST.md`** — Phase 0 orient, Phase 1 clone/tooling, Phase 2 backend setup, Phase 3 verify healthy, Phase 4 frontend/mobile setup, a mandatory design-review gate before writing code, closing "done when" checklist. **Defer this one** — a checklist like this onboards a new person into an *already-existing* codebase (clone repos, verify a running backend), which only makes sense once Epic 1 has produced a working skeleton. Writing it now, before there's anything to clone or a second person to onboard, would just be documentation with no reader yet. Draft it once Epic 1 has a runnable skeleton and a second hire is actually joining — at that point it pays for itself on repeat use.
- **`PROJECT_SUMMARY_AND_DEMO.md`** — status table, architecture diagram, "what makes this real not a toy," known gaps, live demo script — for updating Charlie and other stakeholders separately from engineering trackers.

Worth drafting `AGENTS_DZO.md` early and literally, since Charlie explicitly said he wants "the initial team to help establish the technology, infrastructure, standards, and culture ... from the ground up" — that document is exactly the artifact that captures and enforces those standards once the team exists. Note it already includes its own Init/Exit session checklists, so there's some deliberate overlap with `WEEK1_CHECKLIST.md`'s later purpose — no need to duplicate that content until the week-1 doc is actually warranted.

---

## 2. Epic breakdown, mapped to DZO's stated feature list

Charlie's list of what needs to be built maps cleanly onto epics. Each epic below tags which DZO product(s) it primarily serves.

**Epic 0 — Business & legal foundations** *(all products)*
- Entity structure — decide now whether Food/Ride/Biz/HQ are one legal entity or structured for eventual separation
- Courier classification (contractor vs. employee) for DZO Ride
- Payment facilitator/marketplace registration, sales-tax obligations
- Insurance: general liability, driver auto/liability, cargo/food liability
- Restaurant partnership agreement template (even for Charlie's own restaurants — sets the pattern for future ones)
- Food safety compliance research for the launch market
- Data privacy posture (PCI-DSS for payments; applicable state/federal privacy law)

**Epic 1 — Core platform & backend foundations** *(platform-wide)*
- Secure, scalable backend architecture — the shared spine all four products and all client apps sit on
- User/account system for all roles: customer, driver, merchant, internal admin/staff
- Core DB schema: users, restaurants, menus/items, orders, deliveries, drivers, payments, ratings, promotions
- Auth, session/token handling, role-based access
- API layer + third-party integrations, designed for both current in-house use and later external partners (esp. if DZO Biz is ever sold standalone)
- Cloud infrastructure, environments (dev/staging/prod), CI/CD, observability from day one

**Epic 2 — DZO HQ (admin & operations console, cross-product)**
Goal: one place for Charlie and internal staff to see and manage everything happening across Food, Ride, and Biz.
- Cross-product analytics and reporting: order volume, delivery time, cancellation rate, driver utilization, merchant performance, revenue — all three products in one dashboard
- Cross-product user/account/permission management (customers, drivers, merchants, internal staff roles)
- Financial oversight: payouts, commissions, subscription revenue (see section 8), refunds/disputes across all products
- System configuration: pricing rules, commission/subscription settings, service areas, feature flags
- Support/escalation oversight — a manager's view above the front-line customer service tools in DZO Biz/Food
- Open design question: DZO Ride's real-time live-dispatch map (Epic 6) could live as a module inside DZO HQ, or stand alone as a purpose-built tool for active dispatchers — the audiences (a founder/ops-manager reviewing the business vs. someone actively reassigning drivers in real time) may want different interfaces even if they share the same underlying data
- Note: HQ's full value depends on data from the other three products, so it gets built incrementally rather than all at once up front. Concrete trigger points rather than a vague "alongside everything": a **minimum viable HQ** (just a list of restaurants, menus, and their current orders — nothing else) starts as soon as Epic 3 (DZO Biz) has real restaurants and menus in the database, since that's the earliest point there's anything to show. Driver/dispatch visibility is added once Epic 6 (DZO Ride) exists and produces claim/location data. Financial oversight and commission/subscription configuration wait for Epic 5 (payments) and the business-model decisions in section 8. Full cross-product analytics only becomes meaningful once all three product epics are producing real activity.

**Epic 3 — DZO Biz (restaurant & merchant portal)**
- Merchant onboarding
- Ordering and menu management (items, categories, modifiers, pricing, photos, availability/"86" toggles)
- Order-receiving flow: acknowledge/accept incoming orders, set a prep-time estimate, then send the claimed driver a ready-time notification as food nears completion (see section 3 for the full order lifecycle)
- Analytics and reporting for merchants (sales, item performance)
- Customer service tools, merchant-facing side

**Epic 4 — DZO Food (customer apps)**
- Customer iOS and Android applications
- Restaurant discovery, menu browsing, cart, modifiers
- Checkout: address, instructions, tip, promo codes, confirmation
- Order status / tracking screen, reflecting the full lifecycle in section 3 (placed → acknowledged → claimed by a driver → out for delivery → delivered)
- Notifications and communications (order updates, receipts)
- Promotions, loyalty, credits, and referrals

**Epic 5 — Payment processing** *(platform-wide, shared by Food/Ride/Biz)*
- Customer payment capture via a PCI-compliant processor (e.g. Stripe Connect) rather than handling raw card data in-house
- Split payments: platform take, restaurant payout, driver payout, tax
- Refunds/disputes/chargebacks
- Payout scheduling for merchants and drivers

**Epic 6 — DZO Ride (driver app, GPS, dispatch)** *(the hardest engineering problem)*
- Driver application: go online/offline, browse and claim acknowledged orders open for delivery (see section 3 — this claim-based model replaces the need for an automated matching algorithm at launch), navigate, proof of delivery
- GPS and real-time driver tracking
- Ready-time notification handling: driver receives the restaurant's "come now" / "arrive by X" signal for a claimed order
- Live-dispatch console: live map of active orders/drivers, manual reassignment, exception handling — e.g. an order that goes unclaimed (see section 3's open questions) (see Epic 2 for the open question on whether this lives inside DZO HQ or stands alone)
- Designed so DZO Ride's dispatch/tracking core isn't hard-wired only to DZO Food orders, if the long-term plan is for Ride to be a standalone logistics product

**Epic 7 — Trust, quality & support** *(platform-wide)*
- Ratings/reviews across all relationships (customer↔restaurant, customer↔driver, restaurant↔driver)
- Customer service tools and support/ticketing flow
- Driver background-check integration
- Fraud/abuse detection basics (fake accounts, promo abuse, GPS spoofing)

**Epic 8 — Launch prep** *(all products)*
- Load/perf testing on ordering + dispatch path
- Security review (auth, payments, PII) — this is also where the Cybersecurity Engineer role plugs in directly
- Staged rollout across Charlie's own restaurants first, then controlled expansion
- QA/automation coverage across all client apps before opening to outside restaurants/drivers

**Epic 9 — Growth (post-launch)**
- Expansion beyond Charlie's own restaurants and controlled market
- DZO Biz as a standalone product pitch to outside merchants
- DZO Ride as a standalone logistics product beyond DZO Food orders
- Automatic prep-time/ready-time prediction (see section 3) instead of relying on restaurant staff to manually signal timing
- AI/ML features (recommendations, demand forecasting, fraud detection, or a support agent) — if built, a scorer/judge library plus a CI regression gate (test each change against a versioned dataset, block the merge if quality scores drop versus a stored baseline) is a proven pattern for grading and guarding these before they ship

---

## 3. Order & dispatch lifecycle — Charlie's specified flow

Charlie described the actual sequence he wants: the customer places the order → the restaurant acknowledges (accepts) it → that acceptance opens the order up for a driver to choose to deliver it → the restaurant then tells that driver the "perfect time" to arrive, timed so the driver shows up right as the food finishes, rather than the food sitting out or the driver waiting around.

This is a real, well-established dispatch pattern, and the comparison to Walmart's delivery system is apt: it's essentially a **driver-claim model with just-in-time pickup timing**. Drivers browse a pool of available orders and choose which to accept, rather than the platform algorithmically pushing one assignment to one driver the way Uber/DoorDash's automated matching typically works.

**Proposed state machine, translating Charlie's description into concrete system states:**

1. **Placed** — customer submits the order (DZO Food)
2. **Acknowledged** — restaurant accepts the order and gives a prep-time estimate (DZO Biz)
3. **Open for claim** — once acknowledged, the order becomes visible to available drivers as a job they can choose to take (DZO Ride)
4. **Claimed** — a driver selects the order; it's no longer visible to other drivers
5. **Ready-time set / driver notified** — as the food nears completion, the restaurant sends the claimed driver a "come now" or "arrive by X" signal, timed to the prep clock
6. **Picked up** — driver collects the order at the restaurant
7. **Delivered** — driver completes the delivery, customer/driver confirm (photo/PIN, per Epic 6)

**Open questions this raises, worth resolving before Epic 3/6 design work starts:**

- **What happens if no driver claims an order?** A fallback is needed — a timeout that either expands visibility, pings drivers directly, or escalates to manual assignment via the DZO HQ/dispatch console.
- **Cherry-picking risk:** if drivers can see order details (distance, likely tip, which restaurant) before claiming, some orders may go consistently unclaimed — short tip, far distance, a slower restaurant. Walmart's own driver platform relies on transparency and fair rotation of offers rather than penalizing declines, which suggests a small, trusted pool may be enough for DZO at launch without needing round-robin distribution or bot-prevention machinery on day one.
- **How does the restaurant compute/communicate the "perfect time"?** Is this a manual action by restaurant staff (tap a button when food is close to done), or does it need an automatic prep-time estimation feature that notifies based on order complexity/kitchen load? Manual is far simpler for MVP; automatic prediction is a reasonable Epic 9 growth feature (already added there).
- **Single order vs. multi-order claims:** if a driver can only claim one order at a time under this model, that's simpler to build but may limit driver earnings efficiency since there's no batching multiple pickups into one trip. Worth confirming whether Charlie intends single-order claims only, at least initially.

This lifecycle should become the backbone of the `EPIC3_TRACKER.md` and `EPIC6_TRACKER.md` task breakdowns once drafted, since it defines the actual state transitions and the API contract between DZO Biz, DZO Food, and DZO Ride.

---

## 4. Recommended build order

The order to build in isn't a matter of preference — it follows directly from the dependencies in sections 2 and 3. Working through those dependencies:

**Epic 0 (legal/business) and Epic 1 (core platform) start at the same time, for different reasons.** Epic 0 doesn't block engineering at all — it's Charlie's and legal counsel's track, not a coding task — so it should run in parallel from day one rather than delay anything. Epic 1 is a hard prerequisite: the shared backend, database schema, auth, and API layer are what every other product sits on top of. Nothing else can be meaningfully built until this exists, so it's the actual first engineering work.

**Epic 3 (DZO Biz) comes before Epic 4 (DZO Food).** Looking at the lifecycle in section 3: a customer can't order from a menu that doesn't exist, and a restaurant has to be able to acknowledge an order before anything can move to a driver. So menu/catalog management and order-acknowledgment need to exist, even roughly, before the customer-ordering flow is worth building against. Since the pilot restaurants are Charlie's own, this doesn't need to be a polished self-serve merchant portal yet — even an internal tool to seed menus would unblock Food.

**Epic 4 (DZO Food) follows, with Epic 5 (payments) woven in as part of checkout rather than a separate later phase.** Once there's a menu to order from and a restaurant that can acknowledge orders, the customer app becomes buildable end-to-end — and checkout needs real payment capture from the start, so payments should track alongside Food rather than after it.

**Epic 6 (DZO Ride) comes last of the three product epics.** It's the piece that consumes the upstream "acknowledged order" and "ready-time" states from section 3, and it's the hardest engineering problem on the list — the upstream states should already be working before building the driver-side that depends on them.

**Epic 2 (DZO HQ) starts once Epic 3 has real data, not on day one.** Before Biz has restaurants and menus in the database, HQ would just be an empty dashboard — wasted work. So the concrete trigger is: begin a minimum viable HQ (restaurant/menu/order list only) once Epic 3 is producing real data, roughly overlapping the tail end of Epic 3 and the start of Epic 4. From there it grows in slices tied to its own dependencies — driver/dispatch visibility once Epic 6 exists, financial oversight once Epic 5 and the business-model decisions (section 8) are settled, full cross-product analytics only once all three product epics are live. Given WIP = 1 per person, this is likely picked up in slivers by whoever's touching the shared database/schema layer rather than staffed as its own dedicated epic early on.

**Epic 7 (trust, quality & support) can stay light initially** — ratings, background checks, and fraud detection matter most once the platform opens beyond a small circle of restaurants Charlie already knows and drivers he already trusts — then should expand before any controlled expansion beyond the pilot.

**Epic 8 (launch prep) and Epic 9 (growth) close out the sequence** — launch prep right before going live to the pilot restaurant list, growth work only after that pilot validates the core loop.

In short: **Epic 1 first (Epic 0 in parallel) → Epic 3 → Epic 4 + Epic 5 together → Epic 6 → Epic 2 growing throughout → Epic 7 expanding pre-launch → Epic 8 → Epic 9.**

---

## 5. Tech stack — a reasonable default

- **Backend (decided):** Python/FastAPI + PostgreSQL + SQLAlchemy (async) + Alembic for migrations. Repository pattern for DB access (never raw SQL in route handlers) is a good house rule to set from day one.
- **Real-time layer:** WebSockets or a managed real-time service for live order + driver location updates, and for pushing "open for claim" and "ready-time" notifications from section 3's lifecycle to drivers in real time.
- **Mobile apps (customer + driver):** React Native or Flutter for one codebase across iOS/Android.
- **Merchant portal (DZO Biz) and admin console (DZO HQ):** responsive web apps (React + Tailwind) — both are primarily desktop/tablet tools for internal or merchant staff rather than mobile-first experiences.
- **Maps/geocoding/routing:** Google Maps Platform or Mapbox — budget for usage-based billing that scales with driver/order volume.
- **Payments:** Stripe Connect (built for marketplaces — handles split payments, payouts, PCI compliance) rather than building payment splitting in-house.
- **Push notifications:** Firebase Cloud Messaging.
- **Observability:** OpenTelemetry end-to-end across all client apps and backend.
- **CI/lint/security baseline:** static analysis, unit/integration tests, dependency and secret scanning wired into CI before any code merges — directly relevant to the Cybersecurity Engineer and QA/Automation roles Charlie listed.

Given Charlie explicitly listed an AI/ML Engineer role, worth clarifying early what AI features (if any) are actually planned for v1 vs. later — that changes whether this role is needed from day one or joins post-launch.

---

## 6. MVP scope — leverage the controlled launch

Charlie's plan already avoids the classic mistake of launching cold to strangers on both sides of the marketplace. The MVP should lean into that advantage rather than rebuild generic assumptions:

- Launch only with Charlie's own restaurants — menu/catalog setup can be done hands-on rather than via a polished self-serve onboarding flow.
- The claim-based dispatch model in section 3 is itself an MVP-friendly design — no automated matching algorithm needed at launch, just a small, known driver pool browsing and claiming orders, and Walmart's own experience suggests transparency alone is enough to start without extra anti-cherry-picking tooling.
- Customer app can launch with the core ordering + tracking loop; loyalty/promotions/referrals (listed by Charlie) can follow once the core loop is proven.
- Payments should be built correctly from the start (Stripe Connect or similar) even in a small pilot — this isn't a place to cut corners given compliance exposure.
- DZO HQ at MVP stage can be minimal — basic order/driver visibility for Charlie and an ops person — rather than the full cross-product admin suite described in Epic 2.

This lets the team validate the ordering → prep → claim → ready-time → delivery loop end-to-end in a market Charlie already controls, before investing in multi-restaurant onboarding, automated prep-time prediction, or full admin tooling.

---

## 7. Legal/business items to not skip

- Entity structure across DZO Food / Ride / Biz / HQ (one company vs. related entities) — worth deciding before contracts and payment processor accounts get set up.
- Driver classification (contractor vs. employee) for DZO Ride and the associated labor-law research for the launch jurisdiction.
- Insurance: driver auto/liability, platform general liability, food liability.
- Marketplace facilitator sales-tax registration.
- Food handling/safety rules for delivered food in the launch market.
- Background-check vendor for drivers.
- Restaurant partnership agreement — needed even for Charlie's own restaurants, since it establishes the template for every restaurant that follows.
- Terms of service / privacy policy covering customers, drivers, and merchants.

---

## 8. Business model — driver subscription vs. commission

**Confirmed by Charlie directly, superseding the earlier proportional read of this model:** the driver's bonus is a **flat $1.50 per order**, regardless of order size — not a percentage that scales up on bigger orders. A subscribed driver gets the same extra $1.50 whether the order is $10 or $50, funded by a flat **$99/month driver subscription**. Customers pay less than a standard ~30%-markup platform, drivers keep a fixed bonus per order, and the platform's revenue shifts from a variable per-order cut to a fixed subscription fee.

**Break-even is now one fixed number, not an average-order-value table.** Because the driver's gain is flat rather than proportional, the number of orders needed to cover $99/month doesn't depend on order size at all:

$99 ÷ $1.50/order = **66 orders/month**, or about 2.2 orders/day.

This replaces the earlier AOV-dependent break-even table (built on an assumption that the driver's cut scaled with order value, which Charlie's clarification rules out). One real consequence of the flat structure: larger orders don't help a subscribed driver's economics at all — $1.50 on a $50 order is worth proportionally much less than $1.50 on a $10 order. So driver-recruiting messaging and incentive design should be built around *order count/volume*, not order value, since that's what actually determines whether the subscription pays off for a given driver.

**30-day trial — confirmed as designed, not just proposed.** Drivers work under the standard model for their first 30 days, then decide whether to subscribe — based on their own real order count, not a blind guess. This meaningfully de-risks the model for drivers during the low-volume controlled-market launch, and makes the fee much harder to characterize as a "pay to work" scheme from a labor-law standpoint, since it's optional and evidence-based rather than mandatory upfront.

**The platform-side tension this doesn't solve.** The subscription only offsets the $1.50/order DZO gives up per order up to 66 orders/month. A driver who completes far more than that in a month still costs the platform more in forgone margin than the flat $99 recovers — so this structure trades platform revenue on high-volume drivers for a lower, more predictable customer price and a strong driver-recruiting pitch. Worth being explicit with Charlie that this is a strategic trade (better pricing/driver supply for slower revenue-per-active-driver), not a pure cost reduction — unless it's expected to pay off through higher order volume overall, better driver retention, or lower recruiting costs than the alternative.

**Open questions on this model:**

- Is the customer-facing price reduction also a flat amount (e.g., always $1.50 less than the standard markup, regardless of order size), or does the customer side stay proportional to a ~30%-style markup while only the driver's cut is fixed — meaning DZO would keep more margin on larger orders since it isn't passing along a proportionally bigger discount? Charlie's clarification settles the driver side; the customer-facing side of this same question is still open.
- How is the customer price set when the driver fulfilling an order isn't yet known to be subscribed or not (during someone's 30-day trial, or if they opt out after)? Either the customer price is fixed regardless of which driver fulfills it (platform absorbs the gap on non-subscribed drivers), or pricing varies by driver assignment, which is a confusing customer experience.
- Can a driver downgrade back to commission mid-subscription if their volume drops, and can someone who declines after their first trial ever re-trial later?
- Is there a plan to show drivers a personalized comparison at the end of the 30-day trial ("you completed X orders this month; subscribing would have earned you $Y more/less")? With a flat $1.50/order this is a simple calculation — order count × $1.50 vs. $99 — and a small addition to the DZO HQ analytics/reporting scope (Epic 2) that turns this into a data-backed decision rather than a guess.
- Is the intended goal of this model revenue-neutral infrastructure, or a deliberate below-market-rate incentive to build driver supply and win customers on price while DZO is still proving out the market? That answer should drive whether $99/$1.50 are the final numbers or just a starting point.

---

## 9. Mapping Charlie's role list to the epics above

Charlie wants to define team roles by actual strength rather than a blanket "software engineer" title. Here's how his listed roles map to the epics, useful both for staffing discussions and for positioning your own background:

| Role | Primary epic(s) |
|---|---|
| Technical Lead / Software Architect | Epic 1 (platform architecture across all four products) |
| Senior Full Stack Engineer | Epic 1, floats across Epics 3–4 |
| Backend Engineer | Epic 1, Epic 5 |
| Frontend Engineer | Epic 4 (customer web), Epic 3 (merchant portal), Epic 2 (HQ admin UI) |
| iOS / Android / Mobile Developer | Epic 4 (customer apps), Epic 6 (driver app) |
| Cloud / DevOps Engineer | Epic 1 (infrastructure, CI/CD), Epic 8 (launch readiness) |
| Database / Data Engineer | Epic 1 (schema/data model), Epic 2 (cross-product analytics/reporting) |
| API / Integration Engineer | Epic 1 (third-party integrations), Epic 5 (payment processor integration) |
| GPS / Mapping / Dispatch Engineer | Epic 6 — note the claim-based model in section 3 simplifies initial scope (no matching algorithm needed at launch), but GPS tracking and the live-dispatch console are still substantial builds |
| Payment Systems Engineer | Epic 5 |
| AI / Machine Learning Engineer | Epic 9 (unless AI is planned for v1) |
| QA / Automation Engineer | Epic 8, but should be involved from Epic 1 onward |
| Cybersecurity Engineer | Epic 1 (architecture-level), Epic 5 (payments), Epic 8 (launch review) |
| UI / UX and Product Development | Epics 3 and 4 primarily, plus Epic 2 (HQ admin UX) |
| Technical Project Management | Cross-cutting — owns the tracker/checklist system in section 1 |

---

## 10. Minimum team size

The 15 roles Charlie listed (section 9) are a full org chart, not a starting roster. For the MVP scope in this plan — Charlie's own restaurants, a small trusted driver pool, the claim-based dispatch model in section 3 that avoids needing an automated matching algorithm — a real build is achievable with a small, specific team, though it's tight rather than comfortable.

**3 engineers is the minimum for an actual build, not just a prototype:**

- **Engineer 1 — Backend / Technical Lead.** Owns Epic 1 (core platform, DB, auth, API), Epic 5 (payments — substantially simplified by using Stripe Connect instead of building payment splitting from scratch), and the backend side of Epic 2 (DZO HQ's data/reporting layer). Also owns architecture-level security decisions, covering the Cybersecurity role's early responsibilities without a dedicated hire yet.
- **Engineer 2 — Mobile.** Owns Epic 4 (DZO Food customer app) and Epic 6 (DZO Ride driver app) — these share a codebase if built in React Native/Flutter as recommended in section 5, so one person can plausibly own both, plus the GPS/tracking integration. The claim-based dispatch model matters here too: no automated matching algorithm to build means the GPS/Mapping/Dispatch role's hardest work is deferred to Epic 9 (growth), not needed at launch.
- **Engineer 3 — Web/Frontend.** Owns Epic 3 (DZO Biz merchant portal) and the frontend of Epic 2 (DZO HQ console) — both web apps per section 5, naturally one person's territory rather than two separate hires.

**Charlie covers product, business, and Epic 0** (legal/entity/insurance) — that track runs through Charlie and outside counsel in parallel regardless of team size, per section 7, and isn't engineering headcount.

**What a 3-person team gives up**, worth being explicit about rather than glossing over: no dedicated QA/automation or security engineer means testing and security review become a part-time responsibility split across the three engineers rather than someone's actual job. That's a workable trade for a controlled pilot with known restaurants and trusted drivers, but a real risk the moment DZO opens to strangers' money and food. It also means zero redundancy — if the mobile engineer is unavailable for two weeks, both Epic 4 and Epic 6 stall with no backup.

**4 is the realistic minimum before opening beyond the controlled pilot** (Epic 8/9) — the natural 4th hire is a QA/DevOps generalist or a second backend/mobile engineer for redundancy, since that's exactly where security review and real testing stop being optional per the Definition of Done in `AGENTS_DZO.md`.

So: **3 engineers + Charlie to build the pilot, 4 engineers + Charlie before expanding past it.**

---

## 11. Open questions — updated after Charlie's message

Some of the original brainstorm questions are now answered by Charlie's outreach (target market = his own restaurants; team is actively being assembled; the four-product structure and the claim-based order lifecycle are set). Remaining open questions worth raising:

**Scope & sequencing**

- Does Charlie's own sense of build order (section 4) match this reasoning, or does he see Food and Biz needing to launch simultaneously for some reason not captured here?
- Where does DZO HQ fit in the build sequence — does a lightweight version need to exist from day one so Charlie has visibility into the pilot, or is it acceptable to build it up incrementally as Food/Biz/Ride produce data worth surfacing?
- Is DZO Ride meant to only serve DZO Food orders at launch, or is there any near-term ambition for it to handle other logistics work?

**Order lifecycle (section 3)**

- What's the fallback when an order goes unclaimed by any driver?
- Does Charlie want any cherry-picking mitigation at launch, or is the driver pool small/trusted enough to skip that for now (Walmart's own approach suggests this is a reasonable default)?
- Is the "perfect time" notification a manual action by restaurant staff, or does it need to be computed automatically from day one?

**Team & fit**

- Is Charlie hiring one person per role, or expecting early team members to cover multiple roles at this stage (likely, given team size at this point)?
- What's the actual current team size and what roles (if any) are already filled?
- Is this a paid role, equity, or some combination — and what's the expected time commitment?

**Technical decisions still open**

- Any existing technical assets already built (even prototypes) for any of the four products, or is this fully greenfield?
- Preferred cloud provider, or is that up to the technical lead to decide?
- Is a native iOS/Android approach preferred over cross-platform, given "iOS / Android / Mobile Developer" is listed as one role rather than split into two?
- What platform does Charlie actually want for each of the four products? This plan assumes DZO Food and DZO Ride are downloadable mobile apps while DZO Biz and DZO HQ are responsive web apps (see section 5) — worth confirming that split matches his intent, rather than assuming all four should be app-store mobile apps or that any of them should be web-only.

**AI/ML scope**

- What specific AI/ML use case does Charlie have in mind (recommendations, support chat, fraud detection, demand forecasting)? This significantly changes whether that role is needed at launch or later.

---
