"""Request/response contracts for the AI query endpoint, and the argument
schemas for two of the three tools the model may call (the third,
`analyze_series`, reuses `app.models.analysis.PipelineRequest` directly --
its shape already matches what that tool needs exactly).

Tool argument models double as the actual validation boundary for
model-generated arguments (see `app.services.ai_tools`) -- a tool call is
never executed without first being validated against one of these.
"""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.series import TransformationType


class AIQueryRequest(BaseModel):
    """Request body for POST /api/v1/ai/query. A single message is
    sufficient for this increment -- no conversation history/memory yet."""

    message: str


class ToolCallRecord(BaseModel):
    """Evidence that a tool was called and with what arguments -- not
    chain-of-thought. `arguments` are the raw (model-generated) arguments
    for the call, whether or not they ultimately validated successfully."""

    name: str
    arguments: dict[str, Any]


class AIQueryResponse(BaseModel):
    answer: str
    tools_used: list[ToolCallRecord] = []


class GetObservationsArgs(BaseModel):
    """Validated arguments for the `get_observations` tool -- maps
    directly onto `EconomicDataService.get_observations` (Increment 004)."""

    series_id: str
    start_date: date | None = None
    end_date: date | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    order: Literal["asc", "desc"] = "asc"


class TransformSeriesArgs(BaseModel):
    """Validated arguments for the `transform_series` tool -- maps
    directly onto `EconomicDataService.get_transformed_observations`
    (Increment 005). `window`'s numeric bounds are enforced here
    structurally; whether it's required (moving_average) or inapplicable
    (the other two types) is validated by that service itself via
    `InvalidWindowError`, not re-validated here -- the same rule, enforced
    in the same one place, regardless of caller."""

    series_id: str
    transformation: TransformationType
    window: int | None = Field(default=None, ge=2, le=365)
    start_date: date | None = None
    end_date: date | None = None
