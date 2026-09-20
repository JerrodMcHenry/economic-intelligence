# ADR-031: Point-in-Time History Derives Its Inputs From the Methodology's Own Evidence, Compares Then and Today Through the Same Primitive, and Refuses a Comparison Rather Than Faking One

## Status
Accepted

## Context

Increment #31 (ADR-030) made MacroChipz able to answer "what did we know at time T?" and to prove a recorded conclusion reproduces from the data available when it was made. It shipped no UI and no route: `app/models/replay.py`'s own docstring said the contract existed "so verification (and a future #32 surface) has something honest to consume."

Increment #32 is that surface. The product question set is: what did MacroChipz know, what did it conclude, does that conclusion still reproduce, what does today's revised dataset say about the same period, and why might the two differ.

The dangerous part is not the rendering. It is that MacroChipz now holds two different, both-correct answers about the same month — the conclusion it recorded then, and the conclusion today's revised data produces — and blurring them would be the most misleading thing this feature could do. `docs/product/recorded-state-history-v1.md` §23 already froze the boundary being crossed here: recorded state proves EI's own *output* at time T, and before #31 could not prove its *inputs*. #31 moved that boundary for observations written since the migration and left it in place, explicitly marked, for everything backfilled.

## Decision

**A read-only, monitor-parameterized history API whose every economic judgement is made server-side, whose inputs come from the methodology's own evidence, and which refuses a comparison it cannot make honestly.**

- **`historical_inputs` is read off the recomputed result's evidence, never from a lookback window.** `inflation_v1.0` resolves t, t-1, t-3, t-6 and t-12 by exact calendar lookup and reports each endpoint and value as `InflationMetricEvidence`; `labor_v1.0` reports every required month as `LaborObservationEvidence`, missing ones included. A window invented by this layer would be a **second definition of the methodology's input set**, free to drift from the real one. Replay already recomputes the result, so the input list is a by-product of work already being done.

- **Then and today are produced by the SAME primitive at the SAME period.** `compute_series_momentum_at` / `compute_labor_monitor_result_at` are called twice — once over `get_observations_as_of` data at the recorded `calculated_at`, once over current observations. Any difference is therefore attributable to the data, never to two code paths that merely resemble each other.

- **The comparison is evidence-against-evidence, never evidence-against-storage.** This is a correctness requirement, not tidiness. `labor_v1.0` converts PAYEMS from FRED-native thousands into actual jobs before putting it in evidence (158,268,000 vs the persisted 158,268), so the first implementation — evidence on one side, a raw `economic_observations` read on the other — reported *every* Labor input as revised by a factor of 1,000. Comparing like with like makes a unit mismatch structurally impossible. The backend additionally declares `value_unit` per input so the frontend never infers a unit from a series id, which would be re-deriving a methodology decision in React.

- **A comparison is refused rather than faked.** Across methodology versions no `current_state` is computed at all — today's code implements different rules, so its answer is not "the same analysis on newer data" — and `state_differs` is `null`, never defaulted to `false`, which would read as "nothing changed". When replay could not run there is no "then" to compare against, so the input comparison is `NOT_COMPARABLE` while today's standalone reconstruction is still reported.

- **`{monitor}` is a two-value Literal path parameter.** The existing per-monitor routes exist because `InflationMonitorResult` and `LaborMonitorResult` are different types; history returns one shape for both, so the reason for separate routes does not apply. The Literal also means `/monitors/rates/history` is a 422 from FastAPI's own validation: Rates gained observation versioning in #31 but records no monitor state, and answering it with an empty list would imply a history that does not exist.

- **Related changes are narrowed to used inputs, and the remainder is counted.** `recorded_monitor_results` and `release_observation_updates` share a `release_check_run_id` — a real persisted link, not proximity. It still records no causation, so ADR-023's "no causal nesting" stands: the field is `related_changes`, the copy says the changes "happened together; it does not record that one caused the other", and a guard asserts no field name in the contract implies a cause. Narrowing is what makes the list meaningful rather than merely true (a bootstrap run carries 118 changes across 59 results); `other_changes_in_same_run` keeps the remainder visible.

- **Replay status is coloured from the `feedback-*` family, economic state from `state-*`.** #27B's hard rule keeps those disjoint because an economic state is a classification, not a verdict. A replay outcome is precisely a verdict — about MacroChipz's own integrity — so it takes the feedback treatment, and a `MISMATCH` keeps the error styling plus a screen-reader description naming it a data-integrity issue rather than an economic signal.

- **Read-only, and bounded.** GET only, default limit 20 and maximum 100 (the read-model family `#19B` established), ordered `calculated_at DESC, id DESC` — the id tiebreak is load-bearing because every result one run writes shares a `calculated_at` verbatim (recorded-state-history-v1.md §15), so without a total order paging could repeat and skip rows.

## Alternatives Considered

- **Derive historical inputs from a per-methodology lookback window.** Rejected: a second, drifting definition of what the methodology reads, when the methodology already reports it exactly.
- **Compare against a raw current-observation read.** Rejected after it produced a real 1,000× defect on every Labor input; the unit mismatch was invisible to the backend tests written at that point.
- **Let the frontend diff `value_then` against `value_today`.** Rejected: two characters of work that would move a methodology decision into React and hide exactly the unit problem above. Guarded, not merely discouraged.
- **Compare across methodology versions anyway, with a warning.** Rejected: a confident number answering a different question is worse than an explicit refusal.
- **Hide `INSUFFICIENT_DATA` rows so the timeline looks more informative.** Rejected: those conclusions really were recorded, and filtering recorded history to improve appearances is the opposite of what this surface is for.
- **Per-monitor routes (`/monitors/inflation/history`).** Rejected: the response shape is monitor-independent, and a Literal parameter additionally gives the correct 422 for Rates for free.
- **Expose Rates history as an empty list.** Rejected: it would imply recorded Rates state exists.
- **Fetch every row's detail with the list.** Rejected: a dozen requests nobody asked for. Detail loads on open, which is also why this is the one resource the page does not own.

## Consequences

- A reader can see what MacroChipz concluded, whether it still reproduces, exactly which observations fed it, and what today's data says about the same month — without being told anything the stored evidence does not support.
- Every current local result discloses reconstructed inputs, because all pre-#31 history was backfilled. That is accurate and will remain so for those rows permanently.
- A replay `MISMATCH` is now user-visible as an integrity problem. None exist in local data today; the presentation is proven by fixture and by service-level tests that construct one.
- The `state-*` / `feedback-*` split now carries a second, sharper meaning: classification versus verdict. Both guards enforce it from their own side.
