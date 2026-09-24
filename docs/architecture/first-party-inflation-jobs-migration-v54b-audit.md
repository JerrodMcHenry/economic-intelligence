# First-Party Inflation and Jobs Data — Feasibility Audit (#54B)

**Audit only. Nothing implemented, deployed, committed or pushed. No
secret read.** Baseline: `7c7e5ce`. Supersedes nothing: it executes the
#M1–#M4 track planned in `macrochipz-deployment-launch-plan-v46b.md` §D,
with evidence that plan did not have.

**Labels:** **VERIFIED** = executed or read this increment, with the
source named · **OFFICIAL** = quoted from bls.gov / bea.gov, fetched
2026-09-24 · **INFERRED** = reasoned from evidence and not stated by a
source · **DECISION** = yours to make.

---

## §0. Findings that shape everything else

1. **The values are identical.** The six replacement series were
   fetched straight from BLS (API v1, no key) and BEA (keyless NIPA flat
   files) and compared with every stored FRED observation in the
   development database. **358 of 358 month-values match exactly**,
   including the October 2025 gaps. Switching providers would record
   **zero** spurious revisions today. VERIFIED.
2. **Production has no history to preserve.** Nothing has ever been
   deployed (#54A). If the migration lands **before** the first public
   deploy, the production database never contains FRED data. The
   hardest part of a live cutover, keeping pre-cutover evidence and
   replay honest, then applies only to development databases.
3. **The release calendar is the real dependency, not the series.**
   Release occurrences come only from FRED's `release/dates`. Maintenance
   processes occurrences that already exist, and every Inflation/Jobs
   update is triggered by one. Removing FRED from the series without
   replacing the calendar leaves the worlds frozen.
4. **The BLS machine-readable calendar blocks non-browser clients.**
   `bls.gov/schedule/news_release/bls.ics` returns "Access Denied" to
   curl. BEA's `release_dates.json` works without a key. VERIFIED.
5. **BEA's annual update is on 2026-09-30, in six days.** It revises
   2021Q1–2026Q1 (OFFICIAL). Any baseline taken before then will record
   a large, genuine revision burst on that date.
6. **Existing defect, found in passing: the Jobs evidence table is
   labelled wrongly.** `app/domain/labor.py:196-201` puts jobs-unit
   values (×1000) into `LaborObservationEvidence`.
   `EmploymentSection.tsx:71` labels them "Thousands of persons", and
   the model docstring (`app/models/labor.py:99-103`) says native
   units. A value of 159,075,000 is presented as thousands. VERIFIED
   from code; the rendered page was not checked.

---

## §1. Series mappings

| Concept (unchanged) | FRED today | Replacement | Units / SA / freq | Base | History | Precision |
|---|---|---|---|---|---|---|
| `us.cpi.headline.price-index.sa.monthly` | CPIAUCSL | **BLS `CUSR0000SA0`** (CPI-U, all items) | Index, SA, monthly | 1982-84=100 | 1947-01 | 3 dp since 2017 (observed) |
| `us.cpi.core.price-index.sa.monthly` | CPILFESL | **BLS `CUSR0000SA0L1E`** (CPI-U less food & energy) | Index, SA, monthly | 1982-84=100 | 1957-01 | 3 dp since 2017 (observed) |
| `us.nonfarm.payroll-employment.sa.monthly` | PAYEMS | **BLS `CES0000000001`** (CES, total nonfarm) | Thousands of jobs, SA, monthly | — | 1939-01 | integer thousands |
| `us.unemployment-rate.sa.monthly` | UNRATE | **BLS `LNS14000000`** (CPS, U-3) | Percent, SA, monthly | — | 1948-01 | 1 dp |
| `us.pce.headline.price-index.sa.monthly` | PCEPI | **BEA NIPA T20804 line 1, code `DPCERG`** | Fisher index, SA, monthly | 2017=100 | 1959-01 | 3 dp |
| `us.pce.core.price-index.sa.monthly` | PCEPILFE | **BEA NIPA T20804 line 25, code `DPCCRG`** | Fisher index, SA, monthly | 2017=100 | 1959-01 | 3 dp |

Sources:
- BLS series ID formats: `bls.gov/help/hlpforma.htm`. `LNS14000000` is
  confirmed by the API returning the expected series; its format page
  was not found.
- BEA table/line: `SeriesRegister.txt`. `DPCERG` → `T20804:1`, `DPCCRG`
  → `T20804:25`.
- FRED's own page cites `DPCERG` for PCEPI. FRED's citation for PCEPILFE
  was not found; the mapping rests on BEA's register and the exact value
  match.

Base years stay the same:
- CPI "Most CPI index series have a 1982-84=100 reference base" (OFFICIAL).
- For BEA, "The reference year … remains 2017" in the 2026 update (OFFICIAL).
- `inflation_v1.0` is ratio-based (`app/domain/inflation.py:105-116`), so
  a future rebasing would not change any computed rate. It would change
  displayed index levels.

**Units to preserve:** CES is published in thousands, identical to
PAYEMS (159075 = 159075). The BLS binding therefore keeps
`canonical_unit_factor = 1000.0` and stores **native** units, as FRED
does today. Do **not** copy Census's write-time conversion: it would
double-convert and break `tests/test_methodology_golden_vectors.py`,
which encodes the ×1000 conversion.

### §1.1 Value comparison — VERIFIED

Stored FRED observations are 2021-09 → 2026-08 (60 months). PCE ends
2026-07 (59 months). Each was compared with the official file.

| Series | Months compared | Exact | Differ | Gaps (both sides) |
|---|---|---|---|---|
| CPIAUCSL ↔ CUSR0000SA0 | 60 | 60 | 0 | 2025-10 |
| CPILFESL ↔ CUSR0000SA0L1E | 60 | 60 | 0 | 2025-10 |
| PAYEMS ↔ CES0000000001 | 60 | 60 | 0 | none |
| UNRATE ↔ LNS14000000 | 60 | 60 | 0 | 2025-10 |
| PCEPI ↔ DPCERG | 59 | 59 | 0 | none (Oct 2025 imputed by BEA) |
| PCEPILFE ↔ DPCCRG | 59 | 59 | 0 | none |

Because every input value is identical, `inflation_v1.0` and
`labor_v1.0` outputs are identical by construction: they are pure
functions of those values (`app/domain/*.py`, no I/O). This is to be
re-proven at implementation time by running both monitors against both
rows (§6, acceptance A3).

### §1.2 Revision and publication behaviour

| Series | Routine revisions | Annual revision | Vintages via API? |
|---|---|---|---|
| CPI (both) | NSA final when issued | SA factors revise the prior **5 years** each February, with January data | No — current values only (INFERRED; no vintage parameter or field) |
| CES payrolls | Prior 2 months each release ("P" = preliminary) | Benchmark + 5 years re-seasonally-adjusted each February. Preliminary March 2026 benchmark is **−79,000** (OFFICIAL) | No (INFERRED) |
| CPS unemployment | none monthly | 5 years of SA data revised at year end; population controls with January | No (INFERRED) |
| PCE (both) | Prior months each Personal Income and Outlays release | Annual update — **2026-09-30** covers 2021Q1–2026Q1 | No — BEA past vintages live only in the Data Archive (`apps.bea.gov/histdata/`) |

None of this is new. FRED passes on exactly the same revisions, and the
application already versions them (ADR-030) under `latest_revised_data`
(`docs/methodology/inflation-monitor-v1.0.md:555-572`). Real-time
vintages were never claimed, so losing FRED does not lose a capability
the product uses. (The FRED client never sends `realtime_*`/`vintage_dates`.)

### §1.3 Missing values

- **BLS:** `"-"` with a footnote for Oct 2025. CPI:
  `X: Data unavailable due to the 2025 lapse in appropriations`. CPS:
  footnote 9. OFFICIAL/VERIFIED.
- **FRED:** `"."`. The application stores it as a **row with NULL**
  (`release_processing.py:158-164`). VERIFIED in the development database.
- **Parity rule:** the BLS parser must turn `"-"` into a NULL row, not
  skip the month. If a later BLS value ever appears for 2025-10, that is
  a real NULL→value revision and must be recorded as one.
- **BEA:** the October 2025 PCE value exists; BEA built it from the
  geometric mean of the September and November CPI (OFFICIAL). No gap.

---

## §2. Access, limits and terms

### BLS Public Data API
- **Limits** (`bls.gov/developers/api_faqs.htm`, OFFICIAL):
  - v1: no key, 25 queries/day, 25 series/query, 10 years/query.
  - v2: registered key, **500/day**, 50 series, 20 years; registration
    renewed at least yearly.
  - Both: 50 requests / 10 s.
  - One release check needs a single request, since two series fit in
    one query.
- **Terms** (`bls.gov/developers/termsOfService.htm`, modified 2023-08-30,
  OFFICIAL):
  - Users must state *"BLS.gov cannot vouch for the data or analyses
    derived from these data after the data have been retrieved from
    BLS.gov."*
  - "Users of the public API should cite the date that data were
    accessed or retrieved."
  - "may not modify or falsely represent content … and still cite the
    source as BLS.gov."
  - BLS logo not usable.
  - Access may be limited or terminated "in its sole discretion."
- **Silent on:** caching, commercial use, redistribution or display,
  per-end-user keys.
- **Copyright:** "Everything that we publish … is in the public domain"
  (`bls.gov/bls/linksite.htm`). The BLS emblem is a registered trademark.

### BEA
- **API** (`apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf`, OFFICIAL):
  - A registered 36-character UserID is required.
  - Limits: 100 requests/min, 100 MB/min, 30 errors/min. Over the limit:
    HTTP 429, 1-minute lockout.
  - Query: `DataSetName=NIPA&TableName=T20804&Frequency=M&Year=…`.
- **Terms** (`apps.bea.gov/API/_pdf/bea_api_tos.pdf`, OFFICIAL):
  - Display *"This product uses the Bureau of Economic Analysis (BEA)
    Data API but is not endorsed or certified by BEA."* This is the exact
    wording; it ends "by BEA", which differs from #46B's paraphrase.
  - No modification while still claiming BEA as the source.
  - No implied endorsement.
  - Termination at BEA's discretion.
  - Silent on caching, commercial use and per-user keys.
- **Keyless flat files:** `apps.bea.gov/national/Release/TXT/NipaDataM.txt`
  (36.7 MB, all monthly NIPA series) plus `SeriesRegister.txt`.
  - HTTP 200 without a key; vintage only in the `Last-Modified` header.
  - No terms page specific to the files was found; general bea.gov
    content is public domain (`bea.gov/help/faq/147`). VERIFIED/OFFICIAL.

### Release schedules
- **BEA:**
  - `apps.bea.gov/API/signup/release_dates.json`, keyless JSON with ISO
    timestamps.
  - Personal Income and Outlays is listed through **2026-12-23**.
  - VERIFIED.
- **BLS:**
  - Per-release HTML (`/schedule/news_release/cpi.htm`, `empsit.htm`) and
    `bls.ics`, both behind bot protection.
  - Dates published only through **2026-12**; the 2027 schedule is not
    yet out (404). VERIFIED.

---

## §3. Impact assessment

| Area | Impact | Evidence |
|---|---|---|
| **Storage identity** | `economic_series.series_id` is UNIQUE and the row's `source` + `series_id` *are* the provider identity stamped on evidence (`series_repository.py:73-96`, "ALWAYS come from the row … ADR-034 Invariant D"). A BLS/BEA series therefore needs **its own row**. Flipping `source` on the FRED row would re-attribute FRED-supplied history to BLS. | code |
| **Bindings** | `ProviderBinding` already supports several bindings per concept with exactly one `active` (`bindings.py:41-71, 288-303`). Role constants derive from the active binding at import (`models/inflation.py:53-56`, `models/labor.py:62-70`), so the Python services follow a flag flip. | code |
| **Observation versions** | Revision detection is **exact equality** (`observation_versions.py:168`). With 358/358 identical, a switchover produces no revisions. A new row must be **baseline-imported** (`baseline=True`, as Housing does); if its first write came from release processing, about 60 months would appear as newly observed events. | code + §1.1 |
| **Provenance** | FRED rows have **no** `observation_provenance` (VERIFIED, 0 rows). BLS/BEA rows get provenance the way Rates/Housing do, with the landing-page URL and never an API URL containing a key (`housing_repository.py:47-58`). | DB + code |
| **Calculations** | Unchanged: same values, native units, factor 1000 for CES, ratio-based inflation formula. Golden vectors unaffected. | §1 |
| **API contracts** | Shapes unchanged. `provider` and `series_id` in evidence change **values** from `FRED`/`CPIAUCSL` to `BLS`/new id. Frontend fixtures assert the literal old values. | code |
| **Monitor history (then vs today)** | Keys inputs by `(series_id, date)` (`monitor_history.py:115-153`). Across a cutover every input reads ONLY_AVAILABLE_THEN/TODAY. Keying by `(concept_id, date)` fixes it; evidence already carries `concept_id`. | code |
| **Replay** | Pre-cutover recorded results read the new row, whose versions begin at import, so they become **NOT_REPLAYABLE**. That is honest (ADR-031 refuses rather than fakes). It affects development databases only (§0.2). | code |
| **Since-last-visit / what-changed** | Joined through `release_series_mappings.series_id` and role constants; they follow new mapping rows. | code |
| **Release calendar and processing** | FRED-only: `ReleaseSyncService(fred_client)`, seed migration `fbbe6b1ab8d9` (FRED ids 10/54/50/192/53/9), `release_processing._check_one_series` fetches from FRED and `create_series` sets neither `source` nor `concept_id`. `run_maintenance` / `process_release` exit without `FRED_API_KEY`. | code |
| **Intelligence objects** | Observation/analysis ids are concept-keyed and unaffected. `release:{provider}:{release_id}:{date}` ids for **new** occurrences take the new provider. No Inflation/Jobs page is prerendered (`PRERENDERED_TYPES = RATES_MOVEMENT`), and nothing is public, so no share link breaks. | code |
| **Frontend** | FRED named in the footer (`AppShell.tsx:176-179`, `IntelligenceShell.tsx:111`), `Inflation.tsx:83` ("BEA, via FRED" — wrong even today, since CPI is BLS), `Jobs.tsx:99`, `ReleaseScheduleDisclosure.tsx:33`, `content/explanations/{inflation,labor,releases}.ts`. Hard-coded ids in `api/series.ts:29-38`, release ids `"10"/"54"/"50"` in `releaseMonitorRelation.ts:38-50`, `api/labor.ts`, `RelevantRelease.tsx`. No `fred.stlouisfed.org` links exist. | code |
| **Charts with longer history** | `getSeriesObservations` asks for `limit=200` with default `asc` order. After a baseline longer than 200 months it charts the **oldest** 200. | code |
| **Tests** | 42 backend and 18 frontend files reference the six ids; 34 backend files inject a FRED client fake. | grep |

---

## §4. Recommended architecture — the smallest safe change

**Keep:** concepts, methodologies, domain functions, API shapes, frontend
components, the version writer, and the recorded-result model.

**Change:**

1. **Two small provider clients and one protocol.**
   - `app/clients/bls.py` (v2 with key, v1 fallback) and
     `app/clients/bea.py` (API with UserID).
   - Both implement one method used by release processing:
     `fetch_observations(binding, start) -> list[(date, value | None)]`.
   - This is #46B's `SeriesSource`, reduced to the one call that exists.
     FRED gets a thin adapter implementing the same method, so
     development and rollback keep working.
2. **New rows, keyed by concept id (the Census precedent).**
   - New bindings with `storage_series_id = concept_id`, `provider` BLS
     or BEA, and `provider_series_id` the official code.
   - The FRED bindings stay, set `active=False`.
   - `SeriesIdentity.provider_series_id` must come from the binding for
     the row's provider, not from `series.series_id`. Otherwise evidence
     prints a concept id as the "BLS series id" (the Housing builder
     already works around this, `builder.py:637-642`).
3. **Baseline import command.**
   - `python -m app.operations.sync_first_party --baseline` with an
     operator route, modelled on `census_ingestion.py`.
   - Writes versions with `baseline=True`, provenance per observation,
     and one run row.
   - The run table is the deferred `provider_ingestion_runs`
     (`models.py:481-485`) — one additive migration.
   - Being a CLI, it runs as a Render job and not in a web request
     (#54A §4 risk).
4. **Release processing dispatches on the binding's provider** instead
   of calling `FREDClient` directly.
   - `create_series` sets `source` and `concept_id`.
   - Maintenance and CLIs take the source registry. `FRED_API_KEY`
     stops being required.
5. **First-party calendar.**
   - New `economic_releases` rows: `BLS/cpi`, `BLS/empsit`, `BEA/pio`,
     plus `BEA/gdp` and `BLS/jolts` if kept — a DECISION.
   - New `release_series_mappings` rows to the new storage ids, with the
     FRED rows deactivated rather than updated (additive).
   - Occurrences come from `release_dates.json` (BEA) and from a
     **committed, reviewed BLS schedule file** (≈36 dates/year for the
     three BLS releases), refreshed each December when BLS publishes the
     next year.
   - Do not circumvent bls.gov's bot protection.
   - The frontend release-id constants move to the new ids.
6. **Monitor history keys by `(concept_id, date)`.** A small change
   that keeps then-versus-today comparable across providers while still
   showing each side's real provider.
7. **Frontend:**
   - Attribution: the BLS disclaimer sentence plus retrieval date, the
     verbatim BEA notice, "Source: U.S. Bureau of Labor Statistics /
     U.S. Bureau of Economic Analysis".
   - Remove FRED from production copy.
   - Series constants read from the API.
   - Chart fetch uses `order=desc` and reverses.
   - Fix the Jobs unit label (§0.6).

**Rejected:**

- **Flip `source` on the existing rows.** Fewest file changes, but it
  rewrites who supplied five years of history and breaks ADR-034
  Invariant D. Faster is not a reason to falsify provenance.
- **Keep `CPIAUCSL`-style storage ids for BLS rows.** Blocked by the
  UNIQUE constraint and `test_concept_identity_boundary.py:223-233`. It
  would also publish FRED® mnemonics beside a BLS source line.
- **Keyless-only (BLS v1 + BEA flat files) in production.**
  - Workable: 25/day is enough, and the 37 MB file per BEA check is
    tolerable.
  - But v1's 10-year window caps the baseline, and parsing a 37 MB file
    on a 512 MB instance for two numbers is waste.
  - Recommended only as the fallback and for verification tooling.
- **Keep FRED for the calendar only.** Leaves the FRED API terms in
  force for a public product: the question this milestone exists to
  close.

---

## §5. Dependency-ordered plan and effort

| Step | Scope | Depends on | Effort |
|---|---|---|---|
| **S0** | Decisions D1–D6 (§8). Register a BLS v2 key and a BEA UserID (human action). | — | — |
| **S1** | `bls.py`, `bea.py`, and a FRED adapter behind `fetch_observations`. Parsers for `"-"` → NULL, footnotes, BEA comma-formatted values. Recorded-response fixtures. No wiring. | S0 | 1 day |
| **S2** | Bindings (inactive), `get_identity` fix, `provider_ingestion_runs` migration, baseline sync service + CLI + operator route, provenance. | S1 | 2 days |
| **S3** | Release-processing dispatch; `create_series` sets identity; maintenance/CLIs accept the registry; new mapping rows (additive migration). | S2 | 2–3 days (heaviest test churn) |
| **S4** | First-party calendar: release rows, BEA JSON importer, committed BLS 2026 schedule, `release sync` from them, frontend release-id constants. | S3 | 2 days |
| **S5** | Activate: flip bindings; monitor history keyed by concept; fixture updates. | S3, S4 | 1 day |
| **S6** | Frontend attribution and copy, Jobs unit label, chart ordering, remove FRED from production copy. | S5 | 1–1.5 days |
| **S7** | Verification (§6) on a fresh database with **no** `FRED_API_KEY`; update the #54A checklist (ingestion, cron, smoke test, config). | S6 | 1 day |

**About 10–11 working days**, as roughly 3 reviewable increments:
S1–S2, S3–S5, S6–S7.

---

## §6. Acceptance criteria

- **A1 — parity.** For all six concepts, every month present in both
  the development FRED row and the new row matches exactly. The
  NULL-month sets are identical, and a script produces the report.
- **A2 — no fake revisions.** A baseline import writes only `NEW`
  versions with `is_backfilled=true`, and **zero** `REVISED`. Re-running
  it writes nothing.
- **A3 — calculations identical.** `inflation_v1.0` and `labor_v1.0`
  computed from the FRED rows and from the new rows give equal results
  in every field except `provider` and `series_id`. Golden vectors pass
  unchanged.
- **A4 — no FRED in production.** On a fresh database with
  `FRED_API_KEY` unset:
  - migrate, baseline, calendar sync and `process_release` for one CPI,
    one Employment Situation and one PIO occurrence all succeed;
  - Inflation and Jobs show real states;
  - a grep of production copy finds no "FRED".
- **A5 — attribution present.** The BLS disclaimer and retrieval date,
  and the verbatim BEA notice, appear on every page showing BLS or BEA
  values. A test pins the exact strings.
- **A6 — honest history.** In a development database carrying FRED-era
  recorded results:
  - replay of a pre-cutover result returns NOT_REPLAYABLE, never a
    BLS-attributed replay;
  - monitor history compares then and today by concept and shows each
    side's real provider.
- **A7 — suites green.** Backend, frontend, typecheck, lint and build all
  pass, and CI is green.
- **A8 — idempotent calendar.** Re-importing the schedule creates no
  duplicate occurrences.

---

## §7. Rollback

- **Before first deploy (recommended timing):** revert the commits. The
  new migrations are additive (new release rows, mapping rows, run
  table), and the FRED rows and bindings are untouched throughout.
- **After deploy:** flip `active` back to the FRED bindings and set
  `FRED_API_KEY`. The new rows and data stay (additive); nothing is
  dropped. Re-enabling FRED re-opens the terms question, so a rollback
  in production means re-gating Inflation and Jobs (#54A B1) until the
  migration is fixed.
- **Never:** downgrade migrations or delete the new rows. They carry
  provenance and recorded results.

---

## §8. Unresolved questions

### Legal / policy — human sign-off required, not engineering
- **L1.** Both ToS are **silent** on caching, storage, commercial use
  and per-user keys. Silence is not permission, and public-domain status
  covers the *data*, not the *API contract*. Recommendation: a human
  reads both ToS in full and records acceptance. Clarification from the
  agencies is optional. Neither text contains FRED's "each user must use
  their own key" clause.
- **L2.** Both agencies may terminate access at their discretion. That
  is an availability risk, mitigated by keeping the keyless paths (BLS
  v1, BEA flat files) as fallbacks.
- **L3.** Derived figures (annualized rates, 3-month averages,
  classifications) must be presented as **MacroChipz calculations**, not
  as BLS or BEA figures ("may not modify … and still cite the source").
  The current UI already separates evidence from calculation, but the
  copy should be reviewed against this clause.
- **L4.** Legacy FRED-sourced data in development databases must
  **never** be copied into production.
- **L5.** Whether a legal review is wanted before any commercial use —
  carried from #46B §L.6.

### Technical
- **T1.** BLS 2027 dates are unpublished, so the committed schedule
  needs a yearly December refresh. Missing it silently stalls both Jobs
  and CPI. Needs a staleness check: warn when the last known future
  occurrence is less than 30 days away.
- **T2.** Timing around the **BEA annual update on 2026-09-30.**
  Baseline after it, or expect a genuine revision burst through release
  processing.
- **T3.** The **CES benchmark and CPI seasonal revisions each February**
  revise 5 years. That is expected behaviour today via FRED, but it
  produces many OBSERVATION_CHANGE objects; confirm the homepage
  selection policy is acceptable under that burst.
- **T4.** State duration needs about 73 months; stored history is 60.
  This is existing coverage debt. A 20-year baseline (BLS v2) fixes it
  and requires the chart ordering fix.
- **T5.** No official BLS statement of CPI precision was found; parity
  is proven only empirically for 2017–2026.

### Decisions (DECISION)
- **D1.** Approve the six mappings in §1.
- **D2.** Approve the architecture in §4, notably new concept-keyed rows
  over flipping `source`.
- **D3.** Keyed APIs (register BLS v2 + BEA UserID) or keyless-only.
- **D4.** Which calendar releases to keep. CPI, Employment Situation and
  PIO are required. GDP (BEA) and JOLTS (BLS) are available first-party;
  FRED 9 (Retail Sales, Census) has no verified first-party schedule
  source yet — drop it or research it.
- **D5.** Baseline depth: 10 years (keyless-compatible) or 20 years.
- **D6.** Implement before the first public deploy, making #54A's B1
  gating unnecessary, or deploy Rates + Housing first with B1 and
  migrate afterwards.

---

## Evidence retained

- **Scratchpad:** raw official responses
  (`bls/raw_v1_*.json`, `bea/NipaDataM.txt`, `bea/SeriesRegister.txt`,
  `bea/release_dates.json`, ToS PDFs), per-series CSVs, and the
  comparison script (`cmp/compare.py`).
- **Development database:** read inside `BEGIN READ ONLY`; nothing
  written. No API key used; no `.env` read.
