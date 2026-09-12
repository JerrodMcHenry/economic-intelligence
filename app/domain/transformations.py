"""Pure, deterministic transformations over economic observations.

This module has no knowledge of FastAPI, HTTP, FRED, SQLAlchemy, database
sessions, environment variables, or logging, and it never mutates global
state. Every function here takes plain data in and returns plain data out:
given the same `observations` and parameters, a function always produces
the same result. `app/models/series.py`'s `Observation` and
`TransformedObservation` are reused as the input/output shapes (they're
just data -- Pydantic, not FastAPI), so this module doesn't need to
duplicate a parallel set of plain types.

Every function here assumes `observations` is already in ascending
chronological order -- that's the caller's (the service's) responsibility
to guarantee, since only the caller knows where the data came from.
"""

from app.models.series import Observation, TransformedObservation


def absolute_change(observations: list[Observation]) -> list[TransformedObservation]:
    """Point-to-point difference: value[t] - value[t-1].

    The first observation has no predecessor, so its result is always
    null. A null current or immediately previous source value also
    produces a null result -- never skipped forward/backward to find an
    earlier non-null value. For a percentage-valued source series, this
    is a percentage-*point* change, not a percent change (see
    `percent_change`).
    """
    results: list[TransformedObservation] = []
    previous_value: float | None = None
    for index, obs in enumerate(observations):
        if index == 0 or previous_value is None or obs.value is None:
            change = None
        else:
            change = obs.value - previous_value
        results.append(TransformedObservation(date=obs.date, original_value=obs.value, value=change))
        previous_value = obs.value
    return results


def percent_change(observations: list[Observation]) -> list[TransformedObservation]:
    """Point-to-point percent change: ((current - previous) / previous) * 100.

    Same first-observation and missing-value alignment rules as
    `absolute_change`, plus: a zero previous value always produces a null
    result -- this never divides by zero, returns infinity, or substitutes
    zero.
    """
    results: list[TransformedObservation] = []
    previous_value: float | None = None
    for index, obs in enumerate(observations):
        if index == 0 or previous_value is None or obs.value is None or previous_value == 0:
            change = None
        else:
            change = ((obs.value - previous_value) / previous_value) * 100
        results.append(TransformedObservation(date=obs.date, original_value=obs.value, value=change))
        previous_value = obs.value
    return results


def moving_average(observations: list[Observation], window: int) -> list[TransformedObservation]:
    """Simple moving average over `window` consecutive chronological points.

    A result is null until at least `window` points have been seen (i.e.
    there are fewer preceding observations -- including the current one --
    than `window`), and null if any source value within that window is
    null. Missing values are never forward/backward filled, interpolated,
    or silently skipped -- a null anywhere in the window nulls the result.
    """
    results: list[TransformedObservation] = []
    for index, obs in enumerate(observations):
        if index + 1 < window:
            average = None
        else:
            window_values = [o.value for o in observations[index + 1 - window : index + 1]]
            average = None if any(value is None for value in window_values) else sum(window_values) / window
        results.append(TransformedObservation(date=obs.date, original_value=obs.value, value=average))
    return results
