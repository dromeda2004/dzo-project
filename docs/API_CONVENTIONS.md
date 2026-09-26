# API_CONVENTIONS.md — DZO Backend API Conventions

Established in `epic1.task4`. Every future router (DZO Food, Ride, Biz, HQ)
should follow these rather than inventing its own shape.

## Error responses

Every 4xx/5xx response — from any router, including ones raised by FastAPI
itself (validation errors, 404s) — comes back in one shape:

```json
{
  "error": {
    "code": "unauthorized",
    "message": "Incorrect email or password",
    "fields": null
  }
}
```

- `code` is a stable, snake_case slug derived from the HTTP status phrase
  (`401` → `unauthorized`, `403` → `forbidden`, `404` → `not_found`), except
  `422` validation errors, which always use `code: "validation_error"`.
- `fields` is only present for validation errors: a map of field path →
  list of error messages.

This is wired up once in `app/core/error_handlers.py` via
`register_exception_handlers(app)` — route handlers just `raise
HTTPException(status_code=..., detail=...)` as normal; the handler does the
enveloping. Don't build a parallel exception class — this covers all of
FastAPI/Starlette's built-in exceptions already.

## Pydantic schema conventions

- Request bodies: `XCreate` / `XUpdate` for CRUD, or `XRequest` for a
  non-CRUD action (e.g. `LoginRequest`).
- Responses: `XOut` for CRUD reads, or `XResponse` for a non-CRUD action
  (e.g. `TokenResponse`).
- Any response schema that reads directly from a SQLAlchemy model instance
  inherits `app.schemas.base.ORMBase` (sets `from_attributes=True`) instead
  of repeating that config inline.
- Schemas live under `app/schemas/`, one file per domain (`auth.py`,
  `errors.py`, ...), mirroring `app/models/`.

## Versioning

None yet — there are no external consumers of this API (all four DZO
clients are in-house). Revisit before DZO Biz is ever sold standalone or
DZO Ride serves non-Food logistics (roadmap Epic 9), at which point a URL
prefix (`/v1/...`) is the likely approach.

## Third-party integrations

Config scaffolding for payments/maps/push credentials lives in
`app/core/config.py` (`stripe_secret_key`, `google_maps_api_key`,
`fcm_server_key`) — all optional, since none of these providers are
confirmed yet (see `docs/DZO_TECH_ROADMAP.md` section 5). They're unused
until Epic 5 (payments) or Epic 6 (DZO Ride) actually integrate.
