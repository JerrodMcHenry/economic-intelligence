# ADR-010: Pure Transformation Engine Over Persisted Data, With No Derived-Data Persistence

## Status
Accepted

## Context

Increment 005 needed to compute derived series (`absolute_change`,
`percent_change`, `moving_average`) from the raw observations Increment
003 persisted. Two related design questions came with it: where should
the actual mathematical logic live relative to the existing
route/service/repository layers, and should the computed results be
stored anywhere once produced?

These two questions turned out to have one shared answer, which is why
they're recorded together rather than as separate ADRs: a transformation
is fully and deterministically reproducible from the raw observations it
was computed from plus its parameters (transformation name, window) — so
neither "where does the math live" nor "should the result be cached"
needed a different answer than "keep it pure, keep it recomputed."

## Decision

- Introduce a new architectural layer, `app/domain/`, holding only pure
  functions (`absolute_change`, `percent_change`, `moving_average`) with
  no FastAPI, SQLAlchemy, FRED/httpx, environment-variable, or logging
  imports, and no mutation of anything outside a function call. Given the
  same input, a function always returns the same output.
- Never persist a derived (transformed) value. `.../transform` recomputes
  from `economic_observations` on every request; no derived-data table,
  no cache.

## Alternatives Considered

- **Compute transformations as private methods on `EconomicDataService`.**
  Would have avoided introducing a new package. Rejected: it would mix two
  genuinely different kinds of code in one class — I/O orchestration
  (sessions, repository calls) and pure arithmetic — making the arithmetic
  harder to test in isolation (every test would need a session/repository
  in scope even to check `4.0, 4.2 -> null, 0.2`) and harder to *trust* as
  side-effect-free, since nothing would structurally prevent a future edit
  from reaching for `self._fred_client` or a database call inside what was
  supposed to be pure math.
- **A transformation "strategy" framework** (abstract base class, a
  registry mapping names to strategy objects, a plugin interface).
  Rejected as unwarranted for three fixed, fully-specified functions —
  the project's own engineering rules single this out explicitly
  ("do not introduce strategy frameworks... unless genuinely necessary").
  Plain functions dispatched by a simple `if`/`elif` in the service are
  the whole solution three cases actually need.
- **Persist derived values in a new table** (e.g.
  `economic_transformed_observations`), refreshed on sync or computed
  lazily and cached. Rejected: it would introduce staleness (does a
  stored derived value get invalidated when `sync` updates the underlying
  raw data?), versioning (if the transformation formula itself ever
  changes, are old stored rows now silently wrong?), and duplicate storage
  — all to save recomputing values that are cheap to recompute at this
  project's current data volume. This is exactly the kind of premature
  optimization the project's engineering rules ask to avoid.
- **A caching layer (e.g. Redis) in front of the computation**, without a
  dedicated table. Same objection as above, one layer removed: it still
  introduces an invalidation question with no corresponding, demonstrated
  performance problem to justify it.

## Why This Decision

Purity and non-persistence reinforce each other: a function with no I/O
and no hidden state is the cheapest, most trustworthy thing to recompute
on every call, and *because* it's cheap and trustworthy to recompute,
there's no pressure to cache its output. Choosing one without the other
would have been a weaker design — a pure engine feeding a caching layer
would still need cache-invalidation logic; a persisted-derived-data table
fed by impure computation would need to trust that the computation was
side-effect-free without any structural guarantee that it was.

Keeping the transformation code in its own package with a stated import
restriction also makes "this code has no side effects" a fact checkable
by inspecting imports, not a claim resting on the author's memory of what
the functions were supposed to do — verified directly for this increment
by `grep`ing the module's imports and by proving (via an exploding-mock
test) that the transform endpoint never reaches FRED even indirectly.

## Consequences / Tradeoffs

- Gains: the transformation engine is trivially unit-testable without a
  database, a running server, or mocks of any kind — verified in this
  increment by testing all three functions' example cases and
  determinism in well under a second of test runtime. No invalidation,
  versioning, or staleness concern exists for derived data, because none
  of it is retained anywhere. Adding a fourth transformation later means
  adding one more pure function, not touching persistence at all.
- Cost: every `.../transform` request recomputes from raw data rather
  than reading a precomputed value — acceptable at current data volumes
  (single series, low thousands of observations at most), but a real cost
  that would need revisiting if either the data volume or the request
  volume against this endpoint grew substantially.
- Cost: the boundary-context problem (a transformed value near the start
  of a requested range needs a preceding raw observation) has to be
  solved by the service on every call, rather than being solved once and
  cached — a direct consequence of never storing intermediate or final
  derived state.

## Revisit When

- Recomputing transformations on every request becomes a measured
  performance problem (not a hypothetical one) — at that point, a caching
  layer with an explicit invalidation policy tied to `sync` events would
  be the natural next step, still computed by these same pure functions
  underneath.
- A transformation is added whose "purity" is genuinely harder to
  guarantee (e.g. one that would benefit from a numerical library) — at
  that point, revisit whether `app/domain/`'s no-dependencies stance still
  holds, per the project's existing constraint against adding a
  numerical/data-science dependency without a demonstrated need.
- The number of transformations grows enough that a plain `if`/`elif`
  dispatch in the service becomes a real readability problem — at that
  point, a small dispatch table (not a strategy framework) is the
  proportionate next step.
