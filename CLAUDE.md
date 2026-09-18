# DZO Backend — Start Here

Read `docs/AGENTS_DZO.md` first — it's the constitution for this project (hard constraints, work rules, session routines, definition of done, repo layout). Then read `docs/DZO_TECH_ROADMAP.md` for the full planning context (the four products, the order/dispatch lifecycle, build order, tech stack, business model, team, and open questions).

This backend (Python/FastAPI + PostgreSQL + SQLAlchemy async + Alembic) is Epic 1 of that roadmap. Follow the hard constraints and work rules in `docs/AGENTS_DZO.md` for anything you do here — in particular: WIP = 1, no code ships without `make check` passing, and the order lifecycle states in `docs/AGENTS_DZO.md` section 1 are the shared source of truth across all four DZO products.
