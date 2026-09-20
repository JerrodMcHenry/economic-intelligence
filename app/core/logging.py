"""Application logging configuration (Increment #34).

This module exists because of a specific, verified defect: **before
#34, every `logger.info` in this application emitted nothing.** Under
uvicorn's default configuration the root logger sits at WARNING with no
handler attached to `app.*`, so the structured telemetry #33 built for
the Analyst -- model, prompt version, context version, latency, tokens,
outcome, evidence validation -- was correct code that never reached a
log. Rates-ingestion telemetry was invisible for the same reason.

So this is not "add logging". It is connecting instrumentation that
already existed to an output that can receive it.

Two deliberate choices:

- **`extra` fields are rendered.** The repo's convention is a short
  static message plus structured `extra` (established by
  `rates_ingestion.py`). The stdlib's default formatter drops `extra`
  entirely, which would have made the convention pointless. The JSON
  formatter below emits every custom field.

- **JSON in production, human-readable locally.** A log aggregator can
  parse the former; a developer reads the latter.

Nothing here logs a secret, a user question, a model answer, or a
provider payload -- that discipline lives at the call sites (#33) and
is unchanged.
"""

import json
import logging
import logging.config
from typing import Any

from app.core.config import settings

#: Attributes every `LogRecord` carries. Anything NOT in this set was
#: passed by the call site as `extra` and is what we actually want.
_STANDARD_RECORD_FIELDS = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name",
        "pathname", "process", "processName", "relativeCreated", "stack_info",
        "thread", "threadName", "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """One JSON object per line, including every `extra` field."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_FIELDS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            # The class name and message, never the full traceback --
            # a traceback can carry a provider error string or a
            # connection detail, and the stderr uvicorn logger already
            # records unhandled exceptions separately.
            exc_type, exc_value, _ = record.exc_info
            payload["exception_class"] = getattr(exc_type, "__name__", str(exc_type))
            payload["exception_message"] = str(exc_value)

        return json.dumps(payload, default=str)


class KeyValueFormatter(logging.Formatter):
    """Human-readable local output, with `extra` appended as key=value."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<8} {record.name} :: {record.getMessage()}"
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_RECORD_FIELDS and not key.startswith("_")
        }
        if not extras:
            return base
        rendered = " ".join(f"{key}={value}" for key, value in extras.items())
        return f"{base} | {rendered}"


def configure_logging() -> None:
    """Attach a handler to the application's own logger namespace.

    Scoped to `app` rather than the root logger on purpose: uvicorn owns
    its own loggers and formats them its own way, and hijacking the root
    would reformat access logs as a side effect of fixing ours.
    """
    formatter = JsonFormatter() if settings.log_format_json else KeyValueFormatter()

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    app_logger = logging.getLogger("app")
    app_logger.handlers.clear()
    app_logger.addHandler(handler)
    app_logger.setLevel(settings.log_level)
    # Do not also bubble to root: uvicorn's root handler would print a
    # second, unformatted copy of every line.
    app_logger.propagate = False
