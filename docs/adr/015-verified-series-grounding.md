# ADR-015: Application-Enforced Verified-Series Grounding

## Status
Accepted, but **not currently implemented in code**. Increment 012.5
reverted `app/services/ai.py`/`app/services/ai_tools.py`/`app/models/ai.py`
to their last-committed, pre-Increment-009 state (three tools, no
discovery, no grounding) as part of removing the autonomous multi-round
tool-orchestration experiment that never passed its own acceptance
gate (see ENGINEERING_JOURNAL.md, Increment 012.5). This ADR's
*decision* -- never trust a model-proposed series identifier without
verifying it against a real, application-controlled source -- was
implemented, worked, and is preserved here as the correct concept for
whenever discovery-capable AI re-enters the product (see Part 11 of the
architecture reset audit). It should be re-read and re-applied, not
re-derived from scratch, at that point.

## Context

Increment 009 let the model discover real candidate series via
`search_series` instead of requiring a user to already know a FRED
identifier. That capability creates a new risk distinct from anything
Increment 008 had to address: a model could pass a series identifier to
`get_observations`/`transform_series`/`analyze_series` that it was never
actually given by a verified source — not necessarily a nonexistent
identifier (which Increment 004's `SeriesNotFoundError` already catches
harmlessly), but a *real, persisted* identifier the model guessed,
misremembered, or substituted, producing a confident, correct-looking
answer about data the user never actually asked about. A decision was
needed about whether, and how, to prevent that.

## Decision

Every series identifier reaching an analysis-plane tool must be
"grounded": present in the current request's `search_series` results, or
literally typed by the user in their own message (checked via a
case-insensitive whole-word match against a specific identifier the model
already proposed — never by extracting/guessing candidate identifiers
from free text). This is enforced in `app/services/ai_tools.execute_tool`,
via a request-scoped `GroundingContext`, *before* any analysis-plane
handler runs — not left to the system instruction alone.

## Alternatives Considered

- **Trust the system instruction alone** ("only use identifiers from
  search_series or the user's message"). Rejected: an instruction is a
  request to the model, not an enforcement mechanism — the same reasoning
  Increment 008 already applied to tool *arguments* (validate with
  Pydantic, don't just ask nicely) applies equally to tool *targets*.
  Nothing about an instruction prevents a sufficiently confident model
  from substituting a plausible-looking real identifier for one it never
  actually verified.
- **Rely solely on `SeriesNotFoundError`** (the existing check that a
  series is persisted). Rejected as insufficient: it only catches
  identifiers that don't exist at all. It cannot catch a model confidently
  substituting one *real, persisted* series for another it was never
  actually asked about or shown — exactly the failure mode this ADR
  exists to prevent, and one that produces no error at all if left
  unaddressed.
- **A regex extracting candidate identifiers from the user's message**
  (e.g. "any all-uppercase token is a candidate ID"). Rejected explicitly:
  this is a brittle heuristic that both over-triggers (ordinary
  capitalized acronyms/words get treated as series IDs) and doesn't
  actually solve the problem (it grounds identifiers by *guessing* them
  from text, rather than verifying a *specific* identifier the model
  proposed). The chosen mechanism inverts this: it never generates
  candidates from text, it only checks one already-proposed identifier
  against the text.

## Why This Decision

Grounding closes a gap that source-of-truth verification
(`search_series`) and shape validation (Increment 008's Pydantic
argument models) don't cover on their own: neither one checks *why* the
model chose *this specific* identifier for *this specific* request. A
`GroundingContext` populated only by this request's actual verified
sources (search results, or the user's own words) is a direct,
checkable answer to "is this identifier something we actually gave this
conversation, or something the model supplied on its own." Enforcing it
as a hard `execute_tool` gate — refusing to call the underlying service
at all — means the worst case of a grounding failure is a clear
`ungrounded_series` tool error the model can react to, never a
successful, wrong analysis presented with full confidence.

## Consequences / Tradeoffs

- Gains: a security/correctness property that can be demonstrated by
  direct test (calling `execute_tool` with a fabricated identifier and
  confirming it never reaches `EconomicDataService`/`AnalysisService`),
  not just asserted from the system instruction's wording.
- Cost: an extra `search_series` round trip is sometimes needed even when
  a user's phrasing is close to unambiguous (verified during this
  increment: the system instruction has to explicitly tell the model to
  search first for a named concept, adding at least one tool round most
  requests wouldn't otherwise need).
- Cost: the message-text grounding path is deliberately conservative — it
  only recognizes an identifier the model already typed, checked against
  the user's exact wording. A user who refers to a series indirectly
  ("that unemployment number from before") without it or its identifier
  appearing verbatim gets no benefit from this path and must go through
  `search_series` instead. Accepted as the safer default for this
  increment.

## Revisit When

- Conversation memory/multi-turn context is added (explicitly out of
  scope for Increment 009) — grounding would then need to decide whether
  an identifier verified in an *earlier* turn remains valid, which this
  ADR's single-request scope doesn't address.
- A real usability complaint emerges that grounding's extra
  `search_series` round trip is a meaningful cost for the common case —
  evaluate a narrow relaxation then, against the actual friction observed,
  not preemptively.
