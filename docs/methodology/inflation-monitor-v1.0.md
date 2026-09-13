# Economic Intelligence
# Inflation Monitor Methodology Specification v1.0

| | |
|---|---|
| Methodology ID | `inflation_v1.0` |
| Specification version | 1.0 |
| Status | **FROZEN** |
| Methodology type | Deterministic |
| AI dependency | None |
| Canonical geography | United States |
| Data basis | Latest revised data |
| Primary frequency | Monthly |
| Selected candidate | Candidate B — Dual Confirmation |
| Neutral band | δ = 0.10 percentage points |
| Primary series | Core PCE (`PCEPILFE`) |
| Confirmation series | Core CPI (`CPILFESL`) |
| Target series | Headline PCE (`PCEPI`) |
| Headline context series | Headline CPI (`CPIAUCSL`) |

> **This document is normative.** Production behavior MUST conform to
> this specification. Where implementation convenience conflicts with
> this specification, this specification wins. Implementation must not
> reinterpret, extend, simplify, or improve the economic methodology.

This document is documentation only. It does not implement, and must
not be read as authorizing implementation of, any production code,
API endpoint, service, repository, or domain module. Production
implementation is a separate, explicitly authorized task (referred to
elsewhere in this repository as "Increment #14") and has not begun.

---

## Why this document exists

The project previously attempted autonomous LLM orchestration of
analytical execution and learned that probabilistic behavior cannot be
trusted to own canonical analytical results (see
[ADR-016](../adr/016-no-ai-triggered-ingestion.md) and
[ADR-017](../adr/017-deterministic-analytical-execution-eligibility.md)).
The permanent architecture principle is:

> Facts are sourced. Calculations are deterministic. AI is
> interpretive.

The stronger engineering rule this project holds is:

> No probabilistic component may be required for the correctness,
> reproducibility, availability, or integrity of the Economic
> Intelligence Engine.

The Inflation Monitor therefore needs a frozen deterministic
methodology contract *before* production implementation begins. The
methodology below was selected through repository-based historical
research (`research/inflation_momentum/`, see
[Research Lineage](#research-lineage)) rather than intuition or prompt
behavior, and the choice of candidate/parameter is not reconsidered by
this document — it records the decision, it does not make it.

## Architecture context

The intended production layering, once implemented, is:

```
External economic sources
        ↓
Persistence
        ↓
Repositories
        ↓
Services
        ↓
Deterministic domain
        ↓
Versioned methodology   <-- this document specifies this layer
        ↓
Canonical evidence object
        ↓
FastAPI
      ↙       ↘
    UI       future AI explanation
```

AI is optional and non-canonical. Research code informs methodology
selection but MUST NOT become a runtime production dependency —
`app/` must never import anything under `research/` (enforced today by
`tests/research/test_inflation_momentum.py`'s architectural guard, and
must remain enforced for any future inflation-methodology code the
same way).

---

## Frozen economic hierarchy

```
TARGET LEVEL
  Headline PCE — FRED series: PCEPI

UNDERLYING MOMENTUM
  Core PCE — FRED series: PCEPILFE
  CANONICAL PRIMARY SIGNAL

UNDERLYING CONFIRMATION
  Core CPI — FRED series: CPILFESL
  CONFIRMATION ONLY

HEADLINE CONTEXT
  Headline PCE — PCEPI
  Headline CPI — CPIAUCSL
```

There is no voting system.

- Core CPI cannot override Core PCE.
- Headline CPI cannot override Core PCE.
- Headline PCE cannot override Core PCE momentum.
- Missing confirmation cannot override Core PCE.

## Frozen constants

```
FED_OBJECTIVE_PERCENT = 2.0

NEUTRAL_BAND_PP = 0.10

PRIMARY_SERIES       = PCEPILFE
CONFIRMATION_SERIES  = CPILFESL
TARGET_SERIES        = PCEPI
HEADLINE_CPI_SERIES  = CPIAUCSL
```

Changing any of these constants requires a new methodology version
(see [Versioning](#versioning)).

---

## Data source / runtime rule

Canonical calculation operates **only** on persisted canonical
observations.

Runtime methodology calculation MUST NOT:

- fetch FRED observations,
- trigger synchronization,
- trigger ingestion,
- search for replacement series,
- substitute series,
- call external providers,
- ask AI to select or repair data.

If required persisted observations are unavailable, the methodology's
missing-data semantics apply (see
[Missing intermediate months](#missing-intermediate-months) and
[Invalid index values](#invalid-index-values)).

Discovery is not analysis. Discovery is not ingestion.

## Monthly period semantics

All four canonical series are monthly. A period `t` means a specific
calendar month. Offsets MUST be resolved using **exact calendar-month
endpoints** — never "the Nth previous row in a database result set" or
"the Nth previous item in a list."

Example: if `t = 2026-07`, then:

```
t-1  = 2026-06
t-3  = 2026-04
t-6  = 2026-01
t-12 = 2025-07
```

A missing month cannot shift the meaning of later offsets. This
distinction is mandatory: implementing horizons by counting back N
rows of whatever happens to be persisted (rather than looking up the
exact calendar date N months earlier) is a methodology violation, not
an acceptable implementation shortcut, even where it happens to produce
the same numeric result on dense, gap-free data.

## Required observations

| Horizon | Required endpoints | Authority |
|---|---|---|
| Contextual 1M | `P_t`, `P_(t-1)` | Contextual only |
| Canonical 3M | `P_t`, `P_(t-3)` | Canonical |
| Canonical 6M | `P_t`, `P_(t-6)` | Canonical |
| Canonical 12M | `P_t`, `P_(t-12)` | Canonical |

Canonical state classification requires valid `r_3m`, `r_6m`, and
`r_12m`. `r_1m` is contextual only. Therefore **a missing `t-1` MUST
NOT invalidate an otherwise valid canonical momentum state.**

## Missing intermediate months

The annualized calculations are **endpoint calculations**. A missing
month *between* valid endpoints does not invalidate the calculation.

Example:

```
January available
February missing
March available
April available
```

April's 3M uses `P_April / P_January` directly. That 3M calculation is
valid. February remains missing — it is not interpolated, not
fabricated; it is simply not required by that endpoint calculation.

However, if an exact required endpoint itself is missing, the affected
derived metric is unavailable (see next section).

## Invalid index values

A required index endpoint must be finite and strictly greater than
zero. The affected metric is unavailable if an endpoint is:

- missing,
- null,
- NaN,
- +infinity,
- −infinity,
- zero,
- negative.

Do not silently coerce invalid values. If `r_3m`, `r_6m`, or `r_12m` is
unavailable, the canonical state is `INSUFFICIENT_DATA`.

Implementation note (non-normative but required for correctness):
a naive `value <= 0` guard does **not** reliably exclude `NaN` in
IEEE-754 floating point, because every comparison against `NaN`
evaluates to `False`. Production code must test finiteness and
positivity explicitly (e.g. `math.isfinite(value) and value > 0`), not
rely on `<=`/`>` alone to reject `NaN`.

---

## Transformations

Use full available precision. Do not round before classification (see
[Rounding](#rounding)).

**1M annualized** (contextual only):
```
r_1m = ((P_t / P_(t-1)) ^ 12 - 1) * 100
```

**3M annualized** (canonical):
```
r_3m = ((P_t / P_(t-3)) ^ 4 - 1) * 100
```

**6M annualized** (canonical):
```
r_6m = ((P_t / P_(t-6)) ^ 2 - 1) * 100
```

**12M** (canonical):
```
r_12m = (P_t / P_(t-12) - 1) * 100
```

Do **not** annualize by multiplying a simple percentage change by 12,
4, or 2. Compounding is required. (Equivalently, `r_12m` is the special
case of the general compounding formula `((P_t/P_(t-n))^(12/n) - 1)*100`
at `n=12`, where the exponent `12/n` is exactly 1.)

## Role of 1M

`r_1m` is contextual evidence only. It has **zero authority** over
canonical state. No extreme 1M value creates an exception.

## Neutral band

```
delta = 0.10 percentage points

lower = r_12m - 0.10
upper = r_12m + 0.10
```

`0.10` means **percentage points**. It does not mean 10 percent, 10
percent of the trailing rate, or a relative 10 percent change.

## Canonical state enum

Exactly five states exist:

```
COOLING
HEATING
STABLE
MIXED
INSUFFICIENT_DATA
```

Do not add aliases or extra canonical states.

## Classification rules

**COOLING** iff: `r_3m < lower` AND `r_6m < lower` (both strict).

**HEATING** iff: `r_3m > upper` AND `r_6m > upper` (both strict).

**STABLE** iff: `lower <= r_3m <= upper` AND `lower <= r_6m <= upper`
(the neutral interval is inclusive on both ends).

**MIXED** iff: `r_3m`, `r_6m`, and `r_12m` are all valid, AND none of
COOLING, HEATING, or STABLE applies.

**INSUFFICIENT_DATA** iff any of `r_3m`, `r_6m`, `r_12m` is
unavailable. Missing `r_1m` alone does NOT produce
`INSUFFICIENT_DATA`.

### Normative classification pseudocode

```
if r_3m unavailable OR r_6m unavailable OR r_12m unavailable:
    state = INSUFFICIENT_DATA

else:
    lower = r_12m - 0.10
    upper = r_12m + 0.10

    if r_3m < lower AND r_6m < lower:
        state = COOLING

    elif r_3m > upper AND r_6m > upper:
        state = HEATING

    elif lower <= r_3m <= upper AND lower <= r_6m <= upper:
        state = STABLE

    else:
        state = MIXED
```

### No hidden epsilon

Do not invent an extra floating-point epsilon. The 0.10
percentage-point band **is** the methodology tolerance. Do not add
logic such as `epsilon = 0.00001` to redefine equality or boundaries.
If the repository's numeric representation is found to create a
genuine boundary problem, implementation must stop and report it
rather than silently altering methodology — see
[Adversarial Audit](#adversarial-specification-audit) for the
floating-point verification already performed against this exact
constant.

### Rounding

Classification occurs using full calculation precision. Do not round
before creating boundaries, comparisons, classification, or the
target-gap calculation. Presentation rounding is downstream and may
not alter canonical state.

---

## Target level

Target level uses Headline PCE (`PCEPI`):

```
headline_pce_yoy = (P_t / P_(t-12) - 1) * 100

target_gap_pp = headline_pce_yoy - 2.0
```

There is **no** canonical target-gap state. Do not invent `HIGH`,
`LOW`, `NORMAL`, `ABOVE_TARGET`, `BELOW_TARGET`, `DANGEROUS`, or similar
methodology states. The numeric gap is the canonical target-relative
output.

## Level and momentum are independent

Example: Headline PCE YoY = 3.4%, target gap = +1.4pp, while Core PCE
momentum = COOLING. This is valid. The product may truthfully express:

> Inflation remains above the Federal Reserve's longer-run objective
> while underlying inflation momentum is cooling.

The target gap must not alter momentum classification. Momentum
classification must not alter the target gap.

---

## Core CPI confirmation

Core CPI (`CPILFESL`) is independently classified using **exactly the
same**:

- 3M formula,
- 6M formula,
- 12M formula,
- 0.10pp neutral band,
- five-state enum,
- exact period semantics,
- missing-data semantics.

Core CPI is confirmation only. It **never** changes the Core PCE
canonical state.

## Confirmation relationship enum

Exactly four relationship values exist:

```
CONFIRMS
DIVERGES
INCONCLUSIVE
UNAVAILABLE
```

**CONFIRMS** iff: (Core PCE = COOLING and Core CPI = COOLING) OR
(Core PCE = HEATING and Core CPI = HEATING) OR (Core PCE = STABLE and
Core CPI = STABLE). MIXED + MIXED is **not** confirmation — it is
INCONCLUSIVE.

**DIVERGES** iff: (Core PCE = COOLING and Core CPI = HEATING) OR
(Core PCE = HEATING and Core CPI = COOLING).

**UNAVAILABLE** iff: Core CPI state = `INSUFFICIENT_DATA` OR Core PCE
state = `INSUFFICIENT_DATA`.

**INCONCLUSIVE** applies to every sufficiently-observed state
combination that is not CONFIRMS or DIVERGES.

### Confirmation matrix (illustrative, not exhaustive by enumeration — the rule above is exhaustive)

| Core PCE | Core CPI | Relationship |
|---|---|---|
| COOLING | COOLING | CONFIRMS |
| HEATING | HEATING | CONFIRMS |
| STABLE | STABLE | CONFIRMS |
| COOLING | HEATING | DIVERGES |
| HEATING | COOLING | DIVERGES |
| COOLING | STABLE | INCONCLUSIVE |
| STABLE | COOLING | INCONCLUSIVE |
| STABLE | HEATING | INCONCLUSIVE |
| MIXED | MIXED | INCONCLUSIVE |
| MIXED | COOLING | INCONCLUSIVE |
| COOLING | MIXED | INCONCLUSIVE |
| valid | INSUFFICIENT_DATA | UNAVAILABLE |
| INSUFFICIENT_DATA | any | UNAVAILABLE |

## Primary authority

Canonical underlying state is:

```
classify(Core PCE)
```

It is **not** `combine(Core PCE, Core CPI)`. It is **not**
`vote(Core PCE, Core CPI)`. It is **not** `AI_decide(...)`. This is a
hard invariant.

## Headline context

Headline PCE and Headline CPI may each independently expose `r_1m`,
`r_3m`, `r_6m`, `r_12m`, and `state` using the same deterministic
methodology. However, `inflation_v1.0` defines **no** aggregate
headline-context state. Do not invent one.

---

## Latest observation period

For an individual series, expose `latest_observation_period`: the
latest persisted monthly observation for that series.

Also distinguish `latest_valid_state_period`: the latest period for
which `r_3m`, `r_6m`, and `r_12m` can all be calculated using exact
calendar endpoints.

These may differ (e.g. the newest observation exists but its `t-12`
endpoint does not yet have 12 months of history behind it, or its
`t-3`/`t-6`/`t-12` endpoint is itself missing).

## Latest common period

For Core PCE/Core CPI confirmation, define `latest_common_period` as
the greatest monthly period `t` for which **both** Core PCE and Core
CPI independently have valid canonical states. A shared observation row
is not enough — both canonical states must be calculable. If the
newest shared row does not permit both calculations, search backward
chronologically for the most recent period that does.

## No cross-period confirmation

Never compare Core PCE July against Core CPI August and call it
confirmation. The confirmation relationship uses states from the exact
same period.

## Latest standalone vs. comparison states

The canonical contract must preserve the distinction between:

- primary latest state,
- primary state at the comparison period,
- confirmation latest state,
- confirmation state at the comparison period,
- latest common period.

**Example A:** Core PCE latest valid = July; Core CPI latest valid =
August; both series are valid in July. Then: primary latest = Core PCE
July; confirmation latest = Core CPI August; latest common period =
July; the relationship uses Core PCE July vs. Core CPI July.

**Example B (reversed):** Core PCE latest valid = August; Core CPI
latest valid = July. Then: primary latest = Core PCE August; latest
common period = July; the relationship uses Core PCE July vs. Core CPI
July.

## No common period

If the two series have valid standalone states but no period exists in
the supported history where both have valid states:

```
latest_common_period = null
relationship = UNAVAILABLE
```

Never compare mismatched months.

## Staleness

There is no canonical `STALE` inflation state. Expose dates. A future
freshness policy may be added separately. For v1.0, "Data through:
YYYY-MM" is metadata, not economic direction.

## Evidence coverage

Canonical availability booleans:

```
primary_available
confirmation_available
target_available
headline_cpi_available
```

A component is `true` only if its required canonical result can
actually be calculated. Do not infer availability merely from the
presence of a latest observation. A UI may derive
`available_component_count` / `total_component_count = 4` (e.g.
"Evidence coverage: 3/4"). This is coverage. It is **not** confidence.
Never create a confidence percentage from these booleans.

---

## Data basis

Machine-readable value: `latest_revised_data`
User-facing label: **Latest revised data**

Required disclosure concept:

> Historical calculations use the latest revised observations
> available to Economic Intelligence. They may differ from values
> originally reported at the time.

The current persistence model does not provide true point-in-time
historical vintages. Therefore do **not** claim "what was known at the
time" or "what Economic Intelligence would have shown that day" for
historical calculations. Correct framing is equivalent to:

> Using the latest revised historical data, that period classifies as
> [state] under inflation_v1.0.

## Provenance

Every derived metric must be traceable to at least: `series_id`,
`calculation_period`, `transformation`, endpoint dates, endpoint
values, calculated unrounded value, `methodology_id`, `data_basis`.

| Horizon | Endpoint values required |
|---|---|
| 1M | `P_t`, `P_(t-1)` |
| 3M | `P_t`, `P_(t-3)` |
| 6M | `P_t`, `P_(t-6)` |
| 12M | `P_t`, `P_(t-12)` |

Do not fabricate retrieval timestamps, release timestamps, vintage
dates, or revision numbers if they are not currently available from
the canonical persistence architecture.

---

## Canonical result structure (conceptual — not implemented by this document)

The future production implementation must expose a typed,
application-owned canonical result. At minimum it must conceptually
contain: `methodology_id`, `data_basis`, `target`, `underlying_momentum`,
`confirmation`, `headline_context`, `periods`, `coverage`. This task is
documentation-only — these production models are **not** created here.
This specification makes the required concepts explicit so a future
implementation has an unambiguous contract to type against.

### Underlying evidence requirements

The future canonical underlying result must contain enough information
to represent: `series_id`, `calculation_period`, `r_1m_annualized`,
`r_3m_annualized`, `r_6m_annualized`, `r_12m`, `neutral_band_pp`,
`lower_boundary`, `upper_boundary`, `state`, `missing_required_metrics`,
and metric provenance.

`r_1m` may be unavailable without invalidating state. If state is not
`INSUFFICIENT_DATA`, then `r_3m`, `r_6m`, `r_12m`, `lower_boundary`, and
`upper_boundary` must all be present. If state is `INSUFFICIENT_DATA`,
`missing_required_metrics` must be non-empty.

### Target evidence

The future target result must represent: `series_id = PCEPI`,
`calculation_period`, `headline_pce_yoy`, `fed_objective_percent = 2.0`,
`target_gap_pp`, provenance, `available`. If target YoY cannot be
calculated: `available = false`, `headline_pce_yoy = null`,
`target_gap_pp = null`.

### Confirmation evidence

The future canonical contract must make a clear distinction between
Core CPI latest standalone state, Core CPI comparison-period state, the
comparison period itself, and the confirmation relationship. It must
not be possible for callers to accidentally interpret August Core CPI
as the confirmation evidence for July Core PCE.

---

## What changed?

The methodology distinguishes: metric change, state change,
availability change, confirmation relationship change. These must
never be conflated.

Example: 3M goes from 2.8 to 2.7; state stays COOLING → COOLING. This
means the metric changed but the state did not change. A state
transition exists only when `previous_state != current_state` for
valid, comparable methodology results. Do not silently jump across a
missing-data period and imply continuity. A valid → `INSUFFICIENT_DATA`
change is an **availability** change, not an economic transition to a
directional state.

---

## AI boundary

AI is outside `inflation_v1.0`. Future AI may consume the **final**
deterministic evidence object.

AI may: explain, summarize, translate, answer questions using the
supplied result, describe already-computed changes, suggest further
investigation.

AI may **not**: calculate canonical inflation metrics, classify
canonical state, alter state, choose replacement series, fill missing
data, choose cross-series comparison periods, alter target gap, invent
provenance, change methodology.

If future AI prose disagrees with deterministic evidence, the
deterministic evidence wins. The Inflation Monitor must remain fully
functional with AI unavailable.

---

## Versioning

Every canonical result will carry `methodology_id = inflation_v1.0`. A
new methodology version is required if any of these change: series
IDs, the Fed objective constant, primary authority, confirmation role,
transformation formulas, horizons, neutral band, state enum, boundary
operators, state logic, missing-data semantics, calendar-offset
semantics, latest-common-period semantics, target-gap formula,
confirmation relationship semantics. Presentation-only changes do not
necessarily require a new methodology version.

---

## Research lineage

The repository's historical methodology study (`research/inflation_momentum/`,
in particular `STUDY_RESULTS.md` and `FINALIST_ANALYSIS.md`) must
remain visible and unaltered except for additive documentation if
necessary. Nothing in that history is rewritten or deleted by this
specification.

The study considered four candidate families (A — Recent vs Trailing,
B — Dual Confirmation, C — Ordered Momentum, D — Change in Recent
Momentum) and multiple neutral bands for the finalists. The final
selected methodology, decided by a human reviewer from that evidence
(not re-decided here), is:

> Candidate B, Dual Confirmation, δ = 0.10 percentage points, Core PCE
> primary / Core CPI confirmation.

See [Research Consistency](#research-consistency-check) below for the
check confirming this specification did not misstate that research.

---

## Normative adversarial cases

Assume `12M = 3.00`, `lower = 2.90`, `upper = 3.10`:

| 3M | 6M | Expected state |
|---|---|---|
| 2.50 | 2.70 | COOLING |
| 3.40 | 3.20 | HEATING |
| 2.90 | 2.90 | STABLE |
| 3.10 | 3.10 | STABLE |
| 2.90 | 3.10 | STABLE |
| 2.899999 | 2.80 | COOLING |
| 3.100001 | 3.20 | HEATING |
| 2.70 | 3.30 | MIXED |
| 2.70 | 3.00 | MIXED |
| 3.30 | 3.00 | MIXED |
| 3.00 | 2.70 | MIXED |
| 3.00 | 3.30 | MIXED |

| 3M | 6M | 12M | Expected state |
|---|---|---|---|
| unavailable | 2.70 | 3.00 | INSUFFICIENT_DATA |
| 2.70 | unavailable | 3.00 | INSUFFICIENT_DATA |
| 2.70 | 2.80 | unavailable | INSUFFICIENT_DATA |

All of the above were executed against the already-implemented,
already-unit-tested classification function
(`classify_candidate_b_explicit` in
`research/inflation_momentum/methodology.py`, parameterized at
`delta=0.10`) as part of this freeze's adversarial audit; every case
matched exactly (see [Adversarial Audit](#adversarial-specification-audit)).

## Negative-inflation cases

The methodology is relative to the trailing rate, not to zero.

Assume `12M = -1.00`, `lower = -1.10`, `upper = -0.90`:

| 3M | 6M | Expected state |
|---|---|---|
| -2.00 | -1.50 | COOLING |
| 0.00 | -0.50 | HEATING |

Do not add special deflation logic.

## Missing-month case

If October is required as the exact `t-3` endpoint and October is
missing: `r_3m = unavailable`, and canonical state may become
`INSUFFICIENT_DATA`. A later calculation whose exact required endpoints
are present must remain valid even though October is still absent — no
interpolation, no row-position substitution.

## Infrastructure failure vs. economic insufficiency

These are different.

- Missing required persisted observation → `INSUFFICIENT_DATA`
  (an economic-data-availability outcome).
- Database unavailable → infrastructure/API error (e.g. HTTP 503),
  never converted into an economic `INSUFFICIENT_DATA` result.

This distinction already has precedent in the existing API (e.g.
`app/api/analysis.py` distinguishes `503 "Database is currently
unavailable."` from `404`/`400` data-shape errors); the Inflation
Monitor must preserve the same separation.

## Determinism

Given identical persisted canonical observations and methodology
version: numeric results are identical, state is identical, comparison
period is identical, confirmation relationship is identical, evidence
semantics are identical. The calculation must not depend on current
time, randomness, network calls, AI, or unordered iteration behavior.

## Pure domain requirement for future implementation

The eventual methodology core must be implementable as a pure
deterministic operation over explicit inputs. It must not itself open
DB sessions, make HTTP calls, call FRED, call OpenAI, read environment
variables, mutate observations, or persist results. This document only
records that requirement; it does not implement it (see
[ADR-010](../adr/010-pure-transformation-engine.md) for the existing,
directly analogous precedent this future module must follow).

---

## Adversarial specification audit

Performed as part of freezing this document (not part of production
implementation). For each item: does the frozen specification yield
one unambiguous expected behavior?

| # | Case | Result |
|---|---|---|
| 1 | Exact equality at lower boundary | Unambiguous — inclusive, STABLE-eligible (verified numerically, see below) |
| 2 | Exact equality at upper boundary | Unambiguous — inclusive, STABLE-eligible (verified numerically) |
| 3 | Floating values just outside each boundary | Unambiguous — strict COOLING/HEATING; verified `3.0 - 0.10 == 2.9` and `3.0 + 0.10 == 3.1` exactly in IEEE-754 double precision for this constant, no hidden-epsilon issue found |
| 4 | Negative inflation | Unambiguous — band is relative to `r_12m`, not zero; verified numerically |
| 5 | Very large positive inflation | Unambiguous — same strict `>` comparison regardless of magnitude |
| 6 | Missing t-1 only | Unambiguous — contextual only, canonical state unaffected |
| 7 | Missing t-3 | Unambiguous — `r_3m` unavailable → `INSUFFICIENT_DATA` |
| 8 | Missing t-6 | Unambiguous — `r_6m` unavailable → `INSUFFICIENT_DATA` |
| 9 | Missing t-12 | Unambiguous — `r_12m` unavailable → `INSUFFICIENT_DATA` (also invalidates the neutral band itself) |
| 10 | Missing intermediate non-endpoint month | Unambiguous — does not invalidate an endpoint calculation that doesn't require it |
| 11 | Zero index value | Unambiguous — invalid endpoint, unavailable |
| 12 | Negative index value | Unambiguous — invalid endpoint, unavailable |
| 13 | NaN/non-finite value if representable | Unambiguous rule stated (`isfinite` required); flagged as an implementation-note since naive `<=` comparisons don't reliably reject NaN — this is an implementation-correctness note, not a specification ambiguity |
| 14 | Core PCE valid / Core CPI missing | Unambiguous — UNAVAILABLE relationship; Core PCE state unaffected |
| 15 | Core PCE missing / Core CPI valid | Unambiguous — UNAVAILABLE relationship |
| 16 | Core PCE COOLING / CPI HEATING | Unambiguous — DIVERGES |
| 17 | Core PCE MIXED / CPI MIXED | Unambiguous — INCONCLUSIVE (explicitly not CONFIRMS) |
| 18 | Latest CPI later than latest PCE | Unambiguous — see worked Example A above |
| 19 | Latest PCE later than latest CPI | Unambiguous — see worked Example B above |
| 20 | Same recent observation date but one series lacks a historical endpoint | Unambiguous — that series' own state is `INSUFFICIENT_DATA` for that period; `latest_common_period` search continues backward |
| 21 | No common valid comparison period | Unambiguous — `latest_common_period = null`, relationship = UNAVAILABLE |
| 22 | Target available / primary unavailable | Unambiguous — target and underlying momentum are computed and reported independently; one's availability never gates the other |
| 23 | Primary available / target unavailable | Unambiguous — symmetric to #22 |
| 24 | Revised historical data terminology | Unambiguous — "Latest revised data" required framing; "what was known at the time" framing explicitly forbidden |
| 25 | Infrastructure failure vs. economic missing data | Unambiguous — distinct outcomes, existing API precedent for the separation already exists |
| 26 | Methodology versioning ambiguity | Unambiguous — exhaustive list of version-forcing changes given |
| 27 | Accidental dependency on research code | Unambiguous — forbidden; existing architectural guard (`tests/research/test_inflation_momentum.py`) already enforces `app/` never imports `research/`, and must continue to |
| 28 | Accidental dependency on AI | Unambiguous — forbidden; methodology core must be pure (no AI calls) |
| 29 | Accidental live FRED analytical dependency | Unambiguous — forbidden; canonical calculation reads only persisted observations |
| 30 | Evidence contradiction with returned state | Unambiguous — evidence fields (`r_3m`, `r_6m`, `r_12m`, boundaries) must be internally consistent with the returned `state` by construction, since state is a pure function of exactly those fields |
| 31 | Row-offset vs. calendar-offset mistakes | Unambiguous rule stated; flagged as an important implementation note (see below) |
| 32 | Classification after presentation rounding | Unambiguous — forbidden; classification uses full precision, rounding is presentation-only and downstream |
| 33 | Missing 1M incorrectly invalidating canonical state | Unambiguous — explicitly forbidden by the required-observations table |
| 34 | Core CPI accidentally overriding Core PCE | Unambiguous — forbidden by the Primary Authority hard invariant |
| 35 | Headline series accidentally majority-voted into primary state | Unambiguous — forbidden; headline series have no aggregate state and no vote at all |

**Result: PASS.** Every adversarial case listed yields one unambiguous
expected behavior under this specification. No case required inventing
an answer or was left ambiguous.

Two items are recorded above not as ambiguities but as **implementation
notes** a future Increment #14 must observe carefully, because getting
them wrong would silently violate this already-unambiguous
specification:

- **NaN handling (#13):** production code must use an explicit
  finiteness+positivity check (e.g. `math.isfinite(value) and value >
  0`), not a bare `<=`/`>` comparison, since IEEE-754 `NaN` comparisons
  are always `False` and would otherwise slip past a naive guard.
- **Row-offset vs. calendar-offset (#31):** `app/domain/transformations.py`'s
  existing `absolute_change`/`percent_change`/`moving_average` compute
  offsets by **list position** (`observations[index - 1]`,
  `observations[index+1-window : index+1]`), not by exact calendar
  date. That pattern is appropriate for those general-purpose,
  arbitrary-series transformations, but it must **not** be reused for
  `inflation_v1.0`'s horizon lookups, which this specification requires
  to be resolved by exact calendar-month date lookup regardless of
  which rows happen to be persisted. See
  [Architecture Compatibility](#architecture-compatibility-check) for
  confirmation that the existing codebase already has a suitable
  pattern for this (`app/domain/analysis.py`'s `align_series`, which
  builds an exact `{date: value}` mapping rather than assuming row
  alignment).

## Research consistency check

Compared the frozen rules above against the existing research
artifacts (`research/inflation_momentum/methodology.py`,
`finalist_study.py`, `FINALIST_ANALYSIS.md`):

- **Formula equivalence:** the research's general compounding formula
  `((current/past) ** (12/n_months) - 1) * 100` is mathematically
  identical to this specification's four named formulas at `n=1, 3, 6,
  12` respectively (verified by direct substitution: `12/12 = 1`,
  matching `r_12m`'s stated exponent-free form).
- **Boundary operators:** the research's `_horizon_bucket`/
  `classify_candidate_b_explicit` implement exactly this
  specification's inclusive-band/strict-outside boundary rule (`below`
  iff `value < center - delta`; `above` iff `value > center + delta`;
  `in` otherwise) — the same closed-interval semantics this document
  requires.
- **Enum and classification logic:** the research's five-state function
  (COOLING/HEATING/STABLE/MIXED/INSUFFICIENT_DATA) implements exactly
  this specification's classification rules, verified directly by
  executing every worked adversarial case in this document (including
  the exact `12M=3.00, delta=0.10` boundary values) against that real
  function — all matched.
- **Delta value:** `delta=0.10` is one of the three finalist deltas the
  research explicitly computed and reported for Candidate B in
  `FINALIST_ANALYSIS.md` (alongside 0.25 and 0.50) — the selected value
  is drawn from evidence actually produced, not a new, untested number.
- **Primary-authority independence:** the research's
  `finalist_missing_confirmation_check.json` empirically verified,
  against the real 2025-10-01 Core-CPI data gap, that Core PCE's own
  classification is structurally unaffected by a missing Core CPI
  observation — directly supporting this specification's Primary
  Authority invariant.
- **One noted, non-blocking implementation-pattern difference:** the
  research's `compute_transformations` resolves horizons by **row
  position** (`ordered[i - n]`) rather than by exact calendar date
  lookup. This was verified (this session) to produce numerically
  identical results to true calendar-exact lookback for the actual
  cached data, because all four cached series have zero
  structurally-missing calendar months across their entire persisted
  history (every month has a row; the one real gap, 2025-10-01 in both
  CPI series, is present as a row with a null value, not an absent
  row) — confirmed directly by walking each series' date list and
  finding zero row-to-row calendar-month gaps. This equivalence is a
  fact about the specific research dataset, not a property of the
  row-position code itself, and it does **not** carry over to
  production: the persisted `economic_observations` table has no
  structural guarantee against an actually-missing row (see
  [Architecture Compatibility](#architecture-compatibility-check)).
  This is why the specification above states the calendar-exact rule
  explicitly and calls out row-position implementation as forbidden —
  the research code's shortcut was safe for research precisely because
  it was checked, not because row-position and calendar-exact are
  generally interchangeable.

**Result: no material mismatch.** The frozen specification accurately
represents the research methodology and the human-selected
Candidate B / δ=0.10 decision. The one difference identified is a
research-code implementation detail, verified equivalent for the
dataset actually used, and is called out precisely so a future
production implementation does not copy it.

## Architecture compatibility check

Inspected the current production architecture
(`app/domain/`, `app/repositories/series_repository.py`,
`app/services/`, `app/models/`, `app/api/`, and ADR-009/010/011/017) to
determine whether this specification can fit the existing dependency
direction (repository → service → deterministic domain → API) without
a blocking conflict.

- `SeriesRepository.get_observations_in_range` already returns a full,
  unpaginated, chronologically-ordered set of a series' observations —
  sufficient input for a pure domain function to build an exact
  `{date: value}` mapping and resolve calendar-exact endpoints itself,
  with no repository contract change required.
- `app/domain/analysis.py`'s existing `align_series` already builds
  exact-date `{date: value}` mappings from two independently-fetched
  observation lists and performs exact-date-only intersection (per
  [ADR-011](../adr/011-exact-date-alignment.md)) — directly analogous
  to, and reusable as a pattern for, this specification's
  `latest_common_period` search.
- `app/domain/transformations.py`'s row-position offset pattern
  ([ADR-010](../adr/010-pure-transformation-engine.md)) is not reused
  by this specification (see the implementation note above); nothing
  about the existing module prevents a new, separate, calendar-exact
  domain module from being added alongside it.
- `app/models/series.py`'s `Observation` model (`date: date, value:
  float | None`) already carries exactly the shape a calendar-exact
  lookup needs, with no schema change required.
- `app/api/analysis.py`'s existing error handling already distinguishes
  infrastructure failure (503 "Database is currently unavailable",
  500 "Database error...") from data-shape/availability errors
  (400/404) — precedent this specification's infrastructure-vs-
  economic-insufficiency distinction fits directly.
- ADR-017's principle ("the application, never the model, owns whether
  a proposed action may execute") is precedent directly supporting this
  specification's AI Boundary section, requiring no new architectural
  decision.

**Result: no blocking conflict found.** A future Increment #14 can
implement this specification's methodology core as a pure function
(matching the existing `app/domain/` convention) fed by data already
retrievable through the existing repository, without changing any
existing public contract in a dangerous way, without a migration, and
without violating any existing invariant. Mere implementation *work*
(a new domain module, new Pydantic response models, a new service
method, a new route) is expected and is not a blocker — no conflict of
the kind described in this document's charge ("existing storage cannot
retrieve exact calendar endpoints," "existing numeric representation
cannot preserve required boundary semantics," "current repository
behavior makes latest-common-period impossible without violating an
existing invariant") was found.
