# ADR-023: The Release-Processing Read Model Exposes Detected Observation Changes and Analytical Consequences as Sibling Facts, Never Nested by Causality

## Status
Accepted

## Context

Increment #19B builds the first public, read-only API projection over
#18's persisted `ReleaseCheckRun`/`ReleaseObservationUpdate`/
`ReleaseAnalysisUpdate` evidence
(`GET /api/v1/releases/processing-status`). The #19B audit's candidate
contract proposed wrapping each detected data change together with the
analytical consequences it produced, in a shape like:

```
detected_change: {
  observation: { series_id, change_type, ... },
  analysis_consequences: [ { component, event_type, ... }, ... ]
}
```

This reads naturally -- a revision to a series "caused" a metric or
state change -- and it is the shape a consumer would probably reach
for first. It is also not what the database actually records.

`ReleaseObservationUpdate` and `ReleaseAnalysisUpdate` (see
`app/db/models.py`) each reference only `release_check_run_id`.
Neither carries a foreign key to the other, and
`app/services/release_processing.py`'s `_apply_changes_and_compute_analysis`
computes analysis changes from a release-scoped before/after
comparison of the whole evaluation period -- not from any single
observation row. In practice a `ReleaseCheckRun` can persist multiple
observation changes and multiple analysis changes in the same run with
no recorded one-to-one (or even one-to-many) correspondence between a
specific observation and a specific analysis event; see
`tests/integration/test_release_processing_service.py::test_no_analytical_change_when_a_revision_does_not_move_any_canonical_value`
for a case where a real, persisted observation change produces zero
analysis changes, and the two-series PARTIAL_FAILURE tests for cases
where one series' change and another series' failure are both real,
independent facts within the same run.

Manufacturing a `detected_change { observation, analysis_consequences[] }`
wrapper in the API response would assert a causal link -- "this
specific analysis event happened because of this specific observation"
-- the persistence layer does not actually establish and #18 was
never designed to prove. This is the same class of risk ADR-021
addressed for explanations ("looks like it's just describing a result"
while actually asserting one) and ADR-022 addressed for #18's own
write path (a convenient shortcut that would let a detection pipeline
start asserting more than it can prove): a read model is exactly as
capable of overstating evidence as a write path is, and a nested JSON
shape is a very easy way to do it silently.

## Decision

`ReleaseProcessingStatusItem` (see `app/models/release_processing_read.py`)
exposes `detected_observation_changes` and `detected_analysis_changes`
as two independent, top-level, sibling arrays. Both are scoped to the
occurrence (every run the occurrence has ever had, not just the
latest -- see this increment's retry-history-preservation guarantee in
`app/services/release_processing_read.py`), and neither array's items
reference the other. No `detected_change` wrapper, and no
`analysis_consequences` field nested under an observation, exist
anywhere in this contract -- enforced structurally by
`tests/test_release_processing_read_architecture.py::TestNoCausalNestingBetweenObservationAndAnalysisChanges`,
not left to convention.

A consumer that wants to *suggest* (not assert) a relationship between
a given observation change and nearby analysis changes may do so by
comparing `evaluation_period`/`observation_date` and the run's shared
`checked_at` window at render time -- a presentation-layer inference,
clearly distinguishable from a persisted fact, and reversible without
a schema or contract change.

## Consequences / Tradeoffs

- Gains: the response can never claim a causal relationship more
  precise than what `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate`
  actually record. A future reader of this contract cannot be misled
  into thinking #18 tracks per-observation causal attribution when it
  does not.
- Gains: the contract survives unmodified if #18's own attribution
  granularity ever changes (finer or coarser) -- sibling facts require
  no schema renegotiation the way a wrong nesting assumption would.
- Cost: a consumer wanting to *display* "this change likely explains
  that metric shift" must do its own period/time-window correlation
  client-side (or a future increment must add a deliberate, explicitly
  named correlation field once persistence actually supports it) --
  #19B does not hand back that correlation pre-computed.

## Revisit When

- #18's write path is deliberately extended to persist an actual
  per-observation causal attribution (e.g. an analysis event gains a
  genuine foreign key to the specific observation update(s) that
  produced it) -- at that point, add an explicitly named, additive
  correlation field to this contract; do not retrofit nesting onto the
  existing sibling arrays.
- A real frontend consumer of this endpoint (#19C or later) finds the
  sibling-arrays shape genuinely unworkable for its UI and a
  presentation-layer correlation is not sufficient -- revisit with that
  concrete UI requirement in hand, not speculatively.
