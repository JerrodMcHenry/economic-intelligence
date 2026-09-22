# The Housing World

**Increment #45.** MacroChipz's fourth economic world, and the first with **no methodology behind it**.

This document records what Housing is, what it deliberately is not, and the three decisions that shaped it: a world without a state, two units for every measure, and an initial import that must not look like history MacroChipz watched.

---

## 1. The question Housing answers

> **Are more homes entering the construction pipeline?**

Narrow on purpose. It is answerable from three Census measures with no methodology, no threshold and no judgement — which is exactly what MacroChipz can support today.

It is **not** "how is the housing market?". That question needs prices, sales, inventory and affordability, and MacroChipz has none of them. Asking it and answering with construction data would be answering a different question in a confident voice.

---

## 2. There is no `housing_v1.0`

Inflation, Jobs and Rates each render a conclusion a frozen methodology reached. Housing renders none.

`macrochipz-2.0-implementation-sequence.md` names five prerequisites for a legitimate Housing state:

1. a defensible state vocabulary grounded in housing economics rather than chosen for visual symmetry;
2. sufficient history for any historical-position claim;
3. a published methodology document;
4. golden vectors;
5. a defensible answer to what "housing is cooling" means when permits, starts, completions and rates can move in opposite directions at the same time.

**Until all five exist, Housing has no state.** #45 met none of them and invented none.

What Housing publishes instead is arithmetic nobody can disagree with: a latest value, the value before it, the value twelve months earlier, and the differences. **A descriptive change is not a state.** "Permits are 2.7% below last month" is a fact about two numbers; "housing is cooling" is a conclusion MacroChipz is not entitled to reach.

### What enforces this

Not discipline — tests. `tests/test_housing_architecture.py` fails on a state word declared or used as a value anywhere in the Housing modules, on any identifier containing `score`/`weight`/`rank`/`composite`, on a `state`-shaped field appearing in the response contract, on a `METHODOLOGY_ID` constant existing, and on a `docs/methodology/housing-*.md` file existing at all. `frontend/src/test/no-housing-derivation.test.ts` does the same for the UI.

### No significance test either

Census publishes 90-percent confidence intervals for the changes in its own release — *"If a range does not contain zero, the change is statistically significant. If it does contain zero, the change is not statistically significant; that is, it is uncertain whether there was an increase or decrease."* Those intervals are computed from sampling variances the API does not expose. Reconstructing them would be inventing statistics; asserting a change is meaningful without them would be worse.

So MacroChipz reports the change and **quotes Census's own guidance** instead: month-to-month movements in these figures are often irregular, and establishing an underlying trend may take three months for permits and six for starts and completions. That sentence is a canonical limitation on the response, not presentation copy.

---

## 3. Source and semantics

**Provider:** U.S. Census Bureau Data API, `timeseries/eits/resconst` (New Residential Construction). Jointly announced by the Census Bureau and the U.S. Department of Housing and Urban Development. Admitted to the #28 allow-list on 2026-09-21 — see §11A of `macrochipz-product-discovery-data-feasibility-v1.md` for the licensing record and the mandatory attribution.

Every semantic below was verified against Census's own documentation and the live dataset. **None was inferred from a code name.**

| Census category | Adjustment | Unit | Coverage | MacroChipz concept |
|---|---|---|---|---|
| `APERMITS` | Seasonally adjusted, annual rate | Thousands of units | 1960-01 → | `us.housing.units-authorized.saar.monthly` |
| `ASTARTS` | Seasonally adjusted, annual rate | Thousands of units | 1959-01 → | `us.housing.units-started.saar.monthly` |
| `ACOMPLETIONS` | Seasonally adjusted, annual rate | Thousands of units | 1968-01 → | `us.housing.units-completed.saar.monthly` |
| `PERMITS` | Not adjusted, month's own count | Thousands of units | 1959-01 → | `us.housing.units-authorized.nsa.monthly` |
| `STARTS` | Not adjusted, month's own count | Thousands of units | 1959-01 → | `us.housing.units-started.nsa.monthly` |
| `COMPLETIONS` | Not adjusted, month's own count | Thousands of units | 1968-01 → | `us.housing.units-completed.nsa.monthly` |

`data_type_code` is `TOTAL` throughout. The single-family and multi-family breakdowns Census also publishes are **not ingested**, and neither are `UNDERCONST` (units under construction) or `AUTHNOTSTD` (authorised but not started) — all real, all outside #45's scope.

**Census's own definitions**, which is what `equivalence_basis` on each binding records:

- A permit is *"the approval given by a local jurisdiction to proceed on a construction project."*
- *"Start of construction occurs when excavation begins for the footings or foundation of a building."*
- *"A house is defined as completed when all finished flooring has been installed."* In buildings of two or more units, all units count as completed *"when 50 percent or more of the units are occupied or available for occupancy."*
- *"These statistics only include privately-owned buildings. Publicly-owned housing units are excluded."*

**Two source programs, two reliability regimes.** Permits come from the Building Permits Survey; starts and completions from the Survey of Construction. Census's release states the consequence plainly: permit statistics are *"based on a non-probability sample and not subject to sampling error"*, while starts and completions *"are estimated from sample surveys and are subject to sampling variability."* The registry records this as different `source_program` values — the same reasoning that keeps CES and CPS apart for Jobs — and it is why `APERMITS` has no error rows in the dataset while `ASTARTS` does.

**The grain is unique.** `(category_code, data_type_code, seasonally_adj, time)` had zero duplicates across all 26,773 rows of the full history. `program_code` is always `RESCONST`, `geo_level_code` always `US`, `time_slot_id` always `0`. The adapter validates all three rather than assuming them.

---

## 4. Two units, and the trap they exist to avoid

Census publishes each stage twice, and conflating the two is the single most likely way to publish a false number in this world.

- **Pace** — the seasonally adjusted **annual rate**. Census defines it as *"the seasonally adjusted monthly value multiplied by 12"* and states it *"is neither a forecast nor a projection; rather it is a description of the rate ... in the particular month for which they are calculated."* The only form in which one month is comparable with another, because construction is heavily seasonal and **Census publishes no seasonally adjusted monthly level at all**.
- **Actual** — the month's own unadjusted count.

### Three rules, all tested

1. **An annual rate is never presented as homes built in a month.**
2. **An annual rate is never divided by twelve and called monthly production.** 1,394,000 ÷ 12 = 116,167; the real unadjusted August 2026 figure is 117,400. Close enough to look right, wrong on principle — the seasonal adjustment that produced the annual rate is exactly what the division throws away.
3. **An unadjusted count is never multiplied by twelve** to manufacture an annual rate. MacroChipz has no seasonal adjustment of its own.

Rules 2 and 3 are enforced by AST inspection on the backend and regex on the frontend: no Housing module may contain a division or multiplication by twelve.

**Carrying both units is what lets the product *show* the distinction rather than assert it.** The page puts 117,400 directly beneath 1,394,000, and the `saar-housing` explainer uses the same pair.

They are separate concepts, not two views of one, because `seasonal_adjustment` and `canonical_unit` genuinely differ — and #38's registry exists precisely so that a seasonally adjusted value can never be silently substituted for an unadjusted one.

---

## 5. Concept identity (#38)

```
concept  →  binding  →  Census
us.housing.units-authorized.saar.monthly  →  CENSUS APERMITS/TOTAL  →  api.census.gov
```

- **Concepts are source-neutral.** No Census code appears in the registry, in `app/domain/`, in the read service or in any presentation module. A test scans every domain module's non-docstring string literals for `APERMITS`, `RESCONST` and their siblings.
- **Census's vocabulary lives in two places only:** `ProviderBinding.provider_series_id` and `observation_provenance.source_series_field`. The API surfaces the latter as `provenance.provider_series_id`, so a reader verifying a number sees both MacroChipz's concept id and Census's own identifier side by side.
- **`storage_series_id == concept_id`.** A provider added after #38 has no legacy rows to preserve, so Housing stores MacroChipz's own identity from the first write and does not extend the FRED/Treasury asymmetry documented in `economic-concept-identity.md` §6 to a third shape.
- **The unit conversion belongs to the binding.** `canonical_unit_factor = 1000.0`, from Census's "Thousands of Units" — the same pattern `PAYEMS` already uses for FRED's "Thousands of Persons".
- **Equivalence is asserted from Census's definitions, not from names.** No frozen methodology cites these series, so the usual basis ("the methodology already uses it for that role") was unavailable. Each binding's `equivalence_basis` instead quotes the definition and cites the published figure it was verified against.

---

## 6. Ingestion, and the baseline decision

Housing reuses `economic_series`, `economic_observations`, `observation_provenance` and `observation_versions` **unchanged**. The only new table is `housing_ingestion_runs`, an attempt audit. Nothing about Housing's history is Housing-specific, which is what lets point-in-time replay (#31) and Revision Intelligence (#43) work for Housing without knowing Housing exists.

### The decision with no precedent in this codebase

A first import of a new source is **not** a history of observed events. MacroChipz learns sixty-seven years of published values at one instant; it watched none of them arrive and cannot say what Census had published for those months at any earlier time. Recording them as observed would manufacture exactly the revision history #43 exists to refuse — at a scale larger than everything else in the database combined.

So it is decided **per observation**, by a pure function (`app.domain.housing.is_baseline_import`):

| Situation | Classification | Why |
|---|---|---|
| Series is empty | `BACKFILLED_BASELINE` | The first import. Nothing was watched. |
| Incoming month is **older** than the newest stored | `BACKFILLED_BASELINE` | Filling history backwards. Still not watched. |
| Incoming month is **newer** than the newest stored | Observed `FIRST_OBSERVATION` | A new release arriving. MacroChipz *is* watching. |
| Incoming month **equals** a stored month, value differs | Observed `PROSPECTIVE_REVISION` | MacroChipz held the earlier value and saw it change. The one case where "originally reported" is provable. |

`ObservationVersionWriter` gained a `baseline` flag for this, and applies it **only to `NEW` versions** — a revision is always genuinely observed, whatever the caller asks for.

### `is_backfilled` was widened, deliberately

#31 introduced the column for versions its *migration* synthesized. #45 extends it to a new source's initial import. The flag's **meaning is unchanged** and is exactly the one #31 documented: *"this value existed in MacroChipz by this time"*, never *"this was the value the source first published"*. A provider's 1959–2026 history arriving in one request is that case. The widening is recorded in `app/db/models.py` and in `revision-intelligence.md`, not left to be inferred.

### Measured, on the real import

| | |
|---|---|
| Duration | 19.1 s (single request, 26,773 rows, ~1.5 MB) |
| Observations stored | 4,644 across six series |
| Date range | 1959-01 → 2026-08 |
| Rows rejected | 0 |
| Error-measure rows recognised and set aside | 5,760 |
| Rows outside scope | 16,369 |
| Missing-value rows skipped | 0 |
| Version rows written | 4,644, **every one `is_backfilled = true`** |
| Repeat sync | 0 inserted, 0 revised, 4,644 unchanged, **0 new version rows** |

**The values match the published release exactly.** Census's August 2026 release reports permits at 1,394,000 (2.7% below the revised July rate of 1,433,000, 3.5% above August 2025), starts at 1,275,000 (−2.6% / −1.2%), completions at 1,128,000 (−11.9% / −27.1%). MacroChipz's stored values and computed percentages reproduce all twelve figures.

---

## 7. Structured Intelligence (#39)

Housing joined `World` and **added no object type.**

Housing `OBSERVATION_CHANGE` objects are projected from `observation_versions` rather than from release-processing rows, because Housing has no release-calendar entry and never will until a Census schedule mechanism exists. A `HOUSING_OBSERVATION` variant was considered and rejected: every field of `ObservationChangePayload` is populated here from real data and the semantics match exactly, so a type differing only by *which table it came from* would make the taxonomy describe MacroChipz's plumbing instead of the economy.

- `basis` is `SOURCE_FACT` with `methodology = None`. Not a gap to fill later — there is no housing methodology, so there is no conclusion to attribute. Housing is the first world where that is true of every object it produces.
- **Only `is_backfilled = false` versions are read.** The 4,644-observation baseline import therefore contributes **zero** intelligence objects. Verified: 1,899 objects exist, none of them housing.
- **Bounded at the query** (`HOUSING_OBJECT_LIMIT = 50`), because a projection over an append-only table must not grow with the database.
- No `PART_OF_RELEASE` relation, because there is no release to point at.

Revision Intelligence needs **no Housing-specific code**: `selectRevisions` already filters on `change_type === "REVISED" && revision_knowledge === "PROSPECTIVE_REVISION"`, and a Housing revision satisfies both. Proven in `tests/integration/test_housing_intelligence.py` by driving a real revision through the pipeline — MacroChipz has still never captured one in real data, and #45 manufactured none.

---

## 8. The consumer page

`/housing`, in the order a reader asks the questions:

1. **The pipeline** — three boxes, two arrows, and the correction directly beneath at the same weight: *these are three separate counts, not one batch of homes.* A diagram that shows only the sequence says something false, so the sentence is part of the figure rather than a footnote.
2. **The figures** — annual rate as the headline, the month's actual count directly beneath it, then month-over-month and year-over-year changes with the periods they span. No badge, no colour-coded direction, no tone.
3. **One chart, not three** — see §9.
4. **Why the big number is not a count of homes** — the canonical SAAR explanation from the response, plus a link to the explainer.
5. **Rate context** — see §10.
6. **Evidence & limitations** — provenance per measure (concept id beside Census's identifier), every canonical limitation, and the required attribution.

**No Ask MacroChipz.** The bounded Analyst has no canonical Housing context, and widening it because a world appeared is what #45 forbids. Housing questions are unsupported rather than answered from a context that does not exist.

---

## 9. The chart (ADR-041)

**One chart with three lines, not three charts.** Permits, starts and completions are measured in the same unit on the same dates, and the question the reader arrives with is answered by their relationship. Three charts would put three independent y-axes on the page and invite comparison across scales that are not the same scale.

Drawn from the **annual rate only**. Plotting both units on one axis would be the exact conflation §4 exists to prevent.

- Hand-authored SVG, no charting library, no new dependency.
- A viewBox per breakpoint with `xMidYMid meet` — ADR-041's own SSR-safe prescription. **Verified in real Chrome**: mobile 1.286 rendered against 1.286 viewBox, desktop 2.533 against 2.533. No distortion at either.
- `role="img"` with an `aria-label` naming each series' endpoints and direction, and every value in a real captioned table behind a disclosure. One ARIA pattern, not two.
- Series distinguished by **dash pattern as well as tone**, and labelled at their own line ends — so it works without colour and without a legend to map back.
- No interpolation, no smoothing, no forecast, no fill between series (a shaded "backlog" would draw something MacroChipz does not measure).
- Nothing depends on hover.
- One neutral stroke for all three: a line moving down is not bad, and there is no methodology to say otherwise.

---

## 10. Rate context, and what it refuses to show

**It contains no number.**

Every reader of a housing page is thinking about mortgage rates. The honest answer is that MacroChipz does not track them — it tracks Treasury yields, a different number set in a different market.

Putting a live 10-year Treasury yield beside permits and starts would *visually assert a relationship*: two figures side by side on one page read as connected. MacroChipz publishes no housing-to-rates relationship, no elasticity and no lag, so placing them together would be the page making a claim its own data cannot support.

So the section is a signpost. It names what MacroChipz has, names what it does not have, and links to `/rates` and to *"Wait, the Fed doesn't set mortgage rates?"*. No estimated mortgage rate, no Treasury-to-mortgage spread, and nothing implying the Fed sets mortgage rates — all four tested against rendered text.

---

## 11. Explainers (#44)

Two, and only two:

- **"What do permits, starts and completions actually mean?"** — corrects the conveyor-belt reading.
- **"Wait, 1.5 million homes weren't built this month?"** — corrects the annual-rate reading, which is the misconception this world's headline figure creates.

Both meet #44's bar: each corrects a specific, checkable misreading of a number now on `/housing`, and every claim is supportable from Census's published definitions or from MacroChipz's own behaviour.

**A general "what is the housing market" explainer was not written**, because it would have had to describe prices, sales and affordability — things this product cannot show.

**Discovery:** both are listed by `UnderstandWorld` on `/housing`, the annual-rate one is additionally linked inline from the section rendering the figure it explains, and they link to each other and onward to the Fed/mortgage explainer. The site-level explainer-library problem #44 deferred stays deferred.

---

## 12. What Housing does not have

| | Why |
|---|---|
| A state, score, rating or direction label | No `housing_v1.0`. See §2. |
| A significance test | Census's confidence intervals are not in this dataset, and inventing them is not an option. §2. |
| A calendar entry | Census publishes no machine-readable schedule, and the alternatives are FRED (rejected on licensing) or a scraper (#M4). |
| Analyst support | No canonical Housing context exists. §8. |
| A Current State card on the homepage | It has no state. Housing appears in the registry-derived world lists and in primary navigation; `homepage_presentation_v1.0` was not changed. |
| Prices, sales, inventory, affordability, mortgage rates | Out of scope, and mostly unlicensable. §1. |
| Sub-national geography | National only, and the Census privacy term makes any future geographic detail a fresh review. |
| Vintage history before 2026-09-21 | The API serves current vintage only, and the initial import is a baseline. §6. |

---

## 13. Files

**Backend:** `app/clients/census.py` · `app/models/housing.py` · `app/domain/housing.py` · `app/services/housing.py` · `app/services/census_ingestion.py` · `app/repositories/housing_repository.py` · `app/api/housing.py` · `alembic/versions/e7b3d51c8a94_create_housing_ingestion_runs.py`

**Frontend:** `src/pages/Housing.tsx` · `src/components/housing/` · `src/api/housing.ts` · `src/api/housing.types.ts` · `src/lib/housingFormat.ts`

**Guards:** `tests/test_housing_architecture.py` · `tests/test_census_client.py` · `tests/test_domain_housing.py` · `tests/integration/test_census_ingestion.py` · `tests/integration/test_housing_service.py` · `tests/integration/test_housing_intelligence.py` · `tests/api/test_housing_api.py` · `frontend/src/test/no-housing-derivation.test.ts`
