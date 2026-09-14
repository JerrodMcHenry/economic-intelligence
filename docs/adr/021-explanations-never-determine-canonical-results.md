# ADR-021: Explanations Never Determine Canonical Results

## Status
Accepted

## Context

Increment #17C introduces the first frontend subsystem whose entire
purpose is to talk *about* canonical results — plain-English concept
definitions, "why it matters" context, and, for a handful of backend-
classified values (`InflationState`, `ScheduleStatus`), curated copy
selected by that value. This creates a genuinely new risk the frontend
hasn't faced before: unlike a formatter (`lib/format.ts`) or a label
lookup (`lib/inflationLabels.ts`), an "explanation" reads, in prose, as
if it's *reasoning about* the data — which makes it easy, one small
step at a time, for that reasoning to start doing real evaluative work
instead of merely describing work the backend already finished. A
`WhyThisState` component that shows 3M/6M/12M evidence next to a
`state` is one implementation choice away from a `WhyThisState`
component that compares 3M/6M/12M itself and picks which sentence to
show — and once explanation content depends on evaluating raw numbers
rather than looking up an already-classified value, the frontend has
silently become a second, informal implementation of
`inflation_v1.0`'s classification rules, with its own risk of drifting
from the frozen methodology over time. This is the same class of risk
ADR-019 addressed for the release calendar (a schedule fact
"looks like it means something" it doesn't) applied to a new surface:
educational content "looks like it's just describing" a result when it
could instead be computing one.

## Decision

Explanations never determine canonical results. Facts are sourced.
Calculations are deterministic. Canonical classifications are
deterministic. Explanations describe those results. Concretely:

- The dependency direction is one-way: `canonical backend result →
  frontend presentation → curated explanation content`. Nothing under
  `frontend/src/content/explanations/` or
  `frontend/src/components/explanations/` (nor
  `components/inflation/WhyThisState.tsx`, the one result-explanation
  component) may flow back into a calculation, a classification, or a
  mutation of an API response.
- A *result* explanation (e.g. "why is momentum MIXED?") is always
  looked up by a value the backend already classified (`state`,
  `schedule_status`) — never derived from re-evaluating the backend's
  own raw inputs (`r_3m_annualized`, `r_6m_annualized`, `r_12m`,
  `neutral_band_pp`) client-side. Displaying those raw values alongside
  the backend's classification is fine; branching UI logic on them is
  not.
- This is enforced as an executable guard, not merely documented
  intent: `frontend/src/test/no-explanation-classification-logic.test.ts`
  (plus the pre-existing `no-economic-logic.test.ts`, whose recursive
  scan already covers these files) checks every explanation-system file
  for AI/LLM imports, direct network calls, non-type imports from
  `api/`, and prop/parameter mutation — and a dedicated contradictory-
  evidence test (`WhyThisState.test.tsx`) proves the component renders
  a backend `MIXED` state as MIXED even when given numbers a human
  might read as STABLE, and vice versa.

## Alternatives Considered

- **Let a result-explanation component independently interpret the raw
  evidence values to produce richer, numbers-aware prose** (e.g. "3M is
  running noticeably above 6M, which is why this reads as heating").
  Rejected: this requires re-implementing comparison logic against the
  frozen neutral-band rules in TypeScript, creating exactly the second,
  informal, driftable implementation this decision exists to prevent —
  and the backend's `state` field already exists to answer this
  question authoritatively.
- **Generate explanation copy with an LLM**, either at build time or at
  request time, to reduce the curation burden of covering every
  concept/state/release type by hand. Rejected outright, and
  explicitly out of scope per the increment's own framing ("this is
  NOT an AI feature") — probabilistic content has no place describing
  a deterministic system's deterministic conclusions, and it would
  reintroduce exactly the ungrounded-explanation risk this project's
  read-only AI tools (ADR-013–018) were built to avoid on the query
  side.
- **A single shared "insight" module that both classifies and explains**
  (i.e., merge the explanation lookup and the classification logic into
  one function, on the theory that keeping them adjacent keeps them
  consistent). Rejected: adjacency is exactly how the two responsibilities
  quietly merge over time — keeping the explanation lookup as a pure
  function of an already-computed value, in a separate module with its
  own architectural guard, is what keeps the boundary real instead of
  aspirational.

## Why This Decision

This is the same permanent principle already governing every other part
of this project — *facts are sourced, calculations are deterministic* —
applied to a new kind of frontend content that, unlike a label or a
number format, reads as reasoning and is therefore uniquely prone to
quietly becoming reasoning. Making the guard executable (a test that
fails if classification-shaped code appears in these files, and a test
that fails if the UI ever reclassifies contradictory-looking evidence)
means this boundary survives future increments even if no one rereads
this document before extending the explanation system to a new
surface.

## Consequences / Tradeoffs

- Gains: a `WhyThisState`/`ExplanationTrigger` panel can never disagree
  with the Badge sitting next to it — both are reading the same
  backend field, so there is no code path where they could drift apart.
- Gains: the explanation system can be extended to future product
  surfaces by any contributor without re-deriving this boundary from
  first principles — the architectural guard fails loudly if a future
  change crosses it.
- Cost: result explanations can only be as numerically specific as the
  backend's evidence fields already are — a request for a more nuanced,
  numbers-aware explanation sentence is a backend evidence-contract
  gap to report, never something to compute around in the frontend.
- Cost: adding a new curated concept or state/status/release-type
  explanation is manual, one entry at a time — by design; there is no
  templating or generation shortcut consistent with this decision.

## Revisit When

- A future increment wants explanation prose that genuinely needs more
  granular evidence than the backend currently returns (e.g. a
  per-boundary distance, not just the boundary itself) — that is a
  backend response-contract change to design deliberately, informed by
  the frozen methodology, not a reason to compute the missing value in
  the frontend.
- A second result-explanation surface (beyond `WhyThisState`) is added
  for a different canonical classification — at that point, confirm the
  same "looked up by an already-classified value, never re-derived"
  shape still fits, or revise this decision if a genuinely new pattern
  is needed.
