"""Typed, application-owned result models for the Housing world
(Increment #45).

Plain Pydantic data, like `app.models.rates` — no FastAPI or SQLAlchemy
dependency. Consumed by `app.domain.housing`'s pure functions and
`app.services.housing`'s orchestration, and returned directly by
`app.api.housing`.

================================================================
THERE IS NO `housing_v1.0`, AND THIS MODULE IS WHERE THAT IS TRUE
================================================================

Every other world here has a frozen methodology that classifies it:
`inflation_v1.0` has COOLING/HEATING, `labor_v1.0` has a labour
condition. Housing has NOTHING of the kind, and that is a decision
rather than an omission — `macrochipz-2.0-implementation-sequence.md`
names five things a legitimate Housing state would require (a defensible
state vocabulary grounded in housing economics, sufficient history for
any historical-position claim, a published methodology, golden vectors,
and a defensible answer to what "housing is cooling" means when permits,
starts, completions and rates can move in opposite directions at once)
and until all five exist, Housing has no state.

So there is deliberately:

- no `METHODOLOGY_ID` constant, because no methodology produced these
  numbers — they are source facts;
- no state field, no condition field, no direction label, no composite
  index, no component weights, no score;
- no significance test. Census's own explanatory notes say month-to-month
  movements "often show movements which may be irregular" and that it
  "may take three months to establish an underlying trend for building
  permit authorizations, six months for total starts, and six months for
  total completions". MacroChipz reports the change and quotes that
  guidance; it does not decide which changes matter.

What this module DOES carry is arithmetic no one can disagree with: a
latest value, the value before it, the value a year earlier, and the
differences between them.

================================================================
THE SAAR TRAP, AND THE TWO UNITS THAT AVOID IT
================================================================

Census publishes each pipeline stage twice, and conflating the two is
the single most likely way to publish a false number here.

`PACE` is the seasonally adjusted ANNUAL RATE. Census defines it as "the
seasonally adjusted monthly value multiplied by 12" and states that it
"is neither a forecast nor a projection; rather it is a description of
the rate of building permits, housing starts, housing completions, or
new home sales in the particular month for which they are calculated."
It is the only form in which one month is comparable with another.

`ACTUAL` is the month's own unadjusted count.

**An annual rate must never be presented as homes built in a month, and
it must never be divided by twelve and called monthly production.** The
second is subtly worse than the first: dividing 1,394,000 by 12 gives
116,167, while the actual unadjusted August figure is 117,400 — close
enough to look right and wrong on principle, because the seasonal
adjustment that produced the annual rate is exactly what that division
throws away.

Carrying both units side by side is what lets the product SHOW that
distinction rather than assert it, which is why the response has two
measures per stage rather than one.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.concepts.registry import (
    HOUSING_UNITS_AUTHORIZED_NSA,
    HOUSING_UNITS_AUTHORIZED_SAAR,
    HOUSING_UNITS_COMPLETED_NSA,
    HOUSING_UNITS_COMPLETED_SAAR,
    HOUSING_UNITS_STARTED_NSA,
    HOUSING_UNITS_STARTED_SAAR,
)

#: Bumped if the shape below changes incompatibly. Deliberately NOT
#: called a methodology id: it versions a response contract, not an
#: economic conclusion, and nothing here concludes anything.
HOUSING_CONTRACT_VERSION = "housing_v1_data"

DATA_BASIS = "latest_published_data"

PROVIDER = "CENSUS"

#: The attribution Census's Data API terms of service require verbatim.
#: Rendered on every surface that shows this data. Recorded here, beside
#: the data it governs, so it travels with the response rather than
#: depending on a frontend string staying in sync.
PROVIDER_ATTRIBUTION = (
    "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau."
)

#: The joint publisher. Census's own release states that "The U.S. Census
#: Bureau and the U.S. Department of Housing and Urban Development
#: jointly announced" these statistics, so naming Census alone as the
#: publisher would be incomplete.
SOURCE_STATEMENT = (
    "Source: U.S. Census Bureau and U.S. Department of Housing and Urban Development, "
    "New Residential Construction."
)

DATASET = "timeseries/eits/resconst"

#: The human-resolvable page these observations come from, recorded as
#: provenance. Deliberately the program's own landing page rather than an
#: API URL: an API URL for this provider would carry a credential.
SOURCE_URL = "https://www.census.gov/construction/nrc/"

#: The three stages, in pipeline order. An ORDER, not a causal claim:
#: see `PIPELINE_LIMITATIONS`.
HousingStageId = Literal["PERMITS", "STARTS", "COMPLETIONS"]

PIPELINE_STAGES: tuple[HousingStageId, ...] = ("PERMITS", "STARTS", "COMPLETIONS")

#: Stage -> (seasonally adjusted annual rate concept, unadjusted count
#: concept). THE one place the pipeline's structure is declared, and it
#: names concepts only -- never a Census category code, which lives in
#: `app/concepts/bindings.py` where the provider's vocabulary belongs.
STAGE_CONCEPTS: dict[HousingStageId, tuple[str, str]] = {
    "PERMITS": (HOUSING_UNITS_AUTHORIZED_SAAR.concept_id, HOUSING_UNITS_AUTHORIZED_NSA.concept_id),
    "STARTS": (HOUSING_UNITS_STARTED_SAAR.concept_id, HOUSING_UNITS_STARTED_NSA.concept_id),
    "COMPLETIONS": (HOUSING_UNITS_COMPLETED_SAAR.concept_id, HOUSING_UNITS_COMPLETED_NSA.concept_id),
}

#: Every Housing concept, in a deterministic order -- the ingestion
#: service's work list and the read service's lookup order.
HOUSING_CONCEPT_IDS: tuple[str, ...] = tuple(
    concept_id for stage in PIPELINE_STAGES for concept_id in STAGE_CONCEPTS[stage]
)

#: Stored-series titles. `economic_series.title` is display metadata, so
#: these are the concept names verbatim rather than a second, drifting
#: set of words.
SERIES_TITLES: dict[str, str] = {
    HOUSING_UNITS_AUTHORIZED_SAAR.concept_id: HOUSING_UNITS_AUTHORIZED_SAAR.name,
    HOUSING_UNITS_STARTED_SAAR.concept_id: HOUSING_UNITS_STARTED_SAAR.name,
    HOUSING_UNITS_COMPLETED_SAAR.concept_id: HOUSING_UNITS_COMPLETED_SAAR.name,
    HOUSING_UNITS_AUTHORIZED_NSA.concept_id: HOUSING_UNITS_AUTHORIZED_NSA.name,
    HOUSING_UNITS_STARTED_NSA.concept_id: HOUSING_UNITS_STARTED_NSA.name,
    HOUSING_UNITS_COMPLETED_NSA.concept_id: HOUSING_UNITS_COMPLETED_NSA.name,
}

#: `economic_series.units`, the stored unit label. Housing units, because
#: the 1000x conversion from Census's "Thousands of Units" happens at the
#: binding before anything is persisted.
SERIES_UNITS: dict[str, str] = {
    concept_id: ("Housing units, seasonally adjusted annual rate" if ".saar." in concept_id else "Housing units")
    for concept_id in HOUSING_CONCEPT_IDS
}

#: How many months of history a trend series carries for display.
#: Bounded so the payload cannot grow with the database. 60 months,
#: because Census's own guidance is that establishing an underlying
#: trend takes three to six months -- a window that shows only a few
#: months would invite exactly the month-to-month reading that guidance
#: warns against.
TREND_MONTHS = 60

#: What a Housing response does NOT establish. Canonical, not
#: presentation: these sentences constrain what any surface may claim,
#: so they travel with the data rather than living in a component.
PIPELINE_LIMITATIONS: tuple[str, ...] = (
    "Permits, starts and completions are three separate measurements, not one cohort followed through "
    "time. A permit issued this month is not the same home as a start this month, and no fixed share of "
    "permits becomes a start or of starts becomes a completion.",
    "Not every authorized home is built, and the time from authorization to completion varies by home, "
    "by builder and by market. MacroChipz publishes no expected lag and no conversion rate.",
    "MacroChipz applies no state, score, rating or direction label to Housing. There is no housing "
    "methodology, so there is no conclusion here \u2014 only the figures Census published and the arithmetic "
    "differences between them.",
    "Census's own guidance is that month-to-month movements in these seasonally adjusted statistics are "
    "often irregular, and that establishing an underlying trend may take three months for permits and six "
    "months for starts and completions.",
    "MacroChipz does not test whether a change is statistically significant. Census publishes confidence "
    "intervals for the changes in its own release; those intervals are not available through this dataset "
    "and MacroChipz does not reconstruct them.",
    "Privately-owned housing only. Publicly-owned units are excluded by Census from these statistics.",
    "Building permits come from the Building Permits Survey and are, in Census's words, based on a "
    "non-probability sample and not subject to sampling error. Starts and completions come from the Survey "
    "of Construction and are sample estimates subject to sampling variability. They are not equally precise "
    "measurements.",
)

#: The sentence a surface must show wherever a seasonally adjusted annual
#: rate appears. Canonical for the same reason the limitations are: the
#: number is meaningless, and easy to misread, without it.
SAAR_EXPLANATION = (
    "A seasonally adjusted annual rate describes the pace of building in one month, expressed as what a "
    "full year at that pace would total. Census calculates it by adjusting the month's figure for normal "
    "seasonal patterns and multiplying by twelve. It is not a count of homes in that month, it is not a "
    "forecast, and dividing it by twelve does not give the month's actual figure \u2014 the actual unadjusted "
    "count is reported separately."
)


class HousingProvenance(BaseModel):
    """Where one persisted Housing observation came from, and whether
    the provider has since revised it.

    `provider_series_id` is CENSUS'S identifier for the series
    (`APERMITS/TOTAL`), read from the stored provenance row rather than
    from a module constant, so a binding change cannot make an old
    observation's provenance lie.

    There is no API URL here and never will be: a Census API URL carries
    the credential. `source_url` is the program's published landing page,
    which is what a reader verifying a number actually needs.
    """

    provider: str
    dataset: str
    provider_series_id: str
    observation_date: date
    source_url: str
    retrieved_at: datetime
    revision_count: int
    last_revised_at: datetime | None


class HousingTrendPoint(BaseModel):
    """One published month. Nothing else: no label, no coordinate, no
    flag for how it should be drawn."""

    observation_date: date
    value: float


class HousingTrend(BaseModel):
    """The bounded recent history behind one measure, so a surface can
    SHOW the movement rather than only state it.

    `points` contains ONLY published observations. A month Census
    published no usable value for is absent -- never interpolated,
    carried forward or zero-filled -- so `available_months` may be
    smaller than `requested_months`, which is a fact about the record
    and is reported rather than hidden.
    """

    concept_id: str
    unit: str
    requested_months: int
    available_months: int
    points: list[HousingTrendPoint]


class HousingMeasure(BaseModel):
    """One concept's latest published figure and its deterministic
    comparisons.

    `available: false` with an explicit `unavailable_reason` is the
    representation of missing data -- never a zero, never a null value
    presented as a figure. Missing economic data and infrastructure
    failure are different outcomes, and only the second is an error.

    Both comparisons are plain subtraction between two published values
    at two published periods. `change_percent` is present only when the
    earlier value is non-zero, because a percentage change from zero is
    undefined rather than infinite.
    """

    concept_id: str
    #: The concept's canonical unit: `HOUSING_UNITS_ANNUAL_RATE` or
    #: `HOUSING_UNITS`. A surface MUST branch on this rather than on the
    #: stage, because the two units read completely differently.
    unit: str
    seasonal_adjustment: str
    available: bool
    unavailable_reason: str | None = None

    period: date | None = None
    value: float | None = None

    previous_period: date | None = None
    previous_value: float | None = None
    change_from_previous: float | None = None
    change_percent_from_previous: float | None = None

    year_ago_period: date | None = None
    year_ago_value: float | None = None
    change_from_year_ago: float | None = None
    change_percent_from_year_ago: float | None = None

    observation_count: int = 0
    earliest_period: date | None = None

    provenance: HousingProvenance | None = None
    trend: HousingTrend | None = None


class HousingStage(BaseModel):
    """One stage of the construction pipeline, in both units.

    `pace` is the seasonally adjusted annual rate; `actual` is the
    month's unadjusted count. Two measures rather than one, because they
    answer different questions and neither substitutes for the other.
    """

    stage: HousingStageId
    pace: HousingMeasure
    actual: HousingMeasure


class HousingResult(BaseModel):
    """The canonical Housing read model.

    Note what is absent: no `state`, no `methodology_id`, no headline
    conclusion, no ordering by importance. The stages are in pipeline
    order, which is a fact about construction, not a ranking.
    """

    contract_version: str = HOUSING_CONTRACT_VERSION
    data_basis: str = DATA_BASIS
    provider: str = PROVIDER
    attribution: str = PROVIDER_ATTRIBUTION
    source_statement: str = SOURCE_STATEMENT
    source_url: str = SOURCE_URL

    #: The most recent month any Housing concept has a published value
    #: for. `None` when nothing has been ingested into this environment.
    as_of_period: date | None
    stages: list[HousingStage]
    saar_explanation: str = SAAR_EXPLANATION
    limitations: list[str]


# ----------------------------------------------------------------------
# Ingestion contract
# ----------------------------------------------------------------------

#: How a sync classified its own writes for one series.
#:
#: `BASELINE_BACKFILL` is the honest description of an initial import:
#: MacroChipz learned a long history of values at one instant and cannot
#: say what the provider had published for those months before then.
#: `INCREMENTAL` means the series already existed and this run observed
#: whatever changed. The distinction is what stops a first import
#: appearing as revision evidence (#43).
HousingImportMode = Literal["BASELINE_BACKFILL", "INCREMENTAL"]

HousingSyncStatus = Literal["SUCCEEDED", "PARTIAL_FAILURE", "FAILED"]


class HousingSyncSeriesOutcome(BaseModel):
    """What happened to one series during one sync."""

    concept_id: str
    provider_series_id: str
    import_mode: HousingImportMode
    observations_received: int
    observations_inserted: int
    observations_revised: int
    observations_unchanged: int
    #: Rows Census published for this series with no usable numeric
    #: value. Skipped entirely -- never stored as zero.
    observations_skipped_missing_value: int
    first_period: date | None
    last_period: date | None


class HousingSyncResponse(BaseModel):
    """One Housing ingestion attempt, reported in full.

    Counts and a status only. No credential, no request URL, no upstream
    payload, and no response body can appear in this model -- it is
    returned over HTTP and written to a log, and both are places a
    secret must never reach.
    """

    status: HousingSyncStatus
    provider: str = PROVIDER
    dataset: str = DATASET
    started_at: datetime
    completed_at: datetime
    duration_ms: int

    rows_received: int
    #: Rows Census published as reliability statistics rather than
    #: estimates. Recognised and set aside, never ingested as counts.
    error_measure_rows_ignored: int
    #: Rows this client refused, by fixed reason code.
    rows_rejected: int
    rejected_reasons: dict[str, int]
    #: Rows for categories MacroChipz does not bind (`UNDERCONST`,
    #: `AUTHNOTSTD`, single-family and multi-family breakdowns). Not a
    #: problem -- the dataset is simply wider than #45's scope.
    rows_outside_scope: int

    series: list[HousingSyncSeriesOutcome]
    error_class: str | None = None
