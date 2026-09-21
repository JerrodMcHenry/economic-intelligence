"""Pure, deterministic implementation of `rates_v1.0` (frozen and
normative in `docs/methodology/rates-v1.0.md`).

No I/O, no framework, no provider knowledge, no randomness, no model --
the same discipline `app.domain.inflation`/`app.domain.labor` already
enforce, checked by `tests/test_domain_architectural_independence.py`.
Every function here is a total function of its arguments: the same
inputs always produce the same outputs.

Three deliberate properties, each of which the methodology states and
this module implements literally:

1. **Windows are counted in OBSERVATIONS, never calendar days.** A
   "5-session change" is the latest observation minus the observation
   five published sessions earlier, whatever calendar dates those are.
   Rates series skip weekends and holidays, so a calendar-day rule
   would need a fallback policy; an observation-count rule needs none
   and is exactly reproducible by hand from the stored series.

2. **Alignment is exact, never fuzzy.** A derived metric combining two
   series (a spread, an inflation compensation) requires both series to
   have an observation on the SAME date. No nearest-date search, no
   forward-fill, no interpolation: a missing counterpart produces an
   explicitly unavailable result carrying the reason.

3. **Missing is never zero.** Every function distinguishes "no data"
   from "no change" in its return type.
"""

from dataclasses import dataclass
from datetime import date

# Basis-point arithmetic is done on percentage-point inputs (a par yield
# is published as e.g. 4.76 meaning 4.76%), so one percentage point is
# 100 basis points. Results are rounded to this many decimal places to
# remove binary floating-point residue (0.30000000000000004) while
# preserving far more precision than the two decimals the provider
# actually publishes.
_BASIS_POINT_DECIMALS = 6
_PERCENT_DECIMALS = 6


@dataclass(frozen=True)
class RateObservation:
    """One dated level for one series, as persisted. `value` is
    nullable because a provider legitimately publishes a missing value
    for a date (e.g. a maturity not offered that day)."""

    observation_date: date
    value: float | None


@dataclass(frozen=True)
class WindowChange:
    """The result of one windowed change calculation. `available` is
    False whenever the window could not be formed from real data, in
    which case every other field is None."""

    available: bool
    sessions: int
    change_basis_points: float | None
    from_date: date | None
    from_value: float | None
    to_date: date | None
    to_value: float | None


@dataclass(frozen=True)
class AlignedPair:
    """Two series' values on one exact shared date."""

    observation_date: date
    first_value: float
    second_value: float


@dataclass(frozen=True)
class RankResult:
    """Deterministic rank of one value against a population. Counting
    only -- no distribution is fitted and nothing is predicted."""

    available: bool
    observation_count: int
    percentile_rank: float | None
    magnitude_percentile_rank: float | None
    minimum: float | None
    maximum: float | None


def to_basis_points(percentage_points: float) -> float:
    """Convert a percentage-point quantity to basis points.

    1 percentage point = 100 basis points, so 0.15pp -> 15.0bp. The one
    conversion in the codebase; nothing else multiplies by 100 to mean
    this.
    """
    return round(percentage_points * 100.0, _BASIS_POINT_DECIMALS)


def basis_point_change(from_value: float, to_value: float) -> float:
    """The change from `from_value` to `to_value`, in basis points.

    Both arguments are percentage-point levels (4.25 meaning 4.25%).
    4.25 -> 4.40 is +15.0bp; the sign always follows the direction of
    travel (later minus earlier).
    """
    return to_basis_points(to_value - from_value)


def percentage_point_difference(minuend: float, subtrahend: float) -> float:
    """`minuend - subtrahend`, in percentage points, rounded to remove
    floating-point residue. Used for inflation compensation, which is
    reported in percent rather than basis points."""
    return round(minuend - subtrahend, _PERCENT_DECIMALS)


def usable_observations(observations: list[RateObservation]) -> list[RateObservation]:
    """Chronologically ascending observations that carry a real value.

    A null-valued observation is dropped rather than treated as zero or
    carried forward: for window counting, a session the provider did
    not publish a value for is not a session this methodology can use.
    Input order is not trusted -- the result is always sorted by date.
    """
    return sorted(
        (obs for obs in observations if obs.value is not None),
        key=lambda obs: obs.observation_date,
    )


def latest_observation(observations: list[RateObservation]) -> RateObservation | None:
    """The most recent usable observation, or None if there is none."""
    usable = usable_observations(observations)
    return usable[-1] if usable else None


def change_over_sessions(observations: list[RateObservation], sessions: int) -> WindowChange:
    """The change in basis points over exactly `sessions` published
    sessions, ending at the latest usable observation.

    Requires `sessions + 1` usable observations; with fewer, the result
    is explicitly unavailable rather than computed over a shorter
    window. `sessions` must be >= 1.
    """
    if sessions < 1:
        raise ValueError("sessions must be at least 1")

    usable = usable_observations(observations)
    if len(usable) < sessions + 1:
        return WindowChange(
            available=False,
            sessions=sessions,
            change_basis_points=None,
            from_date=None,
            from_value=None,
            to_date=None,
            to_value=None,
        )

    current = usable[-1]
    past = usable[-1 - sessions]
    # Both values are non-None by construction of `usable_observations`.
    assert current.value is not None and past.value is not None
    return WindowChange(
        available=True,
        sessions=sessions,
        change_basis_points=basis_point_change(past.value, current.value),
        from_date=past.observation_date,
        from_value=past.value,
        to_date=current.observation_date,
        to_value=current.value,
    )


def recent_session_observations(
    observations: list[RateObservation],
    sessions: int,
    as_of: date,
) -> list[RateObservation]:
    """The latest `sessions` USABLE observations at or before `as_of`,
    chronologically ascending.

    Selection only -- no arithmetic, no interpolation, no carry-forward.
    A date the provider published no value for is simply absent from the
    result, exactly as `usable_observations` leaves it: this is the same
    rule every `rates_v1.0` window already counts by, so a chart drawn
    from this list and a change computed by `change_over_sessions` are
    reading the same population.

    Fewer than `sessions` available is a normal outcome, not an error --
    the caller reports the real count rather than padding it.
    """
    if sessions < 1:
        raise ValueError("sessions must be at least 1")

    usable = [obs for obs in usable_observations(observations) if obs.observation_date <= as_of]
    return usable[-sessions:]


def historical_session_changes(observations: list[RateObservation], sessions: int) -> list[tuple[date, float]]:
    """Every `sessions`-length change available in the history, as
    `(end_date, change_basis_points)` in ascending date order.

    This is the population the current change is ranked against. Each
    element uses the same construction as `change_over_sessions`, so the
    final element equals that function's result whenever both are
    available.
    """
    if sessions < 1:
        raise ValueError("sessions must be at least 1")

    usable = usable_observations(observations)
    changes: list[tuple[date, float]] = []
    for index in range(sessions, len(usable)):
        past = usable[index - sessions]
        current = usable[index]
        assert current.value is not None and past.value is not None
        changes.append((current.observation_date, basis_point_change(past.value, current.value)))
    return changes


def rank_against(population: list[float], value: float) -> RankResult:
    """Rank `value` within `population` by strict "less than" counting.

    `percentile_rank` is the share of the population strictly less than
    `value` in signed terms; `magnitude_percentile_rank` is the share
    whose absolute value is strictly less than `abs(value)`. Strict
    comparison means an all-ties population ranks at 0.0 rather than
    silently reading as "unremarkable but positive" -- deliberate, and
    stated in the methodology.

    An empty population is explicitly unavailable, never 0.0.
    """
    if not population:
        return RankResult(
            available=False,
            observation_count=0,
            percentile_rank=None,
            magnitude_percentile_rank=None,
            minimum=None,
            maximum=None,
        )

    count = len(population)
    below = sum(1 for item in population if item < value)
    below_magnitude = sum(1 for item in population if abs(item) < abs(value))
    return RankResult(
        available=True,
        observation_count=count,
        percentile_rank=round(below / count, _PERCENT_DECIMALS),
        magnitude_percentile_rank=round(below_magnitude / count, _PERCENT_DECIMALS),
        minimum=min(population),
        maximum=max(population),
    )


def align_on_exact_date(
    first: list[RateObservation],
    second: list[RateObservation],
) -> list[AlignedPair]:
    """Every date on which BOTH series have a usable value, ascending.

    Exact-date intersection only. A date present in one series and
    absent (or null) in the other is omitted entirely -- never
    interpolated, never forward-filled, never matched to a nearby date.
    This is the single rule that keeps every derived two-series metric
    honest.
    """
    second_by_date = {obs.observation_date: obs.value for obs in usable_observations(second)}
    pairs: list[AlignedPair] = []
    for obs in usable_observations(first):
        counterpart = second_by_date.get(obs.observation_date)
        if counterpart is None:
            continue
        assert obs.value is not None
        pairs.append(
            AlignedPair(observation_date=obs.observation_date, first_value=obs.value, second_value=counterpart)
        )
    return pairs


def spread_series(long_maturity: list[RateObservation], short_maturity: list[RateObservation]) -> list[RateObservation]:
    """The derived curve-spread series in PERCENTAGE POINTS: longer
    maturity minus shorter maturity, on exactly-shared dates only.

    Percentage points, not basis points, deliberately: every consumer of
    a series in this module (`change_over_sessions`,
    `historical_session_changes`) treats a series value as a
    percentage-point level and converts differences to basis points
    itself. A series already expressed in basis points would therefore
    be multiplied by 100 a second time, reporting a 2bp move as 200bp.
    Callers that want the spread LEVEL in basis points convert once, at
    the presentation boundary, via `to_basis_points`.

    A negative value is an inversion; this module assigns it no meaning
    beyond the arithmetic (no "inverted" label, no recession reading --
    see the methodology's "does NOT support").
    """
    return [
        RateObservation(
            observation_date=pair.observation_date,
            value=percentage_point_difference(pair.first_value, pair.second_value),
        )
        for pair in align_on_exact_date(long_maturity, short_maturity)
    ]


def inflation_compensation_series(
    nominal: list[RateObservation],
    real: list[RateObservation],
) -> list[RateObservation]:
    """The derived market-implied inflation compensation series in
    PERCENTAGE POINTS: nominal par yield minus real (TIPS) par yield, on
    exactly-shared dates only.

    Deliberately NOT called an inflation expectation or forecast: the
    difference contains an inflation risk premium and a TIPS liquidity
    premium that `rates_v1.0` does not attempt to separate.
    """
    return [
        RateObservation(
            observation_date=pair.observation_date,
            value=percentage_point_difference(pair.first_value, pair.second_value),
        )
        for pair in align_on_exact_date(nominal, real)
    ]
