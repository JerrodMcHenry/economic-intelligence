"""Contracts for the MacroChipz Analyst (Increment #33).

**MacroChipz Analyst explains canonical intelligence. It does not create
canonical intelligence.**

Plain Pydantic -- no FastAPI, no SQLAlchemy, no OpenAI. Three contracts
live here and the separation between them is the whole point:

1. `AnalystExplainRequest` -- what a BROWSER may say. Deliberately tiny:
   a context type, an optional recorded-result id, and a question. It
   carries no state, no evidence, and no numbers, because a client that
   could supply those could make the Analyst explain a fabricated
   economy ("inflation state = hyperinflation"). The server resolves
   every fact itself.

2. `AnalystContextPacket` -- what the SERVER assembles from canonical
   intelligence, and the only economic input the model ever sees. It is
   structured and versioned rather than a concatenated blob, so a change
   to what the model is told is a reviewable change to a schema.

3. `AnalystExplainResponse` -- what comes back, after the model's output
   has been schema-validated and its evidence references checked against
   the packet. A reference the packet does not contain never becomes
   product evidence.

Values in a packet are PRE-FORMATTED STRINGS carrying their own units
(`"130.658 index"`, `"+25 bp"`, `"158,268,000 jobs"`). That is
deliberate: the model is never handed a bare number whose unit it has to
infer, which is the class of mistake that produced a 1,000x error inside
deterministic code during #32.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: The context-packet schema version. Bump this when the SHAPE of what
#: the model is told changes, so an operational record can always be
#: traced back to the exact contract that produced it.
ANALYST_CONTEXT_VERSION = "analyst_context_v1"

#: Allow-listed subjects. An unrecognised value is a 422 from FastAPI's
#: own validation -- the model never influences which intelligence is
#: loaded, and a client cannot name an arbitrary table, series, or
#: resource.
AnalystContextType = Literal["INFLATION", "LABOR", "RATES", "MONITOR_HISTORY"]

#: What an evidence item is, so a reader (and the UI) can tell a sourced
#: observation from a derived metric from a classification.
EvidenceKind = Literal["OBSERVATION", "METRIC", "STATE", "CHANGE", "COMPARISON", "PROVENANCE"]

#: Why the Analyst could not answer. Each is a real, distinct condition,
#: and none of them is "we answered anyway".
AnalystFailureReason = Literal[
    "NOT_CONFIGURED",
    "PROVIDER_UNAVAILABLE",
    "TIMEOUT",
    "MALFORMED_OUTPUT",
    "CONTEXT_UNAVAILABLE",
]


class ContextFact(BaseModel):
    """One labelled, pre-formatted deterministic fact.

    `value` is a string, always, including for numbers. The backend owns
    formatting and units; the model is never asked to interpret a raw
    float whose meaning depends on a convention it cannot see.
    """

    label: str
    value: str


class MethodologyRef(BaseModel):
    """Which frozen methodology produced this subject's conclusions."""

    methodology_id: str
    data_basis: str
    #: One plain sentence describing what the methodology does, written
    #: by MacroChipz -- never left to the model to characterise.
    summary: str


class EvidenceItem(BaseModel):
    """One piece of deterministic evidence the model MAY cite, by id.

    Ids are assigned by the server and are stable and descriptive
    (`inflation.metric.3m_annualized`, `rates.level.UST_NOMINAL_10Y`).
    The model may reference them; it may not invent them, and it is never
    asked to produce a URL. MacroChipz owns the evidence; the model only
    points at it.
    """

    id: str
    kind: EvidenceKind
    label: str
    value: str | None = None
    #: Supporting specifics -- the exact observations behind a metric,
    #: the provider behind an observation.
    detail: str | None = None


class ReplayInformation(BaseModel):
    """Increment #31's integrity verdict, carried verbatim.

    Present only for `MONITOR_HISTORY`. `outcome` is reported to the
    model as-is precisely so a `MISMATCH` cannot be quietly reframed as
    "unverified" in prose.
    """

    outcome: str
    replayed_state: str | None
    reason: str | None
    inputs_include_backfilled: bool


class AnalystContextPacket(BaseModel):
    """Everything the model is allowed to know, and nothing else.

    Assembled server-side from canonical services. Contains no secrets,
    no configuration, no connection details, no internal identifiers
    beyond the evidence ids it deliberately publishes, and no free-text
    passed through from the client.
    """

    context_version: Literal["analyst_context_v1"] = ANALYST_CONTEXT_VERSION
    context_type: AnalystContextType
    generated_at: datetime

    #: Plain-language description of what this context is about.
    subject: str

    #: The canonical classification, if this subject has one. `None` for
    #: subjects that legitimately do not (Rates publishes levels and
    #: derived metrics, not a classified state) -- never a placeholder.
    canonical_state: str | None = None
    evaluation_period: date | None = None

    methodology: MethodologyRef
    deterministic_metrics: list[ContextFact] = []
    changes: list[ContextFact] = []
    evidence: list[EvidenceItem] = []
    provenance: list[ContextFact] = []
    historical_context: list[ContextFact] = []
    replay_information: ReplayInformation | None = None

    #: What this context does NOT establish -- carried into the prompt so
    #: the model is told the boundaries of its own evidence rather than
    #: being left to discover them.
    limitations: list[str] = []

    def evidence_ids(self) -> set[str]:
        return {item.id for item in self.evidence}


# ---------------------------------------------------------------------
# HTTP contracts
# ---------------------------------------------------------------------


class AnalystContextRef(BaseModel):
    """How a client NAMES a context -- never how it supplies one.

    `extra="forbid"`, matching `PipelineRequest`'s own hardening: a
    legitimate client never needed to send an unrecognised field, and
    silently ignoring one here would be the obvious place to try
    smuggling state in.
    """

    model_config = ConfigDict(extra="forbid")

    type: AnalystContextType
    #: Required for `MONITOR_HISTORY`, rejected for every other type.
    #: Resolved server-side against `recorded_monitor_results`.
    recorded_result_id: int | None = None
    #: Required for `MONITOR_HISTORY` -- which monitor the recorded
    #: result belongs to, so the lookup is scoped exactly as #32's own
    #: route scopes it.
    monitor: Literal["inflation", "labor"] | None = None


class AnalystExplainRequest(BaseModel):
    """Request body for `POST /api/v1/analyst/explain`.

    The question is untrusted user text and is treated as data
    throughout: it is placed in a user turn, never interpolated into the
    system instruction, and it cannot change which context is loaded.
    """

    model_config = ConfigDict(extra="forbid")

    context: AnalystContextRef
    question: str = Field(min_length=1, max_length=500)


class AnalystEvidenceReference(BaseModel):
    """One VALIDATED evidence reference, resolved back to the packet.

    The model returns only an id; the label/value/kind here come from
    MacroChipz's own packet, never from the model. A reference that did
    not validate is absent from this list entirely.
    """

    id: str
    kind: EvidenceKind
    label: str
    value: str | None = None
    detail: str | None = None


class AnalystMetadata(BaseModel):
    """Operational metadata -- what produced this answer, and whether it
    validated. Deliberately carries no secret, no prompt text, and no
    provider payload."""

    context_version: str
    prompt_version: str
    model: str
    #: How many evidence references the model returned, and how many were
    #: dropped because the packet did not contain them. A non-zero
    #: `evidence_references_dropped` is a real signal, surfaced rather
    #: than hidden.
    evidence_references_returned: int
    evidence_references_dropped: int


class AnalystExplainResponse(BaseModel):
    answer: str
    evidence: list[AnalystEvidenceReference] = []
    limitations: list[str] = []
    metadata: AnalystMetadata


class AnalystAvailability(BaseModel):
    """Whether the Analyst can be used at all.

    Deliberately a boolean plus a neutral reason code -- never the
    configuration state itself, never which variable is missing, and
    never anything that would help an unauthenticated caller learn about
    this deployment's setup.
    """

    available: bool
    #: `NOT_CONFIGURED` when the optional integration is not set up.
    #: `None` when available.
    reason: Literal["NOT_CONFIGURED"] | None = None
