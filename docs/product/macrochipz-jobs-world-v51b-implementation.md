# Jobs World #51B — implementation notes and deviations

**Increment #51B.** The #51A prototype, in production.
**Date:** 2026-09-24
**Audit:** `macrochipz-jobs-world-v51a-audit.md`
**Specification:** `macrochipz-jobs-world-v51a-spec.md`

Preserved untouched: `labor_v1.0`, every state, condition, momentum, deadband,
3-month average, delta, observation, revision note and unavailable state. No
dependency added, no backend change, **no canonical classification recalculated
in the frontend**.

---

## 1. What shipped

### 1.1 The two-survey threshold

`components/labor/SurveyThreshold.tsx`. A switch between the employer and
household surveys; for the selected one, an axis centred on *no change*, the
methodology's own deadband shaded around it, and the measure's own change
plotted as a point.

Live: payroll employment sits **outside** its band at −70,333 jobs a month →
`Cooling`. Unemployment sits **inside** its band at −0.10 pp → `Stable`. Same
diagram, two verdicts.

Beneath each, the survey's own published series as context — 60 monthly
observations from `GET /api/v1/series/{id}/observations`, an endpoint that
already existed and that this world had never called.

### 1.2 Refinement 1 — the disagreement in plain English, `Mixed` retained

"What MacroChipz concludes" opens with: *"The two surveys are pointing different
ways this month. Payroll employment is Cooling and the unemployment trend is
Stable. Neither is overridden and no average is taken between them."*

`LaborHero` and its formal `Mixed` badge render **inside** that section,
unchanged. The plain sentence introduces the classification; it does not
replace it.

### 1.3 Refinement 2 — a consumer-readable band with the exact threshold

> The shaded band is what labor_v1.0 treats as no meaningful move — anything
> within **50,000 jobs a month** either way counts as no real change.

and

> …anything within **0.2 percentage points** either way counts as no real
> change.

Both are rendered from `momentum_deadband_jobs` and `unemployment_deadband_pp`,
which were in the response and had never been shown. The same threshold appears
in the chart's accessible label alongside the verdict.

### 1.4 Refinement 3 — gaps excluded, broken and disclosed

`UNRATE` carries a published gap. The axis domain is computed from **real values
only** (`observations.filter(o => o.value !== null)`), the path is emitted as
one segment per run so the line **breaks** at the gap, and the gap is disclosed
twice: as the words "1 month not published" beside the series, and inside the
chart's `aria-label`.

Verified in production: the unemployment series renders **2 path segments**, the
payroll series **1**.

### 1.5 Progressive disclosure, nothing deleted

| Behind a disclosure | Was |
|---|---|
| `EmploymentSection` + `UnemploymentSection` in full | Two full-width sections, ~1,230px on a phone |
| `IntelligenceHistorySection` | 1,413px — 31% of the phone page |

Both are complete and unsummarised, one tap away. `WhatChangedSection`,
`LatestDataDetected`, `RelevantRelease`, `MethodologyDisclosure`,
`AskMacroChipz`, `UnderstandWorld` and the revisions link all stay where they
were.

### 1.6 What this page does not have

New section. Job openings, participation, the broader underemployment rate and
new claims are **not available from this API** — all 404 — so the page says so,
and carries the reviewed sentence *"This is why the rate alone does not tell you
whether the jobs picture improved."* **No claim is made that this page measures
job-search difficulty.**

---

## 2. Measured

Genuine CSS viewports, dark theme, live local API.

| | 390 | 440 | 768 | 1024 | 1440 |
|---|---|---|---|---|---|
| Document height | **3,725** | 3,528 | 3,171 | 3,173 | 3,175 |
| *Before #51B* | *4,632* | *4,271* | *3,340* | *3,342* | *3,344* |
| Horizontal overflow | 0 | 0 | 0 | 0 | 0 |
| Text clipped | 0 | 0 | 0 | 0 | 0 |
| **Controls under 44px** | **0** | **0** | **0** | **0** | **0** |
| *Before #51B* | *1* | *1* | *1* | *1* | *1* |
| **Charts** | **2** | 2 | 2 | 2 | 2 |
| *Before #51B* | *0* | *0* | *0* | *0* | *0* |

Mobile falls **20%**, desktop **5%**.

**Interaction:** both surveys switch, focus retained on the control, exactly one
selected, each explaining its own classification from the backend's own numbers.
**Themes:** identical light and dark; lowest measured contrast 6.72:1.
**Motion:** all 22 animated elements carry `motion-reduce`.
**Live region:** the panel is `aria-live="polite"`.

### 2.1 Independent failure states, verified in the browser

Produced by patching `window.fetch` at runtime and navigating client-side — no
application code changed to produce them.

| Failure | Result |
|---|---|
| `PAYEMS` series only | Classification still renders from the monitor; an explicit sentence replaces the series; the **other survey still works**; all 14 sections present |
| `/monitors/labor` | "Jobs data could not be loaded." + Retry; the threshold panel correctly absent; What changed, Latest data detected, the release, history and Ask all still render |
| `/monitors/labor` slow | Skeleton labelled "Loading the two surveys"; no figure in that section |
| A classification not computed | "…has not been computed for this period… Nothing is estimated in its place", including when the reader selects it deliberately |

---

## 3. Deviations from the prototype

| | Prototype | Shipped | Why |
|---|---|---|---|
| Overall conclusion | Bespoke chip + sentence | Plain sentence **plus** `LaborHero` unchanged | The real component carries state duration and the "Why {state}?" disclosure, which the prototype's chip dropped. |
| Band label | "the momentum deadband ±50,000 jobs" | "anything within 50,000 jobs a month either way counts as no real change" | Refinement 2 asked for consumer-readable. |
| Recorded states | 12 coloured bars | `IntelligenceHistorySection`, collapsed | The real component carries replay outcomes. |
| Each survey's detail | Not present | `EmploymentSection` + `UnemploymentSection`, collapsed | Preserve, do not delete. |

---

## 4. Files changed

**New:** `components/labor/SurveyThreshold.tsx` (+ test, 11 cases),
`buildPayrollObservations` / `buildUnemploymentObservations` fixtures.

**Modified:** `pages/Jobs.tsx` (+ test), `api/series.ts` (two named series
accessors on the existing client), `layouts/pageSurface.ts` (+ test),
`App.test.tsx`.

**Not touched:** every `api/labor*`, `labor_v1.0` behaviour, `LaborHero`,
`EmploymentSection`, `UnemploymentSection`, `TwoSurveysNote`,
`WhatChangedSection`, `LatestDataDetected`, `RelevantRelease`,
`MethodologyDisclosure`, `IntelligenceHistorySection`.

**Tests:** 1,997 passing across 84 files. Typecheck, lint and production build
clean.
