# ADR-016: No Automatic Ingestion From AI-Driven Discovery

## Status
Accepted as a standing principle; **currently inapplicable** rather than
implemented, since Increment 012.5 reverted the AI path's discovery
capability (`search_series`) along with the rest of the failed
autonomous-orchestration experiment (see ENGINEERING_JOURNAL.md,
Increment 012.5, and ADR-015's status note). There is, right now, no
AI-driven discovery for this rule to constrain. The principle itself --
AI-triggered discovery must never be allowed to also trigger a write --
stands unconditionally for whenever discovery-capable AI returns, and
should govern that design from the start rather than be rediscovered.

## Context

`search_series` (Increment 009) can discover a real FRED series that is
not yet persisted (e.g. `GDPC1` when a user asks about "real GDP"). The
natural next step from a pure usability standpoint is obvious and
tempting: since `POST /{series_id}/sync` (Increment 003) already exists
and could persist that series in one call, why not have the AI path call
it automatically so the user's question can actually be answered in the
same turn? A decision was needed on whether discovery should be allowed
to trigger ingestion.

## Decision

`search_series` never triggers `sync_series` or any other write. A
discovered-but-unpersisted candidate (`persisted: false`) is reported to
the model as exactly that; the model's only correct response is to
explain the limitation, never to substitute a different (persisted)
series or fabricate an answer. This is a hard boundary, not a
configuration flag — no code path in Increment 009 calls
`EconomicDataService.sync_series` or constructs a write-capable
`FREDClient` usage.

## Alternatives Considered

- **Auto-sync on discovery when a series is requested for analysis.**
  Rejected: this would mean a natural-language request — a user typing a
  sentence, interpreted by a model — could trigger an external HTTP call
  to FRED and a database write, with no explicit user action against a
  specific, reviewable endpoint. This is the same category of risk
  Increment 008's [ADR-014](014-read-only-ai-tools.md) already rejected
  for the AI path generally, now revisited specifically because discovery
  makes the temptation concrete and immediate rather than abstract.
- **Auto-sync only for series above some popularity threshold** (e.g.
  "only auto-sync if FRED's popularity score is high enough to be
  obviously legitimate"). Rejected: popularity is a measure of how often
  *other FRED users* look at a series, not a measure of whether *this
  user, in this conversation* actually intended to persist new data into
  *this application's* database. Using it as an authorization proxy would
  quietly encode a policy ("popular enough series get to bypass explicit
  approval") nobody asked for.
- **Prompt the model to ask the user for confirmation, then sync if they
  say yes, within the same request.** Not attempted here: Increment 009
  has no conversation state (Increment 008's explicit "no memory, no
  multi-turn" scope), so there is no mechanism for a "yes" in a later
  message to refer back to a specific proposed sync from an earlier one.
  Building that mechanism is real, separate scope, not a corner that can
  be cut inside a single-message request/response cycle.

## Why This Decision

Discovery's entire value is letting a user ask in plain language without
learning FRED identifiers first; it was never meant to also grant the AI
path a write capability by the back door. Keeping ingestion strictly
outside the AI path — reachable only through the existing, explicit
`POST /{series_id}/sync` a human (or a deliberate, separately-designed
future flow) calls directly — preserves the same small, auditable blast
radius [ADR-014](014-read-only-ai-tools.md) established for the whole AI
surface: the worst outcome of a discovery-driven request is an unhelpful
or incomplete *answer*, never new data appearing in PostgreSQL that
nobody explicitly asked to be persisted.

## Consequences / Tradeoffs

- Gains: the AI path's data-mutation surface remains exactly zero,
  regardless of how good discovery gets at finding real, legitimate,
  analyzable-looking series the user would probably want persisted. A
  reader auditing "can the AI write to the database" never has to
  special-case "except when it discovers something first."
- Cost: a real usability gap — "How has real GDP changed?" cannot be
  fully answered in one turn today if `GDPC1` isn't already persisted; the
  best the system can currently do is name the gap accurately. Verified
  directly: this is exactly what happens, and the model does not
  compensate by substituting a different, already-persisted series or
  inventing a plausible-sounding trend.

## Revisit When

- A well-scoped, explicitly user-confirmed ingestion flow is designed as
  its own increment (named directly in the task as future work) — likely
  requiring, at minimum, conversation state to carry a "yes, sync that"
  confirmation across turns, which Increment 009 deliberately does not
  build.
- Any design for AI-triggered ingestion should be evaluated against this
  ADR's reasoning specifically — the risk named here (a free-text request
  triggering an external fetch and a write) doesn't go away just because
  a later increment adds more scaffolding around it; it needs to be
  addressed on its own terms, not incidentally loosened.
