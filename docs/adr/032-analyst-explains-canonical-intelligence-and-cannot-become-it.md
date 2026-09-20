# ADR-032: The MacroChipz Analyst Explains Canonical Intelligence and Is Structurally Incapable of Becoming It

## Status
Accepted

## Context

Increment #33 adds the first generative-AI capability to a system that has spent thirty increments making its economic conclusions deterministic, versioned, reproducible and provenance-bearing. The question is not whether a language model can write a good paragraph about inflation. It is whether adding one can be done without putting any of that at risk.

This project already has direct, measured evidence of the failure mode. Increment #9 built model-driven tool orchestration and corrected it three times — prompt guidance, then a deterministic execution gate, then dynamic tool-schema shaping. The final attempt's own acceptance measurement was that **the model supplied a `series_id` outside the enum it had just been offered in roughly 60% of later-round calls**, with 16 of 28 live trials exhausting the round budget. ADR-018 records this as SUPERSEDED — FAILED ACCEPTANCE GATE, with the durable lesson stated at the top: *a declared schema constraint under non-strict function calling is a strong hint, not an enforcement mechanism, and should never be treated as one for anything correctness- or safety-load-bearing.*

Three existing decisions bear directly on this one. ADR-013 chose native tool calling over an agent framework. ADR-014 made every model-reachable tool read-only. ADR-021 established, for curated frontend explanation content, that **explanations never determine canonical results** — a `WhyThisState` component is one implementation choice away from becoming a second, informal implementation of a frozen methodology. #33 adds generated prose to a surface where ADR-021's risk was already recognised for hand-written prose.

The governing rule for this increment: **AI can speak for the system. AI cannot become the system.**

## Decision

**The Analyst is an optional interpretive layer that receives a deterministic, server-built context packet and returns validated prose, and every prohibition that matters is enforced by architecture rather than by instructions.**

- **The model-facing module is structurally incapable of reaching data.** `app/services/analyst.py` imports no SQLAlchemy, no `app.db`, no repository, and no canonical service, and no method on `AnalystService` accepts a `Session`. The route builds the packet inside `session_scope()`, closes it, and then calls the service with the packet alone. "The LLM cannot touch canonical data" is a property of the import graph, asserted by AST inspection — not a sentence in a prompt.

- **No tools, and exactly one generation per request.** The model is given a finished packet and asked for prose; there is no tool to call, no round to continue, and no next action to choose. Asserted by counting `responses.create` call sites and by checking that no loop encloses it. This is the direct, deliberate consequence of ADR-018's measurement: an orchestration loop the model drives is not made safe by bounding it.

- **A browser names a context; it never supplies one.** `AnalystExplainRequest` carries only `{context: {type, recorded_result_id?, monitor?}, question}` with `extra="forbid"`. It has no state field, no evidence field, no numbers. A client that could supply those could make the Analyst explain a fabricated economy, so the request contract's poverty is the contract.

- **Context types are an allow-list expressed as a `Literal`**, so an unsupported value is rejected by framework validation before any application code runs. Rates is included as a context but carries `canonical_state: null`, because `rates_v1.0` publishes levels and derived metrics rather than a classification — and fabricating a state to make packets uniform would invent intelligence the engine does not produce.

- **Packet values are pre-formatted strings carrying their units.** `"158,268,000 jobs"`, not `158268000`. A bare number whose unit must be inferred is exactly what produced a 1,000x error inside #32's own deterministic code; a model is a worse place to relocate that risk than a service is.

- **The model may cite only ids the packet published, and every citation is re-resolved server-side.** It never produces URLs, source names or provenance. An id the packet does not contain is dropped and counted; a valid id has its label and value taken from the packet, so even a correct citation cannot carry model-authored provenance. The response schema is deliberately **static** — injecting the valid ids as an enum was possible and rejected, because ADR-018's whole finding is that a dynamically shaped schema is a hint. Validation is the enforcement.

- **Failure is contained and never retried into a second bill.** Unconfigured, timeout, connection, auth, rate limit, 5xx, refusal, empty completion, malformed JSON and schema-validation failure each map to a contained 503 with no provider detail. A malformed answer is not retried. `max_retries=1` covers only the SDK's transient conditions, which never re-run a completed generation.

- **Availability is a `200`, not an error.** Whether an optional integration is configured is not a failure, and the answer names no setting — a deployment with no provider keeps every canonical page working and renders one sentence where the Analyst would be.

- **Instructions are versioned code, and are explicitly a soft control.** `macrochipz_analyst_v1` lives in a reviewed module and is recorded in every response's metadata. It shapes tone, scope and honesty; it is not the security boundary, and the architecture above holds if the model ignores all of it.

- **No canonical side effects, ever.** Nothing on this path writes an observation, a version, a recorded result, provenance or a methodology. Repeated questions produce repeated explanations and change nothing. No chat memory, no threads, no persistence.

## Alternatives Considered

- **Revive Increment #9's orchestration with a higher round budget.** Rejected on its own evidence: #9's journal notes raising the budget "would only have delayed the same failure for a slightly larger candidate pool, and would have hidden genuinely wasteful behavior rather than fixing it."
- **Give the model read-only database tools (ADR-014's posture).** Rejected as unnecessary here and therefore unjustifiable: the Analyst's job is to explain one page's already-computed intelligence, which the server can assemble completely and deterministically. A tool would add a decision the model does not need to make.
- **Accept a context packet from the browser to save a round trip.** Rejected outright. It is the single change that would let a client dictate the facts the Analyst explains.
- **Put the valid evidence ids in the response schema as an enum.** Rejected: ADR-018 measured how well that works. Kept as server-side validation instead.
- **Retry once on malformed output to improve the success rate.** Rejected as the default: it doubles cost on exactly the requests already going wrong, and "this attempt failed" is an honest answer. A second call would need its own justification.
- **Trust the system instruction to prevent data access, forecasting and advice.** Rejected as the *primary* control while kept as a secondary one. Every prohibition that would matter if violated is also structurally impossible.
- **Let the Analyst generate suggested questions.** Rejected: an unreviewed prompt the product puts in a user's mouth, and a billable request on every page load. Suggestions are deterministic UI copy.
- **Put an Analyst surface on Home and Overview.** Rejected: one contextual surface per analytical page is enough, and Overview has a standing guard that it imports nothing AI-related.

## Consequences

- MacroChipz gains a plain-English explanation layer over Inflation, Labor, Rates and point-in-time history, with visible evidence drawn from its own provenance.
- The Analyst is genuinely optional. With no provider configured — the current state of this development machine — every canonical page, replay and history surface behaves exactly as before.
- Answer quality now depends on a probabilistic component, and is therefore *not* covered by the deterministic guarantees around it. The evaluation suite asserts objective properties; prose quality requires human review, and the suite says so rather than implying otherwise.
- A future probabilistic product (a forecast, a confidence model) does not inherit permission from this ADR. It would need its own, because the Analyst is explicitly allowed to describe only what the deterministic engine already established.
