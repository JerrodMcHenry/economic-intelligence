# Economic Intelligence — Labor Market "What Changed?" Contract Specification v1.0

| | |
|---|---|
| Contract ID | `labor_what_changed_v1.0` |
| Specification version | 1.0 |
| Status | **FROZEN** |
| Source methodology | `labor_v1.0` (frozen in `LABOR_V1_FROZEN_METHODOLOGY.md`) |
| Comparison mode | `MONTH_OVER_MONTH` — the only mode this contract defines |
| AI dependency | None |
| Confirmation component | None (JOLTS deferred — no `CONFIRMATION_CHANGED` event type in V1) |

> **This document is normative.** Production behavior for Increment
> #20C.2 MUST conform to this specification exactly. Where
> implementation convenience conflicts with this specification, this
> specification wins. Implementation must not reinterpret, extend,
> simplify, or improve the comparison semantics — and must never
> recalculate any `labor_v1.0` formula.

This document is documentation only. It authorizes no production code,
migration, or frontend change. Implementation is a separate,
explicitly authorized task ("Increment #20C.2").

This specification was produced by direct inspection of the actual
committed `labor_v1.0` implementation (`app/models/labor.py`,
`app/domain/labor.py`, `app/services/labor.py`, `app/api/labor.py`)
and the actual committed `inflation_what_changed_v1.0` implementation
(`app/models/inflation_what_changed.py`, `app/domain/inflation_what_changed.py`,
`app/services/inflation.py`, `docs/methodology/inflation-what-changed-v1.0.md`)
— every design decision below either transcribes a proven Inflation
precedent directly, or explicitly names why Labor departs from it.

---

## 1. Core rule (restated, load-bearing)

`labor_v1.0` calculates economics. `labor_what_changed_v1.0` compares
already-computed results. The comparator imports **zero** `labor_v1.0`
formula knowledge — no PAYEMS arithmetic, no UNRATE averaging, no
50,000/0.2pp deadbands, no condition/momentum/state classification
logic. It reads already-computed fields off two already-canonical
`EmploymentResult`/`UnemploymentResult`/`LaborState` values (built
elsewhere, by `app.domain.labor`'s own primitives, at periods this
contract's own period-selection logic — itself living in
`app.domain.labor`, not in the comparator — chooses) and does
arithmetic/equality/membership checks on them only. This mirrors
`app.domain.inflation_what_changed`'s own frozen architectural
boundary exactly (see that module's own docstring).

## 2. Inflation reuse audit

**Reused directly (proven, unmodified precedent):**
- The four-transition metric pattern (`AVAILABLE→AVAILABLE`:
  `METRIC_CHANGED` if canonically unequal; `AVAILABLE→UNAVAILABLE`:
  `AVAILABILITY_LOST`; `UNAVAILABLE→AVAILABLE`: `AVAILABILITY_RESTORED`;
  `UNAVAILABLE→UNAVAILABLE`: nothing).
- Exact float inequality for metric-change detection — *"changed :=
  previous_value != current_value (plain float inequality on
  canonical, already-computed values)... No epsilon is introduced."*
  (`docs/methodology/inflation-what-changed-v1.0.md`'s own frozen
  "Float/display rule," cited verbatim as the precedent this contract
  adopts unmodified).
- `INSUFFICIENT_DATA` (Labor's availability value, analogous to
  Inflation's own `INSUFFICIENT_DATA`) is excluded from the "valid
  economic state" set for state-shaped comparisons — a state-shaped
  field changes are only `STATE_CHANGED` when BOTH sides are valid and
  unequal; validity itself flipping is `AVAILABILITY_LOST`/`RESTORED`;
  both invalid produces nothing. Transcribed directly from
  `app.domain.inflation_what_changed._state_events`.
- `previous_period = month_before(current_period, 1)`, **never
  searched backward** — the exact `month_over_month_series_momentum`
  precedent (`app/domain/inflation.py`), confirmed by direct
  inspection: `current_period = latest_observation_date(...)` (a row
  exists, regardless of classification validity — never "latest
  *valid*" period), `previous_period = month_before(current_period, 1)`,
  and the previous period is **always evaluated**, never skipped —
  `compute_series_momentum_at` is called unconditionally at
  `previous_period`, producing its own honest `INSUFFICIENT_DATA`
  result if that period genuinely lacks data.
- The pure per-section comparator function shape
  (`previous_period, current_period, previous_evidence, current_evidence
  → section result`), assembled by one top-level function that
  flattens and sorts every section's events into one list.
- `delta: float | None` on every event, computed whenever both sides
  are numeric and available — a real, low-cost, already-useful field
  with no reason to omit for Labor.
- A deterministic 3-key total ordering (`component`, `event_type`,
  `field`), each an explicit, exposed tuple constant — never dict
  iteration, database row order, or judgment.
- `changes: []` (never a synthesized "Labor remained stable" narrative)
  when nothing differs.
- Each `ChangeEvent` carries the **source** monitor's `methodology_id`
  (`"labor_v1.0"`) — **not** a duplicated pair of source+comparison
  IDs. The comparator's own identity (`comparison_contract_id`,
  `comparison_type`) lives **once**, at the top-level result only —
  confirmed by direct inspection of `app.models.inflation_what_changed.ChangeEvent`
  (carries only `methodology_id = METHODOLOGY_ID`, i.e.
  `"inflation_v1.0"`) vs. `InflationWhatChangedResult` (carries
  `comparison_contract_id = "inflation_what_changed_v1.0"` once).

**NOT reused (Labor-specific departures, each justified below):**
- No `CONFIRMATION_CHANGED` event type (§8) — Labor V1 has no
  confirmation component.
- No per-section `previous_period`/`current_period`/`comparison_available`
  triplet (§7) — Inflation needs this because its sections anchor to
  *different* periods (confirmation uses `latest_shared_observation_period`,
  distinct from primary momentum's own anchor); Labor has exactly ONE
  shared `evaluation_period` for both owners (`labor_v1.0`'s own §10),
  so this triplet is hoisted to the top level once instead of
  repeated per-section — a genuine simplification, not an oversight.
- Two NEW `field` values within the `EMPLOYMENT` component —
  `"condition"` and `"momentum"` — that have no Inflation analog,
  because `inflation_v1.0` never exposed an intermediate
  condition/momentum decomposition the way `labor_v1.0`'s redesigned
  payroll formula deliberately does (§6).

**Strong preference honored:** no universal `WhatChanged` framework
was designed. Labor is the second comparator; this contract is
independently specified, reusing Inflation's *proven patterns* by
conscious choice, not by inheriting a shared abstraction. A future
third comparator, if one is ever built, is the right point to decide
whether a real shared framework is justified.

## 3. Comparison period rule (frozen)

```
current_period  = determine_evaluation_period(payems_observations, unrate_observations)
                   # unchanged from labor_v1.0 -- min(latest PAYEMS date, latest UNRATE date);
                   # None only if either series has zero observations at all
previous_period = month_before(current_period, 1)   # EXACT t-1, never searched
```

Both periods are **always** evaluated via `compute_labor_monitor_result_at`
(§11) — never skipped, never silently advanced to "the last period with
data." If `current_period` is `None`, `comparison_available = False`
and `previous_period` is also `None` (the degenerate case: neither
series has any data at all — mirrors Inflation's own "no current
anchor exists at all" degenerate case).

### Why exact t-1, illustrated against the real UNRATE 2025-10 gap

Consider evaluating December 2025 (`current_period`), so
`previous_period = November 2025`. UNRATE's own current-window
requirement (`labor_v1.0` §6) means:
- December's own evaluation needs `{Dec, Nov, Oct-2025}` — includes
  the gap → `INSUFFICIENT_DATA`.
- November's own evaluation (as `previous_period`) needs
  `{Nov, Oct, Sep-2025}` — also includes the gap → `INSUFFICIENT_DATA`.
- Result: both sides invalid → **no event** for unemployment's `state`
  field (an honest "we can't classify either side" outcome, not a
  fabricated claim).

Now consider evaluating October 2025 itself (`current_period`),
compared against September 2025 (`previous_period`): October's own
window `{Oct, Sep, Aug-2025}` includes the gap (`INSUFFICIENT_DATA`);
September's own window `{Sep, Aug, Jul-2025}` does **not**
(`STABLE`/`IMPROVING`/`DETERIORATING`, whatever it classifies to). This
produces `AVAILABILITY_LOST` (component=`UNEMPLOYMENT`, field=`state`)
— exactly where the gap actually first becomes visible. A symmetric
`AVAILABILITY_RESTORED` appears once a later month's window no longer
touches it (and, independently, a **second** `AVAILABILITY_LOST`/
`AVAILABILITY_RESTORED` pair appears roughly a year later, since the
same October 2025 value also falls inside the *prior-year* window for
evaluations around October 2026 — `labor_v1.0` §13's own
`{0,1,2}∪{12,13,14}` UNRATE affected-horizon structure, restated here
as direct evidence for why "exact t-1, never skip" is the only rule
that surfaces this truthfully). A "nearest available previous result"
rule would have silently skipped past this entirely.

## 4. Economic vs. availability — the load-bearing distinction

`INSUFFICIENT_DATA` (at every level: `LaborState`, `EmploymentState`,
`UnemploymentTrendState`, and `EmploymentCondition`/`EmploymentMomentum`)
is an **availability** condition, never an economic direction. A
state-shaped field's comparison uses exactly the following rule,
applied independently per field:

```
valid(x) := x is not "INSUFFICIENT_DATA"

previous valid, current valid,   previous == current  -> no event
previous valid, current valid,   previous != current  -> STATE_CHANGED
previous valid, current invalid                        -> AVAILABILITY_LOST
previous invalid, current valid                         -> AVAILABILITY_RESTORED
previous invalid, current invalid                        -> no event
```

`COOLING → INSUFFICIENT_DATA` is **always** `AVAILABILITY_LOST`, never
`STATE_CHANGED`. `INSUFFICIENT_DATA → STRENGTHENING` is **always**
`AVAILABILITY_RESTORED`, never `STATE_CHANGED`. This rule is frozen
identically for all five state-shaped fields Labor has:
`LABOR.state`, `EMPLOYMENT.state`, `EMPLOYMENT.condition`,
`EMPLOYMENT.momentum`, `UNEMPLOYMENT.state`.

## 5. Component and field vocabulary (frozen)

```
ChangeComponent = "LABOR" | "EMPLOYMENT" | "UNEMPLOYMENT"
```
Never `PAYEMS`/`UNRATE` as component names — those are series IDs,
which belong in evidence (the embedded `EmploymentResult`/
`UnemploymentResult` objects), not in the event's own `component`
field. This mirrors Inflation's own `PRIMARY_MOMENTUM`/`TARGET`/etc.
naming (semantic roles, not provider identifiers).

```
LABOR fields:        "state"
EMPLOYMENT fields:    "state", "condition", "momentum",
                      "current_3m_avg_jobs", "prior_3m_avg_jobs", "momentum_delta_jobs"
UNEMPLOYMENT fields:  "state",
                      "current_3m_avg", "prior_year_3m_avg", "delta_pp"
```

## 6. Condition and momentum changes — reported independently, never suppressed (frozen decision)

**Frozen: `condition` and `momentum` each produce their own
independent `STATE_CHANGED`/`AVAILABILITY_LOST`/`AVAILABILITY_RESTORED`
event (§4's rule, applied per-field), exactly like `state` — with NO
suppression when `EmploymentState` also changed in the same
comparison.**

Justification: `labor_v1.0`'s entire payroll redesign (#20A.1
rejecting the original formula, #20A.2 introducing the
condition/momentum split) exists specifically because condition and
momentum are two genuinely independent, non-redundant facts —
collapsing them back into a single `state`-only event in the
comparator would silently undo the exact benefit the redesign was
built to deliver. It is also directly consistent with Inflation's own
proven behavior: `compare_series_momentum_section` computes `state`
events and every metric-field event completely independently, with
zero suppression logic between them, and that has been this project's
working, shipped behavior since Increment #17C. A concrete case this
matters for: `condition` can hold a real value while `momentum` (and
therefore `state`) is `INSUFFICIENT_DATA` (`labor_v1.0` §3 vs. §4 — a
narrower 4-month requirement for condition vs. momentum's 7-month
one), so these fields are not even always simultaneously available —
treating them as one fused signal would be actively wrong, not merely
redundant.

Backend preserves evidence; it does not make UX suppression decisions
— exactly the principle this increment's own brief states, now backed
by both an architectural precedent and a Labor-specific correctness
reason.

## 7. Numeric metric changes (frozen: every field, exact inequality, evidence-embedded — no separate suppression policy)

Every numeric field independently follows §2's reused four-transition
rule: `METRIC_CHANGED` when both sides are present and canonically
(exactly) unequal; `AVAILABILITY_LOST`/`RESTORED` when only one side is
present; nothing when both are absent or exactly equal. **No epsilon,
no rounding, no comparison of formatted display strings** — plain
`!=` on the raw computed float, identical to Inflation's own frozen
"Float/display rule." This was audited, not assumed: real month-to-month
PAYEMS/UNRATE-derived averages are effectively never bit-for-bit equal
in genuine data, so `METRIC_CHANGED` will fire nearly every real
comparison for at least one numeric field — this mirrors Inflation's
own real-world behavior exactly (its own r_3m/r_6m/r_12m fields behave
identically) and is not treated as "noise" there; the UI's own job is
to curate/truncate for display (see `WhatChangedPreview.tsx`'s
existing `.slice(0, 3)` pattern), never the backend's job to
pre-filter genuine evidence.

Numeric metrics are **not** folded into their parent state event as an
inline delta-only annotation — each gets its OWN `ChangeEvent`,
exactly like Inflation's `r_3m_annualized`/`r_6m_annualized`/`r_12m`
each get their own event alongside `state`'s own event. This keeps
every field independently auditable and avoids inventing a nested
event shape this project has deliberately avoided elsewhere (see
ADR-023's own no-causal-nesting precedent for release-processing
evidence — the same "sibling facts, not parent/child" principle
applies here).

## 8. Event vocabulary (frozen: smallest sufficient set)

```
LaborChangeEventType = "STATE_CHANGED" | "AVAILABILITY_LOST" | "AVAILABILITY_RESTORED" | "METRIC_CHANGED"
```

No `CONFIRMATION_CHANGED` — Labor V1 has no confirmation component
(JOLTS deferred, `labor_v1.0` §8). No new `CONDITION_CHANGED`/
`MOMENTUM_CHANGED`/`COMPONENT_CHANGED` event type — `condition` and
`momentum` reuse the **same** `STATE_CHANGED`/`AVAILABILITY_*`
vocabulary as `state` (§6), distinguished by `field`, not by a
proliferated event-type taxonomy. This directly satisfies the brief's
own "avoid proliferating event types unnecessarily" instruction: the
generic-`COMPONENT_CHANGED`-with-a-field-discriminator alternative the
brief raised was considered and rejected in favor of reusing
`STATE_CHANGED` (already exactly that shape — a discrete/categorical
field changed, discriminated by `field`) rather than inventing a
same-shaped fifth event type with a different name. When JOLTS
eventually exists, `labor_what_changed_v1.0` is versioned forward
(`labor_what_changed_v1.1`+) if its comparison semantics materially
change — never silently extended in place.

## 9. Event schema (frozen)

```
LaborChangeEvent
  component: "LABOR" | "EMPLOYMENT" | "UNEMPLOYMENT"
  event_type: "STATE_CHANGED" | "AVAILABILITY_LOST" | "AVAILABILITY_RESTORED" | "METRIC_CHANGED"
  field: str                          # see §5
  previous_value: float | str | None  # str for state-shaped fields, float for numeric fields
  current_value: float | str | None
  delta: float | None                 # current - previous, only when both numeric and available
  previous_period: date | None
  current_period: date | None
  methodology_id: str = "labor_v1.0"  # the SOURCE monitor's id -- never the comparator's own
  data_basis: str = "latest_revised_data"
```

## 10. Component hierarchy / result schema (frozen)

```
EmploymentSectionChanges
  previous_evidence: EmploymentResult | None
  current_evidence: EmploymentResult | None
  changes: list[LaborChangeEvent]
  state_changed: bool
  metric_changed: bool
  availability_lost: bool
  availability_restored: bool

UnemploymentSectionChanges
  # identical shape, UnemploymentResult evidence

LaborWhatChangedResult
  methodology_id: str = "labor_v1.0"
  comparison_contract_id: str = "labor_what_changed_v1.0"
  comparison_type: str = "MONTH_OVER_MONTH"
  data_basis: str = "latest_revised_data"
  comparison_available: bool             # False only when current_period is None
  previous_period: date | None
  current_period: date | None
  previous_labor_state: LaborState | None
  current_labor_state: LaborState | None
  employment_changes: EmploymentSectionChanges
  unemployment_changes: UnemploymentSectionChanges
  changes: list[LaborChangeEvent]        # flattened, deterministically sorted, ALL sections
  any_state_changed: bool
  any_metric_changed: bool
  any_availability_changed: bool
  current_labor_result: LaborMonitorResult | None = None   # optional context, never required for auditability
```

No per-section `comparison_available`/`previous_period`/`current_period`
triplet (§2's departure note) — Labor's one shared `evaluation_period`
makes these top-level-only fields sufficient and non-redundant. The
top-level `LABOR.state` comparison has no dedicated section wrapper
(unlike `EMPLOYMENT`/`UNEMPLOYMENT`) because it has no nested evidence
of its own beyond the bare state value — `previous_labor_state`/
`current_labor_state` at the top level are sufficient; adding an empty
wrapper object around two scalars would be overbuilding.

## 11. Pure comparator contract (frozen — supports both month-over-month AND same-period revision comparison)

```python
def compare_employment_section(
    previous_period: date | None, current_period: date | None,
    previous_evidence: EmploymentResult, current_evidence: EmploymentResult,
) -> EmploymentSectionChanges: ...

def compare_unemployment_section(
    previous_period: date | None, current_period: date | None,
    previous_evidence: UnemploymentResult, current_evidence: UnemploymentResult,
) -> UnemploymentSectionChanges: ...

def compare_labor_state(
    previous_period: date | None, current_period: date | None,
    previous_state: LaborState, current_state: LaborState,
) -> list[LaborChangeEvent]: ...

def assemble_labor_what_changed_result(
    previous_period: date | None, current_period: date | None,
    labor_state_changes: list[LaborChangeEvent],
    employment_changes: EmploymentSectionChanges,
    unemployment_changes: UnemploymentSectionChanges,
    current_labor_result: LaborMonitorResult | None = None,
) -> LaborWhatChangedResult: ...
```

**Critical, explicitly verified:** none of these four functions ever
compares `previous_period` against `current_period` (no `<`/`>`/`==`
check between them anywhere) — they are used ONLY to label each
produced event's own `previous_period`/`current_period` fields. This
was confirmed directly against Inflation's own equivalent functions
(`compare_series_momentum_section` et al. never relate the two period
parameters to each other either — the exact same property, inherited
for free by following the same signature shape). This means:

- **Month-over-month** (§3): `previous_period != current_period`
  (exactly one month apart), `previous_evidence`/`current_evidence`
  computed via `compute_labor_monitor_result_at` at two different
  periods.
- **Same-period revision** (a future #20D release-processing use
  case): `previous_period == current_period` (identical date — the
  SAME `evaluation_period`, before and after a persisted observation
  revision), `previous_evidence`/`current_evidence` computed via
  `compute_labor_monitor_result_at` called TWICE at the SAME period
  against two different observation snapshots (before/after the
  revision). Requires **zero** change to the comparator — the value
  comparisons work identically either way, since the functions never
  inspect period ordering at all.

`month_over_month_labor_periods` (§3's period-selection logic) is
**not** part of the pure comparator — it lives in `app.domain.labor`
(the monitor's own domain module, mirroring exactly where
`month_over_month_series_momentum` lives in `app.domain.inflation`,
not in `app.domain.inflation_what_changed`). Month-over-month period
selection is the SERVICE/orchestration layer's concern (via that
`app.domain.labor` helper); the pure comparator in
`app.domain.labor_what_changed` never chooses a period itself.

## 12. `#20C.2` service/domain seam — smallest additive refactor (audited, not performed)

`app.domain.labor`'s existing `compute_employment_result`/
`compute_unemployment_result` **already accept an explicit period
parameter** (never restricted to "latest") — the clean period-specific
evaluation seam this contract needs already exists, unlike Inflation's
own `compute_series_momentum`/`compute_series_momentum_at` split,
which required two separate functions. **No refactor of the existing
`labor_v1.0` implementation is required.** #20C.2 needs exactly two
small, additive, non-breaking new functions in `app/domain/labor.py`:

1. `compute_labor_monitor_result_at(payems_observations, unrate_observations, period, condition_deadband_jobs, momentum_deadband_jobs, unemployment_deadband_pp) -> LaborMonitorResult` — evaluates both owners at an EXPLICIT given `period` (never searches), always sets `evaluation_period = period` (even if that period turns out to have no computable data — distinct from `compute_labor_monitor_result`'s own "`None` if no candidate at all" behavior, since here a candidate is *given*, not searched for).
2. `month_over_month_labor_periods(payems_observations, unrate_observations) -> tuple[date | None, date | None]` — returns `(previous_period, current_period)`, reusing `determine_evaluation_period` (unmodified) for `current_period` and `month_before(current_period, 1)` for `previous_period`.

Neither touches `compute_labor_monitor_result`'s existing signature or
behavior. `LaborMonitorService` (§13) gains one new method,
`get_what_changed_result`, mirroring `InflationMonitorService`'s own
identical two-methods-on-one-service-class precedent — no new service
class.

## 13. Service design (frozen shape, not implemented)

```
LaborMonitorService.get_what_changed_result(session) -> LaborWhatChangedResult:
    1. load PAYEMS/UNRATE observations (reuse the existing `_load` helper, unmodified)
    2. previous_period, current_period = month_over_month_labor_periods(payems_obs, unrate_obs)
    3. if current_period is None: return the degenerate/comparison_available=False result
    4. previous_result = compute_labor_monitor_result_at(payems_obs, unrate_obs, previous_period, ...)
       current_result  = compute_labor_monitor_result_at(payems_obs, unrate_obs, current_period, ...)
    5. employment_changes = compare_employment_section(previous_period, current_period, previous_result.employment, current_result.employment)
       unemployment_changes = compare_unemployment_section(previous_period, current_period, previous_result.unemployment, current_result.unemployment)
       labor_state_changes = compare_labor_state(previous_period, current_period, previous_result.state, current_result.state)
    6. return assemble_labor_what_changed_result(previous_period, current_period, labor_state_changes, employment_changes, unemployment_changes, current_labor_result=current_result)
```

Both `previous_result`/`current_result` are always computed via
`compute_labor_monitor_result_at`, never a mix of the plain
`compute_labor_monitor_result` for "current" and the `_at` variant for
"previous" — one code path, no risk of subtle divergence.

## 14. API design (frozen: mirror Inflation exactly, no query parameters)

```
GET /api/v1/monitors/labor/changes
```

No query parameters — Inflation's own `GET /api/v1/monitors/inflation/changes`
has none (verified directly against `app/api/inflation.py`: the route
function takes zero arguments), always comparing the latest evaluable
period against exactly one month before it. Labor mirrors this
exactly; a `?period=` parameter was considered (per this increment's
own prompt) and rejected for lacking any Inflation precedent or a
Labor-specific reason to diverge. Missing/insufficient data is **not**
an error — `comparison_available: false` inside a normal `200`
response, per the same infrastructure-vs-economic-data distinction
every other route in this project already makes. Only a genuine
database/infrastructure failure is non-`200`.

## 15. Methodology / provenance IDs (frozen)

Each `LaborChangeEvent.methodology_id = "labor_v1.0"` (the source
monitor). `LaborWhatChangedResult.comparison_contract_id =
"labor_what_changed_v1.0"`, `comparison_type = "MONTH_OVER_MONTH"` —
both once, at the top level, never duplicated per-event (§2).

## 16. Data basis (frozen)

`data_basis = "latest_revised_data"` on every event and the top-level
result — both snapshots (previous and current) reflect whatever is
currently persisted at comparison time; no vintage reconstruction is
implied or performed, for either the month-over-month API or a future
release-processing before/after snapshot pair. A future
release-processing snapshot's "before"/"current" pair represents
persisted state before and after processing, still never a
reconstruction of a provider's original historical publication.

## 17. JOLTS

No JOLTS event type, field, or component designed in this contract
(§8). When JOLTS confirmation is eventually implemented,
`labor_what_changed_v1.0`'s comparison semantics are revisited and, if
materially changed, versioned forward explicitly — never silently
extended.

## 18. Historical scenario review (semantic coherence only, no new economics)

Using `labor_v1.0`'s own already-validated research findings as
context (never recomputed here):

- **2008 deterioration**: `EMPLOYMENT.state EXPANDING→COOLING` (or
  directly to `CONTRACTING` by March 2008, per `#20A.2`'s own regime
  review), `UNEMPLOYMENT.state STABLE→DETERIORATING`, `LABOR.state
  →COOLING` once both agree — a clean, coherent `STATE_CHANGED` cascade
  across all three levels, each independently timed exactly as the
  underlying `labor_v1.0` evidence already shows.
- **August 2009 (`CONTRACTING → RECOVERING`)**: exactly the
  first-class transition §"Contracting → Recovering" of this
  increment's own brief demands — `EMPLOYMENT.state: CONTRACTING →
  RECOVERING` is a genuine `STATE_CHANGED` event (both sides valid,
  unequal), never summarized as generic "improved," and never
  conflated with `EXPANDING`. `EMPLOYMENT.momentum` would also show
  its own `STEADY→IMPROVING`-shaped event independently (§6).
- **2020 collapse**: multiple `AVAILABILITY_LOST`-shaped false alarms
  are NOT a risk here — payroll collapse months are still classifiable
  (`CONTRACTING`), not `INSUFFICIENT_DATA`; the real events are
  `STATE_CHANGED` cascades (`EXPANDING→CONTRACTING`, `IMPROVING→
  DETERIORATING`, `STRENGTHENING→COOLING`), coherent and expected.
- **2020/2021 recovery**: per `#20A.2`'s own found `CONTRACTING→
  RECOVERING→EXPANDING` progression, this contract produces a genuine
  three-state `STATE_CHANGED` sequence for `EMPLOYMENT.state`, each
  transition distinct and auditable — never collapsed into one
  "recovered" event.
- **2022–2024 cooling/normalization**: `EMPLOYMENT.state` alternating
  `EXPANDING`/`COOLING` (per `#20A.2`'s own found month-to-month churn
  in this period) would produce a real, if somewhat frequent, sequence
  of `STATE_CHANGED` events — an honest reflection of genuine
  short-window churn in the underlying redesigned methodology, not a
  comparator defect; any future UI-level noise concerns belong to
  display curation (§7), not to suppressing real backend events.

The vocabulary communicates every reviewed scenario coherently with no
gaps, no misleading conflation, and no invented severity language.

## 19. `#20C.2` required test matrix (frozen, not implemented)

**Top level:** every economic state → different economic state
(`STATE_CHANGED`); same state → no event; sufficient→insufficient
(`AVAILABILITY_LOST`); insufficient→sufficient (`AVAILABILITY_RESTORED`);
insufficient→insufficient (no event).

**Employment state:** `EXPANDING→COOLING`, `COOLING→CONTRACTING`,
`CONTRACTING→RECOVERING` (exact-value regression, §18), `RECOVERING→
EXPANDING`, same→no event, every remaining state-pair at least once.

**Employment condition:** `EXPANDING→FLAT`, `FLAT→CONTRACTING`,
`CONTRACTING→FLAT`, same→no event — independent of any simultaneous
`state` change (§6's no-suppression proof: a fixture where `condition`
changes but `state` does not, and vice versa, each still producing
exactly the expected independent event(s)).

**Employment momentum:** `IMPROVING→STEADY`, `STEADY→WORSENING`,
`WORSENING→IMPROVING`, same→no event.

**Unemployment:** `IMPROVING→STABLE`, `STABLE→DETERIORATING`,
`DETERIORATING→IMPROVING`, same→no event.

**Availability:** employment lost/restored; unemployment lost/restored;
Labor lost/restored; a fixture proving employment AND Labor
availability-lost co-occur from one underlying PAYEMS gap (not
duplicative — two distinct semantic layers, §"why co-occurrence is
correct"); partial availability (employment sufficient, unemployment
insufficient, and vice versa) each independently comparable.

**Numeric metrics:** every one of the 6 metric fields (3 employment +
3 unemployment) independently produces `METRIC_CHANGED` on exact
inequality, `AVAILABILITY_LOST`/`RESTORED` on a one-sided `None`,
nothing on exact equality or double-`None`; a floating-point-noise
regression proving no epsilon/rounding is applied anywhere.

**Periods:** exact adjacent months; a year boundary (`t-1` crossing
December→January); the real UNRATE 2025-10 gap shape reproduced as a
`AVAILABILITY_LOST`/`RESTORED` pair exactly where the gap first
becomes visible and clears (§3's worked example, turned into an exact
regression); no skip-to-nearest (a fixture with a deliberately sparse
history proving the comparator/service never substitutes a
farther-back period); same-period revision comparison
(`previous_period == current_period`, still produces correct events).

**Ordering:** multiple simultaneous events sort deterministically per
§ordering; repeated comparison of identical inputs is byte-identical.

**Architecture:** `app/domain/labor_what_changed.py` imports zero of
`app.domain.labor`, `app.repositories.*`, `sqlalchemy`, `fastapi`,
`app.clients.fred`, `app.services.ai*` (structural guard, mirroring
`test_no_forbidden_imports` + the existing
`test_what_changed_comparator_has_zero_inflation_formula_knowledge`
precedent, extended for Labor); service reuses
`compute_labor_monitor_result_at`/`month_over_month_labor_periods`
only, never re-implements period math inline; route is read-only, no
mutation endpoint; no `frontend/` change; no `ReleaseSeriesMapping`
row added.

## 20. Freeze criteria — verified against this document

1. ✅ Comparator consumes canonical `EmploymentResult`/`UnemploymentResult`/
   `LaborState` values only (§1, §11).
2. ✅ Economic vs. availability transitions are structurally distinct
   at every level (§4).
3. ✅ Exact month-over-month period rule is explicit (§3).
4. ✅ Pure comparator supports same-period revision snapshots with
   zero code change (§11, explicitly verified no period-ordering
   comparison exists anywhere in the four comparator functions).
5. ✅ Event vocabulary is small (4 types) and sufficient — no
   `CONFIRMATION_CHANGED`, no proliferated condition/momentum-specific
   types (§8).
6. ✅ Component identifiers (`LABOR`/`EMPLOYMENT`/`UNEMPLOYMENT`) are
   stable, semantic, not series IDs (§5).
7. ✅ Event ordering is deterministic — three explicit tuple constants,
   never dict/DB iteration (§9, §10, mirroring Inflation's own
   `COMPONENT_ORDER`/`EVENT_TYPE_ORDER`/`FIELD_ORDER`).
8. ✅ Duplicate-event policy is explicit: no suppression, every
   independently-changed field reports its own event (§6, §7).
9. ✅ Numeric metric-change policy is explicit: every field, exact
   inequality, no epsilon (§7).
10. ✅ Methodology provenance is explicit and non-duplicated (§15).
11. ✅ Missing periods cannot be silently skipped (§3, worked example).
12. ✅ #20C.2 can implement without inventing semantics — every
    formula, table, schema field, and function signature above is
    fully specified; the one implementation-time decision left open
    (§12) is an explicitly-scoped, additive, two-function refactor,
    not a semantic gap.

No unresolved ambiguity remains.
