"""AI query orchestration: natural-language request -> OpenAI native tool
calling -> our deterministic economic engine -> natural-language response.

The model never computes an economic value itself. Every factual or
numeric claim it can make about persisted data must come from one of the
three tools in `app.services.ai_tools`, each a thin, validated wrapper
around an existing, already-tested application capability. This module
owns the tool-calling loop and the OpenAI SDK boundary; it contains no
transformation, alignment, or correlation math, and it never touches
PostgreSQL directly -- `app.services.ai_tools.execute_tool` does that,
against the one session this module is given for the whole request.
"""

import json
from dataclasses import dataclass, field

from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.ai_tools import TOOL_SCHEMAS, execute_tool

# A small, explicit ceiling on tool-calling rounds -- one round is one
# batch of tool call(s) plus the model's follow-up. Protects against a
# runaway loop; this is not autonomous recursive planning, it's a bounded
# request/tool/response cycle.
MAX_TOOL_ROUNDS = 4

SYSTEM_INSTRUCTIONS = (
    "You are an economic analysis assistant for a platform that persists "
    "official economic data series in PostgreSQL. For any factual or "
    "numerical claim about economic data -- a value, a change, a moving "
    "average, a correlation -- call the appropriate tool rather than "
    "inventing or calculating it yourself; you have no reliable knowledge "
    "of what is actually persisted, and deterministic tools exist "
    "specifically so calculations don't depend on you. Never state a "
    "number you did not obtain from a tool result. Correlation does not "
    "imply causation -- say so when relevant. If a request needs a series "
    "identifier you cannot determine, or data these tools can't provide, "
    "say so plainly instead of guessing."
)


class AIServiceError(Exception):
    """Base error for AI service failures (configuration, provider, or loop limits)."""


class AIProviderUnavailableError(AIServiceError):
    """Raised when OpenAI is unreachable, times out, or rejects our credentials."""


class ToolRoundLimitExceededError(AIServiceError):
    """Raised when the model still wants to call tools after MAX_TOOL_ROUNDS."""


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict


@dataclass
class AIQueryResult:
    answer: str
    tools_used: list[ToolCallRecord] = field(default_factory=list)


class AIService:
    def __init__(self):
        if not settings.openai_api_key:
            raise AIProviderUnavailableError("OPENAI_API_KEY is not configured.")
        if not settings.openai_model:
            raise AIProviderUnavailableError("OPENAI_MODEL is not configured.")
        self._client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
        self._model = settings.openai_model

    def query(self, message: str, session: Session) -> AIQueryResult:
        """Answer one natural-language message, calling tools as needed.

        Every tool call this loop executes runs against `session` --
        callers own that session's lifetime/transaction boundary (see
        `app.db.session.session_scope`), the same convention every other
        database-backed route in this project follows.
        """
        tools_used: list[ToolCallRecord] = []

        response = self._create_response(input=[{"role": "user", "content": message}])

        round_count = 0
        while True:
            function_calls = [item for item in response.output if item.type == "function_call"]
            if not function_calls:
                break

            round_count += 1
            if round_count > MAX_TOOL_ROUNDS:
                raise ToolRoundLimitExceededError(f"Exceeded the maximum of {MAX_TOOL_ROUNDS} tool-calling rounds.")

            tool_outputs = []
            for call in function_calls:
                arguments = self._parse_arguments(call.arguments)
                if arguments is None:
                    result = {
                        "ok": False,
                        "error": {"type": "invalid_arguments", "message": "Tool arguments were not a valid JSON object."},
                    }
                    recorded_arguments: dict = {}
                else:
                    result = execute_tool(call.name, arguments, session)
                    recorded_arguments = arguments

                tools_used.append(ToolCallRecord(name=call.name, arguments=recorded_arguments))
                tool_outputs.append(
                    {"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result)}
                )

            response = self._create_response(input=tool_outputs, previous_response_id=response.id)

        answer = getattr(response, "output_text", None) or ""
        return AIQueryResult(answer=answer, tools_used=tools_used)

    def _create_response(self, input: list[dict], previous_response_id: str | None = None):
        kwargs = {
            "model": self._model,
            "input": input,
            "tools": TOOL_SCHEMAS,
        }
        if previous_response_id is None:
            kwargs["instructions"] = SYSTEM_INSTRUCTIONS
        else:
            kwargs["previous_response_id"] = previous_response_id

        try:
            return self._client.responses.create(**kwargs)
        except AuthenticationError as exc:
            raise AIProviderUnavailableError("OpenAI rejected the configured API key.") from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise AIProviderUnavailableError("OpenAI request timed out or was unreachable.") from exc
        except APIStatusError as exc:
            raise AIProviderUnavailableError("OpenAI returned an error status.") from exc

    @staticmethod
    def _parse_arguments(raw: str) -> dict | None:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
