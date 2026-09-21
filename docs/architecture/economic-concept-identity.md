# Economic Concept Identity

**Increment #38, implementing [ADR-034](../adr/034-economic-concept-identity-separate-from-provider-series-identity.md).**

The authoritative description of how MacroChipz identifies economic data: what a concept is, what a binding is, which identifier means what, and the rules a future provider migration must follow.

---

## 1. The problem this solves

Before #38, `PAYEMS` — a FRED identifier — was MacroChipz's canonical identity for total nonfarm employment. Migrating the source would therefore have meant migrating the identity.

That was the visible problem. The real one was worse. `app/models/series.py`'s `Observation` carries exactly two fields:

```python
class Observation(BaseModel):
    date: date
    value: float | None
```

No identity. So a methodology stamped its evidence from a module-level constant:

```python
LaborObservationEvidence(series_id=PAYEMS_SERIES_ID, observation_date=..., value=...)
```

**Change the provider and the observations flow through unchanged — they are only dates and values — while the evidence goes on saying `PAYEMS`.** Evidence would assert a provenance that no longer reflected where the number came from. On a product whose entire differentiator is that its claims are checkable, that is a correctness failure waiting for a migration to trigger it.

---

## 2. The three identifiers

| Identifier | Means | Example | Owner |
|---|---|---|---|
| **Concept id** | What MacroChipz *means*, source-neutral and stable forever | `us.nonfarm.payroll-employment.sa.monthly` | MacroChipz (`app/concepts/registry.py`) |
| **Provider series id** | How the *provider* names it in their own vocabulary | `PAYEMS` (FRED), `BC_10YEAR` (Treasury) | The provider |
| **Stored series id** | What is in `economic_series.series_id` | `PAYEMS`, `UST_NOMINAL_10Y` | Historical accident — see §6 |

A concept identifier is **opaque**. It is readable so a human can scan a log, but **nothing parses it** to recover an attribute — attributes are fields. Discovering that an attribute was wrong must never force a rename of an identifier that is supposed to be stable.

---

## 3. Concepts

Twelve registered, matching the twelve series actually persisted. Each carries the dimensions that prevent an accidental semantic substitution:

`concept_id` · `name` · `world` · `frequency` · `canonical_unit` · `seasonal_adjustment` · `geography` · `universe` · `source_program`

**`universe` is the field doing the most work.** BLS's own documentation states CES counts *jobs* ("multiple jobholders are counted for each nonfarm payroll job") while CPS counts *employed people* ("counted only once"). #35's Radar research found that conflating the two is exactly what makes a cross-survey "divergence" a statistical artifact. **A registry that cannot express that distinction would eventually be used to assert something false**, so it is a required field rather than a comment.

**Code-defined, not database-defined.** Frozen methodologies depend on these identities, so they must be type-checked, versioned with the code that uses them, and incapable of changing without a deploy and a test run. The database records which concept a stored series *belongs to*; it does not get to decide what a concept *is*.

---

## 4. Bindings

A binding is a claim of **semantic equivalence** between one provider's series and one concept. `equivalence_basis` is where that claim is justified in words, and **"the names match" is not a justification** — every binding cites the frozen methodology that already uses that series for that role, which is the strongest possible basis because the equivalence is being *recorded* rather than newly asserted.

Bindings also own:

- **`provider_native_unit` and `canonical_unit_factor`.** The jobs conversion (`× 1000`) moved here from `app/models/labor.py`, where its own comment already described it as *"FRED's native Thousands of Persons"* — i.e. it was always a property of the provider, never of the concept. A different provider may publish the same concept in different units.
- **`active`.** Exactly one active binding per concept, enforced by `active_binding()`, which raises rather than picking the first match.

---

## 5. The mapping inventory

Every mapping, and why it is justified. This is the table the backfill used.

| Provider | Provider series | Stored as | Concept | Basis |
|---|---|---|---|---|
| FRED | `PCEPILFE` | `PCEPILFE` | `us.pce.core.price-index.sa.monthly` | `inflation_v1.0`'s PRIMARY input |
| FRED | `CPILFESL` | `CPILFESL` | `us.cpi.core.price-index.sa.monthly` | `inflation_v1.0`'s CONFIRMATION input |
| FRED | `PCEPI` | `PCEPI` | `us.pce.headline.price-index.sa.monthly` | `inflation_v1.0`'s TARGET + headline PCE context |
| FRED | `CPIAUCSL` | `CPIAUCSL` | `us.cpi.headline.price-index.sa.monthly` | `inflation_v1.0`'s headline CPI context |
| FRED | `PAYEMS` | `PAYEMS` | `us.nonfarm.payroll-employment.sa.monthly` | `labor_v1.0`'s employment component (CES, jobs) |
| FRED | `UNRATE` | `UNRATE` | `us.unemployment-rate.sa.monthly` | `labor_v1.0`'s unemployment component (CPS, persons) |
| TREASURY | `BC_2YEAR` | `UST_NOMINAL_2Y` | `UST_NOMINAL_2Y` | `rates_v1.0` nominal curve, `NOMINAL_FIELD_MAP` (#29) |
| TREASURY | `BC_5YEAR` | `UST_NOMINAL_5Y` | `UST_NOMINAL_5Y` | ditto |
| TREASURY | `BC_10YEAR` | `UST_NOMINAL_10Y` | `UST_NOMINAL_10Y` | ditto |
| TREASURY | `BC_30YEAR` | `UST_NOMINAL_30Y` | `UST_NOMINAL_30Y` | ditto |
| TREASURY | `TC_5YEAR` | `UST_REAL_5Y` | `UST_REAL_5Y` | `rates_v1.0` real curve, `REAL_FIELD_MAP` (#29) |
| TREASURY | `TC_10YEAR` | `UST_REAL_10Y` | `UST_REAL_10Y` | ditto |

**No speculative BLS or BEA bindings exist.** Their identifiers and unit semantics have not been verified against the agencies' own documentation, and inventing them would be exactly the fabricated equivalence this design prevents. #M2/#M3 add them, with evidence.

---

## 6. A pre-existing ambiguity, documented rather than migrated

**`economic_series.series_id` means two different things**, and #38 did not change that:

- For **FRED** series it holds the *provider's* identifier (`PAYEMS`).
- For **Treasury** series it holds *MacroChipz's own* identifier (`UST_NOMINAL_10Y`), because Increment #29 solved this problem correctly for Rates before it had a name — deliberately choosing `UST_NOMINAL_10Y` over FRED's `DGS10` so "a Treasury-sourced observation must never be confusable with a FRED-sourced one."

Bindings express the asymmetry faithfully via `provider_series_id` (what the provider calls it) and `storage_series_id` (what is in the column).

**Why not migrate it now:** rewriting `economic_series.series_id` for six Treasury rows would touch observation, provenance and version rows keyed to them, for naming symmetry and no correctness gain. The #38 brief explicitly rules out refactoring Rates for aesthetic uniformity. **The ambiguity is contained by the binding table and is now named rather than latent.**

---

## 7. Identifier semantics in the API

Per ADR-034's Invariant G, every identifier field in a contract is classified:

| Field | Semantics |
|---|---|
| `InflationMetricEvidence.concept_id`, `LaborObservationEvidence.concept_id` | **Concept id** |
| `InflationMetricEvidence.provider`, `LaborObservationEvidence.provider` | **Provider**, read from the stored row |
| `InflationMetricEvidence.series_id`, `LaborObservationEvidence.series_id` | **Provider series id**, read from the stored row |
| `SeriesMomentumResult.concept_id` | **Concept id** |
| `SeriesMomentumResult.series_id` | **Provider series id** |
| `TargetResult.series_id` | **Legacy** — a module-level default, not data-derived. See below |
| `RatesMonitorResult` series ids, `SourceProvenance.series_id` | **Stored series id**, which for Treasury is MacroChipz's own (§6) |
| `EconomicSeries.series_id` (`/api/v1/series/*`) | **Stored series id** (§6) |
| `EconomicSeries.concept_id` | **Concept id**, nullable |
| `observation_provenance.source_series_field` | **Provider series id** |
| `observation_versions`, `release_*` tables | **Stored series id** |

**Legacy items, kept deliberately and not depended on by new canonical code:**

- **`TargetResult.series_id`** still defaults to the module constant. It is a label on a derived result, not an evidence record — the evidence *inside* `TargetResult` carries the data-derived triple. Migrating it would change a response field for no provenance gain.
- **`EmploymentResult.series_id` / `UnemploymentResult.series_id`** — same reasoning.

**All three are frontend-visible and unchanged**, so #38 required no frontend work.

---

## 8. How identity reaches a methodology

```
persisted economic_series row
   ├── concept_id   ─┐
   ├── source        ├─> SeriesRepository.get_identity() -> SeriesIdentity
   └── series_id    ─┘
                           |
                           v
         service builds InflationSeriesIdentities / LaborSeriesIdentities
                           |
                           v
              frozen methodology stamps evidence from it
```

**All three fields come from storage.** `app/services/series_identity.py` is the single resolver, and it has exactly two cases:

1. **The series is persisted** → identity comes entirely from the row. This is the honest case, and the one that makes a cutover safe.
2. **The series is not persisted at all** → there are no observations, so no provenance claim is being made about any real value. Identity falls back to the active binding: *"this is the concept we looked for, at the provider we would have looked at, and nothing was there."* The methodologies already treat an absent series exactly like a persisted one with no usable observations.

**The fallback may never be used for a series that has observations.** That is precisely how evidence would start naming a provider that did not supply the data.

**Identity parameters are keyword-only** (`*, identities=...`). Two reasons: existing positional calls to frozen methodologies keep working unchanged, and a positional mix-up between the employment and unemployment identities — which would attribute one survey's evidence to the other — becomes impossible to write.

---

## 9. Migration rules

**Schema:** one additive, nullable column, `economic_series.concept_id`, plus an index. No observation value, observation date, provenance row or version row is read or written by the migration.

**Nullable permanently, by design.** `POST /api/v1/series/{series_id}/sync` accepts any FRED series a caller names, and those are not canonical concepts. Forcing NOT NULL would either break that endpoint or require inventing a concept for every arbitrary series — the fabricated identity this design exists to prevent. So:

- **Canonical methodology paths require a concept** and raise `MissingConceptIdentityError` without one.
- **Generic series endpoints neither require nor care.**

**Backfill refuses to guess.** A stored series is mapped only where `bindings.py` declares an explicit binding. No display label, no title, no fuzzy match. An unmapped series stays NULL.

**Verified after applying:** 12 of 12 series mapped, 0 unmapped, 1,072 observations unchanged (checksum `9414455.108000`), 175 distinct observation dates unchanged, 714 provenance rows unchanged, 1,072 observation versions unchanged, 133 recorded monitor results unchanged.

**Downgrade** drops the index and the column. Nothing else is touched, so it is exactly reversible.

---

## 10. Dual-provider cutover rules

The sequence a future BLS or BEA migration follows:

```
CURRENT      concept ──active──> FRED binding ──> PAYEMS

VALIDATION   concept ──active──> FRED binding ──> PAYEMS
                     └─inactive─> BLS binding  ──> CES0000000001
             (both ingested; compared over overlapping history)

CUTOVER      concept ──active──> BLS binding  ──> CES0000000001
                     └─inactive─> FRED binding ──> PAYEMS
```

**Rules:**

1. **A new binding starts inactive.** Adding it changes nothing.
2. **Ingest into a separate `economic_series` row** with its own `series_id` and `source`, sharing the `concept_id`. Historical rows are never rewritten.
3. **Verify by golden-vector equality** over overlapping history before flipping. Equivalence must be demonstrated, not assumed.
4. **Cutover is a flag flip** in `bindings.py` — one line, one deploy, trivially reversible.
5. **Historical evidence keeps naming the provider that produced it.** Because identity is read from each observation's own series row, a replay of a 2026 conclusion still reports FRED/`PAYEMS` after the active binding has moved to BLS. This is ADR-034's Invariant D, and it is structural rather than conventional.
6. **Verify units independently.** Whether BLS publishes CES in thousands, as FRED does, is a **verification task against BLS's own documentation, not an assumption** inherited from the FRED binding.

---

## 11. Guards

`tests/test_concept_identity_boundary.py` enforces:

- **No provider-shaped literal** (`PAYEMS`, `CPIAUCSL`, …) appears in any `app/domain/*` module — an AST scan over string constants. This is the guard that would have caught `labor_release_processing.py`'s `PAYEMS_SERIES_ID = "PAYEMS"`, duplicated "by convention" with nothing keeping it true.
- **No domain module imports a provider client or the binding table.**
- Every binding names a registered concept; every concept has **exactly one** active binding; every binding justifies its equivalence claim.
- **Employment and unemployment are different universes and different source programs.**
- The unit conversion lives on the binding, not the concept.
- Evidence and result models carry both identities.
- **Dual bindings resolve unambiguously**, and ambiguity — an unregistered concept, an unmapped stored series, a doubly-claimed stored series — **raises rather than silently succeeding**.
