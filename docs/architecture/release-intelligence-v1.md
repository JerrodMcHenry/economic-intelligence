# Economic Intelligence
# Release Intelligence Specification v1

| | |
|---|---|
| Specification version | 1 |
| Status | **FROZEN FOR #17A/#17B** |
| Scope | Release calendar (catalog + occurrences) and its read API only |
| Canonical data provider, V1 | FRED |
| Data basis | Release *schedule* facts only — never observation values |
| AI dependency | None |
| Depends on | [Increment #17 architecture audit] (prior session; superseded in its details by this document where they conflict) |

> **This document is normative for #17A and #17B.** Where an earlier
> audit or conceptual proposal conflicts with this document, this
> document wins — it reflects verification against FRED's official API
> documentation and an explicit narrowing of scope.

This document is documentation only. It does not implement, and must
not be read as authorizing implementation of, any production code, API
endpoint, database migration, SQLAlchemy model, service, or repository.
Production implementation is a separate, explicitly authorized task
("Increment #17A"/"#17B") and has not begun.

---

## 1. Purpose

Release Intelligence answers, eventually: what releases are coming up,
what was just released, which canonical series are affected, whether
new observations actually became available, which deterministic
monitors changed as a result, and what changed after the release. This
document freezes only the first slice of that: a curated **release
calendar** — what's scheduled, and whether a scheduled date has passed
— with no claim whatsoever about whether new data exists. Everything
downstream of "does new data exist" is explicitly out of scope here
(§14).

---

## 2. Permanent invariants

These hold for #17A, #17B, and every future increment that builds on
this document. They are not V1-only conveniences.

1. **A scheduled release date passing must never itself change a
   canonical economic conclusion.** No `EconomicObservation` write, no
   monitor state change, no What Changed event, and no claim that new
   data exists may ever be caused merely by a schedule date passing.
2. **Release scheduling metadata and economic observation availability
   are structurally separate concepts**, persisted in structurally
   separate tables, with no write path from one to the other anywhere
   in this document's scope.
3. **Facts are sourced. Calculations are deterministic. AI is
   interpretive.** Release Intelligence must remain fully useful with
   AI completely disabled — nothing in this document's scope calls AI,
   and nothing ever will without a separate, explicit decision.
4. **News/context can never determine release schedule truth,
   observation availability, economic observations, monitor states, or
   What Changed events** (§15).
5. **Missing timing precision must remain explicit, never fabricated.**
   If the source data doesn't give a fact (an exact time, a
   cancellation, a confirmation that data exists), this system does
   not invent one.

---

## 3. Source limitations (verified against FRED's official API)

FRED's `fred/release/dates` endpoint returns release occurrences as
`(release_id, date)` — **no stable provider-native per-occurrence ID**.
Therefore occurrence identity must be derived from `(release, date)`,
not from a provider-issued occurrence ID (§6).

FRED's release-dates data exposes **dates, not trustworthy time-of-day
release timestamps**. #17A therefore MUST NOT invent or persist a
`scheduled_at` timestamp, a conventional release time (e.g. "8:30 AM"),
a `source_timezone`, or any "exact time" precision level from FRED
calendar data. Every release occurrence in #17A carries a date only.

FRED documents that a release date being on the calendar does **not**
mean data is available on FRED. `scheduled release != data available`
is therefore a permanent invariant (§2.1), not a V1 simplification to
be "upgraded" later — it will still be true once a second, more precise
provider is integrated.

FRED may expose a `release_last_updated` field on release-dates
responses (particularly when dates without data are requested). This
field is **not** treated as canonical EI proof that required
observations are available, and #17A does not persist it. It may be
treated as raw, non-canonical provider metadata by a future
increment, if and when that increment proves it useful — never as a
substitute for checking the actual required series observations
themselves (that check belongs to #18, §14).

---

## 4. `EconomicRelease` contract (conceptual — not an implemented model)

Represents one recurring, curated release definition (e.g. "Consumer
Price Index").

| Field | Notes |
|---|---|
| `id` | EI's own canonical identity. |
| `name` | Curated, human-readable release name. |
| `provider` | String, e.g. `"FRED"`. Default/only value in V1. |
| `provider_release_id` | The provider's own release identifier, kept separate from `id` — mirrors the existing `EconomicSeries.id` vs. `EconomicSeries.series_id` separation already established in this codebase. |
| `official_url` | Nullable. |
| `active` | Curation toggle — only `active=true` releases are ever synced or returned. |
| `created_at` / `updated_at` | Standard timestamps. |

Canonical EI identity (`id`) and provider identity (`provider` +
`provider_release_id`) remain separate, unique together, never
conflated — the same discipline `EconomicSeries` already applies.

The release catalog itself is **curated**, not synced wholesale from
FRED's full release list — see §12.

---

## 5. `ReleaseOccurrence` contract (conceptual — not an implemented model)

Represents one scheduled instance of a release.

| Field | Notes |
|---|---|
| `id` | EI's own canonical identity. |
| `economic_release_id` | References the parent `EconomicRelease`. |
| `scheduled_date` | Date only. The one fact FRED reliably gives us. |
| `first_seen_at` | Set once, at first sync. |
| `last_seen_at` | Updated every time sync observes this occurrence again. |

Explicitly **not** included in #17A, and not to be added without a
fresh, explicit decision: `scheduled_at` (timestamp), `source_timezone`,
any `time_precision` field, `cancelled_at`/cancellation support,
`published_at`, `data_status`, `analysis_status`. None of these can be
reliably sourced from FRED's date-only calendar feed in #17A, and
inventing a value for any of them (a fake time, a fake timezone, a
guessed cancellation) would violate invariant §2.5.

---

## 6. Occurrence identity

**`UNIQUE(economic_release_id, scheduled_date)`.**

This follows directly from §3: FRED's own data shape is
`(release_id, date)`, with no stable per-occurrence ID to key on
instead. A reschedule that keeps the same date is not distinguishable
from "nothing changed" (there is nothing else to compare), which is
correct — nothing needs to happen. A reschedule that changes the date
is, under this identity, **not** merged into the old row: the old
occurrence's `scheduled_date` stays as it was (accurate, historical),
and a new occurrence row appears at the new date if/when sync observes
it. This is a deliberate, accepted limitation of a date-only provider
feed, not an oversight — see §11 for why this is the *correct* behavior
for the shutdown scenario specifically, and §16 for when a richer
identity becomes possible.

---

## 7. Derived status semantics

V1 defines exactly two statuses: **`SCHEDULED`** and **`PAST_DUE`**.

Status is **derived, never persisted**, computed by a pure domain
function that takes the comparison date **explicitly as a parameter**
— never by reading `date.today()` internally:

```
classify_schedule_status(scheduled_date: date, as_of_date: date) -> Literal["SCHEDULED", "PAST_DUE"]
```

- `scheduled_date >= as_of_date` → `SCHEDULED`
- `scheduled_date < as_of_date` → `PAST_DUE`

This is total and reproducible: every persisted `ReleaseOccurrence` has
a non-null `scheduled_date` (§5), so every occurrence has a well-defined
status for any given `as_of_date` — there is no input for which this
function needs a third answer. **`UNKNOWN` is therefore not defined in
#17A** — it appeared in the original conceptual proposal, but nothing
in this frozen scope ever produces an occurrence without a known date,
so there is no case for it to represent. It is not being permanently
rejected — if a future source genuinely supplies incomplete data, this
function's signature can be revisited then, on real need.

`CANCELLED` is likewise not defined in #17A: FRED's date-only calendar
gives no reliable signal that a release was cancelled (a cancelled
release's date most likely simply stops appearing, which reads as an
occurrence sync no longer refreshing `last_seen_at` — not as a
persisted cancellation fact). Inventing `CANCELLED` support without a
reliable source for it would violate §2.5.

Explicitly passing `as_of_date` (never defaulting to "now" inside the
domain function) keeps this reproducible and trivially testable — the
same discipline already used for `inflation_v1.0`'s pure classification
functions.

---

## 8. Idempotent sync semantics

Sync is **explicit only** — no scheduler, no background job, no
automatic trigger (none exists anywhere in this project today; adding
one is out of scope here). Sync never ingests observations, never
recomputes a monitor, never calls AI, never touches news.

Sync behavior, per curated `active=true` `EconomicRelease`:

- Fetch that release's dates from FRED (§9's client method).
- For each `(release, date)` returned: look up the existing
  `ReleaseOccurrence` by `(economic_release_id, scheduled_date)`.
  - **Found** → update `last_seen_at = now()`. Nothing else changes —
    there is no other mutable field left to update (§5).
  - **Not found** → insert a new row with
    `first_seen_at = last_seen_at = now()`.
- **Never delete** a `ReleaseOccurrence`. A release that stops appearing
  in a later sync (aged out of the provider's window, or genuinely
  cancelled with no reliable signal) is represented by a stale
  `last_seen_at`, not by removal. Historical occurrences are permanent,
  local, auditable facts about what was once on the calendar.
- A provider failure for one release must not prevent syncing the
  others — degrade per-release, the same pattern
  `SeriesDiscoveryService` already uses for FRED search failures.
- **Provider failure never erases persisted release history** — a
  failed sync call simply doesn't update anything; every previously
  persisted row remains fully intact and readable.

---

## 9. API contract direction

**One deterministic, database-only endpoint**: `GET /api/v1/releases`.

Filters justified by the V1 UI: `start_date`, `end_date`, `limit`,
`offset`, `order` (`asc`/`desc`). No `status` filter (status is
derived, not stored, and the two V1 frontend views are fully
constructible from date-range filters alone — see below). No `source`
or `release` filter in #17A — with exactly one provider and a small
curated catalog, neither is genuinely useful yet; either may be added
later if a concrete need appears.

**No `/upcoming` or `/recent` endpoint in #17A.** "Upcoming Releases"
and "Recent Releases" are **frontend/product views** over this one
contract:

- Upcoming ≈ `GET /api/v1/releases?start_date=<today>&order=asc`
- Recent ≈ `GET /api/v1/releases?end_date=<today>&order=desc`

`GET /api/v1/releases` **must never call FRED** — it reads only
persisted `ReleaseOccurrence`/`EconomicRelease` rows, computing each
row's derived status (§7) with `as_of_date` set from the request time
at the route/service boundary (not inside the domain function itself).
External refresh (§8) is a wholly separate, explicit write path (a
sync trigger, mirroring `POST /series/{id}/sync`'s existing shape),
never invoked implicitly by a read.

Client method: `FREDClient` is extended with exactly the one method
#17A actually needs — fetching release dates for a given
`provider_release_id`, including dates that don't yet have associated
data (so upcoming/scheduled occurrences are actually visible, not just
past ones). No release-series method is added — that capability
belongs to whichever increment actually needs a release→series mapping
(§14), and adding it now for hypothetical future use is exactly the
premature-abstraction pattern this project's ADRs already reject
(ADR-004, ADR-009). No provider abstraction is introduced — FRED
remains the sole provider `FREDClient` talks to (§16).

---

## 10. Failure isolation

Reuses the project's existing, established failure taxonomy — no new
error model:

| Failure | Existing precedent | Applies to |
|---|---|---|
| Provider unconfigured | 503, "not configured" | sync only |
| Timeout | `FREDTimeoutError` → 504 | sync only |
| Auth failure | `FREDAuthError` → 503 | sync only |
| Upstream/malformed | `FREDUpstreamError` → 502 | sync only |
| DB unavailable | `OperationalError` → 503 | both |
| Other DB error | `SQLAlchemyError` → 500 | both |

`GET /api/v1/releases` depends on PostgreSQL only. If FRED is
unreachable, unconfigured, or the sync path has never run, the read
endpoint still succeeds — with whatever's currently persisted (possibly
nothing). Local reads and external sync fail completely independently,
by construction (different service methods, no shared code path) — the
same discipline already documented for `.../observations` and
`.../transform` ("Database-only: never calls FRED").

---

## 11. Shutdown / missing-data example (October 2025 CPI-style scenario)

1. A curated `EconomicRelease` row exists for CPI. An earlier sync
   persisted a `ReleaseOccurrence` with `scheduled_date` in October
   2025.
2. The scheduled date passes.
3. `classify_schedule_status(scheduled_date, as_of_date)` now returns
   `PAST_DUE` for that occurrence — a pure computation, no write of any
   kind occurs.
4. The required series observations (`CPIAUCSL`, `CPILFESL`) remain
   exactly whatever was last actually persisted in
   `economic_observations` — untouched, because #17A's scope contains
   no write path from `ReleaseOccurrence` to `EconomicObservation` at
   all (§2.2).
5. The Inflation Monitor (`inflation_v1.0`, frozen, unmodified) reports
   exactly what its own existing logic already reports from real
   persisted data — `INSUFFICIENT_DATA` if genuinely stale, or its last
   valid state — with **zero knowledge that a release calendar even
   exists**.
6. If the actual date shifts (a real reschedule, e.g. the release
   resumes three weeks later), the original occurrence's status stays
   `PAST_DUE` (accurate — that date came and went with nothing
   released), and a later sync persists a *new* occurrence at the new
   date (§6) — no occurrence is silently rewritten to hide that the
   original date passed.

Nothing above requires special-case code. It is the direct, by-
construction consequence of §2's invariants and §5/§6/§8's design —
which is itself the strongest argument that the design is right.

---

## 12. #17A scope (frozen)

- `EconomicRelease` (§4), `ReleaseOccurrence` (§5) — persistence only,
  no migration authored by this document.
- `FREDClient` extended with one release-dates method (§9). No provider
  abstraction.
- Idempotent catalog + occurrence upsert, per-release degrade, no
  deletion (§8).
- `GET /api/v1/releases` (§9), database-only, no `/upcoming`/`/recent`
  routes.
- Derived `classify_schedule_status` domain function (§7),
  `SCHEDULED`/`PAST_DUE` only.
- Explicit sync trigger only — no scheduler, no automatic ingestion, no
  monitor recomputation, no AI, no news.
- Release catalog is curated (migration-seeded, `active` flag) — never
  a full sync of FRED's release list.

**Not in #17A**: `ReleaseSeriesMapping` (deferred to #18, §14),
`published_at`, `data_status`, `analysis_status`, `CANCELLED`,
`UNKNOWN`, `scheduled_at`/timezone/time-precision fields,
`ReleaseObservationUpdate`, `AnalysisUpdate`, any release-series
`FREDClient` method.

---

## 13. #17B scope (frozen)

Presentation only. Route `/releases`, with **Upcoming Releases** and
**Recent Releases** sections, both reading the single
`GET /api/v1/releases` contract with different date-range filters
(§9) — no separate backend endpoint per section.

V1 displays **date only** — no fabricated release time. The UI must
visually distinguish *scheduled date* from *data availability*: since
#17A's API carries no data-availability signal at all, the UI must not
imply one exists (no "data available" badge, no green/red readiness
indicator, no wording that could be read as a data-availability claim).
`SCHEDULED`/`PAST_DUE` is a schedule fact only, displayed as such.

No AI, no news, no observation ingestion, no client-side calculation of
status or anything else the backend already determines — the same
presentation-only discipline already established for `/inflation`.

---

## 14. #18 deferred scope (not designed here)

#18 will own, when it is actually scoped (this document does not
pre-commit any of these entities' final shape):

- Curated release → canonical series mapping (`ReleaseSeriesMapping` or
  its eventual equivalent) — deliberately deferred rather than added in
  #17A, because #17A's calendar functionality doesn't need it, and
  because `EconomicSeries` rows depend on ingestion state — release
  calendar persistence should not depend on whether a canonical series
  happens to already be synced into a given database. #18 designs this
  mapping alongside the actual observation-update workflow that needs
  it, not before.
- Observation availability checks, proven against the required series'
  actual persisted observations — never against `release_last_updated`
  or any other calendar-side signal (§3).
- Actual series sync triggered by a due release.
- `ReleaseObservationUpdate`, or a simpler equivalent, only if still
  justified once #18 is scoped.
- Deterministic monitor recomputation and release-driven What Changed.
- `published_at`/`data_status`/`analysis_status` modeling, as actually
  required.
- Scheduler/background execution architecture, if required.

---

## 15. News boundary

News is separate future context (#20+). News may eventually *reference*
a release occurrence for display grouping, but can never determine
release schedule truth, observation availability, economic
observations, monitor states, or What Changed events. No code path in
#17A or #18 as scoped here gives news any way to write to
`economic_releases`, `release_occurrences`, `economic_observations`, or
any monitor result — the boundary is architectural (no such repository
method exists for it to call), not a convention to remember.

---

## 16. Future exact-time / provider enrichment (deferred)

When a real second schedule provider is integrated (BLS, BEA, Federal
Reserve, Census, or a FRED capability proven richer than §3 currently
documents), revisit — as a fresh, explicit decision, not by extending
today's fields ad hoc:

- Provider abstraction (still not warranted by FRED alone, per ADR-004
  and ADR-020).
- An exact `scheduled_at` timestamp.
- An IANA `source_timezone`.
- DST handling.
- A `time_precision` field distinguishing date-only from exact-time
  occurrences.
- Provider occurrence reconciliation (the same release appearing from
  two sources with two different native identities).

None of these fields are built now. Building them before a source
exists to populate them honestly would violate §2.5.

---

## 17. Acceptance invariants (checklist for #17A/#17B implementation)

- [ ] No `EconomicObservation` row is ever written by any code path
      introduced under this document's scope.
- [ ] No monitor state or What Changed event ever changes as a result
      of release calendar sync or a schedule date passing.
- [ ] `GET /api/v1/releases` succeeds (with whatever is persisted, or
      empty) when FRED is unreachable, unconfigured, or has never been
      synced.
- [ ] Sync is idempotent: running it twice in a row with no new
      provider data produces no duplicate rows and no changed
      `scheduled_date` values, only refreshed `last_seen_at`.
- [ ] A provider failure during sync for one curated release does not
      prevent syncing the others, and does not delete or alter any
      previously persisted occurrence.
- [ ] `classify_schedule_status` never reads the system clock itself —
      every call site passes `as_of_date` explicitly.
- [ ] No `scheduled_at`, `source_timezone`, `time_precision`,
      `cancelled_at`, `published_at`, `data_status`, or
      `analysis_status` field exists on `ReleaseOccurrence` in #17A.
- [ ] No `ReleaseSeriesMapping` table or `role` enum exists in #17A.
- [ ] No AI import, no news import, and no scheduler/background job
      exists anywhere in the release-calendar code path.
- [ ] The frontend `/releases` page never implies data availability —
      only a scheduled date and its derived schedule status.
