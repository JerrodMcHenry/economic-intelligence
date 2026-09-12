# ADR-014: AI-Accessible Tools Are Strictly Read-Only

## Status
Accepted

## Context

Increment 008 gave an LLM the ability to invoke application code on a
user's behalf, based on natural-language input it doesn't fully control
the interpretation of. `EconomicDataService` already has a write-capable,
FRED-backed method (`sync_series`) alongside its read-only ones. A
decision was needed about which capabilities, if any, an LLM should be
allowed to trigger.

## Decision

Every tool exposed to the model in this increment is read-only against
PostgreSQL and never calls FRED. `sync_series` (and `get_series`, its
FRED-backed read) are not exposed as tools at all — only
`get_observations`, `get_transformed_observations` (as `transform_series`),
and `AnalysisService.pipeline` (as `analyze_series`) are reachable, and
none of the three can write, sync, run a migration, execute raw SQL, or
touch the filesystem/shell/environment.

## Alternatives Considered

- **Expose a `sync_series` tool**, letting the model fetch and persist a
  series it determines is missing when asked about it. Rejected: this
  would mean a natural-language request — inherently more ambiguous and
  less controllable than a direct API call — could trigger an external
  HTTP call to FRED and a database write, initiated by an LLM's
  interpretation of free text rather than an explicit, deliberate user
  action against a specific endpoint. The risk isn't a specific expected
  failure so much as the category of risk: once a write is reachable from
  natural language, every future prompt-injection or misinterpretation
  concern becomes a data-integrity concern, not just an answer-quality
  one.
- **Expose sync but require a confirmation step** (e.g. the model
  proposes a sync, a separate action approves it). A reasonable future
  design, but real scope beyond "prove the tool-calling loop works" — it
  would need its own request/response contract, its own state between the
  proposal and the approval, and its own failure modes, none of which
  this foundation increment needs to get right yet.
- **Trust the model's own judgment to avoid destructive actions** (expose
  broader capabilities, rely on the system instruction to keep the model
  from misusing them). Rejected outright: an instruction is a request to
  the model, not an enforcement mechanism (the same reasoning already
  applied to tool *arguments* — see the journal's "never trust
  model-generated arguments" section — applies equally to *which actions*
  are reachable at all). If a capability must never run without explicit
  human intent, the correct control is not exposing it, not asking the
  model nicely not to use it.

## Why This Decision

A read-only AI surface means the worst outcome of a misinterpreted
request, an adversarial prompt, or a model bug is a wrong or unhelpful
*answer* — never wrong or unhelpful *data*. That's a categorically
smaller failure mode, and it's the appropriate bar for a foundation
increment whose stated goal is proving the tool-calling mechanism works
reliably, not delivering full AI-driven data management. This also keeps
the safety property small and provable: with exactly three tools, all
read-only, "the AI cannot mutate anything" is a claim that can be (and
was) verified directly — by inspecting every handler for absence of
`FREDClient`/write calls, and by confirming database row counts and
timestamps are unchanged after real, live tool-calling requests — rather
than a claim resting on trusting a much larger, harder-to-audit surface.

## Consequences / Tradeoffs

- Gains: the blast radius of any AI-layer bug, prompt injection, or model
  misbehavior is bounded to "gave a wrong answer," never "changed
  persisted data" — a categorically safer default for the first AI
  capability in this project.
- Cost: the assistant cannot help a user who asks about a series that
  isn't persisted yet — it can only explain the limitation
  (`series_not_found`), not fetch the data itself. This is a deliberately
  accepted gap for this increment, not an oversight; see the journal's
  "no automatic FRED sync" reasoning.

## Revisit When

- A specific, well-scoped write capability is genuinely needed from the
  AI path (e.g. "sync this series" as an explicit, confirmed action) —
  design that as its own increment, with its own confirmation/audit
  story, rather than loosening this policy incidentally while adding an
  unrelated feature.
- This project adds authentication/authorization (explicitly out of scope
  for Increment 008) — a write-capable AI tool without a concept of
  *who* is asking would be a materially different risk than one gated
  behind an authenticated, authorized user.
