# ADR-020: FRED V1 Release Occurrences Are Date-Level, and `FREDClient` Is Extended Rather Than Wrapped in a Provider Abstraction

## Status
Accepted

## Context

Increment #17's architecture audit raised two related but distinct
questions: how to uniquely identify a release occurrence given FRED's
actual data shape, and how to structure the client code that fetches
it. Both were left open pending verification against FRED's official
API documentation, which has since been done (see
[docs/architecture/release-intelligence-v1.md](../architecture/release-intelligence-v1.md)
§3). They're combined into one ADR because they're the same underlying
judgment — *don't model or build for a capability FRED doesn't actually
have yet* — applied to the data model and to the client code
respectively, and recording them separately would split one decision
into two smaller ones for no benefit.

**Verified FRED constraint**: `fred/release/dates` returns
`(release_id, date)` — no stable provider-native per-occurrence ID, and
no trustworthy time-of-day timestamp. A release date being present does
not mean data is available (`release_last_updated`, where FRED exposes
it, is provider metadata, not proof — see the spec's §3).

## Decision

**Occurrence identity**: `UNIQUE(economic_release_id, scheduled_date)`
— date-level, matching FRED's own data shape exactly. No
`scheduled_at` timestamp, no `source_timezone`, no `time_precision`
field is invented from FRED calendar data (see the spec's §5–§6).

**Client structure**: extend the existing `FREDClient`
(`app/clients/fred.py`) with exactly the one release-dates method #17A
needs. No `ReleaseProvider`/`FREDReleaseClient` abstraction, no
provider interface or registry. This is a direct, named application of
[ADR-004](004-route-service-client.md)'s own stated reversal
condition — *"A second external data provider is actually added —
that's the point at which it becomes worth asking whether this should
sit behind a shared interface... not before"* — which has not happened:
release dates are still FRED, the same base URL, auth, timeout, and
error taxonomy as every other `FREDClient` method.

## Alternatives Considered

- **A synthetic per-occurrence ID** (e.g. hashing `release_id`+`date`,
  or an auto-generated UUID exposed as if it were provider-native).
  Rejected: it would misrepresent something FRED doesn't actually give
  us as if it were sourced, when it's really just EI's own `id` primary
  key restated — the real primary key already serves this purpose
  without pretending it came from FRED.
- **Inventing a conventional release time** (e.g. defaulting US
  releases to 8:30 AM Eastern). Rejected outright and explicitly: this
  would be fabricated precision presented as fact, violating this
  project's permanent invariant against inventing data the source
  doesn't provide.
- **A `FREDReleaseClient` or `ReleaseProvider` abstraction now**, ahead
  of a second schedule provider. Rejected for the same reason ADR-004
  rejected a generic provider framework for `EconomicDataService`: it
  would guess an interface shape before a second real provider (BLS,
  BEA, Federal Reserve, Census) exists to inform what that interface
  actually needs to support.
- **A release-series `FREDClient` method, added now for #18's
  eventual benefit.** Rejected: #17A's calendar functionality doesn't
  need it, and adding it "for later" is exactly the premature-
  abstraction pattern this project's engineering discipline already
  rejects elsewhere (ADR-004, ADR-009).

## Why This Decision

Both halves of this decision are the same discipline this project has
already applied twice (`EconomicDataService`'s FRED-only client,
`SeriesRepository`'s single concrete repository): build exactly what
the verified, real data source supports, and revisit only when a real
second case exists to inform the redesign — never speculatively.
Matching the occurrence identity to FRED's actual `(release_id, date)`
shape, instead of inventing a richer one, keeps the persisted data
honest about what is and isn't known.

## Consequences / Tradeoffs

- Gains: no fabricated timestamp or timezone can ever leak into the
  product as if it were a sourced fact — the schema makes the
  limitation structural, not just documented.
- Gains: `FREDClient` stays exactly what it already is — one class, one
  provider, one growing set of methods — with no new abstraction to
  maintain until a second provider genuinely requires one.
- Cost: a reschedule that changes a release's date produces a *new*
  occurrence row rather than an updated one (see the spec's §6 and
  §11) — an accepted, documented limitation of a date-only identity,
  not an oversight.
- Cost: #17B cannot display a release time at all in V1 — date only.

## Revisit When

- A second schedule provider (BLS, BEA, Federal Reserve, Census, or a
  richer FRED capability than currently documented) is actually
  integrated — that is the point to design a provider abstraction, an
  exact-time/timezone/DST model, and occurrence reconciliation across
  providers, informed by what that second source's real data shape
  turns out to be (see the spec's §16). Not before.
