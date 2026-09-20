"""The MacroChipz Analyst's language-model boundary (Increment #33).

**MacroChipz Analyst explains canonical intelligence. It does not create
canonical intelligence.**

This module is the ONLY place in the application that sends economic
context to a language model, and it is deliberately the narrowest thing
that can do that job:

- **One generation per request.** No tool loop, no autonomous rounds, no
  model-chosen next action. Increment #9 tried model-driven
  orchestration three times and its last attempt measured a ~60% rate of
  the model violating a constraint it had just been given (ADR-018,
  SUPERSEDED - FAILED ACCEPTANCE GATE). Nothing here reintroduces it.

- **No tools at all.** The model is handed a finished context packet and
  asked for prose. It cannot call anything.

- **No database, by construction.** This module takes no `Session`,
  imports no repository, no `app.db`, and no SQLAlchemy. The packet
  arrives already built by `app.services.analyst_context`. "The model
  cannot reach the database" is therefore a property of the import
  graph, checked by `tests/test_analyst_architecture.py`, not a promise
  made in a prompt.

- **Output is validated, not trusted.** The response is schema-validated
  and every evidence reference is checked against the packet that was
  actually sent. A reference MacroChipz did not publish is dropped and
  counted; it never becomes product evidence.

Failure is contained here. Every provider condition -- missing
configuration, timeout, connection failure, rate limit, 5xx, refusal,
malformed output -- raises a typed error the route maps to a 503. None
of them can alter canonical intelligence, because this module holds
nothing canonical to alter.
"""

import logging
import time
import uuid
from dataclasses import dataclass

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
)
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.models.analyst import (
    AnalystContextPacket,
    AnalystEvidenceReference,
    AnalystExplainResponse,
    AnalystMetadata,
)
from app.services.analyst_prompt import (
    ANALYST_PROMPT_VERSION,
    ANALYST_RESPONSE_SCHEMA,
    ANALYST_RESPONSE_SCHEMA_NAME,
    SYSTEM_INSTRUCTIONS,
    build_user_message,
)

logger = logging.getLogger(__name__)

#: Bounded, and bounded for a reason: the SDK retries only transient
#: conditions (connection errors, 429, 5xx), never a completed
#: generation, so this cannot silently double the cost of a successful
#: answer. One retry absorbs a blip; more would just make a real outage
#: slower to report.
MAX_PROVIDER_RETRIES = 1


class AnalystError(Exception):
    """Base error. Every subclass is a contained failure that leaves
    canonical intelligence untouched."""


class AnalystNotConfiguredError(AnalystError):
    """No provider is configured. The Analyst is optional; the rest of
    MacroChipz does not care."""


class AnalystProviderUnavailableError(AnalystError):
    """The provider timed out, refused our credentials, rate-limited us,
    or failed."""


class AnalystMalformedOutputError(AnalystError):
    """The provider returned something that is not a valid answer. Not
    retried -- a second call would be a second bill for the same
    question, and the honest answer is that this attempt failed."""


class _RawAnalystAnswer(BaseModel):
    """The model's output, before validation against the packet."""

    answer: str
    evidence_references: list[str] = []
    limitations: list[str] = []


@dataclass(frozen=True)
class _Usage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


def analyst_available() -> bool:
    """Whether the optional Analyst integration is configured.

    Deliberately a plain boolean. Callers expose availability; they never
    expose which setting is missing, which would tell an unauthenticated
    client about this deployment's configuration.
    """
    return bool(settings.openai_api_key) and bool(settings.openai_model)


class AnalystService:
    """One bounded generation over one deterministic context packet."""

    def explain(self, packet: AnalystContextPacket, question: str) -> AnalystExplainResponse:
        if not analyst_available():
            raise AnalystNotConfiguredError("The MacroChipz Analyst is not configured on this server.")

        model = settings.openai_model or ""
        request_id = uuid.uuid4().hex
        started = time.monotonic()

        # The packet is serialized as JSON rather than prose: structured
        # fields the model reads as data, never a blob of concatenated
        # text that untrusted input could hide inside.
        context_json = packet.model_dump_json(exclude_none=True)

        try:
            raw_text, usage = self._generate(model, context_json, question)
        except AnalystError as exc:
            self._log(
                request_id=request_id,
                packet=packet,
                model=model,
                started=started,
                outcome="failed",
                failure_category=type(exc).__name__,
                question_length=len(question),
            )
            raise

        try:
            parsed = _RawAnalystAnswer.model_validate_json(raw_text)
        except ValidationError as exc:
            self._log(
                request_id=request_id,
                packet=packet,
                model=model,
                started=started,
                outcome="failed",
                failure_category="schema_validation_failed",
                usage=usage,
                question_length=len(question),
            )
            raise AnalystMalformedOutputError("The Analyst returned an unusable response.") from exc

        evidence, dropped = self._validate_references(packet, parsed.evidence_references)

        self._log(
            request_id=request_id,
            packet=packet,
            model=model,
            started=started,
            outcome="succeeded",
            usage=usage,
            question_length=len(question),
            evidence_returned=len(parsed.evidence_references),
            evidence_dropped=dropped,
        )

        return AnalystExplainResponse(
            answer=parsed.answer,
            evidence=evidence,
            limitations=parsed.limitations,
            metadata=AnalystMetadata(
                context_version=packet.context_version,
                prompt_version=ANALYST_PROMPT_VERSION,
                model=model,
                evidence_references_returned=len(parsed.evidence_references),
                evidence_references_dropped=dropped,
            ),
        )

    # -----------------------------------------------------------------
    # Provider boundary
    # -----------------------------------------------------------------

    def _generate(self, model: str, context_json: str, question: str) -> tuple[str, _Usage]:
        """Exactly one `responses.create`. No tools are passed, so there
        is no tool call to handle and no second round to run."""
        client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
            max_retries=MAX_PROVIDER_RETRIES,
        )

        try:
            response = client.responses.create(
                model=model,
                instructions=SYSTEM_INSTRUCTIONS,
                input=[{"role": "user", "content": build_user_message(context_json, question)}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": ANALYST_RESPONSE_SCHEMA_NAME,
                        "schema": ANALYST_RESPONSE_SCHEMA,
                        "strict": True,
                    }
                },
                store=False,
            )
        except (APITimeoutError, APIConnectionError) as exc:
            raise AnalystProviderUnavailableError("The Analyst provider did not respond.") from exc
        except AuthenticationError as exc:
            raise AnalystProviderUnavailableError("The Analyst provider rejected the configured credentials.") from exc
        except APIStatusError as exc:
            raise AnalystProviderUnavailableError("The Analyst provider returned an error.") from exc

        text = getattr(response, "output_text", None)
        if not text:
            # A refusal or an empty completion is malformed for our
            # purposes -- there is no answer to show, and inventing one
            # is exactly what this feature must not do.
            raise AnalystMalformedOutputError("The Analyst returned an empty response.")

        return text, self._usage(response)

    @staticmethod
    def _usage(response: object) -> _Usage:
        """Token counts where the provider reports them. Absence is
        recorded as `None`, never as zero, so an unobserved cost is not
        mistaken for a free request."""
        usage = getattr(response, "usage", None)
        if usage is None:
            return _Usage(None, None, None)
        return _Usage(
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )

    # -----------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------

    @staticmethod
    def _validate_references(
        packet: AnalystContextPacket, references: list[str]
    ) -> tuple[list[AnalystEvidenceReference], int]:
        """Resolve model-returned ids against the packet MacroChipz sent.

        Policy, deliberately strict: an id the packet does not contain is
        DROPPED, not repaired and not passed through. The resolved
        label/value/detail come from the packet, never from the model, so
        even a valid id cannot carry model-authored provenance. The
        number dropped is returned so it can be logged and surfaced
        rather than disappearing.
        """
        by_id = {item.id: item for item in packet.evidence}
        resolved: list[AnalystEvidenceReference] = []
        seen: set[str] = set()

        for reference in references:
            item = by_id.get(reference)
            if item is None or reference in seen:
                continue
            seen.add(reference)
            resolved.append(
                AnalystEvidenceReference(
                    id=item.id, kind=item.kind, label=item.label, value=item.value, detail=item.detail
                )
            )

        return resolved, len(references) - len(resolved)

    # -----------------------------------------------------------------
    # Observability
    # -----------------------------------------------------------------

    @staticmethod
    def _log(
        *,
        request_id: str,
        packet: AnalystContextPacket,
        model: str,
        started: float,
        outcome: str,
        failure_category: str | None = None,
        usage: _Usage | None = None,
        question_length: int = 0,
        evidence_returned: int = 0,
        evidence_dropped: int = 0,
    ) -> None:
        """Structured operational logging, following the convention
        `app/services/rates_ingestion.py` established: a short static
        message plus structured `extra` fields.

        Deliberately absent: the API key, the question text, the answer
        text, the packet contents, and any provider payload. The
        question's LENGTH is recorded instead of the question, which
        answers "was this a long prompt?" without logging what a user
        asked.
        """
        logger.info(
            "analyst explain",
            extra={
                "request_id": request_id,
                "context_type": packet.context_type,
                "context_version": packet.context_version,
                "prompt_version": ANALYST_PROMPT_VERSION,
                "model": model,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "outcome": outcome,
                "failure_category": failure_category,
                "input_tokens": usage.input_tokens if usage else None,
                "output_tokens": usage.output_tokens if usage else None,
                "total_tokens": usage.total_tokens if usage else None,
                "question_length": question_length,
                "evidence_offered": len(packet.evidence),
                "evidence_references_returned": evidence_returned,
                "evidence_references_dropped": evidence_dropped,
            },
        )
