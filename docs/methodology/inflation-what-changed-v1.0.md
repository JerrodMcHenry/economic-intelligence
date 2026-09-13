# Economic Intelligence
# Inflation Monitor — "What Changed?" Contract Specification v1.0

| | |
|---|---|
| Methodology/Contract ID | `inflation_what_changed_v1.0` |
| Specification version | 1.0 |
| Status | **FROZEN** |
| Depends on | `inflation_v1.0` (`docs/methodology/inflation-monitor-v1.0.md`, unmodified) |
| Contract type | Deterministic comparison layer, not a methodology |
| AI dependency | None |
| Comparison mode | `MONTH_OVER_MONTH` — the only mode this contract defines |
| Data basis | `latest_revised_data` (inherited from `inflation_v1.0`, unchanged) |

> This document is **not** a second economic methodology. It defines how
> already-canonical `inflation_v1.0` component results are *compared*,
> section by section, at explicit calendar periods this contract selects
> for its own purpose. Canonical economic truth remains owned entirely
> by `inflation_v1.0`; this contract adds no new classification rule, no
> new formula, no new series, and no new economic state. Where this
> document is silent, `inflation_v1.0` governs.

This document does **not** authorize implementation. It is a frozen
specification for a future increment (referred to elsewhere as
"Increment #15"), which has not begun. No production code was written
or modified to produce this document.

---

## Why this document exists

`inflation_v1.0` answers "what is the state of inflation right now." It
has no concept of "since when" or "compared to what." The product
question this contract answers is:

> What changed in inflation since the previous calendar-period
> canonical result, what did not change, and exactly which
> deterministic evidence supports that conclusion — **including
> whether canonical analysis itself became available or unavailable**?

Per this project's standing architecture principle:

> Facts are sourced. Calculations are deterministic. AI is
> interpretive. No probabilistic component may be required for the
> correctness, reproducibility, availability, or integrity of the
> Economic Intelligence Engine.

"What changed" is exactly the kind of question it would be tempting to
hand to an LLM. This contract exists to make that unnecessary: every
fact an AI might later narrate is precomputed here, deterministically,
before any AI ever sees it.

## Why the comparator does not recalculate

Each independently-anchored section is compared like this:

```
for each section S in {primary momentum, confirmation, target, headline PCE, headline CPI}:
    current_evidence(S)  = inflation_v1.0 canonical component result AT S.current_period
    previous_evidence(S) = inflation_v1.0 canonical component result AT S.previous_period
    change(S)            = compare_section(previous_evidence(S), current_evidence(S))
```

`compare_section` operates only on already-canonical component results
(`SeriesMomentumResult`/`TargetResult`-shaped values, or the pair of
states + relationship that make up confirmation evidence). It must
never recalculate an annualization formula, choose a different series,
reclassify momentum, alter target-gap semantics, reinterpret
confirmation, repair missing data, or use AI judgment. `current_evidence(S)`
is not guaranteed to be classifiable — see
[Monitor vs. What Changed: Anchor Semantics](#monitor-vs-what-changed-anchor-semantics)
below for exactly why, and why an unclassifiable *current* result is a
required, not exceptional, outcome of this contract.

There is deliberately **no single global `previous`/`current` pair**
feeding every section — each section's period is independently derived
from that section's own data, per
[Independent Period Semantics](#independent-period-semantics).

---

## Inspected #14 capabilities (grounding, not assumption)

The actual committed Increment #14 code was read directly:
`app/models/inflation.py`, `app/domain/inflation.py`,
`app/services/inflation.py`, `app/api/inflation.py`, and their test
suites. Findings:

- `InflationMonitorService.get_result(session)` takes **no period
  argument**. It always fetches each canonical series' entire persisted
  history (unbounded `get_observations_in_range(..., None, None)`) and
  returns the single **latest-valid** canonical result for each tier.
- `inflation_v1.0` already defines three distinct period concepts per
  series, each with a precise, different meaning (see the comparison
  table in the next section) — `latest_observation_period`,
  `latest_valid_state_period`, and (confirmation-specific)
  `latest_common_period`. All three already exist in
  `app/domain/inflation.py` today (`latest_observation_date`,
  `find_latest_valid_state_period`, `find_latest_common_period`) and are
  reused, unmodified, by this contract.
- The pure domain primitives one layer down already support exact-period
  evaluation and are not "latest-only" internally: `classify_period`,
  `_metric_evidence`, and `classify_confirmation_relationship` all take
  or operate on an explicit period/pair of states — no search. This is
  the machinery this contract's corrected anchor selection relies on.
- `build_index(observations)` and the raw `Observation` lists this
  contract needs are already fully available from the same fetch
  `InflationMonitorService` already performs — no new repository
  capability is required (see
  [Architecture Recheck](#architecture-recheck)).

---

## Comparison mode: `MONTH_OVER_MONTH` — the only mode

```
for a section's own current calendar period t:
    previous calendar period = exact calendar month immediately preceding t
```

No week-over-week, quarter-over-quarter, release-over-release, custom
arbitrary date range, or AI-selected comparison exists in this
contract. A future version may add additional modes; each would need
its own contract version.

This contract does not describe its subject as "the previous comparable
canonical result" — that phrasing would suggest a backward search for
*some* earlier valid result, which this contract never performs.
Throughout, "previous period" means **the literal calendar month
immediately before the current period**, evaluated once, whatever the
outcome.

---

## Monitor vs. What Changed: anchor semantics

**This is the central correction this revision makes, and it is now
frozen.** The Inflation Monitor and What Changed answer different
questions:

- **Monitor** (`inflation_v1.0`): *"What is the latest **valid**
  canonical state?"* — it deliberately searches past an unclassifiable
  recent period to find the latest one that **does** classify, because
  its job is to always show the best available current reading.
- **What Changed**: *"What occurred in the latest **observed** calendar
  period, including whether canonical analysis itself became
  available or unavailable?"* — it must **not** search past an
  unclassifiable period, because doing so is precisely what would hide
  an availability loss from the comparison.

Four distinct period concepts exist across the two contracts. Only the
first and the new fourth are used as **What Changed's own current
anchors**; the middle two remain exactly what `inflation_v1.0` already
defines them as, unmodified, and are not reused as anchors here:

| Concept | Defined by | Meaning | Used as a What Changed anchor? |
|---|---|---|---|
| `latest_observation_period` | `inflation_v1.0` (#14), per series | Latest calendar month for which **any** observation row exists, regardless of value validity | **Yes** — primary, target, headline PCE, headline CPI |
| `latest_valid_state_period` | `inflation_v1.0` (#14), per series | Latest calendar month for which `r_3m`/`r_6m`/`r_12m` are **all** calculable | No — this is the Monitor's own "current state" anchor; reusing it here would silently skip exactly the availability-loss periods this contract must detect |
| `latest_common_period` | `inflation_v1.0` (#14), confirmation only | Latest calendar month for which **both** Core PCE and Core CPI have a **valid** canonical state | No — this is the Monitor's own confirmation anchor; by definition it can never itself be an unavailable relationship, which would make `CONFIRMS → UNAVAILABLE` unrepresentable |
| `latest_shared_observation_period` | **New — this contract only** | Latest calendar month for which **both** Core PCE and Core CPI have **any** observation row, regardless of classifiability | **Yes** — confirmation |

`latest_shared_observation_period` does **not** modify `inflation_v1.0`,
does **not** create a new economic state, and does **not** replace
`latest_common_period` in the Monitor — the Monitor's own confirmation
behavior is completely untouched. It exists solely as a **period-
selection** concept for this contract. See its own definition below.

**Structural fact worth stating explicitly** (it explains why this
correction matters in practice, not just in theory): because "valid
state" is a strictly stronger condition than "observation exists,"
`latest_valid_state_period <= latest_observation_period` always, and
`latest_common_period <= latest_shared_observation_period` always. What
Changed's anchors are never *earlier* than the Monitor's own — they are
equal in the common case (nothing currently unavailable) and strictly
later exactly when there is an availability event for What Changed to
report that the Monitor's own "current" reading would otherwise hide.

## `latest_shared_observation_period` (new period-selection concept)

```
latest_shared_observation_period(primary_observations, confirmation_observations) :=
    max( dates(primary_observations) ∩ dates(confirmation_observations) )
    or null if the intersection is empty
```

where `dates(observations)` is the set of **every** date an observation
row exists for, regardless of whether its value is valid — exactly the
same row-exists convention `inflation_v1.0`'s own
`latest_observation_period` already uses (deliberately reused, not
reinvented). This is pure date-set arithmetic over the same two
observation lists the service already has in hand; it requires no new
classification, no new formula, and no repository change (see
[Architecture Recheck](#architecture-recheck)).

---

## Independent period semantics

Each of the five sections has its **own** current/previous period pair.
`inflation_v1.0` already allows its own per-tier "latest" anchors to
differ from one another; this contract's anchors differ from
`inflation_v1.0`'s in a different, additional way (per the table
above), and still differ from each other, section by section.

- **Primary momentum**: `current_period = Core PCE's latest_observation_period`.
  `previous_period` = exact calendar month immediately preceding it.
  Construct Core PCE's canonical momentum result (`classify_period`,
  `inflation_v1.0`'s own function) at **both** exact periods. The
  result at either period may legitimately be `INSUFFICIENT_DATA`.
- **Confirmation**: `current_confirmation_period = latest_shared_observation_period(Core PCE, Core CPI)`.
  `previous_confirmation_period` = exact calendar month immediately
  preceding it — plain calendar arithmetic, **not** a re-intersection of
  observation dates. At each of the two exact periods: (1) construct
  Core PCE's canonical momentum via `classify_period`, (2) construct
  Core CPI's canonical momentum via `classify_period` — both at the
  **exact same period**, never a mismatched pair — (3) apply
  `classify_confirmation_relationship` to the two resulting states. The
  relationship at either period may legitimately be `UNAVAILABLE`.
- **Target**: `current_period = Headline PCE (PCEPI)'s latest_observation_period`.
  `previous_period` = exact calendar month immediately preceding it.
  Construct the canonical target evidence (`_metric_evidence` for
  `r_12m`, `inflation_v1.0`'s own function) at both exact periods. May
  legitimately be unavailable at either period.
- **Headline PCE**: `current_period = PCEPI's latest_observation_period`
  — the same underlying series as target, so this section's period pair
  will in practice coincide with target's (same raw data, independently
  computed; this is an emergent consequence of sharing a series, not a
  rule forcing them together). `previous_period` = exact calendar month
  before it.
- **Headline CPI**: `current_period = CPIAUCSL's latest_observation_period`.
  `previous_period` = exact calendar month before it. Never substituted
  for or aligned to Headline PCE's period.

**No section ever substitutes another section's period**, and no
section's previous period is ever found by searching — always exactly
one calendar month before that section's own current period, evaluated
directly, whatever the outcome.

### The degenerate case: no current anchor exists at all

If a section's current anchor is itself `None` (the relevant series, or
— for confirmation — the pair, has no observation at all), there is no
date to compute "one month before" from:

```
current_period = null           (or current_confirmation_period = null)
previous_period = null          (or previous_confirmation_period = null)
comparison_available = false
changes = []
```

No `NOT_APPLICABLE` enum value is introduced (see
[Decision 1](#decision-1--no-not_applicable-state)); nothing is
fabricated merely from the absence of an anchor.

---

## Decision 1 — no `NOT_APPLICABLE` state

**Rejected.** No `NOT_APPLICABLE` enum value is introduced anywhere in
this contract. Instead, each section carries a plain, typed
`comparison_available: bool` (see
[Comparison Availability Semantics](#comparison-availability-semantics)
for the exact, corrected rule).

## Decision 2 — confirmation uses its own period basis

**Frozen, corrected in this revision.** Confirmation's current anchor
is its **own** basis, independent of primary — but that basis is now
`latest_shared_observation_period`, **not** `inflation_v1.0`'s
`latest_common_period` (the original freeze incorrectly reused
`latest_common_period`, which structurally cannot represent a lost
confirmation — see [Adversarial Re-Audit](#adversarial-re-audit) cases
10/11). `previous_confirmation_period` is the exact calendar month
immediately preceding `current_confirmation_period` — never a backward
search for "a more convenient valid comparison," and never re-anchored
to Core PCE's own period.

## Decision 3 — no global two-snapshot assumption

**Unchanged from the prior revision; remains correct.** There is no
single global `previous_result`/`current_result` pair of full
`InflationMonitorResult` objects. Each change section owns its exact
canonical evidence and its own period pair — see
[Corrected Canonical Change Result](#corrected-canonical-change-result).
A live, current-only `InflationMonitorResult` may be attached as
optional convenience context but is never the required evidence basis
for any section's comparison.

---

## Change taxonomy

Five categories, and they may coexist within one comparison:

### 1. Metric change

A canonical **numeric** value differs between a section's previous and
current calendar-period evidence, using full, unrounded precision (see
[Float/Display Rule](#floatdisplay-rule)). Applies to `r_1m_annualized`,
`r_3m_annualized`, `r_6m_annualized`, `r_12m` (primary/confirmation/
headline sections), `headline_pce_yoy`, `target_gap_pp` (target
section). Reported as `previous_value`, `current_value`,
`absolute_delta` (percentage points). Only meaningful when **both**
sides are available (see [Metric Availability](#metric-availability)
for what happens otherwise).

### 2. State change

`inflation_v1.0`'s canonical momentum state differs between two
**economically classifiable** states: `COOLING`, `HEATING`, `STABLE`,
`MIXED`.

```
state_changed :=
    previous_state in {COOLING, HEATING, STABLE, MIXED}
    AND current_state in {COOLING, HEATING, STABLE, MIXED}
    AND previous_state != current_state
```

`INSUFFICIENT_DATA` on either side means this is **not** a state
change — it is an availability change (category 4). Because `current`
is now anchored at `latest_observation_period` rather than
`latest_valid_state_period`, `current_state == "INSUFFICIENT_DATA"` is
an **ordinary, expected** outcome, not an edge case.

### 3. No state change (with metric change)

`previous_state == current_state` (both economically classifiable) but
one or more underlying metrics differ. Economically important; never
described as "nothing changed."

### 4. Availability change

A section's state, or a specific metric within it, moved between
calculable and `INSUFFICIENT_DATA`/unavailable — **symmetrically, in
either direction**:

```
AVAILABLE   → AVAILABLE    : compute the change normally (categories 1-3)
AVAILABLE   → UNAVAILABLE  : availability_lost
UNAVAILABLE → AVAILABLE    : availability_restored
UNAVAILABLE → UNAVAILABLE  : no_availability_change (no event; nothing to report)
```

All four are reachable in this corrected contract — the previous
revision's wording accidentally implied the current side could never be
`UNAVAILABLE`, which made `AVAILABLE → UNAVAILABLE` (current side)
unreachable; that implication is retracted here. The same shape applies
at the individual metric level (e.g. `r_6m` specifically becomes
unavailable while `r_3m`/`r_12m` remain valid) and is not mutually
exclusive with a state-level availability change.

### 5. Confirmation relationship change

```
relationship_changed := previous_relationship != current_relationship
```

over `CONFIRMS`/`DIVERGES`/`INCONCLUSIVE`/`UNAVAILABLE`. Can **coexist**
with an availability change — `CONFIRMS → UNAVAILABLE` is reported as
**both** `relationship_changed = true` **and**
`confirmation_availability_lost = true`. The frozen #14 invariant
(`confirmation_available == (relationship != "UNAVAILABLE")`) is read
from each already-canonical evaluation at the relevant period, never
recomputed independently.

## No-change result (machine-readable semantics)

Each section always has a `changes` list (possibly empty) and its own
summary flags. "No canonical changes detected" is `len(changes) == 0`
**for a section where `comparison_available = true`** — categorically
different from `comparison_available = false` (see
[Comparison Availability Semantics](#comparison-availability-semantics)).
No separate `NO_CHANGE` enum value is defined.

## Deterministic change event model

Five event types, deliberately structural, never interpretive:

```
METRIC_CHANGED
STATE_CHANGED
AVAILABILITY_LOST
AVAILABILITY_RESTORED
CONFIRMATION_CHANGED
```

No `INFLATION_IMPROVED`/`WORSENED`, no `GOOD_NEWS`/`BAD_NEWS`, no
`SHARP_DROP`/`SIGNIFICANT_CHANGE`/`ACCELERATING`. Each event
conceptually carries:

```
component        : PRIMARY_MOMENTUM | CONFIRMATION | TARGET | HEADLINE_PCE | HEADLINE_CPI
event_type        : one of the five above
field             : e.g. "r_3m_annualized", "state", "relationship", "target_gap_pp"
previous_value    : the previous canonical value/state (typed per field)
current_value     : the current canonical value/state (typed per field)
delta             : current_value - previous_value when both are numeric and available
                    (per "Metric change"'s absolute_delta above); null otherwise --
                    never fabricated across an availability boundary or for a
                    state/relationship field
previous_period   : the exact period previous_value was computed at (this section's own)
current_period    : the exact period current_value was computed at (this section's own)
methodology_id    : "inflation_v1.0"
data_basis        : "latest_revised_data"
```

### Deterministic ordering

Never dependent on dict iteration, database row order, or judgment.
Fixed, total order:

1. **By component**: `PRIMARY_MOMENTUM`, `CONFIRMATION`, `TARGET`,
   `HEADLINE_PCE`, `HEADLINE_CPI`.
2. **Within a component, by event type**: `STATE_CHANGED`,
   `CONFIRMATION_CHANGED`, `AVAILABILITY_LOST`, `AVAILABILITY_RESTORED`,
   `METRIC_CHANGED`.
3. **Within `METRIC_CHANGED` events for one component, by field**:
   `r_1m_annualized`, `r_3m_annualized`, `r_6m_annualized`, `r_12m`,
   `headline_pce_yoy`, `target_gap_pp` (only applicable fields appear).

## Metric change semantics (no invented thresholds)

No arbitrary economic threshold labels. A metric change is reported as
fact — `previous_value`, `current_value`, `absolute_delta` — never
bucketed into severity labels. `inflation_v1.0` defines no such
thresholds beyond its own frozen 0.10pp neutral band, which already
governs `state`, not a separate "is this change big" judgment.

## Float/display rule

A metric change is `changed = true` based on the canonical, unrounded
value — never a presentation-rounded display value. `2.844 → 2.846` is
`changed = true` even though both may display as `2.85`. No epsilon is
introduced. `changed := previous_value != current_value` (plain float
inequality on canonical, already-computed values).

## Metric availability

Four transitions, always representable, never conflated (restated here
per-metric, mirroring category 4 above):

```
AVAILABLE   → AVAILABLE    : compute absolute_delta = current - previous
AVAILABLE   → UNAVAILABLE  : no delta; AVAILABILITY_LOST for that metric
UNAVAILABLE → AVAILABLE    : no delta; AVAILABILITY_RESTORED for that metric
UNAVAILABLE → UNAVAILABLE  : no delta; no availability event for that metric
```

"Unavailable" for a metric means its value is `None` in the canonical
evidence — never a fabricated numeric delta across an availability
boundary.

## Primary momentum changes

Compares Core PCE's `r_1m_annualized`, `r_3m_annualized`,
`r_6m_annualized`, `r_12m` (metric changes) and `state`
(state/availability change) between `previous_period` and
`current_period`, where `current_period = Core PCE's latest_observation_period`
(see [Independent Period Semantics](#independent-period-semantics)).
Either period's evidence may be `INSUFFICIENT_DATA`.

`lower_boundary`/`upper_boundary` remain excluded from the event-level
change summary (pure functions of `r_12m` and the frozen
`NEUTRAL_BAND_PP`; reporting them separately would restate the `r_12m`
change under a different name). They remain visible in each section's
embedded canonical evidence (`SeriesMomentumResult`, unmodified).

## Target changes

Compares `headline_pce_yoy` and `target_gap_pp` between target's own
`previous_period`/`current_period`, where `current_period = Headline
PCE's latest_observation_period`. Either period's evidence may be
unavailable. The Fed objective (`2.0`) is a frozen constant and never
itself a "change." A target-gap change is never automatically paired
with a momentum interpretation — two separate deterministic facts.

## Confirmation changes

Compares the same-period relationship (`CONFIRMS`/`DIVERGES`/
`INCONCLUSIVE`/`UNAVAILABLE`) between `previous_confirmation_period` and
`current_confirmation_period`, where `current_confirmation_period =
latest_shared_observation_period` (per [Decision 2](#decision-2--confirmation-uses-its-own-period-basis)).
Uses `classify_confirmation_relationship` — the exact pure function
`inflation_v1.0` already defines — applied to Core PCE's and Core CPI's
states at those two exact periods. Either relationship may legitimately
be `UNAVAILABLE`. `relationship_changed` and the frozen
`confirmation_available == (relationship != UNAVAILABLE)` invariant are
reported for both previous and current; a relationship change crossing
the `UNAVAILABLE` boundary is represented as **both** a
`CONFIRMATION_CHANGED` event and an availability event.

### Worked example (from this correction's own motivating case)

```
Core PCE:  July valid COOLING;  August valid COOLING
Core CPI:  July valid COOLING;  August observation exists, but t-3 endpoint missing
```

`inflation_v1.0`'s own Monitor may still report
`latest_common_period = July`, `relationship = CONFIRMS` — correct and
unchanged, because July is the latest period where both sides are
*valid*. What Changed evaluates independently:
`current_confirmation_period = latest_shared_observation_period = August`
(both series have *an observation* in August), `previous_confirmation_period
= July`. July's relationship: `CONFIRMS`. August's: Core CPI is
`INSUFFICIENT_DATA` there, so the relationship is `UNAVAILABLE`. What
Changed therefore reports `relationship_changed: CONFIRMS → UNAVAILABLE`
and `confirmation_availability_lost = true` — correctly surfacing
exactly the transition the Monitor's own `latest_common_period` cannot
see. `latest_common_period` and `latest_shared_observation_period` are
never confused with each other in this contract.

## Headline context changes

Headline PCE (`headline_pce_changes`, anchored at PCEPI's own
`latest_observation_period`) and Headline CPI (`headline_cpi_changes`,
anchored at CPIAUCSL's own `latest_observation_period`) are compared
**independently**, each with its own period pair — never substituted
for each other even when one series' latest observation is a month
newer than the other's. No aggregate headline-change state, no majority
vote.

---

## Comparison availability semantics

```
section.comparison_available = true
    iff section.current_period is not null
        (equivalently, for confirmation: current_confirmation_period is not null)

section.comparison_available = false
    iff section.current_period is null
        -- no current anchor exists for this section at all
```

**Corrected in this revision:** `comparison_available` means *"does an
exact current calendar anchor exist, such that a month-over-month
comparison can be attempted"* — it does **not** mean, and must never be
read as meaning, *"did both canonical sides successfully classify."*
The prior revision's wording incorrectly implied the current side is
always valid by construction; that implication is retracted. Under the
corrected anchors (`latest_observation_period` for ordinary series,
`latest_shared_observation_period` for confirmation), **either or both**
of the current and previous sides may independently be
`INSUFFICIENT_DATA`/`UNAVAILABLE` — and that is not a failure of the
comparison, it is exactly the kind of fact this contract exists to
report (category 4, availability change).

`comparison_available = false` is reserved **exclusively** for the case
where no current anchor date exists at all (the relevant series, or —
for confirmation — the pair, has no observation in its entire
persisted history). In that case alone: both periods `null`, `changes
= []`, no flags raised.

**Do not equate "no changes" with "unable to perform comparison."**
`changes == []` with `comparison_available == true` means a comparison
was performed and found nothing different (which now legitimately
includes both sides agreeing on `INSUFFICIENT_DATA`, i.e.
`UNAVAILABLE → UNAVAILABLE` — see category 4). `comparison_available ==
false` means no comparison was attempted at all. These remain
structurally distinct fields, never inferred from one another.

## Missing-month invariant (reconfirmed under the corrected anchors)

```
July:      COOLING
August:    INSUFFICIENT_DATA
September: HEATING
```

**When September is the latest observed period** (`current_period =
September`, i.e. September is Core PCE's `latest_observation_period`):
`previous_period = August`. Reported: `availability_restored = true`
(August unavailable, September is not), `state_changed = false` (a
state change requires both sides classifiable; August is not). **Never**
`COOLING → HEATING` — July is not examined by this comparison at all.

**When August is the latest observed period** (`current_period =
August`): `previous_period = July`. Reported: `availability_lost =
true` (July valid, August is not). This is the case the prior revision
could not represent (because its anchor, `latest_valid_state_period`,
would have silently resolved `current_period` to July itself, hiding
August entirely) — it is now fully representable, because
`current_period` is August's `latest_observation_period` regardless of
August's classifiability.

No unavailable calendar month disappears from the transition history:
whichever month is latest-observed is always examined as `current`,
and its immediate predecessor is always examined as `previous` — never
skipped, never searched past.

---

## Corrected canonical change result

```
InflationWhatChangedResult
    methodology_id: "inflation_v1.0"
    comparison_contract_id: "inflation_what_changed_v1.0"
    comparison_type: "MONTH_OVER_MONTH"
    data_basis: "latest_revised_data"

    primary_momentum_changes:
        comparison_available: bool
        previous_period: date | null      # exact calendar month before current_period
        current_period: date | null       # Core PCE's latest_observation_period
        previous_evidence: SeriesMomentumResult | null   # inflation_v1.0's own shape; state may be INSUFFICIENT_DATA
        current_evidence:  SeriesMomentumResult | null   # state may be INSUFFICIENT_DATA
        changes: list[ChangeEvent]
        metric_changed / state_changed / availability_lost / availability_restored: bool

    confirmation_changes:
        comparison_available: bool
        previous_confirmation_period: date | null
        current_confirmation_period: date | null   # latest_shared_observation_period
        previous_primary_state: SeriesMomentumResult | null        # Core PCE at previous_confirmation_period
        previous_confirmation_state: SeriesMomentumResult | null   # Core CPI at previous_confirmation_period
        previous_relationship: ConfirmationRelationship | null     # may be UNAVAILABLE
        current_primary_state: SeriesMomentumResult | null         # Core PCE at current_confirmation_period
        current_confirmation_state: SeriesMomentumResult | null    # Core CPI at current_confirmation_period
        current_relationship: ConfirmationRelationship | null      # may be UNAVAILABLE
        changes: list[ChangeEvent]
        relationship_changed / confirmation_availability_lost / confirmation_availability_restored: bool

    target_changes:
        comparison_available: bool
        previous_period: date | null
        current_period: date | null       # Headline PCE's latest_observation_period
        previous_evidence: TargetResult | null   # may be unavailable
        current_evidence:  TargetResult | null   # may be unavailable
        changes: list[ChangeEvent]
        metric_changed: bool

    headline_pce_changes:    # same shape as primary_momentum_changes; current_period = PCEPI's latest_observation_period
    headline_cpi_changes:    # same shape as primary_momentum_changes; current_period = CPIAUCSL's latest_observation_period

    changes: list[ChangeEvent]   # flattened union of all five sections' events, deterministically ordered

    any_metric_changed: bool
    any_state_changed: bool
    any_availability_changed: bool
    confirmation_changed: bool

    current_monitor_result: InflationMonitorResult | null   # OPTIONAL convenience/context only --
                                                              # never required for auditability, never
                                                              # the basis for any section's comparison
```

Every leaf is a specifically-typed value — `SeriesMomentumResult` and
`TargetResult` are `inflation_v1.0`'s own, unmodified models, reused
verbatim as each section's canonical evidence at an explicit period; no
new economic type is introduced. `latest_shared_observation_period` is
a period-selection value (a `date | null`), not a new model.

## Machine-readable evidence requirement

Each section is independently auditable from its own embedded evidence
alone — never from a global pair, and never dependent on the optional
`current_monitor_result`. For numeric metrics: previous value, current
value, delta if comparable. For state changes: previous state, current
state. For availability: previous availability, current availability.
For confirmation: previous relationship, current relationship, and the
four underlying `SeriesMomentumResult` objects that produced them.

## No recalculation in the comparator

The eventual pure comparator, conceptually
`compare_section(previous_evidence, current_evidence) -> SectionChanges`,
must not know how CPI/PCE annualization works, must not import
`app.domain.inflation`'s formula-level helpers (`_rate`, `month_before`,
`classify_state`), and must not construct a `SeriesMomentumResult`
itself. It only reads already-computed fields off its two inputs and
does arithmetic or equality checks on them. Constructing the previous
and (now, critically) the current evidence — evaluating
`inflation_v1.0`'s existing classification primitives at this
contract's own explicit periods — belongs in the inflation methodology/
service layer, never inside the comparator. Selecting *which* period is
current (i.e., computing `latest_observation_period`/
`latest_shared_observation_period`) is period-selection logic, not
economic calculation, and may live in the service/orchestration layer
without violating this boundary — it decides *when*, never *what the
economics are*.

## AI boundary (unchanged)

Future AI may consume the **final** `InflationWhatChangedResult` and
narrate it in prose. AI may not decide whether state changed, whether
availability changed, what a delta is, which period is previous/
current, whether confirmation changed, whether a comparison was even
available, or whether a value is canonical. AI explains the change
object; it does not create it. This contract's own comparator must be
fully functional, deterministic, and complete with AI entirely
unavailable.

---

## Adversarial re-audit

| # | Case | Resolution |
|---|---|---|
| 1 | Valid → valid, same state | `comparison_available=true`; `state_changed=false`; any metric deltas still reported (category 3) — resolved |
| 2 | Valid → valid, different state | `state_changed=true` (category 2) — resolved |
| 3 | Valid → unavailable | `availability_lost=true`; no fabricated state transition — resolved. **This is the case the prior anchor design made unrepresentable**, now fixed by anchoring `current_period` at `latest_observation_period` |
| 4 | Unavailable → valid | `availability_restored=true` — resolved |
| 5 | Unavailable → unavailable | `no_availability_change`; no event; `comparison_available` remains `true` (a current anchor exists — the anchor date itself has an observation row, it just isn't classifiable); `changes=[]` is a legitimate "compared, nothing different" outcome — resolved |
| 6 | July valid / August unavailable, August latest | `current_period=August`, `previous_period=July` → `availability_lost=true` — resolved, see [Missing-Month Invariant](#missing-month-invariant-reconfirmed-under-the-corrected-anchors) |
| 7 | July valid / August unavailable / September valid, September latest | `current_period=September`, `previous_period=August` → `availability_restored=true`; July never examined; no manufactured `COOLING→HEATING` — resolved |
| 8 | Core CPI current observation exists but canonical state unavailable | `current_confirmation_period` still resolves (an observation exists), `current_confirmation_state.state = "INSUFFICIENT_DATA"`, `current_relationship = "UNAVAILABLE"` — resolved exactly by `latest_shared_observation_period`'s definition |
| 9 | Core PCE current valid / Core CPI current unavailable | Same exact period for both (never mismatched); relationship `UNAVAILABLE` per `classify_confirmation_relationship`'s existing rule — resolved |
| 10 | Confirmation `CONFIRMS → UNAVAILABLE` | Representable and required: `current_confirmation_period` (a `latest_shared_observation_period`) can independently be `UNAVAILABLE` even while an earlier `latest_common_period` was `CONFIRMS` — resolved, see the [worked example](#worked-example-from-this-corrections-own-motivating-case) |
| 11 | Confirmation `UNAVAILABLE → CONFIRMS` | Symmetric to 10: previous period unavailable, current period (later, more data now valid) confirms — `relationship_changed=true`, `confirmation_availability_restored=true` — resolved |
| 12 | `latest_common_period` older than `latest_shared_observation_period` | Expected and proven structural: `latest_common_period <= latest_shared_observation_period` always, since "valid state" implies "observation exists" but not vice versa — resolved, stated explicitly in [Monitor vs. What Changed](#monitor-vs-what-changed-anchor-semantics) |
| 13 | `latest_valid_state_period` older than `latest_observation_period` | Same structural relationship for primary — this is exactly the July/August scenario; expected, not an error — resolved |
| 14 | No shared Core PCE/Core CPI observation period at all | `latest_shared_observation_period = null` → `confirmation_changes.comparison_available = false`, both periods `null`, `changes=[]` — resolved |
| 15 | PCE and CPI have different latest observation periods | `latest_shared_observation_period` is the max of the *intersection*, not either series' own max in isolation — correctly resolves to the later of the two only if both have a row there, otherwise to the latest date both actually share — resolved |
| 16 | No arbitrary backward skipping | Every `previous_period` is exactly one calendar month before its section's `current_period`, always — no section ever searches for "a more convenient" period — resolved throughout |
| 17 | No cross-period confirmation | Core PCE and Core CPI are evaluated at the **exact same** period in both the previous and current confirmation evaluations — never a mismatched pair — resolved by construction (`classify_confirmation_relationship` is only ever called with two states computed at one shared period) |

**Result: PASS.** All 17 cases resolve to one unambiguous behavior. No
case was left open, and the specific contradiction that prompted this
correction (an unreachable `AVAILABLE → UNAVAILABLE` transition) is
fully resolved for both primary/target/headline (case 3) and
confirmation (case 10).

## Architecture recheck

```
existing persisted observations (existing repository, unmodified)
        ↓
inflation_v1.0 exact-period canonical component construction:
    classify_period(index, series_id, EXPLICIT period, ...)          -- EXISTING primitive, reused as-is
    _metric_evidence(index, series_id, EXPLICIT period, n, ...)      -- EXISTING primitive, reused as-is
    classify_confirmation_relationship(state_a, state_b)             -- EXISTING primitive, reused as-is
    latest_observation_date(observations)                            -- EXISTING primitive, reused as-is
    latest_shared_observation_period(primary_obs, confirmation_obs)  -- NEW, pure date-set intersection only
        ↓
pure change comparator (NEW, additive, zero formula knowledge):
    compare_section(previous_evidence, current_evidence) -> SectionChanges
        ↓
typed InflationWhatChangedResult (NEW models, additive)
        ↓
service (NEW method, analogous to InflationMonitorService.get_result)
        ↓
future API (not built in this task)
```

**`latest_shared_observation_period` requires no repository change.**
It is computed from exactly the same two observation lists (Core PCE's
and Core CPI's) that `InflationMonitorService.get_result` already
fetches in full today — a plain set intersection over `Observation.date`
values already in memory, then `max()`. No new query, no new column, no
migration.

The comparator itself still contains **zero** inflation formula
knowledge — period anchor selection (`latest_observation_period`,
`latest_shared_observation_period`) and all economic calculation/
classification happen in the service/methodology layer, reusing
`inflation_v1.0`'s existing primitives unmodified; the comparator only
ever receives already-computed evidence and diffs it.

---

## Remaining human decisions

**NONE.** The contradiction identified (unreachable `AVAILABLE →
UNAVAILABLE` transitions caused by anchoring "current" to
`inflation_v1.0`'s own *valid-state* period concepts) is fully
corrected by introducing `latest_shared_observation_period` for
confirmation and by anchoring ordinary series to
`latest_observation_period` instead of `latest_valid_state_period`.
Both carry-over decisions from the prior revision remain resolved.
`inflation_v1.0` itself was not modified — `latest_observation_period`,
`latest_valid_state_period`, and `latest_common_period` retain their
existing meanings and continue to serve the Monitor exactly as before.

## Freeze status

**FROZEN.**

- Contract ID: `inflation_what_changed_v1.0`
- Version: `1.0`

Frozen on the basis that: the anchor contradiction is fully resolved
without touching `inflation_v1.0`; the required #15 extension
(`latest_shared_observation_period` plus exact-period evaluation using
existing primitives) is precisely specified and needs no repository
change; no unresolved human product/methodology decision remains; and
the adversarial audit (17 cases) passes in full. As with
`inflation_v1.0`, freezing this contract means: implementation must
conform to it exactly; where implementation convenience conflicts with
this specification, this specification wins.
