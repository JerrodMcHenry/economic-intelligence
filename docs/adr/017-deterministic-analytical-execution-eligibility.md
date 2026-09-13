# ADR-017: Deterministic Analytical Execution Eligibility

## Status
Accepted, but **not currently implemented in code**. Increment 012.5
reverted `app/services/ai_tools.py` (which owned this ADR's
`GroundingContext`/`execute_tool` gate) to its last-committed,
pre-Increment-009 state, along with the rest of the failed autonomous
multi-round orchestration experiment (see ENGINEERING_JOURNAL.md,
Increment 012.5). This ADR's central decision -- the application, never
the model, owns whether a proposed action may execute -- was
implemented, verified with 100% enforcement across every live and mocked
test this project ran, and is preserved here as the correct, load-bearing
principle for any future AI-facing execution surface. It is the one
piece of the Increment 009 era's AI work that should be re-applied
first and essentially unchanged whenever AI is allowed to trigger
analytical execution again.

## Context

ADR-015 already established that a series identifier's *identity* must be
application-verified before an analysis-plane tool may act on it
("grounding"). It deliberately left a distinct question open: a real,
verified series can still be `persisted: false` (discovered, but not yet
available in the local analytical dataset). Increment 009's original
implementation asked the system instruction to handle that case --
"check `persisted` before attempting an analytical tool; if it's false,
don't." Live verification against the real environment showed this
prompt-level instruction was not reliable: across repeated runs of the
same and different economic concepts (inflation, real GDP, the federal
funds rate, an intentionally ambiguous inflation/unemployment request),
the model repeatedly requested `get_observations`/`transform_series` on
`persisted: false` candidates anyway -- not occasionally, but as the
dominant pattern for several concepts, each wasted attempt consuming one
of `MAX_TOOL_ROUNDS=4`. A decision was needed on whether execution
eligibility could continue to rely on the model honoring a fact already
visible to it, or needed its own enforcement layer independent of
wording.

## Decision

Whether a grounded series identifier may actually be passed to
`EconomicDataService.get_observations`, `EconomicDataService.get_transformed_observations`,
or `AnalysisService.pipeline` is now a second, deterministic check in
`app.services.ai_tools.execute_tool`, entirely independent of grounding:

1. **Grounded?** (ADR-015, unchanged) -- is this a real, verified series
   the model was shown or the user typed?
2. **Persisted?** (new) -- is this specific series actually available in
   the local analytical dataset *right now*? Resolved by
   `GroundingContext.resolve_persisted`: authoritative from a
   `search_series` result already seen this request if one exists, or
   (for an explicitly user-typed identifier never returned by search) a
   direct, read-only `SeriesRepository.get_series_by_series_id` lookup --
   the same local check `EconomicDataService`/`AnalysisService` already
   perform internally, just run deterministically before the handler
   instead of only inside it.

Both series referenced by `analyze_series` are checked before either is
authorized -- a call with one persisted and one unpersisted series is
rejected wholesale (`series_not_persisted`, naming the unavailable id),
never partially executed. Neither check is influenced by anything the
model asserts in tool arguments: there is no `persisted` or `verified`
field in any of the four tools' argument schemas for the model to set,
and `GroundingContext`'s discovery-backed state is populated only by
`execute_tool` itself, from an actual `search_series` result, after that
call has actually run.

Semantic selection remains entirely the model's responsibility --
including selecting a genuinely correct but unpersisted series, and
explaining that limitation honestly. Only the *execution* decision moved
out of the model's hands.

## Alternatives Considered

- **Keep relying on the system instruction, with clearer wording.**
  Rejected: this is exactly what was tried first (a prior correction
  added the instruction now being replaced), and live, repeated
  verification showed it reduced but did not eliminate the failure --
  several concepts continued to exhaust `MAX_TOOL_ROUNDS` on the exact
  pattern the instruction targeted. A prompt changes model behavior
  probabilistically; execution safety needs a guarantee, not a
  probability.
- **Raise `MAX_TOOL_ROUNDS`.** Rejected for the same reason the original
  diagnosis rejected it: it would not fix wasteful execution, only make
  more room for it, and would mask exactly the pattern this ADR exists
  to close off.
- **Fold this into ADR-015 as an amendment.** Considered, but declined:
  ADR-015 is about identifier *provenance* (is this a real series the
  model actually verified, vs. one it invented or substituted).
  This decision is about identifier *execution eligibility* (is this
  real, verified series usable *right now*), a materially different
  question with its own rejected alternative and its own evidence. Both
  now sit in `GroundingContext`, and both serve the same underlying
  principle ("the application remains authoritative, the model is never
  the security boundary") -- but that shared principle is better
  expressed as two ADRs a reader can cite independently than one ADR
  whose rejected-alternatives section would otherwise conflate two
  different failure modes.

## Why This Decision

The model must remain free to make a probabilistic, informed choice
about *which* series is semantically correct -- that's exactly the kind
of judgment an LLM is good at, and forcing it into deterministic logic
would mean deciding by code whether CPI or PCE is "the" right measure of
inflation, which this project has repeatedly and deliberately refused to
do (no concept-to-series aliasing, anywhere). But *whether a specific,
already-identified series may run against a real database query* is not
a judgment call at all -- it is a fact the application already knows
with certainty the instant a `search_series` result comes back, or the
instant a repository lookup is performed. Asking the model to carry that
fact forward correctly, every time, across an unbounded range of
concepts and phrasings, asks an inherently probabilistic component to
provide a deterministic guarantee. Moving the check into
`execute_tool` makes the guarantee unconditional: proven directly, by
mocking the underlying service methods and confirming they are never
invoked when a referenced series fails either check -- not merely
inferred from the tool result looking right.

## Consequences / Tradeoffs

- Gains: execution safety no longer depends on model behavior at all.
  Verified directly: across dozens of live-model tool calls spanning six
  different economic-concept questions (several repeated), every single
  attempt to execute against a `persisted: false` or ungrounded series
  was blocked before `EconomicDataService`/`AnalysisService` were ever
  invoked -- 100% enforcement, with zero exceptions observed.
- Cost (accepted, not solved here): the deterministic gate guarantees
  *safety*, not *round efficiency*. The model can still spend a tool
  round requesting an unavailable candidate -- it just can no longer
  succeed at executing it, or silently receive incorrect data. Live
  verification after this change showed several concepts (real GDP, the
  federal funds rate, the named target question itself in some runs)
  still exhausted `MAX_TOOL_ROUNDS` via repeated blocked attempts, at a
  rate not clearly better than before this ADR's change. This is a
  known, explicitly out-of-scope-for-this-ADR limitation -- conflating
  "the model wastes a round" with "the application executed something
  it shouldn't have" would be the wrong lesson to draw from that
  finding, and this ADR deliberately keeps the two separate.
- Cost: `SeriesRepository` is now imported directly by
  `app.services.ai_tools` for the explicit-user-id fallback path
  (previously that lookup only ever happened inside
  `EconomicDataService`/`AnalysisService`). A small, intentional
  coupling -- the same repository method those services already call
  internally, not a new query shape.

## Revisit When

- A future orchestration change is deliberately scoped to address round
  *efficiency* specifically (distinct from execution *safety*, which
  this ADR already closes) -- e.g. giving the model a way to request
  several candidates' persisted status in one call rather than
  discovering it one blocked attempt at a time. Not attempted here by
  design: the immediate empirical evidence motivating this ADR was a
  safety gap, not an efficiency complaint, and the two shouldn't be
  solved by the same change without deliberately deciding to.
- User-approved ingestion (ADR-016) is designed -- at that point
  `resolve_persisted`'s local-only lookup remains correct, but the
  overall user experience for a `series_not_persisted` result may
  reasonably change (e.g. offering to sync) in ways this ADR doesn't
  address.
