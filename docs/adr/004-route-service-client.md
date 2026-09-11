# ADR-004: Route → Service → Client Layering

## Status
Accepted

## Context

Increment 002 needed to implement `GET /api/v1/series/{series_id}`, which
involves several distinct concerns: handling the HTTP request/response,
deciding what data to fetch and how to normalize it, and actually talking
to FRED over HTTP. All of this logic, at this increment's scale, would
comfortably fit inside a single FastAPI route function — the entire feature
is a few dozen lines of real logic.

## Decision

Split the feature across three layers, each with one responsibility:

- **`app/api/series.py`** (route) — HTTP-specific concerns: reads the
  request, checks configuration, calls the service, translates exceptions
  into `HTTPException`s with specific status codes.
- **`app/services/economic_data.py`** (`EconomicDataService`) —
  application/use-case logic: orchestrates the client calls needed to
  answer "give me this series," normalizes the result into the app's own
  models. No knowledge of HTTP status codes or `httpx`.
- **`app/clients/fred.py`** (`FREDClient`) — FRED-specific HTTP
  communication only: builds requests, applies the timeout, and turns
  FRED's raw responses (success or error) into either plain dicts or typed
  exceptions.

## Alternatives Considered

- **Everything in the route function.** The straightforward option at this
  size — call `httpx` directly inside `get_series()`, parse the response
  inline, raise `HTTPException` directly on any FRED error. Would have
  worked for Increment 002 alone.
- **A generic provider/plugin framework** (e.g. an abstract `DataProvider`
  base class with a `FREDProvider` implementation, a provider registry,
  etc.), anticipating multiple future data sources. Rejected — see below.

## Why This Decision

The route-only approach was rejected not because it wouldn't have worked
for one endpoint, but because it collapses three things that change for
different reasons and at different rates: how FRED's API works (client),
what "the economic data feature" means (service), and how HTTP requests
are handled (route). Keeping them separate means a change to one — e.g.
FRED changing an error response shape — only touches `app/clients/fred.py`,
not the route or the normalization logic.

The generic provider-framework alternative was rejected for the opposite
reason: it would introduce abstraction (an interface, a registry) to serve
a *second* data provider that does not exist yet. Building that
speculatively means guessing its shape before a real second provider's
actual needs are known — likely to be wrong in some way, and definitely
premature. `EconomicDataService` is structured simply enough that
introducing such an abstraction later, if and when a second provider is
actually added, is a contained change — but it is explicitly not done now.

This is the same judgment call named directly in the project's engineering
rules: **don't create a layer that has no real responsibility, and don't
build an abstraction for a need that doesn't exist yet.** Three layers were
justified here because each one already has a distinct, real job to do in
this single endpoint — not because "layers" are good practice in the
abstract.

## Consequences / Tradeoffs

- Gains: each file is independently readable and testable in isolation
  (the client's FRED-specific parsing can be reasoned about without the
  service; the service's normalization can be reasoned about without HTTP
  concerns). Adding a second FRED endpoint (e.g. a different series-related
  operation) has an obvious home in each layer.
- Cost: more files and more indirection than a single-function
  implementation, for a feature that is still, today, only used by one
  route. The value of the separation is paid for now and cashed in later.

## Revisit When

- A second external data provider is actually added — that's the point at
  which it becomes worth asking whether `EconomicDataService` should sit
  behind a shared interface, based on what that second provider's client
  actually looks like, not before.
- Any layer starts accumulating responsibilities that belong to a
  different layer (e.g. HTTP-status logic creeping into the service) —
  that's a signal to move it back, not to add a fourth layer.
