# ADR-011: Exact-Date Inner Alignment for Multi-Series Comparison

## Status
Accepted

## Context

Increment 006 needed to pair up observations from two independently
persisted series so they could be compared (aligned, spread against each
other, correlated). Two series will not, in general, share the same
observation dates by coincidence — a provider can revise its publication
calendar, one series can report more or less frequently than another, or
syncs can simply happen at different times — so a rule was needed for
*which* dates from each series get paired with which.

## Decision

Pair observations by **exact date match only** — an inner join on the
date field, implemented as a set intersection of each series' observation
dates. A date present in only one series is excluded entirely. No
interpolation, forward/backward filling, resampling to a common
frequency, or nearest-date matching is performed.

## Alternatives Considered

- **Array-position pairing** (`series_a[0]` with `series_b[0]`,
  `series_a[1]` with `series_b[1]`, …). Rejected outright, not as a
  refinement but as simply incorrect: the moment the two series' date
  sets diverge at all — which is the common case, not an edge case — this
  silently pairs observations from different calendar dates while
  producing output that looks exactly like a correctly-aligned pair, with
  nothing in its shape hinting that `value_a` and `value_b` don't actually
  describe the same point in time.
- **Nearest-date matching** (pair each date in one series with the
  closest available date in the other, within some tolerance). Would
  increase the number of matched pairs for series with slightly offset
  reporting schedules, but introduces a tolerance parameter to design and
  justify, and starts making an implicit claim ("close enough in time to
  compare") that the project isn't in a position to make confidently for
  arbitrary series pairs yet.
- **Interpolation/resampling to a common frequency** (e.g. resample both
  series to monthly, filling gaps). Rejected for the same reason
  Increment 005 never interpolates missing values within a single
  series: any interpolated point is a value that was never actually
  observed, and treating it as equivalent to real data risks presenting
  a fabricated number as if it came from the source.

## Why This Decision

Exact-date matching is the only option of the three that never fabricates
or guesses a relationship between two data points that weren't actually
reported for the same date. It's also the simplest correct
implementation: a set intersection of two `{date: value}` mappings, with
no tolerance window, no resampling calendar, and no interpolation formula
to get subtly wrong. This matches the same missing-value discipline
established for single-series transformations in Increment 005 (never
substitute a value that wasn't actually observed) — applied here to the
question of "does a comparable observation exist at all," not just
"is this observation's value present."

The tradeoff is fewer matched pairs for series with genuinely different
reporting calendars, and this project accepts that tradeoff explicitly:
undercounting comparable dates is a safe failure (the caller sees a
smaller, definitely-correct `matching_pairs`), while overcounting via a
looser matching rule risks quietly comparing dates that don't really
correspond to each other.

## Consequences / Tradeoffs

- Gains: every returned pair is definitely, unambiguously the same
  calendar date in both series — no tolerance window or interpolation
  formula to justify or get wrong, and no silent misalignment possible
  even if the two series' date sets differ substantially.
- Cost: two series with different native frequencies (e.g. a monthly
  series and a quarterly one) will have very few or zero exact-date
  matches, even though a meaningfully comparable relationship might exist
  between them at a coarser granularity. Increment 006 does not attempt
  to solve this — a caller comparing series of different frequencies gets
  an honestly small `matching_pairs`, not a resampled approximation.

## Revisit When

- A real need emerges to compare series of different native frequencies
  (e.g. monthly vs. quarterly) — at that point, a deliberate resampling
  or nearest-date-with-tolerance strategy would need its own design and
  its own ADR, offered as an explicit alternative alignment mode rather
  than a silent change to this default.
- Users report that exact-date matching excludes clearly-comparable data
  due to trivial calendar differences (e.g. a series published on the
  1st vs. one published on the last day of the month) — evaluate a
  narrow, explicit tolerance window at that point, rather than
  generalizing preemptively now.
