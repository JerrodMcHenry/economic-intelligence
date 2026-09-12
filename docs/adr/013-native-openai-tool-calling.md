# ADR-013: Native OpenAI Tool Calling, Not an Agent Framework

## Status
Accepted

## Context

Increment 008 needed to let an LLM invoke this project's deterministic
engine (persisted retrieval, single-series transformation, multi-series
analysis) in response to a natural-language request, with a small,
bounded number of tool-calling rounds. A mechanism was needed for
declaring tools to the model, receiving its tool-call requests, executing
them, and returning results so the model could produce a final answer.

## Decision

Use the official OpenAI Python SDK's Responses API
(`client.responses.create`) directly, with native function/tool calling.
No agent framework (LangChain, LangGraph, LlamaIndex, Semantic Kernel, or
a custom one) was introduced.

## Alternatives Considered

- **LangChain / LangGraph.** Provide their own tool-registration
  decorators, agent executors, and graph-based control flow. Rejected:
  this project needs exactly three fixed tools and a small bounded loop —
  a shape the raw SDK already expresses directly
  (`tools=[...]`, check `response.output` for `function_call` items,
  send `function_call_output`s back). A framework's abstractions
  (its own tool base classes, its own executor loop, its own exception
  hierarchy) would sit *between* this project's code and the actual
  OpenAI API surface, adding indirection without adding a capability this
  increment needs.
- **LlamaIndex.** Oriented primarily around retrieval-augmented
  generation and document indexing — this increment has no RAG, no
  document store, and no vector search; adopting it would mean bringing
  in machinery for a problem this increment doesn't have.
- **A custom lightweight agent abstraction built in-house** (e.g. a
  generic `Agent`/`Tool` base class this project defines itself).
  Rejected for the same reason the project's engineering rules
  discourage generic frameworks elsewhere (repositories, transformations):
  building an abstraction layer for a single concrete use case, before a
  second one exists to prove the abstraction's shape is right, is
  premature generalization.

## Why This Decision

The Responses API's native tool-calling loop already *is* almost exactly
the loop this increment needs: declare tools, read `function_call` items
from the output, execute them, send `function_call_output`s back via
`previous_response_id`. Every piece of "orchestration" this increment
required — the `while` loop, the round counter, the dict-based tool
dispatch — is a small amount of this project's own code sitting directly
on top of the SDK, fully visible and auditable in `app/services/ai.py`
and `app/services/ai_tools.py`. An agent framework's value proposition
(coordinating many tools, complex branching, multi-step autonomous
planning) doesn't apply yet — this is explicitly a *foundation*, not an
autonomous agent, and the task was to prove the LLM → tool → deterministic
engine → LLM path works reliably, not to build a general-purpose
agent runtime.

## Consequences / Tradeoffs

- Gains: the entire AI integration surface is a few hundred lines of this
  project's own code calling one well-documented SDK method, with no
  framework-specific concepts (chains, graphs, agents-as-a-type) to learn
  or debug. Verifying the SDK's actual current behavior (see the journal)
  was straightforward because there was only one library's types to
  inspect, not a framework's abstraction over it.
- Cost: if a future increment needs genuinely complex multi-agent
  coordination, longer-running autonomous planning, or a much larger tool
  surface, some of what a framework provides (structured multi-step
  planning, built-in memory/state management across many tool types)
  would need to be built by hand or adopted later — this project isn't
  paying that cost preemptively, and accepts rebuilding some of it later
  if it's ever actually needed.

## Revisit When

- The tool surface grows enough (well beyond three tools, or genuinely
  heterogeneous tool types) that hand-rolled dispatch and looping becomes
  real, recurring engineering burden rather than a few hundred readable
  lines.
- A real requirement emerges for multi-step autonomous planning, parallel
  agent coordination, or conversation memory spanning many turns — at
  that point, evaluate a framework (or a larger in-house abstraction)
  against the *actual* requirement, not preemptively.
