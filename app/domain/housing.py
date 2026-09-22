"""Pure deterministic functions for the Housing world (Increment #45).

No I/O, no session, no client, no clock. Every function here is a pure
function of its arguments, so each one is reproducible by hand from the
stored series -- which is the standard `app/domain/` holds itself to and
the reason `tests/test_domain_architectural_independence.py` exists.

================================================================
WHAT THIS MODULE DELIBERATELY DOES NOT CONTAIN
================================================================

There is no classifier here. Housing has no methodology, so there is:

- no state, condition, rating, direction label or regime;
- no composite index and no component weights;
- no threshold, band or deadband -- the things `inflation_v1.0` and
  `labor_v1.0` legitimately have because a frozen methodology defines
  them, and which would be invented numbers here;
- no significance test. Census publishes 90-percent confidence intervals
  for the changes in its own release, computed from sampling variances
  this dataset does not expose. Reconstructing them would be inventing
  statistics; asserting a change is meaningful without them would be
  worse.

What remains is arithmetic nobody can disagree with: the latest
published value, the value before it, the value twelve months earlier,
and the differences. A DESCRIPTIVE CHANGE IS NOT A STATE. "Permits are
2.7% below last month" is a fact about two numbers; "housing is cooling"
is a conclusion MacroChipz is not entitled to reach.

================================================================
COMPARISON SEMANTICS, AND THE ONE CHOICE THAT MATTERS
================================================================

`previous` means THE PRECEDING PUBLISHED OBSERVATION, not "last calendar
month". For a monthly series with no gaps those coincide, and this
dataset currently has none -- but a policy that says "the month before"
needs a rule for what to do when that month is missing, and every such
rule quietly changes the number reported. Counting published
observations needs no rule. It is the same decision `rates_v1.0` made
for sessions, and it is recorded here for the same reason: the number is
reproducible by hand from the stored series.

`year_ago` is the opposite choice, deliberately: it is an EXACT
CALENDAR match twelve months before the latest period, and it is absent
rather than approximated when that month was not published. A
"year-over-year" comparison against whatever observation happens to sit
twelve slots back would silently become a different span the moment a
month is missing, and the whole value of a year-over-year figure is that
it compares like seasons.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class HousingObservation:
    """One published month. The domain's input type, deliberately
    independent of SQLAlchemy and of Pydantic so these functions can be
    tested with three lines of literals."""

    observation_date: date
    value: float


@dataclass(frozen=True)
class HousingComparison:
    """One comparison between the latest observation and an earlier one.

    Every field is `None` together: either the earlier observation exists
    and all four are populated, or it does not and all four are absent.
    A partially-filled comparison would invite a surface to show a period
    with no change beside it, which reads as "no change" rather than "no
    comparison".
    """

    period: date | None
    value: float | None
    change: float | None
    change_percent: float | None


NO_COMPARISON = HousingComparison(period=None, value=None, change=None, change_percent=None)


def latest(observations: list[HousingObservation]) -> HousingObservation | None:
    """The newest published observation, or `None`.

    Sorts rather than trusting input order: the repository returns
    ascending, but a pure function that depends on its caller's ordering
    is a pure function with a hidden precondition.
    """
    if not observations:
        return None
    return max(observations, key=lambda observation: observation.observation_date)


def preceding_comparison(observations: list[HousingObservation]) -> HousingComparison:
    """The latest observation against the one published before it.

    `NO_COMPARISON` when fewer than two observations exist -- never a
    comparison against zero, and never against the same observation.
    """
    if len(observations) < 2:
        return NO_COMPARISON
    ordered = sorted(observations, key=lambda observation: observation.observation_date)
    return _compare(ordered[-1], ordered[-2])


def year_ago_comparison(observations: list[HousingObservation]) -> HousingComparison:
    """The latest observation against the same calendar month a year
    earlier.

    An EXACT match on `(year - 1, month)`. `NO_COMPARISON` when that
    month was not published -- the nearest available month is never
    substituted, because a "year-over-year" figure whose span is not a
    year is mislabelled rather than approximate.
    """
    newest = latest(observations)
    if newest is None:
        return NO_COMPARISON

    target = date(newest.observation_date.year - 1, newest.observation_date.month, 1)
    for observation in observations:
        if observation.observation_date == target:
            return _compare(newest, observation)
    return NO_COMPARISON


def _compare(current: HousingObservation, earlier: HousingObservation) -> HousingComparison:
    change = current.value - earlier.value
    return HousingComparison(
        period=earlier.observation_date,
        value=earlier.value,
        change=change,
        # Undefined rather than infinite when the earlier value is zero.
        # No housing series has ever published a zero, but a percentage
        # change that silently becomes `inf` would render as a number.
        change_percent=(change / earlier.value) * 100.0 if earlier.value != 0 else None,
    )


def recent_window(observations: list[HousingObservation], months: int) -> list[HousingObservation]:
    """The most recent `months` published observations, oldest first.

    COUNTS PUBLISHED OBSERVATIONS, not calendar months, and returns
    fewer than asked for when fewer exist. Nothing is interpolated,
    carried forward or zero-filled: a month Census did not publish is
    absent from the result, and the caller reports how many it actually
    received.
    """
    if months < 1:
        raise ValueError("months must be at least 1")
    ordered = sorted(observations, key=lambda observation: observation.observation_date)
    return ordered[-months:]


def is_baseline_import(
    series_has_observations: bool,
    latest_stored_period: date | None,
    incoming_period: date,
) -> bool:
    """Whether one incoming observation is an IMPORTED BASELINE rather
    than something MacroChipz watched arrive (#43, #45).

    This is the whole #43 boundary for a new source, expressed as three
    booleans so it is testable without a database:

    - **The series is empty.** Everything in the first import is a
      baseline. MacroChipz is learning sixty-seven years of published
      history at one instant; it did not watch any of it happen and
      cannot say what Census had published for those months earlier.
    - **The incoming month is older than the newest month stored.** The
      import is filling history backwards. Same reasoning: not watched.
    - **The incoming month is newer than the newest month stored.** A
      genuinely new month arriving. MacroChipz IS watching this happen,
      so it is a real first observation.

    A month EQUAL to one already stored is not this function's business:
    that write is an update to an existing observation, and whether it
    changes anything is decided by comparing values. It returns `False`
    so that if such a write does turn out to be a revision, the revision
    is recorded as observed -- which it is, because MacroChipz was
    holding the earlier value. `ObservationVersionWriter` enforces the
    same thing independently.
    """
    if not series_has_observations or latest_stored_period is None:
        return True
    return incoming_period < latest_stored_period
