# ADR-022: Release-Driven Processing Records Detected Changes and Analytical Consequences Without Persisting Monitor Snapshots or Conflating Schedule With Availability

## Status
Accepted

## Context

Increment #18 connects Release Intelligence (#17A/#17B, frozen) to
canonical economic data updates. Doing this safely required resolving
several related but distinct design questions that all bear on the
same underlying risk: once a pipeline exists whose entire purpose is
"did this release change something," it becomes easy, one convenient
shortcut at a time, for that pipeline to start *asserting* economic
conclusions instead of merely *detecting and reporting* the
consequences of data the deterministic Inflation domain already
computes. This is the same class of risk ADR-019 addressed for the
release calendar itself (a schedule fact "looks like it means
something" it doesn't) and ADR-021 addressed for the explainability
system (curated content "looks like it's just describing" a result
when it could instead be computing one) -- applied here to a pipeline
that actually writes canonical data and must not overstate what that
write proves.

Four concrete temptations were identified during design, each of which
would have been a smaller, more convenient thing to build than what
this ADR commits to:

1. Persist a full `InflationMonitorResult` (or a before/after pair of
   them) alongside each detected change, since it's readily available
   and "just in case" richer auditing is wanted later.
2. Let a release-scoped comparison re-derive Inflation classification
   logic directly (comparing raw r_3m/r_6m/r_12m values itself) instead
   of reusing the frozen comparison primitives, since the release-scoped
   before/after shape doesn't exactly match `inflation_what_changed_v1.0`'s
   month-over-month one.
3. Let `ReleaseSeriesMapping` carry a `role`/`importance` field (e.g.
   `PRIMARY`), since it would make the mapping table "more useful" to
   a future reader at a glance.
4. Introduce full observation vintage/history tracking, since it would
   make the audit trail "more complete."

## Decision

**Release-driven processing persists structured, typed *evidence* of
detected provider changes and their deterministic analytical
consequences -- never a canonical-result snapshot, never a
re-derivation of classification logic, and never an economic-
significance judgment baked into curation data.** Concretely:

- `ReleaseAnalysisUpdate` stores individual `ChangeEvent`-shaped rows
  (component, event type, field, previous/current value, delta,
  evaluation period, methodology id, data basis) -- never a full
  `InflationMonitorResult`, before or after. No
  `inflation_monitor_snapshots` table (or anything shaped like one)
  exists (checked structurally: `tests/test_release_processing_architecture.py::TestNoFullMonitorSnapshot`).
- Every analytical consequence is computed by calling
  `app.domain.inflation`'s existing exact-period primitives
  (`compute_series_momentum_at`/`compute_target_at`/`compute_confirmation_at`)
  and `app.domain.inflation_what_changed`'s existing comparators
  (`compare_series_momentum_section`/`compare_target_section`/
  `compare_confirmation_section`), unmodified, with a release-scoped
  before/after pair of snapshots substituted for
  `inflation_what_changed_v1.0`'s own month-over-month pair (see
  `docs/architecture/release-processing-v1.md` §8.1-§8.2 for the exact
  mechanism). No comparison or classification logic was reimplemented
  (checked structurally: `TestExistingComparisonPrimitivesAreReused`,
  `TestNoInflationThresholdOrClassificationLogicInReleaseProcessing`).
- `ReleaseSeriesMapping` has exactly five columns --
  `id`/`economic_release_id`/`series_id`/`active`/`created_at` -- and
  answers only "what should be checked," never "what does this mean."
  Which `inflation_what_changed_v1.0` component a series' change could
  affect is computed separately, by
  `app.domain.release_processing.components_for_series`, a verified
  mirror of `app.services.inflation.InflationMonitorService`'s own
  existing wiring -- never read from curated mapping data (checked
  structurally: `TestNoRoleEnumOnReleaseSeriesMapping`).
- `EconomicObservation` remains one canonical current value per
  `(series, observation_date)`, overwritten on revision, exactly as
  before #18. `ReleaseObservationUpdate` is the append-only record of
  *that a revision was detected, by which check, with what previous and
  new value* -- it explicitly does not claim full point-in-time vintage
  capability, and the existing "Latest revised data" product language
  and its underlying limitation (`docs/methodology/inflation-monitor-v1.0.md`'s
  "Data basis" section: no true historical vintages) is unchanged by
  this decision.

## Alternatives Considered

- **Persist before/after `InflationMonitorResult` snapshots.** Rejected:
  the live Monitor is already, deliberately, fully stateless and
  reproducible from persisted observations alone
  (`app.services.inflation.InflationMonitorService.get_result`'s own
  docstring: "two calls in immediate succession, with no intervening
  write, return identical results") -- persisting a full result would
  both duplicate that guarantee unnecessarily and go stale the moment
  any other series updates independently, inviting a future bug where
  a stored snapshot and the live Monitor silently disagree.
- **Let release-scoped comparison re-derive classification from raw
  values.** Rejected outright: this is precisely the "second, informal
  implementation of `inflation_v1.0`" risk this project has
  structurally avoided everywhere else (release calendar vs.
  observations, explanations vs. canonical results). The frozen
  comparators already generalize cleanly to a release-scoped before/
  after pair (§8.1 of the architecture doc) with zero modification
  needed -- there was no genuine technical obstacle forcing a
  reimplementation, only convenience, which is not a sufficient reason.
- **A `role` enum on `ReleaseSeriesMapping`.** Rejected: "PRIMARY"
  vs. "SUPPORTING" is an economic-significance judgment, and the
  moment such a field exists, something downstream will eventually
  read it as if it were one -- exactly the same collapse-of-separation
  risk ADR-019 was written to prevent structurally, applied to a new
  table.
- **Full observation vintage/history (ALFRED-style).** Rejected for
  #18: nothing in this increment's actual required product behavior
  (audit that a revision was detected, and what its analytical
  consequence was) needs reconstructing "what did EI show on date D" --
  and building the schema for that is a much larger, largely
  independent decision the frozen methodology's own "Data basis"
  section already scopes this product away from making implicitly.

## Why This Decision

Each of the four choices above is the same judgment applied
consistently: build the smallest structure that makes a *real,
already-required* product question answerable and auditable, and
resist building anything richer "because it would be nice to have" --
richness is exactly where an accidental second source of economic
truth, or an accidental economic-significance judgment, tends to creep
in unnoticed. Reusing the frozen comparison primitives unmodified,
rather than adapting them, means #18 cannot drift from
`inflation_v1.0`/`inflation_what_changed_v1.0` even if a future
contributor extends #18 without rereading either specification.

## Consequences / Tradeoffs

- Gains: a `ReleaseAnalysisUpdate` row can never disagree with what the
  live Monitor or What Changed endpoint would independently compute
  for the same evidence, because both paths call the identical
  underlying functions.
- Gains: `ReleaseSeriesMapping` can be extended to a new series the
  moment a real deterministic consumer for it exists, with no
  redesign -- the mapping shape never needed to anticipate what that
  consumer would be.
- Cost: a `ReleaseAnalysisUpdate` row cannot answer "what was the full
  Inflation Monitor state at the moment this check ran" by itself --
  only "what changed for this specific component/field, at this
  period." A consumer wanting the full contemporaneous state must
  combine this evidence with a separate live Monitor read (or, in the
  future, a genuine feature request to persist more, decided
  deliberately then).
- Cost: `#18` cannot answer "what did EI believe about period X on
  historical date D" -- only "what does EI's current, latest-revised
  data say now, and what did EI most recently detect changed." This is
  an accepted, pre-existing product limitation (`latest_revised_data`),
  not a new one #18 introduces.

## Revisit When

- A genuine product need emerges to reconstruct historical
  point-in-time state (not merely "what changed," but "what was
  believed as of date D") -- that is the point to design real vintage
  architecture deliberately, informed by that actual need, not before.
- A second real data provider is integrated -- at that point, revisit
  whether `ReleaseSeriesMapping`'s plain-string `series_id` and
  `FREDClient`'s extended-in-place `get_observations` still fit, the
  same reversal condition ADR-020 already states.
- A future increment's UI genuinely needs a persisted full-result
  snapshot for some new purpose (e.g. a historical "as reported"
  comparison feature) -- design that snapshot store deliberately then,
  as its own explicit decision, not by quietly widening
  `ReleaseAnalysisUpdate`.
