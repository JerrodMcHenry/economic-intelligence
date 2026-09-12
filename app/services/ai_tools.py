"""The explicit tool boundary between the LLM and our deterministic engine.

Exactly three tools are exposed to the model, each a thin, validated
wrapper around an existing, already-tested application capability:

    get_observations  -> EconomicDataService.get_observations   (Increment 004)
    transform_series   -> EconomicDataService.get_transformed_observations (Increment 005)
    analyze_series     -> AnalysisService.pipeline               (Increment 007)

No transformation, alignment, or correlation math lives here or anywhere
in the AI path -- every number the model can report comes from calling
one of these, never from the model computing it itself.

Dispatch is a plain dict from tool name to (argument model, handler) --
no reflection, no dynamic imports, no plugin framework; three tools don't
justify one. Every tool is read-only: none can reach FRED (no handler
constructs a `FREDClient`), and none can write to PostgreSQL (every
handler calls a read-only service method against a session it's given,
never `session.commit()`/`session_scope()` itself -- see
`app.api.ai` for where the one request-scoped session is opened).

`execute_tool` never raises for an expected failure -- model-generated
tool names/arguments, a nonexistent persisted series, or a database
outage all become a structured `{"ok": False, "error": {...}}` result
instead, safe to hand back to the model. A truly unexpected exception
(a real bug) is deliberately NOT caught here and propagates to the
route's default handling, the same "only map exceptions that can
realistically occur" discipline every other route in this project uses.
"""

from typing import Any, Callable

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.ai import GetObservationsArgs, TransformSeriesArgs
from app.models.analysis import PipelineRequest
from app.services.analysis import AnalysisService
from app.services.economic_data import (
    EconomicDataService,
    InvalidDateRangeError,
    InvalidWindowError,
    SeriesNotFoundError,
)

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "name": "get_observations",
        "description": (
            "Retrieve persisted historical observations for one economic series "
            "already stored in our PostgreSQL database. Never fetches from FRED "
            "or any external source -- only returns data that has already been "
            "synced. Use this for raw historical values."
        ),
        "strict": False,
        "parameters": {
            "type": "object",
            "properties": {
                "series_id": {
                    "type": "string",
                    "description": "The persisted series identifier, e.g. 'UNRATE'.",
                },
                "start_date": {
                    "type": ["string", "null"],
                    "description": "Optional ISO date (YYYY-MM-DD) lower bound, inclusive.",
                },
                "end_date": {
                    "type": ["string", "null"],
                    "description": "Optional ISO date (YYYY-MM-DD) upper bound, inclusive.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum observations to return (1-1000). Defaults to 100.",
                    "minimum": 1,
                    "maximum": 1000,
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of matching observations to skip. Defaults to 0.",
                    "minimum": 0,
                },
                "order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "Chronological order of returned observations. Defaults to asc.",
                },
            },
            "required": ["series_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "transform_series",
        "description": (
            "Apply a deterministic transformation to one persisted economic "
            "series: absolute_change, percent_change, or moving_average. "
            "Always use this tool for these calculations rather than computing "
            "them yourself -- absolute_change is a percentage-point change for "
            "percentage-valued series, not a percent change."
        ),
        "strict": False,
        "parameters": {
            "type": "object",
            "properties": {
                "series_id": {
                    "type": "string",
                    "description": "The persisted series identifier, e.g. 'UNRATE'.",
                },
                "transformation": {
                    "type": "string",
                    "enum": ["absolute_change", "percent_change", "moving_average"],
                },
                "window": {
                    "type": ["integer", "null"],
                    "description": "Required only for moving_average; must be 2-365. Omit/null otherwise.",
                    "minimum": 2,
                    "maximum": 365,
                },
                "start_date": {
                    "type": ["string", "null"],
                    "description": "Optional ISO date lower bound for the OUTPUT range, inclusive.",
                },
                "end_date": {
                    "type": ["string", "null"],
                    "description": "Optional ISO date upper bound, inclusive.",
                },
            },
            "required": ["series_id", "transformation"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "analyze_series",
        "description": (
            "Compare two persisted economic series: exact-date aligned values, "
            "spread (value_a - value_b), or Pearson correlation. Each series may "
            "optionally be transformed first (same transformations as "
            "transform_series). Always use this tool for correlation or spread "
            "calculations rather than computing them yourself. Correlation does "
            "not imply causation."
        ),
        "strict": False,
        "parameters": {
            "type": "object",
            "properties": {
                "series_a": {
                    "type": "object",
                    "description": "The first series to compare.",
                    "properties": {
                        "series_id": {"type": "string"},
                        "transformation": {
                            "type": ["object", "null"],
                            "description": "Optional transformation to apply before analysis.",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["absolute_change", "percent_change", "moving_average"],
                                },
                                "window": {
                                    "type": ["integer", "null"],
                                    "description": "Required only for moving_average; 2-365.",
                                    "minimum": 2,
                                    "maximum": 365,
                                },
                            },
                            "required": ["type"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["series_id"],
                    "additionalProperties": False,
                },
                "series_b": {
                    "type": "object",
                    "description": "The second series to compare.",
                    "properties": {
                        "series_id": {"type": "string"},
                        "transformation": {
                            "type": ["object", "null"],
                            "description": "Optional transformation to apply before analysis.",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["absolute_change", "percent_change", "moving_average"],
                                },
                                "window": {
                                    "type": ["integer", "null"],
                                    "description": "Required only for moving_average; 2-365.",
                                    "minimum": 2,
                                    "maximum": 365,
                                },
                            },
                            "required": ["type"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["series_id"],
                    "additionalProperties": False,
                },
                "analysis": {
                    "type": "string",
                    "enum": ["aligned", "spread", "correlation"],
                },
                "start_date": {
                    "type": ["string", "null"],
                    "description": "Optional ISO date lower bound for the OUTPUT range, inclusive.",
                },
                "end_date": {
                    "type": ["string", "null"],
                    "description": "Optional ISO date upper bound, inclusive.",
                },
            },
            "required": ["series_a", "series_b", "analysis"],
            "additionalProperties": False,
        },
    },
]


def _handle_get_observations(args: GetObservationsArgs, session: Session) -> dict:
    service = EconomicDataService()
    response = service.get_observations(
        args.series_id,
        session,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        offset=args.offset,
        order=args.order,
    )
    return response.model_dump(mode="json")


def _handle_transform_series(args: TransformSeriesArgs, session: Session) -> dict:
    service = EconomicDataService()
    response = service.get_transformed_observations(
        args.series_id,
        session,
        transformation=args.transformation,
        start_date=args.start_date,
        end_date=args.end_date,
        window=args.window,
    )
    return response.model_dump(mode="json")


def _handle_analyze_series(args: PipelineRequest, session: Session) -> dict:
    service = AnalysisService()
    response = service.pipeline(args, session)
    return response.model_dump(mode="json")


# name -> (argument model to validate against, handler to execute if valid)
_TOOL_HANDLERS: dict[str, tuple[type[BaseModel], Callable[[Any, Session], dict]]] = {
    "get_observations": (GetObservationsArgs, _handle_get_observations),
    "transform_series": (TransformSeriesArgs, _handle_transform_series),
    "analyze_series": (PipelineRequest, _handle_analyze_series),
}


def execute_tool(name: str, raw_arguments: dict, session: Session) -> dict:
    """Validate and execute one model-requested tool call.

    Never raises for an expected failure: an unknown tool name, arguments
    that don't validate, a nonexistent persisted series, a bad date range,
    an inapplicable/missing transformation window, or a database outage
    all become a structured `{"ok": False, "error": {"type": ..., "message": ...}}`
    result rather than an exception -- safe to serialize straight back to
    the model. A successful call returns `{"ok": True, "result": {...}}`,
    where `result` is the same JSON-serializable shape the equivalent HTTP
    endpoint would return.
    """
    entry = _TOOL_HANDLERS.get(name)
    if entry is None:
        return _error("unknown_tool", f"Unknown tool '{name}'.")

    args_model, handler = entry
    try:
        args = args_model.model_validate(raw_arguments)
    except ValidationError:
        return _error("invalid_arguments", f"Arguments for tool '{name}' did not match the expected schema.")

    try:
        return {"ok": True, "result": handler(args, session)}
    except SeriesNotFoundError as exc:
        return _error("series_not_found", str(exc))
    except InvalidDateRangeError as exc:
        return _error("invalid_date_range", str(exc))
    except InvalidWindowError as exc:
        return _error("invalid_window", str(exc))
    except OperationalError:
        return _error("database_unavailable", "The database is currently unavailable.")
    except SQLAlchemyError:
        return _error("database_error", "A database error occurred while executing this tool.")


def _error(error_type: str, message: str) -> dict:
    return {"ok": False, "error": {"type": error_type, "message": message}}
