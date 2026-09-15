"""Response contract for State Duration V1 (frozen and normative in
`docs/product/state-duration-v1.md`, §32).

Plain Pydantic data, like `app.models.inflation`/`app.models.labor` --
no FastAPI or SQLAlchemy dependency. A genuine two-shape discriminated
union on `status`, not one flat model with nulled fields -- deliberately
different from this project's usual "single model, availability flag"
convention (e.g. `TargetResult.available`), because the frozen contract
itself specifies `CURRENT_INSUFFICIENT` as carrying NO duration/period/
boundary fields at all (§32: "No field not justified above is
included"), not merely nulled ones -- no duration is computed or
implied when the current state itself is unavailable (§14).

Every field name here is load-bearing per the frozen contract's own
historical-truth discipline (§1/§21/§51): `earliest_confirmed_period`
(never `start_period`, §21), `history_type` (a fixed trust-boundary
literal, §19), `boundary_type` (a three-value enum, never a boolean,
§13).
"""

from datetime import date
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from app.models.inflation import InflationState
from app.models.labor import LaborState

BoundaryType = Literal["EXACT", "DATA_BOUNDED", "LOOKBACK_BOUNDED"]

# Frozen literal (§19), reused verbatim on every AVAILABLE response.
# Deliberately NOT derived from `data_basis`, even though the two
# always co-occur in V1 -- its entire purpose is to make it
# structurally awkward for a future recorded-history endpoint to be
# silently merged into this response shape without a reader noticing
# the type changed.
HISTORY_TYPE = "latest_revised_reconstruction"


class StateDurationAvailable(BaseModel):
    """A genuine latest-revised reconstructed consecutive-state run --
    never "recorded historical duration," never a claim about how long
    this project has previously reported the state to be (frozen
    contract §1/§51, the single most load-bearing rule in this
    document)."""

    status: Literal["AVAILABLE"] = "AVAILABLE"
    state: InflationState | LaborState
    evaluation_period: date
    duration_months: int
    earliest_confirmed_period: date
    boundary_type: BoundaryType
    # EXACT-only (§22) -- genuinely not known for DATA_BOUNDED/LOOKBACK_BOUNDED,
    # and populating them with a guess there would violate §1.
    previous_state: InflationState | LaborState | None
    previous_period: date | None
    methodology_id: str
    data_basis: str
    history_type: Literal["latest_revised_reconstruction"] = HISTORY_TYPE


class StateDurationCurrentInsufficient(BaseModel):
    """The current canonical state itself is `INSUFFICIENT_DATA` (or has
    no evaluable period at all) -- no duration is computed or implied
    (frozen contract §14, unified per the same defensive "branch on
    state, never on period presence alone" reasoning already shipped in
    #23B)."""

    status: Literal["CURRENT_INSUFFICIENT"] = "CURRENT_INSUFFICIENT"
    methodology_id: str
    data_basis: str


StateDurationResult = Annotated[
    Union[StateDurationAvailable, StateDurationCurrentInsufficient],
    Field(discriminator="status"),
]
