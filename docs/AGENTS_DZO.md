# AGENTS_DZO.md — DZO Engineering Constitution

This is the entry point for anyone (human or AI-assisted) starting work on DZO — Food, Ride, Biz, or HQ. Read this before touching code. Where a decision hasn't been made yet, that's marked explicitly rather than guessed at — check `DZO_TECH_ROADMAP.md` for the reasoning behind each open item, and update this file once Charlie/the technical lead settles it.

**Status: this file is a draft scaffold, partially confirmed.** DZO is currently greenfield — no repo yet, team still being assembled — but the backend stack is now decided (Python/FastAPI). Other sections below remain proposals carried over from `DZO_TECH_ROADMAP.md` rather than settled fact. Treat anything still marked **[TBD]** as a real open question, not a placeholder to ignore.

---

## 1. Project Overview

**Domain:** DZO is a four-product food ordering, delivery, and restaurant-technology platform:

- **DZO Food** — customer-facing ordering, pickup, and delivery
- **DZO Ride** — driver app, GPS tracking, and dispatch
- **DZO Biz** — restaurant/merchant ordering and menu management portal
- **DZO HQ** — internal, cross-product admin and operations console (no external users)

**Stack:**

- **Backend (decided by the Technical Lead):** Python/FastAPI + PostgreSQL + SQLAlchemy (async) + Alembic for migrations
- Mobile (DZO Food customer app, DZO Ride driver app): React Native or Flutter **[TBD]**
- Web (DZO Biz merchant portal, DZO HQ admin console): React + Tailwind **[TBD]**
- Payments: Stripe Connect **[TBD, pending confirmation]**
- Maps/routing: Google Maps Platform or Mapbox **[TBD, pending confirmation]**
- Real-time: WebSockets or a managed real-time service
- Observability: OpenTelemetry end-to-end

**Core loop** (the order & dispatch lifecycle — see `DZO_TECH_ROADMAP.md` section 3 for the full reasoning and open questions):

1. Customer places an order (DZO Food)
2. Restaurant acknowledges it and gives a prep-time estimate (DZO Biz)
3. Order becomes open for claim by available drivers (DZO Ride)
4. A driver claims it
5. Restaurant signals the ready-time as food nears completion; driver is notified
6. Driver picks up the order
7. Driver delivers it; delivery is confirmed

Every engineering session on DZO Food, Biz, or Ride should be able to say which of these seven states its work affects.

---

## 2. Quick Start

Now that the backend stack is decided (FastAPI/Python/PostgreSQL), the convention below is concrete rather than a placeholder — **exact commands still TBD until Epic 1's repo actually exists**, but the shape is set:

```
make setup      # install deps (pip/poetry), set up local env, run first Alembic migration
make test       # pytest
make lint       # ruff + black + mypy
make check      # lint + test + type-check, the pre-merge gate
```

No code ships without `make check` passing. If the eventual toolchain doesn't use Make, keep the same four verbs (setup/test/lint/check) so the constitution stays accurate without a rewrite.

---

## 3. Hard Constraints

Non-negotiable, regardless of who's writing code or how much of a hurry anyone is in:

- **WIP = 1.** One feature/task active at a time per person. No starting task 2 before task 1 is verified done.
- **No payment or PII-handling code ships without tests.** This isn't optional given the compliance exposure discussed in `DZO_TECH_ROADMAP.md` section 7.
- **No order-lifecycle state transition is skipped or faked.** The seven states in section 1 above are the source of truth for order status everywhere (DZO Food's tracking screen, DZO Ride's driver app, DZO HQ's dashboards) — a shortcut in one product that skips a state breaks the others silently.
- **All new code passes `make check` before merge.**
- **State lives in the repo, not just in chat or someone's head.** Decisions, deviations, and progress go in the relevant `EPICn_TRACKER.md`, not only in a Slack thread or a conversation with Claude.
- **No raw card data touches DZO's own servers.** Payment capture goes through the PCI-compliant processor's SDK (see `DZO_TECH_ROADMAP.md` section 5) — this is a hard line, not a style preference.
- **Three-layer validation before calling anything done:** it runs, it's tested, and it's been checked against the actual acceptance criteria in the relevant epic tracker — not just "looks right."

---

## 4. Work Rules

- One feature at a time (see WIP = 1 above) — no jumping ahead because something else looks more interesting.
- No premature refactors. If existing code is in the way of a task, note it in the tracker's "Deviations & open items" section rather than silently rewriting it as a side quest.
- Follow the build order in `DZO_TECH_ROADMAP.md` section 4 (Epic 1 → Epic 3 → Epic 4 + Epic 5 → Epic 6 → Epic 2 growing throughout → Epic 7 expanding pre-launch → Epic 8 → Epic 9) unless Charlie has explicitly changed the sequencing.
- Never declare a task done without verification (tests passing, acceptance criteria met, and — for anything touching the order lifecycle — a manual walk-through of the actual state transitions).
- When Charlie's stated design (e.g. the claim-based dispatch model) and an engineer's instinct disagree, default to what's written in `DZO_TECH_ROADMAP.md` and raise the disagreement as an explicit open question rather than quietly building it differently.

---

## 5. Session Routines

**Clock in:**
1. Read `DZO_TECH_ROADMAP.md` and the active `EPICn_TRACKER.md` for whatever you're about to work on.
2. Check the tracker's "Progress at a glance" table for the current state of the epic.
3. Run `make check` (or the current equivalent) to confirm the repo is healthy before adding anything.
4. Confirm what the single active task is — if more than one thing looks "in progress," stop and resolve that before writing code.

**Clock out:**
1. Run `make check` again.
2. Update the tracker: mark the task's status, log commit hash(es), and note anything that deviated from the plan in "Deviations & open items."
3. Commit with a message that references the epic/task id.
4. Leave the active task genuinely stoppable — no half-finished state that the next session (or person) can't pick up from the tracker alone.

---

## 6. Definition of Done

| Criterion | Evidence |
|---|---|
| Code runs | `make check` passes locally and in CI |
| Tests exist and pass | Test file(s) referenced in the task's tracker entry |
| Acceptance criteria met | Each criterion in the task's tracker checked off explicitly, not assumed |
| Order-lifecycle correctness (if touched) | Manual or automated walk-through of the relevant state transition(s) in section 1 |
| No regressions | Existing test suite still passes; no order state or payment flow silently broken |
| Documented | Tracker updated (status, files touched, deviations) before the task is called done |

---

## 7. Feature list rules

Every feature/task is tracked as a tuple, not a vague checkbox:

```json
{
  "id": "epic3.task2",
  "behavior": "restaurant can set a prep-time estimate when acknowledging an order",
  "verification": "unit test + manual walkthrough against a seeded order",
  "state": "active | done | blocked",
  "evidence": "link to test file + commit hash"
}
```

- Only one task per epic (ideally per person) is `active` at a time.
- **Verified Completion Rate (VCR)** = verified-done tasks / activated tasks. Don't activate new work while VCR is below 1.0 for the current epic — that's a sign something was declared done without real verification.

---

## 8. DZO concepts glossary

| Term | Meaning |
|---|---|
| Epic | A scoped unit of work mapped to one or more DZO products — see `DZO_TECH_ROADMAP.md` section 2 for the full list (Epic 0–9) |
| Product | One of DZO Food, DZO Ride, DZO Biz, DZO HQ — see section 1 |
| Order lifecycle state | One of Placed / Acknowledged / Open for claim / Claimed / Ready-time set / Picked up / Delivered — see section 1 and roadmap section 3 |
| Claim | A driver voluntarily selecting an open order to deliver (not a platform-assigned dispatch) |
| Ready-time signal | The restaurant's notification to a claimed driver that food is nearly done, timed so pickup and completion coincide |
| Commission model | Standard percentage markup on customer orders (the default before any driver subscribes) |
| Driver subscription | The proposed $99/month plan giving subscribed drivers a larger per-order share instead of the standard commission split — see roadmap section 8 |
| VCR | Verified Completion Rate — see section 7 above |

---

## 9. Repository layout

**[TBD — decided by the Technical Lead once Epic 1 starts.]** Proposed starting shape, given four separate products sharing one backend (see roadmap section 0's note on treating Ride/Biz/HQ as separate domains from day one):

```
dzo/
├── backend/              # Epic 1 — shared API, DB, auth (all products build on this)
│   ├── app/
│   │   ├── food/         # Epic 4 domain logic
│   │   ├── ride/         # Epic 6 domain logic
│   │   ├── biz/          # Epic 3 domain logic
│   │   ├── hq/           # Epic 2 domain logic
│   │   └── payments/     # Epic 5, shared across products
│   └── tests/
├── mobile-food/          # Epic 4 — customer app
├── mobile-ride/          # Epic 6 — driver app
├── web-biz/              # Epic 3 — merchant portal
├── web-hq/               # Epic 2 — admin console
├── EPICn_TRACKER.md      # one per epic
├── DZO_TECH_ROADMAP.md
├── WEEK1_CHECKLIST.md    # not yet drafted — see roadmap section 1
└── AGENTS_DZO.md         # this file
```

A monorepo vs. multi-repo decision, and whether mobile apps share a single React Native/Flutter codebase across Food and Ride, are open — this tree is a starting proposal, not a decision.

---

## 10. Topic docs

| Doc | When to read |
|---|---|
| `DZO_TECH_ROADMAP.md` | Before starting any epic — full reasoning on scope, order lifecycle, build order, stack, business model, and open questions |
| `EPICn_TRACKER.md` | Before and during work on that specific epic |
| `WEEK1_CHECKLIST.md` | Not yet drafted — see roadmap section 1 for why (deferred until Epic 1 has a working skeleton and a second hire is onboarding) |
| `PROJECT_SUMMARY_AND_DEMO.md` | Not yet drafted — for stakeholder updates once there's something to demo |

---

## 11. Validation hierarchy

1. **Level 1 — Static analysis:** lint, type-check, dependency/secret scanning (`make lint`)
2. **Level 2 — Unit & integration tests:** per-task tests referenced in the epic tracker
3. **Level 3 — End-to-end:** a full walk-through of the order lifecycle (section 1) across whichever products the change touches — e.g. a change to DZO Biz's acknowledgment flow gets tested through to DZO Ride's claim screen, not just in isolation
4. **Level 4 — Launch/regression gate:** before any staged rollout (roadmap Epic 8), confirm no prior epic's acceptance criteria have regressed

---

## 12. Initialization checklist

- [ ] Read `DZO_TECH_ROADMAP.md` in full at least once
- [ ] Read the tracker for the epic you're assigned to
- [ ] Confirm the repo builds and `make check` passes (once it exists)
- [ ] Confirm which single task is currently `active` for you
- [ ] Confirm you understand the seven-state order lifecycle in section 1

## Session exit checklist

- [ ] `make check` passes
- [ ] Tracker updated with status, evidence, and any deviations
- [ ] Commit made and referenced in the tracker
- [ ] No task left in an ambiguous "half-active" state

---

## 13. Maintenance

- **Fresh-session test:** could someone with zero context answer "what are the four products, what's the order lifecycle, and what epic are we on" using only this file and the roadmap? If not, this file needs updating.
- **Instruction audit:** periodically check that every hard constraint above still reflects real practice — a constraint nobody follows is worse than no constraint, since it teaches people to skim past this file.
- **Monthly review:** try relaxing one constraint on purpose and see if anything breaks. If nothing does, question whether it should still be "hard."

---

## 14. Key principles

1. The order lifecycle in section 1 is the shared source of truth across all four products — when in doubt, check it before inventing new state.
2. Nothing is "done" without verification against the epic tracker's acceptance criteria.
3. Decisions live in files (this one, the roadmap, the trackers), not in memory or chat history.
4. When Charlie's stated design and convenience disagree, raise it explicitly rather than quietly deviating.
5. This file starts as a scaffold and is expected to be edited as real decisions replace the **[TBD]** placeholders above.
