# Labor UI + Overview Integration V1 — Frozen Contract

**Increment #20E.1 (audit / product design / contract freeze only — no
implementation).** Freezes the dedicated `/labor` page, Labor's
integration into the Economic Overview, and every presentation
decision Increment #20E.2 must implement exactly. The backend owns
economics; the frontend owns presentation — every design below reads a
canonical backend value and formats it; none derives one.

---

## 1. Baseline

- `git status --porcelain`: clean. HEAD: `2a08f0d Add Employment
  Situation release integration for Labor (#20D.2)`.
- Backend suite: **1,173 passed, 0 skipped, 0 failed.**
- Frontend suite: **487 passed, 0 skipped, 0 failed** (23 test files).

## 2. Frontend files inspected

Routing/shell: `App.tsx`, `layouts/AppShell.tsx`. Pages: `pages/Inflation.tsx`,
`pages/Overview.tsx`, `pages/Releases.tsx`. Inflation components:
`Badge.tsx`, `InflationHero.tsx`, `WhyThisState.tsx`,
`MomentumMetrics.tsx`, `TargetPanel.tsx`, `ConfirmationPanel.tsx`,
`HeadlineContext.tsx`, `WhatChangedSection.tsx`, `EvidenceDisclosure.tsx`,
`MethodologyDisclosure.tsx`, `DataBasisNote.tsx`. Overview components:
`CurrentStateSection.tsx`, `WhatChangedPreview.tsx`,
`LatestDataDetected.tsx`, `UpcomingReleasesPreview.tsx`,
`RecentReleasePreview.tsx`. Releases components: `ReleaseRow.tsx`,
`ReleaseScheduleDisclosure.tsx`, `ScheduleStatusBadge.tsx`. Shared:
`Disclosure.tsx`, `ExplanationTrigger.tsx`, `ErrorMessage.tsx`,
`LoadingSkeleton.tsx`, `PageContainer.tsx`. API layer: `api/client.ts`,
`api/errors.ts`, `api/useApiResource.ts`, `api/inflation.ts` +
`.types.ts`, `api/releases.ts` + `.types.ts`, `api/processingStatus.ts`
+ `.types.ts`. Lib: `lib/format.ts`, `lib/inflationLabels.ts`,
`lib/detectedChangeFormat.ts`, `lib/releases.ts`. Content:
`content/explanations/types.ts`, `inflation.ts`, `releases.ts`,
`processingStatus.ts`. Architecture guards:
`test/no-economic-logic.test.ts`,
`test/no-explanation-classification-logic.test.ts`,
`test/no-overview-mutation.test.ts`,
`test/no-release-sync-or-coupling.test.ts`. `package.json` (confirms:
no chart library of any kind is installed).

## 3. Backend Labor contracts inspected — exact response shapes

Recorded from a live `TestClient` call, not from memory or the models
alone.

**`GET /api/v1/monitors/labor`** →
```json
{
  "methodology_id": "labor_v1.0", "data_basis": "latest_revised_data",
  "state": "INSUFFICIENT_DATA", "evaluation_period": null,
  "employment": {
    "series_id": "PAYEMS", "current_3m_avg_jobs": null, "prior_3m_avg_jobs": null,
    "momentum_delta_jobs": null, "condition_deadband_jobs": 50000.0, "momentum_deadband_jobs": 50000.0,
    "condition": "INSUFFICIENT_DATA", "momentum": "INSUFFICIENT_DATA", "state": "INSUFFICIENT_DATA",
    "observations": [{"series_id": "...", "observation_date": "YYYY-MM-DD", "value": <float|null>}, ...]
  },
  "unemployment": {
    "series_id": "UNRATE", "current_3m_avg": null, "prior_year_3m_avg": null, "delta_pp": null,
    "unemployment_deadband_pp": 0.2, "state": "INSUFFICIENT_DATA",
    "observations": [...]
  }
}
```

**`GET /api/v1/monitors/labor/changes`** → top level:
`methodology_id`, `comparison_contract_id` ("labor_what_changed_v1.0"),
`comparison_type` ("MONTH_OVER_MONTH"), `data_basis`,
`comparison_available`, `previous_period`, `current_period`,
`previous_labor_state`, `current_labor_state`, `employment_changes`
(`{previous_evidence, current_evidence, changes[], state_changed,
metric_changed, availability_lost, availability_restored}`),
`unemployment_changes` (same shape), `changes[]` (the flattened,
deterministically-ordered union), `any_state_changed`,
`any_metric_changed`, `any_availability_changed`,
`current_labor_result` (a full `LaborMonitorResult`, or `null`).

**One `LaborChangeEvent`**, confirmed live:
```json
{
  "component": "EMPLOYMENT", "event_type": "STATE_CHANGED", "field": "state",
  "previous_value": "CONTRACTING", "current_value": "RECOVERING", "delta": null,
  "previous_period": "2009-04-01", "current_period": "2009-05-01",
  "methodology_id": "labor_v1.0", "data_basis": "latest_revised_data"
}
```
Numeric `METRIC_CHANGED` events carry raw floats with no unit suffix
(e.g. `"previous_value": -617333.33`) — see §18.

## 4. Release/read-model contracts inspected

`GET /api/v1/releases` → `ReleaseOccurrenceItem { release_id, name,
provider, provider_release_id, official_url, scheduled_date,
schedule_status }` — no filter param beyond date/limit/offset/order,
but `provider_release_id`/`name` are already present on every returned
row, so **client-side filtering on `provider_release_id === "50"`** of
the already-fetched Upcoming/Recent arrays is sufficient; no new
backend endpoint needed. `GET /api/v1/releases/processing-status`
**already accepts a `release_id` query parameter** (confirmed in
`app/api/release_processing_read.py`) — the Labor page can resolve
Employment Situation's `release_id` from the releases call above, then
call processing-status filtered to exactly that release, rather than
scanning the generic default page Overview uses.

## 5. #20D release intelligence — what's available

Employment Situation's own `ReleaseAnalysisUpdate` rows (component
∈ `LABOR`/`EMPLOYMENT`/`UNEMPLOYMENT`) now flow through the *existing*
`/releases/processing-status` read model exactly as any Inflation row
does (confirmed in #20D.2). **Question: should `/labor` show its own
"Latest Data Detected"? Frozen answer: YES**, filtered to Employment
Situation's own `release_id` (§4) — this is genuinely different value
from Overview's generic, all-releases version: a reader on `/labor`
specifically wants to know whether Employment Situation's own data has
recently changed, without scanning an unfiltered list that might be
dominated by CPI/PIO activity. Not a duplication of Overview; a
scoped, single-release view of the same underlying facts.

## 6. Frontend files inspected — hidden-Inflation-coupling findings

Two real, concrete drift issues found, both frontend-only (no backend
change implicated):

**(a) `DetectedAnalysisChange.component` is still typed
`ChangeComponent`** (`api/processingStatus.types.ts`) even though the
*backend* widened this field to plain `str` in #20D.2. Today, a
persisted Labor `component: "EMPLOYMENT"` row would type-check (TS
structural typing doesn't reject an unlisted string literal at the
JSON-parse boundary, since there is no runtime validation), but
`CHANGE_COMPONENT_LABELS[change.component]` in
`LatestDataDetected.tsx`'s `AnalysisChangeRow` (a `Record<ChangeComponent,
string>`) would return `undefined` for `"EMPLOYMENT"`, rendering
literally nothing where the component label should be. **Must fix in
#20E.2**: widen the type to `string` and add a fallback/raw-value
lookup, mirroring the backend's own `str`-widening reasoning (§17 of
`labor-release-integration-v1.md`).

**(b) `formatAnalysisValue`'s `field === "state"` branch is
Inflation-only**, unconditionally calling `inflationStateLabelOrRaw`
regardless of which family emitted the event. Several Labor state
values collide harmlessly with Inflation's own label text ("STABLE" →
"Stable", "MIXED" → "Mixed", "COOLING" → "Cooling" — same words, same
result by coincidence) but `EmploymentState`'s `EXPANDING`/
`CONTRACTING`/`RECOVERING` and `UnemploymentTrendState`'s `IMPROVING`/
`DETERIORATING` are NOT in Inflation's label map, so they fall through
to the raw uppercase string (`"EXPANDING"` shown verbatim instead of
title-cased). **Must fix in #20E.2**: make the analysis-change label
lookup component-aware (dispatch on `change.component`, not just
`change.field`), using a new Labor-specific label map for Labor
components.

**(c) Two stale prose strings assume Inflation is the only monitor:**
`CurrentStateSection.tsx`'s footer — *"Inflation is the first fully
deterministic monitor. More are being added as their methodologies are
built."* — and `content/explanations/processingStatus.ts`'s
`TRACKED_ANALYSIS_CHANGE.definition` — *"...one of Economic
Intelligence's own deterministic **Inflation** metrics or
classifications..."*. Both must be updated in #20E.2 (the first
removed/replaced as part of the Current State redesign, §19; the
second made monitor-agnostic).

None of these require a backend change — all three are corrected
frontend interpretation of an *already-correct* backend contract.

## 7. Page information architecture — `/labor`

Not a mechanical clone of `/inflation`. Frozen hierarchy, in the
mission's own required answer order:

```
LABOR
──────────────────────────────────────
1. Current State          -- "What is happening?"
   LaborState badge + short WhyThisState-style explanation
2. Employment              -- one of two owners, WHY #1 is what it is
   EmploymentState (primary) · condition · momentum · key metrics · evidence
3. Unemployment             -- the other owner
   UnemploymentTrendState · key metrics · evidence
4. What Changed             -- "What changed recently?" (month-over-month)
5. Latest Data Detected     -- Employment Situation's own release-processing evidence (§5)
6. Relevant Release         -- "When is the next release?" (upcoming + most recent Employment Situation)
7. Evidence & methodology   -- page-level disclosure (methodology IDs, data basis, comparison contract)
```

Employment and Unemployment are each their own top-level section
(never nested inside "Current State") because each carries its own
evidence, metrics, and explanation surface substantial enough to need
independent visual weight — mirroring how Inflation gives Core PCE
momentum, Target, Confirmation, and Headline Context each their own
section rather than folding them into the hero. "Latest Data Detected"
sits between "What Changed" and "Relevant Release" — chronologically
it's release-processing evidence about the SAME release the calendar
section below it schedules, so placing them adjacent reads naturally
without implying they're the same concept (see §6's terminology
distinction).

## 8. Top-level Current State presentation

Labels are the canonical value, typographically transformed ONLY
(title case), mirroring `inflationStateLabel` exactly:

| Canonical | Displayed |
|---|---|
| `STRENGTHENING` | Strengthening |
| `COOLING` | Cooling |
| `STABLE` | Stable |
| `MIXED` | Mixed |
| `INSUFFICIENT_DATA` | Insufficient data |

**Tone/color decision (frozen, deliberate):** no directional
good/bad or bullish/bearish color-coding. `STRENGTHENING`/`COOLING`/
`STABLE` all render in the SAME `neutral` tone (gray) — text alone
carries the distinction. `MIXED` uses `caution` (amber) — the same
bucket Inflation's own `MIXED` already uses, since both represent a
genuine disagreement/non-clean-classification, not a data problem.
`INSUFFICIENT_DATA` uses `unavailable` (muted gray), matching every
other unavailable value in the product. This deliberately declines to
reuse Inflation's `cool`(blue)/`warm`(orange) buckets for
`STRENGTHENING`/`COOLING` — Inflation's own blue/orange choice is a
temperature metaphor tied to the WORDS "cooling"/"heating", not a
value judgment (more or less inflation is not obviously good or bad);
for Labor, "strengthening" vs. "cooling" IS commonly read as good/bad
by users, so avoiding directional color entirely is the safer,
frozen choice — text does all the work, exactly satisfying "state must
never be communicated only through color" twice over (here, color
communicates nothing beyond neutral/caution/unavailable).

`MIXED` supporting copy must not say "neutral" or "uncertain" — see
§14 for the exact required framing (explicit disagreement, not
ambiguity). No bullish/bearish or investment language anywhere (§32).

## 9. Employment section presentation

Canonical vocabulary (from `app/models/labor.py`, verified, not
assumed): `EmploymentState` (`EXPANDING`/`COOLING`/`STABLE`/
`CONTRACTING`/`RECOVERING`/`INSUFFICIENT_DATA`), `EmploymentCondition`
(`EXPANDING`/`FLAT`/`CONTRACTING`/`INSUFFICIENT_DATA`),
`EmploymentMomentum` (`IMPROVING`/`STEADY`/`WORSENING`/
`INSUFFICIENT_DATA`).

**Frozen hierarchy** — `EmploymentState` is the single primary badge;
condition and momentum are secondary, textual, explaining WHY:

```
Employment
[ EXPANDING ]  <- EmploymentState, primary badge, same visual weight as Current State's own badge minus one size step

Current hiring condition: Expanding
Momentum: Steady

Key metrics: current 3-month average, prior 3-month average, momentum delta
[Evidence disclosure: exact source observations]
```

Condition/momentum render as plain labeled text (not equally-sized
badges) — three co-equal badges was the hypothesis explicitly
rejected: `EmploymentState` is the canonical PRIMARY result (the
value that actually feeds `LaborState`); condition/momentum are
inputs that explain it, and their own visual weight must say so.

## 10. Unemployment section presentation

Canonical vocabulary: `UnemploymentTrendState`
(`IMPROVING`/`DETERIORATING`/`STABLE`/`INSUFFICIENT_DATA`). One
primary badge, key metrics (`current_3m_avg`, `prior_year_3m_avg`,
`delta_pp`), evidence disclosure — same shape as Employment's, one
tier simpler (no condition/momentum split; `UnemploymentTrendState`
IS the whole story for this owner). A short sentence must make the
Employment+Unemployment→LaborState relationship legible, e.g.:
*"Labor combines this unemployment trend with the Employment section
above into one overall Labor state."* — plain description of a
structural fact already true in the backend, never a claim about
which owner "matters more."

## 11. MIXED semantics — verified against the frozen methodology

Per `research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md` §7 (the
agreement table): `MIXED` is the explicit `.get(..., "MIXED")` default
for every `(EmploymentState, UnemploymentTrendState)` pair not one of
the four clean cells — **including every `RECOVERING` pairing by
design** (RECOVERING never resolves to STRENGTHENING). This is
disagreement/non-alignment, not missing data and not genuine
uncertainty about direction. Frozen copy, mirroring Inflation's own
verified "Mixed is a real, distinct classification, not a data gap"
precedent:

> *"Employment and unemployment are not telling a consistent story
> this month — Economic Intelligence classifies that combination as
> Mixed rather than forcing it into Strengthening, Cooling, or Stable."*

The explanation must show BOTH owners' own canonical states side by
side when `LABOR.state === "MIXED"` (contradiction is useful
intelligence — never hidden, per the mission's own explicit
instruction).

## 12. Insufficient-data presentation — three distinct states, frozen

| State | Trigger | Copy |
|---|---|---|
| LOADING | `useApiResource` in-flight | `LoadingSkeleton` (existing component, reused verbatim) |
| ERROR | network/API failure | `ErrorMessage` + retry (existing component, reused verbatim) |
| `INSUFFICIENT_DATA` (canonical) | a successful 200 whose `state` is this value | The real "Insufficient data" label + tone (§8) — never "No change", "Stable", or a silent fallback to a component's own available state |

These three are architecturally guaranteed distinct already —
`useApiResource`'s own type (`ApiResourceState<T>`) makes a successful
200 with `state: "INSUFFICIENT_DATA"` a `{status: "success"}` value,
never conflated with `{status: "error"}` (see §2's own inspection of
`useApiResource.ts`). Component sections (Employment/Unemployment) may
independently show `INSUFFICIENT_DATA` even when the top-level
`LaborState` is a real value or vice versa — each section renders its
OWN canonical `state` field, never inherits or infers from the other's.

## 13. Explanation-content architecture

Extends `content/explanations/` (Increment #17C), a NEW file
`content/explanations/labor.ts`, same `Explanation` shape (§2), same
lookup-by-canonical-value pattern `inflationStateExplanation`
establishes — never a new content type. Required curated entries
(minimum set, per the mission's own list): `LABOR` (what is Labor
Monitor), `EMPLOYMENT` (what is the Employment section), `UNEMPLOYMENT`
(what is the Unemployment trend), and one `Explanation` per value of
`LaborState`, `EmploymentState`, `EmploymentCondition`,
`EmploymentMomentum`, `UnemploymentTrendState` — mirroring
`INFLATION_STATE_EXPLANATIONS`'s exact `Record<Enum, Explanation>`
shape once per enum. Content describes the METHODOLOGY CONCEPTUALLY
(§14's own good/bad example) — the exact `50,000`-job /
`0.2`-percentage-point deadbands may appear only inside a deeper "How
calculated" disclosure sourced from the frozen methodology doc's own
numbers (transcribed once, verified against
`research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md`, never
independently re-derived) — content must never branch on a metric
value to choose which explanation to show; only on the backend's own
already-classified enum value, exactly like `inflationStateExplanation`.

## 14. Evidence hierarchy

Two-tier, mirroring `MomentumMetrics`/`EvidenceDisclosure`'s exact
established pattern (§2):

**Summary tier** (always visible): the three Employment metrics
(current 3M avg, prior 3M avg, momentum delta) and three Unemployment
metrics (current 3M avg, prior-year 3M avg, delta), each in its own
labeled card, formatted per §18/§19.

**Expanded tier** (behind `Disclosure`, per-section): the exact
`observations: LaborObservationEvidence[]` array — series id,
observation date, raw value — plus `methodology_id`/`data_basis`,
mirroring `EvidenceDisclosure.tsx`'s exact field list. No derived
number appears anywhere that isn't already a backend field; formatting
(comma grouping, month names) is the only transformation applied.

## 15. PAYEMS units — confirmed precisely, two different units in one response

Verified directly against `app/models/labor.py` and a live response:
`EmploymentResult.current_3m_avg_jobs`/`prior_3m_avg_jobs`/
`momentum_delta_jobs` are **already converted to actual jobs** (the
`× 1000` conversion is applied exactly once, in
`app.domain.labor.build_jobs_index`, before these fields are ever
computed) — e.g. `-331333.33`, not `-331.33`. **But**
`EmploymentResult.observations[].value` (the raw evidence list) is
**FRED-native "Thousands of Persons", NOT yet converted** — e.g.
`130472.0` meaning 130,472 thousand persons, not 130,472 persons.

**Frozen display rule:** summary-tier metrics (`current_3m_avg_jobs`
etc.) format as a plain comma-grouped integer count of jobs (§18) —
never divided or multiplied. Raw evidence-tier observation values
format as a plain comma-grouped number WITH an explicit "(thousands of
persons)" unit label directly in the evidence table — never silently
multiplied by 1,000 to "match" the summary tier, and never left
unlabeled (a bare `130,472` next to a bare `-331,333` would read as
the same unit and mislead). This asymmetry is real and native to the
backend response, not a frontend inconsistency to paper over.

## 16. Numeric formatting rules

Reuses `lib/format.ts`'s `formatPeriod`/`formatPeriodPair` UNCHANGED
(generic, no Inflation-specific logic). Does **NOT** reuse
`formatPercent`/`formatMetricValueOrUnavailable` for Employment's
job-count fields (those assume a "%"-suffixed rate — wrong unit for a
job count). New functions, in a new `lib/laborFormat.ts` (or added to
`format.ts` if that file's own scope is judged general enough at
implementation time — #20E.2's call, not frozen here):

- `formatJobs(value: number | null): string` — `-331333.33` →
  `"-331,333"` (comma-grouped, rounded to whole jobs — the frozen
  methodology's own precision never implies fractional persons; `null`
  → `"—"`, the existing convention).
- Unemployment's `current_3m_avg`/`prior_year_3m_avg` reuse
  `formatPercent` UNCHANGED (these genuinely are rate percentages,
  e.g. `4.0` → `"4.00%"`).
- `delta_pp` reuses `formatPercentagePoints` UNCHANGED (signed pp
  delta, identical shape to Inflation's own target gap).

Never let formatting imply more precision than the backend's own
value carries; two decimal places for percentages (matching
Inflation's existing convention) and zero decimal places for job
counts (a fractional job has no meaning).

## 17. What Changed hierarchy

Consumes `GET /api/v1/monitors/labor/changes` verbatim — never infers
change from `GET /api/v1/monitors/labor` alone. **Frozen presentation
priority** (backend event order remains canonical; this is a
PRESENTATION-ONLY re-grouping, explicitly documented as such in the
component's own doc comment, mirroring Inflation's own
"component/event-type/field order is canonical, this component only
truncates" precedent from `WhatChangedPreview.tsx`):

1. `LABOR.state` change/availability event (if any) — always the
   headline, when present.
2. `EMPLOYMENT`/`UNEMPLOYMENT` `state` `STATE_CHANGED`/
   `AVAILABILITY_*` events — secondary headline row per section.
3. `condition`/`momentum` `STATE_CHANGED` events — shown, never
   suppressed merely because `EMPLOYMENT.state` also changed (§20).
4. Numeric `METRIC_CHANGED` events — behind a "Metric updates"
   `Disclosure`, secondary tier (§21).

Grouping/ordering/collapsing is allowed; deleting an event from the
inspectable UI, or claiming an event didn't happen, is not — every
event in `changes[]` must be reachable somewhere on the page (the
top-level summary plus each section's own full event list, mirroring
`WhatChangedSection.tsx`'s existing `ChangeEventList` component, which
already renders every event in a section unconditionally).

## 18. Quiet-month copy — zero events

Mirrors Inflation's own precedent exactly (`WhatChangedSection`'s "No
canonical changes detected" / `WhatChangedPreview`'s "No canonical...
changes were reported for this comparison"), never "Labor remained
stable" (§ mission's own explicit prohibition — absence of an event is
not itself proof of "no change" beyond what the comparison contract
checked). Frozen: **"No canonical Labor changes were reported for this
comparison."**

## 19. Availability-event copy

`AVAILABILITY_LOST`/`AVAILABILITY_RESTORED` render as availability
facts, never economic direction:

- Lost: *"`{Component}` analysis became unavailable."*
- Restored: *"`{Component}` analysis became available."*

Never "improved"/"worsened"/"declined". `{Component}` uses the
existing title-cased component label (LABOR/Employment/Unemployment).

## 20. Condition/momentum event copy

Rendered as their own readable sentences, independently, never
suppressed by a co-occurring `EMPLOYMENT.state` event (the exact
reason #20C.2 emits them independently — §6 of
`LABOR_WHAT_CHANGED_V1_FROZEN_METHODOLOGY.md`): *"Employment condition
changed from `{prev}` to `{curr}`."* / *"Employment momentum changed
from `{prev}` to `{curr}`."* Grouping both under one "Employment"
subsection heading (visually) is allowed; textually collapsing them
into one sentence or dropping either because the other also fired is
not.

## 21. Numeric `METRIC_CHANGED` presentation

Behind a secondary "Metric updates" `Disclosure` per section (§17,
tier 4) — never inline with equal visual weight to a state change, so
a quiet month that happens to cross a float-inequality boundary
(exact-inequality per #20C.2's own frozen rule) doesn't visually read
as dramatic as a real state transition. Every numeric event remains
fully inspectable inside that disclosure, formatted per §16 (job
counts vs. percentage points, field-aware — never blanket
`formatPercent`).

## 22. Monthly vs. release-processing — the distinction, frozen exactly

**"What Changed" (`/monitors/labor/changes`)** = canonical month `t`
vs. exact calendar month `t-1`, a stable economic comparison.
**"Latest Data Detected"** = persisted data/analysis changes detected
during ONE release-processing run's before/after comparison at the
SAME evaluation period (§14 of `labor-release-integration-v1.md`) —
an entirely different comparison axis (same period, before/after a
write) that happens to also use `labor_what_changed_v1.0`'s comparator
under the hood, which is an implementation detail the UI never
surfaces as if it were the same feature. These render as two visually
and textually SEPARATE sections (§7, positions 4 and 5) — never
merged into one feed, never cross-referenced with causal language (no
*"Employment Situation caused Labor to cool"* — §6's own explicit
prohibition, mirrored from `labor-release-integration-v1.md` §18's
identical rule).

## 23. Latest Data Detected — decision and behavior

Frozen YES (§5). Reuses `components/overview/LatestDataDetected.tsx`'s
existing sub-components (`ObservationChangeRow`, `AnalysisChangeRow`)
UNCHANGED after the §6 fixes land (component-aware labeling)  —
composed with a NEW top-level wrapper scoped to one release (Employment
Situation only, via the `release_id` filter, §4) rather than
`selectLatestDataDetectedItem`'s "pick one interesting item from a
mixed list" logic (which exists specifically because Overview's
version has no natural single subject — `/labor`'s version always has
exactly one release in scope, so that selection logic doesn't apply
here and must not be reused/duplicated for a single-item list).

## 24. Relevant release presentation

Shows the next scheduled AND most recent Employment Situation
occurrence (both, when available) — filtered client-side from the
already-fetched Upcoming/Recent arrays (§4) by `provider_release_id
=== "50"`. Reuses `ReleaseRow.tsx` + `ScheduleStatusBadge.tsx`
UNCHANGED (already fully generic over `ReleaseOccurrenceItem`, §2).
Mandatory disclosure: `ReleaseScheduleDisclosure` component, reused
verbatim — **verified exact current text, byte-identical to what the
mission quoted**: *"Release dates indicate scheduled publication
dates. They do not confirm that new data has been published, ingested,
or reflected in Economic Intelligence analysis."*

## 25. Latest-revised disclosure

Reuses `DataBasisNote`/`LATEST_REVISED_DATA` (content/explanations/inflation.ts)
**verbatim for the sentence itself** (it is genuinely monitor-agnostic
prose — "Historical calculations use the latest revised observations
available to Economic Intelligence" — true of Labor too, not an
Inflation-specific claim) — no fork, no duplicate copy. Appears once,
page-level, in the Labor page header (mirroring `/inflation`'s own
placement exactly).

## 26. Payroll benchmark-revision disclosure

Audited: `LABOR_V1_FROZEN_METHODOLOGY.md` does **not** define a
distinct "payroll benchmark revision" caveat sentence of its own
beyond the general latest-revised-data principle (§25) and the
affected-horizon mechanics already covered by evidence/methodology
disclosure (§14/§27) — there is no separate frozen sentence to
transcribe. **Frozen resolution:** no additional disclosure text is
invented here; if a future increment's methodology work adds one, it
must be sourced from that frozen document at that time, never
authored ad hoc in the frontend.

## 27. Provenance/source presentation

Page-level `Disclosure` (mirroring `MethodologyDisclosure.tsx`
exactly): `methodology_id` (`labor_v1.0`), `data_basis`,
`comparison_contract_id`/`comparison_type` (from the changes
endpoint), `evaluation_period`. Per-metric evidence disclosures (§14)
carry the same `methodology_id`/`data_basis` fields the backend
already returns on each `EmploymentResult`/`UnemploymentResult` — no
new provenance field is invented; every value shown already exists in
the response.

## 28. Chart decision — deferred

**Frozen: no chart in #20E.2.** Confirmed: no chart library exists
anywhere in `frontend/package.json` today, and `/inflation` — the more
mature, longer-lived page — has zero charts despite having comparably
rich time-series-shaped data (r_3m/r_6m/r_12m, target gap) available
the entire time. A single current-period snapshot plus 7/6-month
evidence windows (Employment/Unemployment's own `observations`
arrays) is not a meaningful time series to chart on its own — a real
historical Labor chart would need the generic `GET
/api/v1/series/{id}/observations` endpoint queried separately per
series, a genuinely new integration this increment's own scope
excludes ("no new economic API," and charting infrastructure itself
would be new product-wide infrastructure, not a Labor-specific need).
Revisit only as a deliberate, product-wide charting decision, not as a
Labor-specific addition.

## 29. Overview — Current State design

```
Current State
─────────────────────────────
Inflation
[ MIXED ]
short explanation (reuses WhyThisState's own compact form)
View Inflation →

Labor
[ COOLING ]
short explanation
View Labor →
```

Two peer subsections, same visual treatment, same badge size,
stacked vertically (not side-by-side columns at narrow widths —
responsive: stacks on mobile, may sit side-by-side on wide viewports
if `CurrentStateSection`'s own existing single-column layout is judged
too cramped at implementation time; not frozen as a hard two-column
requirement, since the CURRENT single-domain version is already
single-column and #20E.2 may reasonably keep that same stacking for
consistency — implementation's call). Order: Inflation first, Labor
second (existing product order — Inflation shipped first; not a
statement about relative importance). The stale "Inflation is the
first fully deterministic monitor..." sentence (§6c) is REMOVED, not
merely edited — there is no natural monitor-count sentence to replace
it with that wouldn't itself go stale again at the third monitor; #19A
and #20B's own "no premature generic framework" precedent argues
against inventing one now.

**No aggregate "Economy State".** Two independent state values,
rendered independently — never averaged, scored, or combined into a
synthetic economy-wide read (mission's own explicit, absolute
prohibition, restated here as frozen).

## 30. Overview — What Changed design

**Frozen: Option A, separate domain cards** — never one combined
chronological feed (Option B rejected: Inflation's and Labor's
comparisons are each a stable, independently-anchored monthly
comparison, not timestamped news events; merging them chronologically
would misrepresent them as a stream). Structure:

```
What Changed
─────────────────────────────
Inflation
  [existing WhatChangedPreview.tsx output, unchanged]
  See full comparison →

Labor
  [new LaborWhatChangedPreview.tsx, same MAX_EVENTS-truncation pattern]
  See full comparison →
```

New `components/overview/LaborWhatChangedPreview.tsx`, mirroring
`WhatChangedPreview.tsx`'s exact shape (truncate the backend's own
ordered `changes[]` to `MAX_EVENTS`, never reorder/filter-by-importance,
same quiet-month copy per §18) — a new, separate component, not a
generalized/parameterized version of the Inflation one (mirrors this
project's own repeated "no premature generic framework" choice at the
monitor layer, applied here to the preview-component layer too).

## 31. Overview — Latest Data Detected behavior

Audited: `LatestDataDetected.tsx`/`fetchReleaseProcessingStatus()`
(no params, default page) are ALREADY fully generic — once §6's two
fixes land, Employment Situation's own detected changes will appear in
Overview's existing "Latest Data Detected" section automatically,
selected by `selectLatestDataDetectedItem`'s existing logic, with
**zero Labor-specific code added to this Overview component**. No
causal wording exists there today and none is added.

## 32. Overview — Releases behavior

Audited: `UpcomingReleasesPreview`/`RecentReleasePreview` +
`fetchUpcomingReleases`/`fetchRecentReleases` already return every
active curated release, Employment Situation included (it was already
in the curated catalog before #20D — only its SERIES mapping was new).
**No change needed** — Employment Situation already appears in
Overview's Releases section today, unmodified.

## 33. Navigation

`AppShell.tsx`'s `NAV_LINKS` gains exactly one entry: `{ to: "/labor",
label: "Labor" }`, inserted between Inflation and Releases:

```
Overview · Inflation · Labor · Releases
```

No placeholder items for Growth/Housing/other future domains (mission's
own explicit prohibition).

## 34. Routing

`App.tsx` gains exactly one route: `<Route path="labor"
element={<LaborPage />} />`. No query parameters. No `/labor/employment`
or `/labor/unemployment` sub-routes — one coherent page with internal
`Disclosure`-based progressive disclosure, exactly matching
`/inflation`'s own single-page-many-sections shape.

## 35. Frontend API typing plan

New `api/labor.types.ts` — field-for-field TypeScript mirror of
§3's exact confirmed shapes (`LaborMonitorResult`, `EmploymentResult`,
`UnemploymentResult`, `LaborObservationEvidence`,
`LaborWhatChangedResult`, `EmploymentSectionChanges`,
`UnemploymentSectionChanges`, `LaborChangeEvent`), built the same way
`inflation.types.ts`/`releases.types.ts` were (direct inspection of
the actual Pydantic models + a live response, never inferred). New
literal union types (`LaborState`, `EmploymentState`,
`EmploymentCondition`, `EmploymentMomentum`, `UnemploymentTrendState`,
`LaborChangeComponent`, using the SAME string values as the backend
enums, verified against §3/§9/§10) — no `any`, no frontend-only
economic states, no divergent vocabulary. New `api/labor.ts` —
`getLaborMonitor()`/`getLaborWhatChanged()`, mirroring `api/inflation.ts`'s
exact two-function shape. `api/processingStatus.ts` gains one optional
parameter (`releaseId?: number`, forwarded as `release_id`) for §23's
scoped fetch — the existing zero-arg call from Overview is unaffected
(optional parameter, backward compatible).

## 36. Labor page resource boundaries

Five independent `useApiResource` calls, mirroring `/inflation`'s
two-resource and `/`'s five-resource precedent exactly: `getLaborMonitor`,
`getLaborWhatChanged`, `fetchUpcomingReleases`/`fetchRecentReleases`
(reused, filtered client-side per §24), and
`fetchReleaseProcessingStatus(releaseId)` (§23). Each section renders
its own loading/error/success branch independently — Employment/
Unemployment sections render FROM the monitor resource's own success
branch (they are sub-views of one response, not independent fetches —
mirroring how `MomentumMetrics`/`TargetPanel`/`ConfirmationPanel` all
render from `/inflation`'s single `monitor` resource today).

## 37. Overview resource boundaries

Two new independent resources added to Overview's existing five:
`getLaborMonitor`, `getLaborWhatChanged` (Latest Data Detected and
Releases are unchanged — §31/§32). Total seven independent
`useApiResource` calls. Inflation's monitor/changes failing must not
hide Labor's, and vice versa — each of the seven renders its own
loading/error/success UI inline, exactly the existing pattern.

## 38. Failure isolation — frozen behavior table

| Resource fails | What stays visible |
|---|---|
| Labor monitor | Everything else on `/labor` (What Changed, Latest Data Detected, Releases, page header) |
| Labor changes | Current State, Employment, Unemployment (all monitor-resource-derived), Latest Data Detected, Releases |
| Inflation monitor (Overview) | Labor's Current State, both What Changed cards, Latest Data Detected, Releases |
| Inflation changes (Overview) | Everything else, including Labor's own What Changed card |
| Labor monitor (Overview) | Inflation's Current State, both What Changed cards, Latest Data Detected, Releases |
| Labor changes (Overview) | Everything else |
| Releases (either page) | Both state/changes sections remain visible |
| Processing status (either page) | Both state/changes sections and Releases remain visible |

No `Promise.all`, no aggregate endpoint, no page-wide error boundary
that blanks unrelated sections — mirrors the existing, already-audited
Overview precedent exactly (§2).

## 39. Accessibility

Reuses `Disclosure`/`ExplanationTrigger`'s existing native
`<details>/<summary>` foundation UNCHANGED (already keyboard-accessible,
already exposes `aria-expanded` natively, already degrades without
JS). `Badge` is already text-first (§8's tone decision reinforces
this further — Labor adds no color-only signal at all beyond
`caution`/`unavailable`, both already paired with distinct text).
Section headings use `aria-labelledby` + a matching heading id,
mirroring every existing section in the codebase exactly (§2's
inspection found zero deviations from this pattern to reconcile).

## 40. Trust labeling

No "AI" badge (none exists on Inflation either, and no AI touches this
page). Reuses the existing implicit trust vocabulary verbatim —
"Methodology", "Evidence", section headers phrased as plain nouns, no
"Generated by..." framing anywhere. No new labeling scheme invented;
Inflation's own precedent (§2) already establishes what "this is
canonical, not generated" looks like in this product, and Labor
follows it exactly.

## 41. Backend-change requirement

**ZERO backend production changes required.** Every presentation need
identified above is satisfiable from the existing, already-confirmed
(§3/§4) response contracts. The one near-miss — filtering
processing-status to one release — is already supported by an existing
query parameter (§4), not a gap.

## 42. #20E.2 implementation scope (complete list)

1. `frontend/src/api/labor.types.ts` (new) — §35.
2. `frontend/src/api/labor.ts` (new) — §35.
3. `frontend/src/api/processingStatus.ts` — add optional `releaseId` param — §35.
4. `frontend/src/api/processingStatus.types.ts` — widen
   `DetectedAnalysisChange.component` to `string` — §6a.
5. `frontend/src/lib/laborLabels.ts` (new) — Labor state/tone/component/field label maps, mirroring `inflationLabels.ts` — §8/§9/§10/§17.
6. `frontend/src/lib/laborFormat.ts` (new, or added to `format.ts`) — `formatJobs` — §16.
7. `frontend/src/lib/detectedChangeFormat.ts` — make `formatAnalysisValue`'s "state" branch component-aware — §6b.
8. `frontend/src/lib/inflationLabels.ts` (or a shared home) — fix `CHANGE_COMPONENT_LABELS[change.component]` lookup to handle a non-Inflation component with a raw fallback — §6a.
9. `frontend/src/content/explanations/labor.ts` (new) — §13.
10. `frontend/src/content/explanations/processingStatus.ts` — make `TRACKED_ANALYSIS_CHANGE` monitor-agnostic — §6c.
11. New components: `components/labor/Badge.tsx` (or reuse the existing generic one — implementation's call), `LaborHero.tsx`/`CurrentState`, `EmploymentSection.tsx`, `UnemploymentSection.tsx`, `WhatChangedSection.tsx`, `EvidenceDisclosure.tsx` (Labor-specific, mirroring the Inflation one's shape), `MethodologyDisclosure.tsx` (Labor-specific), `LatestDataDetected.tsx` (Labor-scoped, single-release — §23), `RelevantRelease.tsx` — §7-27.
12. `components/overview/CurrentStateSection.tsx` — restructure into two peer subsections, remove the stale monitor-count sentence — §6c/§29.
13. `components/overview/LaborWhatChangedPreview.tsx` (new) — §30.
14. `pages/Overview.tsx` — add two resources, restructure Current State and What Changed sections — §29/§30/§37.
15. `pages/Labor.tsx` (new) — §7/§36.
16. `layouts/AppShell.tsx` — add nav entry — §33.
17. `App.tsx` — add route — §34.
18. `test/no-economic-logic.test.ts` — extend `FORBIDDEN_PATTERNS` with Labor's own `50_000`/`0.2` deadband literals and any Labor-specific formula shape, mirroring the backend's own AST-level guard — §2's own architecture-guard discipline.

No backend file touched.

## 43. #20E.2 test matrix (frozen)

**Routing/nav:** `/labor` renders; nav item present and active on
`/labor`; existing routes (`/`, `/inflation`, `/releases`, unknown)
unchanged.

**Current State:** every `LaborState` value renders its correct label/
tone/copy; backend value controls display with zero frontend branching
on a metric; `INSUFFICIENT_DATA` never reads as "no change"/"stable".

**Employment:** every `EmploymentState` value; condition/momentum
render as secondary text, never equal-weight badges; insufficient-data
per-section independent of top-level state; exact evidence values;
correct job-count formatting (no ×1000/÷1000 drift, §15); period
display.

**Unemployment:** every `UnemploymentTrendState` value; evidence;
insufficient-data independence; percentage formatting (not job-count
formatting).

**Why This State:** each top-level `LaborState`, including MIXED
showing both owners' contradictory states side by side; backend state
controls the explanation; no metric-threshold branch anywhere in the
component.

**What Changed:** one test per event shape (top-level state,
Employment state, condition, momentum, Unemployment state,
availability lost, availability restored, numeric metric, multiple
simultaneous events, zero events); presentation grouping verified
against §17's frozen priority; every backend event remains inspectable
somewhere on the page; a test asserting frontend ordering does not
alter backend `changes[]` order.

**Release/processing:** Employment Situation's own upcoming/recent
occurrence renders via the reused `ReleaseRow`; mandatory disclosure
byte-identical (§24); Latest Data Detected scoped to one release, no
`selectLatestDataDetectedItem` reuse; no causal wording anywhere;
`schedule_status` (SCHEDULED/PAST_DUE) never conflated with
processing status or `LaborState`.

**Disclosures:** latest-revised note present and reuses the shared
sentence verbatim; methodology IDs/data-basis/comparison-contract
values match the live response exactly.

**Failures:** each of the five/seven resources (§38) fails
independently; the failure table's own "what stays visible" column is
directly tested.

**Overview:** Inflation+Labor Current State both render independently;
one monitor failing doesn't hide the other; both What Changed cards
render independently; one changes endpoint failing doesn't hide the
other; Latest Data Detected naturally includes Employment Situation
once §6a/§6b land; Releases naturally includes it (already true, §32);
no aggregate score/state anywhere; both "View X"/"See full comparison"
links resolve to the correct route.

**Architecture:** `no-economic-logic.test.ts` (extended, §42.18)
scans every new Labor file and finds no `50_000`/`0.2` literal, no
condition/momentum/agreement-table reimplementation; no AI import
anywhere in the new files; no backend production file appears in the
diff; no new economic API call exists beyond `getLaborMonitor`/
`getLaborWhatChanged`/the existing `releases`/`processingStatus`
callers; no `JTS*`/`CIVPART` string anywhere; no investment-advice
phrase (a small forbidden-phrase list: "buy", "sell", "invest in",
mirroring the spirit of the existing formula-pattern guard).

**Regression:** all 487 existing frontend tests pass unmodified except
the two deliberately-updated files (§6a/§6c); full frontend suite; full
backend suite (expected unchanged, since no backend file is touched).

## 44. GO / STOP criteria — all resolved

All 26 items in the mission's own checklist are resolved above (§3–§41
directly map to items 1–25; item 26, the test matrix, is §43). No
item required a STOP: no frontend economics were required anywhere,
every backend contract already supports the frozen design (§41), and
no product semantic remained ambiguous after inspection (MIXED,
availability, monthly-vs-release, units, and the Overview aggregate-
score prohibition were the four highest-risk ambiguities, all resolved
with verified, sourced answers above).

## 45. Deferred (explicitly, not build here)

Charts (§28). A shared cross-monitor `Badge`/label abstraction (two
monitors don't yet justify one, per this project's own repeated
precedent — a third would be the trigger to reconsider, mirroring
`labor-release-integration-v1.md` §24's identical reasoning one layer
up). A payroll-benchmark-revision-specific disclosure sentence (§26 —
none exists in the frozen methodology to transcribe; inventing one now
would not be sourced). Any `/labor/employment` or `/labor/unemployment`
sub-route. Any Growth/Housing/JOLTS/CIVPART nav placeholder.


---

## Addendum (#44): a page-level footer beneath the frozen hierarchy

The **seven monitor sections frozen in §7 are unchanged** — same sections, same order, same components.

Increment #44 appended one page-level section *after* "Evidence & methodology":

**"Understand this"** — a short list of curated explainer questions linking to `/explain/:slug`.

It sits outside the monitor hierarchy deliberately: it is not an economic reading, it renders no canonical value, and it comes after the evidence rather than before it. The Jobs page remains an intelligence product; the explainers are an offer at the end of it, not a syllabus in the middle.

Recorded here rather than silently changing the frozen list.
