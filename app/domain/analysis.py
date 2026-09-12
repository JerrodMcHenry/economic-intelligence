"""Pure, deterministic cross-series analysis over economic observations.

Like `app/domain/transformations.py`, this module has no knowledge of
FastAPI, HTTP, FRED, SQLAlchemy, database sessions, environment variables,
or logging, and never mutates global state. Given the same inputs, every
function here always produces the same output.

`app/models/series.py`'s `Observation` and `app/models/analysis.py`'s
`ComparisonObservation` are reused as input/output shapes (plain Pydantic
data, not FastAPI) rather than duplicating a parallel set of plain types.
"""

from app.models.analysis import ComparisonObservation
from app.models.series import Observation


def align_series(
    observations_a: list[Observation], observations_b: list[Observation]
) -> list[ComparisonObservation]:
    """Exact-date inner alignment between two observation lists.

    Only dates present in *both* lists are included -- never interpolated,
    forward/backward filled, resampled, or matched to the nearest
    available date. A matched date's `value_a`/`value_b` may still be
    `None` if the source observation for that date was itself a missing
    value; the pair is still returned so the caller can see that the
    dates matched. Results are always chronologically ascending,
    regardless of the input lists' order.
    """
    values_a = {obs.date: obs.value for obs in observations_a}
    values_b = {obs.date: obs.value for obs in observations_b}
    common_dates = sorted(values_a.keys() & values_b.keys())
    return [
        ComparisonObservation(date=matched_date, value_a=values_a[matched_date], value_b=values_b[matched_date])
        for matched_date in common_dates
    ]


def calculate_spread(aligned: list[ComparisonObservation]) -> list[ComparisonObservation]:
    """spread = value_a - value_b for each aligned pair.

    `None` if either side is `None` for that date -- never substitutes
    zero, a prior value, or an interpolated value. This is purely
    arithmetic: it does not check or reconcile the two series' units (see
    `app/models/series.py`'s `SeriesSummary.units` in the response for
    each series' actual units) -- a spread between series with different
    units is still computed; its economic meaningfulness is left to the
    caller to judge.
    """
    return [
        ComparisonObservation(
            date=point.date,
            value_a=point.value_a,
            value_b=point.value_b,
            spread=(point.value_a - point.value_b)
            if point.value_a is not None and point.value_b is not None
            else None,
        )
        for point in aligned
    ]


def count_usable_pairs(aligned: list[ComparisonObservation]) -> int:
    """Count aligned pairs where both value_a and value_b are non-null --
    the population `pearson_correlation` (and a spread's non-null results)
    actually operates over, as distinct from `len(aligned)` (every
    matching date, nulls included)."""
    return sum(1 for point in aligned if point.value_a is not None and point.value_b is not None)


def pearson_correlation(aligned: list[ComparisonObservation]) -> float | None:
    """Pearson product-moment correlation coefficient over usable numeric
    pairs (both value_a and value_b non-null) within `aligned`.

    Returns `None` -- never `NaN`, infinity, or a substituted `0` -- when
    fewer than 2 usable pairs exist, or when either side has zero
    variance (a constant series has no defined linear relationship with
    anything, including itself). The result is clamped to [-1, 1] to
    absorb microscopic floating-point overshoot from the formula; a
    result outside that range would only ever be floating-point noise,
    never a mathematically real value.
    """
    usable = [(point.value_a, point.value_b) for point in aligned if point.value_a is not None and point.value_b is not None]
    n = len(usable)
    if n < 2:
        return None

    xs = [a for a, _ in usable]
    ys = [b for _, b in usable]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    variance_x = sum((x - mean_x) ** 2 for x in xs)
    variance_y = sum((y - mean_y) ** 2 for y in ys)

    if variance_x == 0 or variance_y == 0:
        return None

    r = covariance / (variance_x * variance_y) ** 0.5
    return max(-1.0, min(1.0, r))
