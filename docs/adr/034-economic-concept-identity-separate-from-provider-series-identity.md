# ADR-034: Economic Concept Identity Is Separate From Provider Series Identity, and Evidence Carries Both

## Status
Proposed (Increment #36A)

## Context

MacroChipz's canonical methodologies currently identify economic series by **provider-shaped identifiers**: `PCEPILFE`, `CPILFESL`, `PCEPI`, `CPIAUCSL`, `PAYEMS`, `UNRATE`. These are FRED's identifiers. BLS's own identifier for total nonfarm payrolls is `CES0000000001`, not `PAYEMS`.

Increment #35 established that FRED cannot be the data spine of a public commercial MacroChipz. Increment #36 identified that migrating the *source* without migrating the *identity* would leave FRED's naming embedded in a system that no longer uses FRED. #36A verified how deep that goes, and found something worse than a naming problem.

### What the audit found

**The good news: the indirection already exists.** `app/domain/inflation.py` references `PRIMARY_SERIES_ID`, not the literal `"PCEPILFE"`. The constants in `app/models/inflation.py` and `app/models/labor.py` are already **named by role**, not by provider. Only their *values* are provider-shaped.

**Two literals leak past that indirection**, in `app/domain/labor_release_processing.py:47-48`:

```python
PAYEMS_SERIES_ID = "PAYEMS"
UNRATE_SERIES_ID = "UNRATE"
```

The module's own comment concedes these duplicate `app.models.labor` "by convention" — a duplication with no mechanism keeping it true.

**The real defect is in evidence.** `app/models/series.py`'s `Observation` carries exactly two fields:

```python
class Observation(BaseModel):
    date: date
    value: float | None
```

No series identity. So evidence is stamped from a module constant:

```python
LaborObservationEvidence(series_id=PAYEMS_SERIES_ID, observation_date=..., value=...)
```

**Consequence: if the provider changed from FRED to BLS, observations would flow through unchanged — they are only dates and values — and the evidence would still say `PAYEMS`.** Evidence would assert a provenance that no longer reflects where the number came from. On a product whose entire differentiator is provenance, that is not a naming inconvenience; it is a correctness failure waiting for a migration to trigger it.

### The pattern already solved once

Increment #29 got this right for Rates. `app/models/rates.py` defines MacroChipz-owned identifiers (`UST_NOMINAL_10Y`) with an explicit comment that they are "deliberately NOT FRED's (DGS10/DFII10)" so that "a Treasury-sourced observation must never be confusable with a FRED-sourced one carrying different provenance and different licensing." It pairs them with `NOMINAL_FIELD_MAP` — "the one place the provider's own column vocabulary is mapped into ours."

**Rates is the reference implementation. This ADR generalises it.**

### Why label similarity is not equivalence

Two provider series are not interchangeable because their names sound alike. Equivalence depends on concept, seasonal adjustment, units, frequency, **statistical universe**, geography, source program, and revision semantics.

The universe distinction is not hypothetical. BLS's own documentation states CES measures *jobs* ("multiple jobholders are counted for each nonfarm payroll job") while CPS measures *employed people* ("counted only once"), with different reference periods. #35's Radar research found that treating these as comparable is exactly what makes cross-survey "divergence" a statistical artifact. **A concept model that cannot express "jobs, not people" will eventually be used to assert something false.**

Relatedly, `PAYEMS_JOBS_PER_NATIVE_UNIT = 1000` is documented as converting from *FRED's* native "Thousands of Persons." Whether BLS publishes CES in the same units is a **verification task, not an assumption** — and it belongs to the binding, not to the concept.

## Decision

**An economic concept and a provider series are different things with different identifiers, and evidence records both.**

### 1. Concepts are MacroChipz-owned and code-defined

A **concept** is what MacroChipz means, independent of who publishes it. Its identifier is a stable, readable, **opaque** slug, and its discriminating attributes are explicit fields — never parsed out of the string.

```
concept_id: "us.nonfarm.payrolls.sa.monthly"        # opaque to code
  concept            TOTAL_NONFARM_EMPLOYMENT
  geography          US
  seasonal_adjustment SEASONALLY_ADJUSTED
  frequency          MONTHLY
  canonical_unit     JOBS
  universe           NONFARM_PAYROLL_JOBS            # jobs, not persons
  source_program     CES
```

**Code-defined**, because frozen methodologies depend on concepts: they must be type-checked, versioned with the code that uses them, and incapable of changing without a deploy and a test run.

### 2. Bindings are per-adapter and code-defined

A **binding** maps one concept to one provider's series, with the units and transformation required to satisfy the concept's canonical unit. Bindings live inside their adapter, exactly as `NOMINAL_FIELD_MAP` does for Treasury today.

**Code-defined, not a database table.** The database does not need to *decide* a binding; it needs to *record which one produced each stored value* — and `observation_provenance` already does that. A `concept_bindings` table would add a runtime lookup, a migration and a failure mode to solve a problem the existing provenance table already solves.

### 3. The database records concept membership, not concept definition

One additive column: `economic_series.concept_id`, nullable on introduction, backfilled, then made non-null. `economic_series.series_id` **keeps its current meaning** — the provider-assigned business identifier, which its own docstring already describes correctly.

During a migration both providers' rows may carry the same `concept_id`, distinguished by which is active for reads. **This is the cutover mechanism, and it is also the verification mechanism:** ingest both, compare over overlapping history, then flip. A provider migration becomes a reversible flag rather than a destructive rewrite.

### 4. Evidence carries both identities

Every evidence record names **the concept it satisfies** and **the provider series the number actually came from**. The provider identity is read from the observation's own provenance, **never stamped from a module constant.**

### 5. Domain code depends on concepts only

Frozen methodologies reference concepts. The provider series identity reaches evidence through the data, not through an import.

## Architectural Invariants

1. **Canonical methodology code must not depend on provider-specific identifiers.** Enforced by extending `tests/test_domain_architectural_independence.py` with a literal check across `app/domain/*`.
2. **Provider mappings must preserve semantic equivalence, not label similarity.** A binding is valid only when concept, adjustment, units, frequency, universe, geography and source program all agree, and equivalence is demonstrated over overlapping history.
3. **Provenance must always retain the actual provider series identifier**, and evidence must source it from the data rather than from a constant.
4. **A concept identifier is opaque.** No code parses it to recover an attribute; attributes are fields.
5. **Units belong to the binding, not the concept.** The concept declares a canonical unit; each binding declares its conversion.
6. **A concept with no active binding is a startup error**, not a runtime `None`.
7. **Two bindings for one concept may coexist only during a verified cutover**, and exactly one is active for reads.

## Alternatives Considered

- **Rename the constants' values in place and be done.** Rejected: it would change `series_id` inside evidence, breaking golden-vector equality, and it fixes naming while leaving the actual defect — evidence sourcing identity from a constant — untouched.
- **A database-backed concept and binding registry.** Rejected as premature. Concepts must be type-checked against frozen methodology code, and bindings change only when an adapter changes, which is a deploy. This adds a table, a lookup and a failure mode for flexibility nothing currently needs. Revisit if bindings ever need to change without a deploy.
- **Encode attributes in the concept string** (`us.payrolls.sa.m.jobs.ces`). Rejected: it invites string parsing, and discovering that an attribute was wrong would force a rename of an identifier that is supposed to be stable.
- **Add series identity to `Observation`.** Rejected for now as the wider change: `Observation` is used everywhere, and the same result is achieved by having services pass a resolved binding into the domain entry points that already accept a series identifier as a parameter.
- **Defer all of this until the BLS migration.** Rejected: the concept split is what makes the migration safe and reversible. Doing it first turns a rewrite into a flag flip; doing it during means doing both at once.

## Consequences

- **Source migration stops being a prerequisite for product work.** FRED becomes one binding behind a stable concept vocabulary, so the Structured Intelligence Layer and every 2.0 surface can be built while migrations proceed underneath.
- **Migration becomes verifiable and reversible** — dual bindings, compared over overlapping history, then flipped.
- **Evidence stops being able to lie about its own source.**
- **The change is additive.** One nullable column; role constants change value while keeping their names; evidence gains a field rather than changing one. Existing canonical outputs stay byte-identical on their existing fields.
- **Cost: roughly 32 files reference the role constants**, mostly tests asserting on evidence. Mechanical, but real, and it is the main work of the first implementation increment.
- **Two literals in `app/domain/labor_release_processing.py` must go**, and the guard that would have caught them gets written.
- **A new obligation:** every binding must document its verified equivalence. "The names match" is not a justification, and the CES/CPS jobs-versus-people distinction is the standing example of why.

---

## Implementation Notes (Increment #38)

The decision above was implemented as written in substance. Six details differed once the code was in front of us, recorded here rather than left as silent divergence.

**1. Role constants keep their names *and* their values.** This ADR said they would "change value, not name." They did not. `PRIMARY_SERIES_ID` is still `"PCEPILFE"` — but it is now *derived* from the active binding's `storage_series_id` rather than hardcoded.

The reason is that changing the value would have broken the very invariant this ADR set. Those constants name **a place to look in storage**, and their value flows into evidence's `series_id`, which Invariant C requires to be *the actual provider series identifier*. Turning them into concept ids would have made evidence claim a concept where a provider identifier belongs, and changed frozen methodology output for every existing golden vector. New `*_CONCEPT_ID` constants were added alongside instead.

**2. A `SeriesIdentity` value object was introduced and threaded through the methodologies.** The ADR implied that changing constant values would be enough. It would not have been. The defect was never *which* constant was used — it was that identity came from a constant **at all**, while `Observation` carries only a date and a value. Identity now travels with the data, resolved from the persisted row.

**3. Identity parameters are keyword-only.** Every existing positional call to a frozen methodology keeps working unchanged, and a positional mix-up between the employment and unemployment identities — which would attribute one survey's evidence to the other — is impossible to write.

**4. Bindings needed two provider-facing identifiers, not one.** `provider_series_id` (what the provider calls it — Treasury's `BC_10YEAR`) and `storage_series_id` (what is in `economic_series.series_id` — `UST_NOMINAL_10Y`). They are equal for FRED and differ for Treasury, because #29 stored MacroChipz's own identifier there. The asymmetry is a pre-existing ambiguity in `economic_series.series_id`, now named and contained rather than latent. See `docs/architecture/economic-concept-identity.md` §6.

**5. Rates concept ids reuse the existing `UST_*` identifiers.** They were already source-neutral, MacroChipz-owned identities — #29 solved this correctly before it had a name — and they are persisted. Renaming them would be a data migration buying only naming symmetry.

**6. No `concept_bindings` table, exactly as predicted.** One additive nullable column on `economic_series`, and `observation_provenance` continues to record which retrieval produced each value. The ADR's reasoning held.

**One thing the implementation found that the ADR did not anticipate:** the unit conversion. `PAYEMS_JOBS_PER_NATIVE_UNIT = 1000` was documented in `app/models/labor.py` as converting from *"FRED's native Thousands of Persons"* — so it was always a property of the provider, never of the concept. It now lives on the binding as `canonical_unit_factor`, and whether BLS publishes CES in the same units is explicitly a **verification task for #M2, not an assumption inherited from FRED**.
