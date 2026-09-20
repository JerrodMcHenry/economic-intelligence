"""Typed, application-owned canonical result models for the Rates
Monitor, methodology `rates_v1.0` (frozen in
`docs/methodology/rates-v1.0.md` -- normative; this module implements
it, it does not reinterpret it).

Plain Pydantic data, like `app.models.inflation`/`app.models.labor` --
no FastAPI or SQLAlchemy dependency. Consumed by `app.domain.rates`'s
pure functions and `app.services.rates`'s orchestration, and returned
directly by `app.api.rates`.

This is the ONE canonical production definition of `rates_v1.0`'s
constants and enums. Nothing else in the application may hardcode a
duplicate canonical series ID, window size, or provider identifier --
every other module imports them from here.

TERMINOLOGY (deliberate, see the methodology's own "what this does NOT
support"): the nominal-minus-real difference is **market-implied
inflation compensation**, never "inflation expectations" -- it contains
an inflation risk premium and a TIPS liquidity premium that this
methodology does not attempt to separate.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

METHODOLOGY_ID = "rates_v1.0"
DATA_BASIS = "latest_published_data"

# The one canonical provider for every series below (Increment #29).
# U.S. Treasury interest-rate statistics are U.S. Government works;
# see docs/methodology/rates-v1.0.md "Sources, licensing, attribution".
PROVIDER = "TREASURY"
PROVIDER_ATTRIBUTION = "Source: U.S. Department of the Treasury (Daily Treasury Par Yield Curve Rates)."

NOMINAL_DATASET = "daily_treasury_yield_curve"
REAL_DATASET = "daily_treasury_real_yield_curve"

# Our own canonical series identifiers -- deliberately NOT FRED's
# (DGS10/DFII10). A Treasury-sourced observation must never be
# confusable with a FRED-sourced one carrying different provenance and
# different licensing (#28 §10.2/§11.1).
NOMINAL_2Y_SERIES_ID = "UST_NOMINAL_2Y"
NOMINAL_5Y_SERIES_ID = "UST_NOMINAL_5Y"
NOMINAL_10Y_SERIES_ID = "UST_NOMINAL_10Y"
NOMINAL_30Y_SERIES_ID = "UST_NOMINAL_30Y"
REAL_5Y_SERIES_ID = "UST_REAL_5Y"
REAL_10Y_SERIES_ID = "UST_REAL_10Y"

NOMINAL_SERIES_IDS: tuple[str, ...] = (
    NOMINAL_2Y_SERIES_ID,
    NOMINAL_5Y_SERIES_ID,
    NOMINAL_10Y_SERIES_ID,
    NOMINAL_30Y_SERIES_ID,
)
REAL_SERIES_IDS: tuple[str, ...] = (REAL_5Y_SERIES_ID, REAL_10Y_SERIES_ID)
CANONICAL_SERIES_IDS: tuple[str, ...] = NOMINAL_SERIES_IDS + REAL_SERIES_IDS

# Upstream field name -> our canonical series id, per dataset. The one
# place the provider's own column vocabulary is mapped into ours.
NOMINAL_FIELD_MAP: dict[str, str] = {
    "BC_2YEAR": NOMINAL_2Y_SERIES_ID,
    "BC_5YEAR": NOMINAL_5Y_SERIES_ID,
    "BC_10YEAR": NOMINAL_10Y_SERIES_ID,
    "BC_30YEAR": NOMINAL_30Y_SERIES_ID,
}
REAL_FIELD_MAP: dict[str, str] = {
    "TC_5YEAR": REAL_5Y_SERIES_ID,
    "TC_10YEAR": REAL_10Y_SERIES_ID,
}

SERIES_TITLES: dict[str, str] = {
    NOMINAL_2Y_SERIES_ID: "2-Year Treasury Par Yield (Nominal)",
    NOMINAL_5Y_SERIES_ID: "5-Year Treasury Par Yield (Nominal)",
    NOMINAL_10Y_SERIES_ID: "10-Year Treasury Par Yield (Nominal)",
    NOMINAL_30Y_SERIES_ID: "30-Year Treasury Par Yield (Nominal)",
    REAL_5Y_SERIES_ID: "5-Year Treasury Par Real Yield (TIPS)",
    REAL_10Y_SERIES_ID: "10-Year Treasury Par Real Yield (TIPS)",
}

SERIES_UNITS = "Percent"

# Change windows are counted in OBSERVATIONS (published business
# sessions), never calendar days -- see the methodology's own
# "Time-window semantics". `1_SESSION` compares against the immediately
# preceding published observation, whatever its calendar date.
ChangeWindow = Literal["1_SESSION", "5_SESSIONS", "21_SESSIONS", "63_SESSIONS"]

CHANGE_WINDOW_SESSIONS: dict[str, int] = {
    "1_SESSION": 1,
    "5_SESSIONS": 5,
    "21_SESSIONS": 21,
    "63_SESSIONS": 63,
}

# Ordered for deterministic response construction.
CHANGE_WINDOWS: tuple[ChangeWindow, ...] = ("1_SESSION", "5_SESSIONS", "21_SESSIONS", "63_SESSIONS")

MetricKind = Literal["SOURCE_OBSERVATION", "DERIVED"]

SpreadId = Literal["2s10s", "2s30s"]
CompensationId = Literal["5Y", "10Y"]


class SourceProvenance(BaseModel):
    """Where one persisted observation actually came from. Present on
    every SOURCE_OBSERVATION metric; absent (by construction) on a
    DERIVED one, whose provenance is its inputs plus a methodology
    version -- see `DerivedProvenance`."""

    provider: str
    dataset: str
    series_id: str
    observation_date: date
    source_url: str
    retrieved_at: datetime
    revision_count: int
    last_revised_at: datetime | None


class DerivedProvenance(BaseModel):
    """Why one DERIVED value is what it is: the methodology that defines
    it, its exact inputs, and when it was calculated. A derived metric
    must never masquerade as a directly sourced observation (#29), so
    this model is structurally distinct from `SourceProvenance` and
    carries no provider/dataset of its own."""

    methodology_id: str = METHODOLOGY_ID
    calculation: str
    input_series_ids: list[str]
    input_observation_date: date
    calculated_at: datetime


class RateChange(BaseModel):
    """The change in one metric over one window, in basis points.

    `available` is false -- and `change_basis_points`/`from_*` are None
    -- whenever the series has fewer than `sessions + 1` persisted
    observations. Never zero-filled: "no data" and "no change" are
    different facts.
    """

    window: ChangeWindow
    sessions: int
    available: bool
    change_basis_points: float | None
    from_date: date | None
    from_value: float | None
    to_date: date | None
    to_value: float | None


class HistoricalContext(BaseModel):
    """Deterministic rank of the current windowed change against every
    same-length windowed change in the persisted history.

    `percentile_rank` is the share of historical changes strictly
    smaller in SIGNED terms than the current one; `magnitude_percentile_rank`
    ranks absolute size. Both are plain counting over stored
    observations -- no model, no distribution assumption, no forecast.
    """

    available: bool
    window: ChangeWindow
    observation_count: int
    history_start_date: date | None
    history_end_date: date | None
    percentile_rank: float | None
    magnitude_percentile_rank: float | None
    minimum_change_basis_points: float | None
    maximum_change_basis_points: float | None


class RateLevel(BaseModel):
    """One canonical rate: its latest persisted level plus every
    configured change window and the historical context of the 5-session
    change. `kind` is always SOURCE_OBSERVATION here."""

    series_id: str
    title: str
    units: str = SERIES_UNITS
    kind: MetricKind = "SOURCE_OBSERVATION"
    available: bool
    latest_date: date | None
    latest_value: float | None
    changes: list[RateChange]
    historical_context: HistoricalContext
    provenance: SourceProvenance | None


class CurveSpread(BaseModel):
    """A derived curve spread, in basis points: the longer maturity's
    yield minus the shorter maturity's, both on the SAME observation
    date. `kind` is always DERIVED."""

    spread_id: SpreadId
    title: str
    kind: MetricKind = "DERIVED"
    available: bool
    observation_date: date | None
    spread_basis_points: float | None
    long_series_id: str
    short_series_id: str
    long_value: float | None
    short_value: float | None
    unavailable_reason: str | None
    changes: list[RateChange]
    historical_context: HistoricalContext
    provenance: DerivedProvenance | None


class InflationCompensation(BaseModel):
    """Market-implied inflation compensation at one maturity, in
    percentage points: the nominal par yield minus the real (TIPS) par
    yield on the SAME observation date.

    NOT an inflation forecast and NOT "inflation expectations" -- it
    embeds an inflation risk premium and a TIPS liquidity premium this
    methodology does not decompose (see the methodology's own
    limitations section). `kind` is always DERIVED.
    """

    maturity: CompensationId
    title: str
    kind: MetricKind = "DERIVED"
    available: bool
    observation_date: date | None
    compensation_percent: float | None
    nominal_series_id: str
    real_series_id: str
    nominal_value: float | None
    real_value: float | None
    unavailable_reason: str | None
    changes: list[RateChange]
    historical_context: HistoricalContext
    provenance: DerivedProvenance | None


class RatesMonitorResult(BaseModel):
    """The complete canonical `rates_v1.0` result.

    Every component independently reports its own availability: a
    missing series, an unaligned date pair, or insufficient history is
    normal economic/data reality reported inside a successful response,
    never an error and never a fabricated value.
    """

    methodology_id: str = METHODOLOGY_ID
    data_basis: str = DATA_BASIS
    provider: str = PROVIDER
    attribution: str = PROVIDER_ATTRIBUTION
    as_of_date: date | None
    nominal_curve: list[RateLevel]
    real_curve: list[RateLevel]
    curve_spreads: list[CurveSpread]
    inflation_compensation: list[InflationCompensation]


class RatesSyncSeriesOutcome(BaseModel):
    """Per-series result of one ingestion run -- counts only, never the
    upstream payload."""

    series_id: str
    dataset: str
    observations_received: int
    observations_inserted: int
    observations_revised: int


class RatesSyncResponse(BaseModel):
    """The operator-facing result of one explicit ingestion run."""

    status: Literal["SUCCEEDED", "PARTIAL_FAILURE", "FAILED"]
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    datasets_requested: list[str]
    datasets_failed: list[str]
    series: list[RatesSyncSeriesOutcome]
