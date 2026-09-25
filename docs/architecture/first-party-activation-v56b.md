# First-Party Activation (#56B)

Completes the migration audited in `first-party-inflation-jobs-migration-v54b-audit.md`
and started in `first-party-ingestion-v56a.md`: **Inflation and Jobs read
BLS and BEA, and nothing in the deployment uses FRED.** Scope was frozen
to activation. No product feature, scheduler, worker or frontend design
changed.

## What changed

| Area | Change |
|---|---|
| Bindings | The six BLS/BEA bindings are **active**; the six FRED bindings are **inactive**, kept so FRED-sourced rows stay identifiable and a rollback is a flag flip |
| Identity | Evidence and results name the agency's own series id (`CES0000000001`, `DPCCRG`) through `provider_series_id_for(series)`. Before, a concept-keyed row would have printed its storage key. FRED rows still name FRED (ADR-034, Invariant D) |
| Result defaults | `EmploymentResult` / `UnemploymentResult` / `TargetResult.series_id` default to the active binding's provider id, not its storage id |
| Release processing | Takes a SOURCE. In production that is `FirstPartyObservationSource`: the two calls FRED's client answered, answered from BLS/BEA. One BLS query and one BEA download per run. It **refuses to create a series** -- a first-party row must start as a baseline from `import_first_party` -- so release processing can never record a five-year window as sixty "new" arrivals |
| Release catalog | Migration `b8d2e4f60a17`: BLS `cpi`, BLS `empsit`, BEA `pio` releases with mappings to the concept-keyed rows. FRED releases and mappings are **deactivated, never deleted**. The downgrade deactivates rather than deletes too, because deleting a release cascades to `recorded_monitor_results` |
| Schedule | `app/models/release_schedule.py`: the agencies' own 2026 dates, each release citing its source page. `sync_schedule` writes them as occurrences (idempotent). `schedule_status` reports OK / EXPIRING (45 days) / EXPIRED / MISSING |
| CLIs | `run_maintenance` and `process_release` need **no FRED key**. Maintenance syncs the schedule first and **exits 1** when a schedule is EXPIRED or MISSING. New `release_schedule [--sync]` |
| Calendar read | Lists occurrences of **active** releases only |
| FRED calendar sync | Skips non-FRED releases (a BLS id means nothing to FRED); with the catalog migrated it has nothing to do |
| Frontend | Storage-id constants, release ids `cpi`/`pio`/`empsit`, the Jobs evidence unit label (**"Jobs"** -- the value always was jobs; it was labelled thousands), and attribution text: BLS/BEA, the verbatim BLS disclaimer, no FRED |
| Dependencies | `requirements.lock` (image) and `requirements-dev.lock` (CI), hash-pinned by pip-tools from `pyproject.toml`. The project installs with `--no-deps`. Guard tests keep the locks consistent with `pyproject.toml` and with each other |

## What did not change

- Methodologies, domain calculations, classifications, thresholds.
- API response shapes: every field is the same; the provider and
  `series_id` values are now correct for the source.
- The version writer and revision semantics. The access gate. Rates and
  Housing.

## Why a committed schedule rather than a feed

BEA publishes machine-readable dates. BLS's feed refuses non-browser
clients, and working around that is not something this project does.
Three releases a month, published a year at a time, are a reviewed file,
not a service. The cost is a yearly refresh, and it is made loud:
EXPIRING 45 days ahead, and a failing maintenance job once expired.
Until the refresh lands, `import_first_party` is the manual path. It
needs no calendar and records only genuine changes.

## Verification (#56B)

A fresh database, a production-only environment built from
`requirements.lock`, no FRED or BLS key, and real BLS and BEA requests:

1. migrate: 14 revisions, COMPATIBLE;
2. `release_schedule --sync`: 37 occurrences, all OK;
3. `import_first_party`: 464 + 230 baseline observations;
4. `process_release` for the latest CPI, Employment Situation and PIO:
   **NO_CHANGE**, 0 new, 0 revised -- no false revisions against the
   baseline;
5. `run_maintenance`: schedule OK, 0 due, exit 0;
6. production-mode server behind the gate: container checks 41/41, smoke
   13/13. Both monitors compute; evidence names only
   `BLS CUSR0000SA0 / CUSR0000SA0L1E / CES0000000001 / LNS14000000` and
   `BEA DPCERG / DPCCRG`; "FRED" appears in neither response.

**Database afterwards:** 6 series (4 BLS, 2 BEA), 0 FRED observations, 0
FRED occurrences.

## Residuals

- **Six inactive FRED catalog rows** (names and FRED release numbers)
  are still seeded by the original, frozen migrations. They hold no data
  and no dates. Removing them means editing history or a deleting
  migration.
- **Pre-activation recorded results** (development databases only)
  replay as NOT_REPLAYABLE, and monitor history compares them by storage
  id, so FRED-era inputs appear as "only then". Honest, and absent in
  any database that never held FRED data.
- **BLS retrieval date on screen:** the BLS terms ask users to cite the
  retrieval date. It is recorded per observation in provenance but not
  displayed.
- **The FRED operator routes** (`/series/{id}/sync`, `/releases/sync`,
  series search) remain as development tooling. With no FRED key they
  answer 503 or local-only.
