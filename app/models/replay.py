"""Result contract for deterministic point-in-time replay
(Increment #31).

Replay is NOT "read back the stored result". It re-executes the
deterministic methodology against the observations MacroChipz actually
had when the result was calculated, and compares. The distinction is the
entire point of the capability, so it is expressed in the type: a
`ReplayResult` always carries BOTH the recorded state and the
independently recomputed one.

Plain Pydantic data, like every other model here -- no FastAPI or
SQLAlchemy dependency. #31 adds no route; this contract exists so
verification (and a future #32 surface) has something honest to consume.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

#: MATCH        -- recomputation from historical inputs reproduced the recorded state.
#: MISMATCH     -- it did not. A real finding, never smoothed over.
#: NOT_REPLAYABLE -- replay could not be attempted honestly; see `reason`.
ReplayOutcome = Literal["MATCH", "MISMATCH", "NOT_REPLAYABLE"]

#: Why a replay could not be attempted. Each is a genuinely different
#: condition, and none of them is "we produced a result anyway".
NotReplayableReason = Literal[
    "UNKNOWN_RECORDED_RESULT",
    "UNKNOWN_METHODOLOGY_VERSION",
    "NO_VERSION_HISTORY_FOR_INPUTS",
    "VERSION_HISTORY_STARTS_AFTER_CALCULATION",
]


class ReplayResult(BaseModel):
    """One recorded monitor result, re-derived from the data known at
    its own `calculated_at`.

    `inputs_include_backfilled` is a deliberate honesty flag rather than
    a footnote: a replay whose inputs come from migration-time backfill
    rests on "this value existed by this timestamp", not on an observed
    write. That is still meaningful evidence, and it is materially
    weaker than a replay over versions this system actually watched
    happen.
    """

    recorded_monitor_result_id: int
    monitor: str
    evaluation_period: date | None
    methodology_id: str
    #: The system-time instant replay was anchored to -- the recorded
    #: result's own `calculated_at`, never "now".
    anchor: datetime | None

    recorded_state: str | None
    replayed_state: str | None

    outcome: ReplayOutcome
    reason: NotReplayableReason | None = None

    input_series_ids: list[str] = []
    input_observation_count: int = 0
    inputs_include_backfilled: bool = False
