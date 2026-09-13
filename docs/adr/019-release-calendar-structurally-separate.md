# ADR-019: Release Calendar Is Structurally Separate From Canonical Observation Availability and Analysis

## Status
Accepted

## Context

Increment #17 introduces the first representation of *when economic
data is expected*, distinct from every prior increment, which only
ever represented data that already existed (`economic_series`/
`economic_observations`) or deterministic conclusions computed from it
(`inflation_v1.0`, `inflation_what_changed_v1.0`). A release calendar
creates a genuine risk this project hasn't faced before: a scheduled
time, on its own, looks like it "means something" economically — a
release date arriving feels like it should imply new data, and a
missed date feels like it should imply something changed. Neither is
true. FRED's own documentation confirms a release date being on the
calendar does not mean data is available (see
[docs/architecture/release-intelligence-v1.md](../architecture/release-intelligence-v1.md)
§3). The October 2025 CPI shutdown scenario is the concrete case this
decision exists to get right.

## Decision

`ReleaseOccurrence` (schedule facts) and `EconomicObservation`
(canonical data) are separate tables with **no write path between
them** anywhere in #17A or #17B's scope. A scheduled release date
passing can change only a *derived, read-time* schedule status
(`SCHEDULED`/`PAST_DUE`) — never an `EconomicObservation` row, never a
monitor state, never a What Changed event, and never any claim that new
data exists. This holds permanently, not just for #17A — it is not
relaxed when #18 adds an actual release-driven update pipeline; #18's
own design (see the spec's §14) still requires proof against the
required series' *actual persisted observations* before anything
downstream is allowed to change, never proof from the calendar side
alone.

## Alternatives Considered

- **A single `ReleaseOccurrence`-like table carrying both schedule and
  data-availability fields** (e.g. a `data_status` column populated
  optimistically once the scheduled date passes). Rejected: this is
  exactly the collapse the task that produced this ADR was written to
  prevent — it would make "the clock passed a timestamp" and "new data
  exists" look like the same fact in one row, inviting a future bug
  where UI or downstream logic reads the wrong one.
- **A `published` boolean set automatically when `scheduled_date <
  today`.** Rejected for the same reason — it would silently encode
  "scheduled release == data available," which this project has
  independently verified against FRED's own documentation to be false.

## Why This Decision

The permanent architecture principle already governing every other
part of this project — *facts are sourced, calculations are
deterministic* — extends naturally here: a schedule is a fact about
intent (what's expected), not a fact about outcome (what happened).
Conflating them would be a new, previously-nonexistent way for this
system to represent something it doesn't actually know. Keeping them
in genuinely separate tables, with zero write coupling, makes the
invariant a structural property (nothing *can* write across the
boundary because no code path exists to) rather than a convention that
could be violated by a future increment written under time pressure.

## Consequences / Tradeoffs

- Gains: the October 2025 shutdown scenario (and any future one) is
  handled correctly *by construction* — see the spec's §11 — with no
  special-case code, because there was never a write path for a missed
  release to accidentally trigger.
- Gains: #18 can be designed later without reopening this question —
  it inherits the same boundary rather than needing to re-decide it.
- Cost: "Upcoming"/"Recent" release views in #17B carry no
  data-availability signal at all, even once a release's date has
  passed — the UI must be explicit that a `PAST_DUE` schedule status is
  not a claim that data arrived (see the spec's §13).

## Revisit When

- Never, for the core separation itself — this is meant to be
  permanent. What *can* change is which increment is allowed to prove
  data availability and write across a still-separate boundary (#18,
  when it's actually scoped) — the boundary staying intact is the part
  that doesn't move.
