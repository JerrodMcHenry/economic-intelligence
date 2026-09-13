# ADR-018: Dynamic Tool Availability for Round Efficiency

## Status
**SUPERSEDED — FAILED ACCEPTANCE GATE.** The open decision this ADR
originally left ("accept the limitation, revert the affected mechanism,
or approve a further change") has been resolved: the mechanism is
reverted. Increment 012.5 restored `app/services/ai.py`/
`app/services/ai_tools.py` to their last-committed, pre-Increment-009
state, removing this ADR's entire implementation (`build_tool_schemas`,
`MAX_DISCOVERY_ROUNDS`, the analytical-tool enum-narrowing) along with
the rest of the autonomous-orchestration experiment it was built on top
of. It is kept here, unmodified below this line, as the historical
record of a real, carefully-designed, honestly-measured architectural
attempt that did not survive contact with a live model — not as a
description of anything currently running.

**The key fact that must survive**, regardless of anything else in this
document: dynamic tool-schema shaping (a JSON-schema `enum` narrowing
what a model may request) did **not** reliably control model behavior
in live trials -- roughly 60% of round-2-or-later analytical tool calls
in the acceptance run supplied a `series_id` outside the schema's
declared `enum` anyway. This is a durable, reusable lesson independent
of this specific product: a declared schema constraint under
non-`strict` function calling is a strong hint, not an enforcement
mechanism, and should never be treated as one for anything
correctness- or safety-load-bearing. (The discovery-round budget half
of this ADR's mechanism, by contrast, worked exactly as designed in
every case it was exercised -- its failure here is entirely
about the analytical-tool enum, not about the general idea of a bounded
orchestration counter.)

Everything below this line is preserved exactly as originally written,
describing the mechanism as it was designed and measured -- not the
current state of the code.

## Context

ADR-017 made analytical execution safety deterministic: a `persisted:false`
or ungrounded series can never reach `EconomicDataService`/`AnalysisService`,
regardless of what the model requests. Live re-verification after ADR-017
showed this guarantee held perfectly (100% of attempts blocked, zero leaks)
but did not improve *round efficiency* — the model could still spend an
entire `MAX_TOOL_ROUNDS=4` budget requesting doomed calls, because
`execute_tool`'s gate necessarily runs *after* the model's turn (a full,
already-spent model inference) has already produced the request. A dedicated
design gate traced round accounting precisely: a round is consumed the
instant the model's response contains a tool call, before any application
code runs — the only lever available *before* that happens is what the
model is offered to choose from at inference time.

## Decision

Two complementary, request-scoped mechanisms, both pure functions of
`GroundingContext` state, built fresh before each model inference after the
first (round 1 is unchanged: all four tools, `series_id` unrestricted, to
preserve the explicit-ID fast path):

1. **Analytical action shaping.** `get_observations`/`transform_series`
   (and, independently, both `series_a.series_id`/`series_b.series_id` in
   `analyze_series`) have their `series_id` constrained via a JSON-schema
   `enum` to exactly this request's currently-known-persisted ids
   (`GroundingContext.known_persisted_ids()`). If that set is empty, all
   three analytical tools are omitted from that round's tool list entirely,
   rather than passed with an empty enum.
2. **Bounded discovery.** A small, explicit `MAX_DISCOVERY_ROUNDS=2`
   orchestration budget — one initial concept-retrieval round, one optional
   refinement round — tracked as a plain local counter in `AIService.query`,
   incremented once per tool-bearing round that contained at least one
   *successful* `search_series` call (parallel searches in one round count
   once; malformed or infrastructure-failed searches don't count at all).
   Once exhausted, `search_series` is also omitted from the next tool list.

`execute_tool`'s deterministic gate (ADR-017) is completely unchanged and
remains the unconditional safety guarantee underneath both mechanisms —
this ADR is an efficiency/orchestration layer *in front of* it, never a
replacement for it.

## Alternatives Considered

- **Prompt-only efficiency rules.** Rejected on direct empirical evidence
  from the immediately preceding correction: an explicit, repeated
  instruction ("check persisted before executing, never retry the same
  identifier") did not reliably change model behavior across repeated live
  trials.
- **Deterministic rejection alone (no action shaping).** Rejected: proven
  correct but insufficient for production UX on its own — the model could
  (and did) exhaust the entire round budget on calls the gate would
  correctly reject one at a time, producing a 503 for ordinary questions.
- **`available`/`unavailable` result regrouping alone.** Rejected as a
  standalone fix: restructuring the same `persisted` information into two
  JSON keys is still a presentational nudge, no stronger a guarantee than
  the instruction already tried and found unreliable. Not implemented at
  all in this correction, per explicit product direction — the existing
  flat candidate list with a `persisted` boolean was judged sufficient.
- **Tool-call rejection cache.** Rejected: request-scoped duplicate-service-
  call prevention already exists (`GroundingContext.resolve_persisted`
  caches its answer); a cache tracking rejected `(tool, series_id)` pairs
  would not change round accounting at all, since a round is consumed the
  instant the model asks, before any cache could intervene.
- **Increasing `MAX_TOOL_ROUNDS`.** Rejected: masks the symptom, doesn't
  address wasted rounds, and round accounting itself was traced and found
  not to be structurally wrong — the problem was what got offered, not how
  rounds were counted.
- **A separate selection/orchestration tool.** Rejected: an explicit
  "select, then let the app decide" round would *add* a round to the common
  case rather than removing one from the failure case, working against the
  stated goal.
- **One tool per series.** Rejected per explicit product direction — the
  design uses one `get_observations`/`transform_series` tool each, with a
  request-scoped enum, never per-series tool proliferation.

## Why This Decision

A schema constraint changes what the model is offered to choose from at
the moment of inference, which is categorically earlier — and, in
principle, more reliable — than asking the model to recall and honor a
fact from earlier in the same conversation. `enum` was already a proven
pattern in this codebase's own static schemas (`order`, `transformation`,
`analysis`), so extending it to a per-request, per-round dynamic value set
was the smallest structural extension of an already-working mechanism,
consistent with keeping `strict: false` and avoiding a larger schema
migration.

## Consequences / Tradeoffs

- **Gains, verified directly**: the discovery-round budget worked exactly
  as designed in every live case it was exercised (7/7 runs that reached 2
  successful discovery rounds correctly had `search_series` omitted
  immediately afterward). The explicit-ID fast path is unaffected — round 1
  remains fully unrestricted. `execute_tool`'s deterministic gate was never
  weakened: every one of 58 cases where the model violated its own offered
  enum was still correctly blocked before any service call, with zero
  leaks.
- **The primary acceptance gate was not met.** Across 28 required live
  trials (5 each for 5 concept-pair questions, 3 for an ambiguity phrasing),
  16 still raised `ToolRoundLimitExceededError` — not the required zero.
  Traced precisely: in ~60% of round-2-or-later analytical calls, the model
  supplied a `series_id` **not present** in that round's declared `enum`,
  continuing to reference an id from its own memory of an earlier
  `search_series` result rather than the narrower set actually offered that
  round. `strict: false` function calling's `enum` is a strong hint, not an
  enforced constraint — this model did not reliably honor it once a
  plausible id was already in its own conversation history. This is a
  genuine, measured limitation of mechanism (1) specifically — the
  discovery-round budget (mechanism 2) is unaffected by this finding and
  continues to work as designed.
- **Cost**: `TOOL_SCHEMAS` is no longer usable as a single static constant
  passed unmodified to every model call — tool-schema construction is now
  request/round-state-dependent, a real (if contained, two-file) increase
  in this module's statefulness.

## Revisit When

- A decision is made on whether to accept the current efficiency limitation,
  revert the analytical-tool enum-narrowing mechanism specifically (keeping
  the discovery-round budget, which does work), or evaluate a `strict: true`
  migration (deliberately out of scope for this ADR — a larger schema
  restructuring, not a natural extension of it) as a harder enforcement
  mechanism for the same idea.
- If `strict: true` is later adopted for these tools, this ADR's "not an
  enforced constraint" framing for the analytical-tool enum should be
  revisited directly against that stronger guarantee, and the acceptance
  criteria re-measured the same way this ADR's were.
