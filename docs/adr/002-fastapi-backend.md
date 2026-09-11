# ADR-002: FastAPI as the Backend Framework

## Status
Accepted

## Context

This project's core deliverable is an **API** — endpoints returning JSON to
programmatic consumers, eventually including an AI reasoning layer as a
consumer of its own data. A Python web framework needed to be chosen for
Increment 001's minimal backend foundation.

## Decision

Use **FastAPI**, served by **Uvicorn** (an ASGI server).

## Alternatives Considered

- **Flask** — mature, minimal, huge ecosystem. Doesn't provide request/
  response validation or OpenAPI schema generation out of the box; both
  would need to be bolted on (e.g. via Marshmallow/Flask-RESTX) to match
  what FastAPI gives natively.
- **Django (+ Django REST Framework)** — full-featured, batteries-included,
  strong for apps that need an ORM, admin panel, and templating built in.
  Heavier than this project needs at this stage, and its conventions (ORM
  models, app structure) fight against building the data layer
  deliberately and incrementally rather than adopting a framework's
  default shape for it.

## Why This Decision

The project is API-centric from the first endpoint, not incidentally. FastAPI
gives, natively and with minimal ceremony:

- Request/response validation and serialization through Pydantic models
  (used directly in this codebase — see `app/models/series.py` and
  [ADR-005](005-own-data-contract.md)).
- Automatic OpenAPI schema and interactive docs generated from the same
  type-annotated code that implements the routes — no separate schema to
  keep in sync.
- Native `async def` route support when it's eventually needed, without a
  framework migration (see [ADR-003](003-fred-rest-httpx.md) for why routes
  are synchronous *for now* regardless).
- A thin enough footprint that the current single-route, then
  single-integration, application isn't carrying framework weight it isn't
  using yet.

Uvicorn is FastAPI's standard ASGI server pairing — it's what actually
listens on a socket and runs the FastAPI application.

## Consequences / Tradeoffs

- Gains: validation, docs, and typing "for free" from code that would need
  to exist anyway (the route signatures and Pydantic models). Growing into
  async, when justified, requires no framework change.
- Cost: FastAPI is opinionated toward Pydantic-typed code; that's a fit
  here, but it means the project's data models are somewhat coupled to
  Pydantic's conventions rather than framework-agnostic plain classes.

## Revisit When

- The project needs framework features FastAPI doesn't provide and Django
  does (e.g. a built-in admin UI, ORM-first modeling) — unlikely given the
  intended incremental, explicit data-layer approach, but worth naming.
- Performance or ecosystem needs specifically point toward a different
  ASGI framework — no such need exists today.
