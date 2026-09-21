"""The Structured Intelligence contract (Increment #39).

The bridge between MacroChipz's canonical economic engine and its
consumer surfaces. Every surface -- What Changed, THE LEDE, world pages,
Revision Intelligence, the Brief, alerts, Analyst context -- should
render THIS, rather than each independently re-deriving what happened
from domain results.

Three design rules, in the order they matter:

1. **A discriminated union, not a god object.** Four variants, each with
   a typed payload carrying only facts that variant genuinely has.
   There is no model here with thirty nullable fields; a consumer
   switches on `type` and gets a payload where every field means
   something.

2. **Source facts and methodology-derived conclusions are machine-
   readably distinct.** `basis` says which, and `methodology` is present
   if and only if `basis == "METHODOLOGY_DERIVED"`. A release arriving
   is not a conclusion about the economy, and the contract refuses to
   let the two blur.

3. **No significance score.** There is deliberately no 0-100 importance
   number and no ranking field. Ordering is by time, deterministically,
   and the interpretable primitives a surface may filter on --
   `type`, `change_class`, `event_type` -- are named facts rather than
   a judgement smuggled into the canonical object. See §10 of
   docs/architecture/structured-intelligence.md for why.

This layer is a PROJECTION. It is never a source of truth, it is
generated on read from already-persisted canonical data, and everything
in it must be reconstructable from that data.
"""

from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

#: Bumped when a breaking change is made to these contracts. Permanent
#: URLs may eventually depend on them, so the version is explicit rather
#: than implied by deployment date.
INTELLIGENCE_CONTRACT_VERSION = "intelligence_v1"

#: The MacroChipz economic worlds that exist today. Housing, consumer and
#: growth join when they have data -- deliberately not pre-declared.
World = Literal["inflation", "jobs", "rates"]

IntelligenceType = Literal[
    "RELEASE_PROCESSED",
    "OBSERVATION_CHANGE",
    "ANALYSIS_CHANGE",
    "RATES_MOVEMENT",
]

#: Whether this object reports something a source published, or a
#: conclusion a frozen MacroChipz methodology reached. The distinction is
#: machine-readable because it governs what a surface may claim: a
#: release arriving is not an economic judgement.
IntelligenceBasis = Literal["SOURCE_FACT", "METHODOLOGY_DERIVED"]

#: Whether this object records something MacroChipz genuinely detected at
#: `recorded_at`, or something reconstructed after the fact.
#:
#: This is the field that stops backfilled history masquerading as
#: knowledge MacroChipz actually had. It is never inferred and never
#: defaulted -- every builder sets it explicitly from the provenance of
#: the data it read.
KnowledgeBasis = Literal["OBSERVED", "BACKFILLED"]

#: Whether a methodology-derived change is about the ECONOMY or about
#: MacroChipz's own DATA COVERAGE.
#:
#: This distinction is not cosmetic. In the current database 1,488 of
#: 1,532 persisted analysis updates are `AVAILABILITY_RESTORED` from a
#: single bootstrap run -- i.e. 97% of them record that MacroChipz
#: acquired data, not that the economy did anything. Presenting those as
#: economic intelligence would be exactly the manufactured activity the
#: Product Constitution forbids, so the class is a typed field a surface
#: can filter on rather than a judgement made in presentation code.
ChangeClass = Literal["ECONOMIC", "COVERAGE"]

RelationKind = Literal[
    "CONCERNS_CONCEPT",
    "PART_OF_RELEASE",
    "AFFECTS_WORLD",
    "DERIVED_FROM_OBSERVATION",
]


class MethodologyRef(BaseModel):
    """Which frozen methodology produced a conclusion.

    Present only on `METHODOLOGY_DERIVED` objects. A source fact carries
    `methodology=None` rather than a domain's methodology id, because
    stamping one there would claim a conclusion was reached when none
    was.
    """

    methodology_id: str
    data_basis: str


class EvidenceRef(BaseModel):
    """A pointer to one canonical observation this object rests on.

    Deliberately a REFERENCE carrying identity and the value, not a copy
    of arbitrary source prose. It reuses Increment #38's identity triple
    unchanged -- concept (source-neutral), provider (who actually
    supplied it) and that provider's own series identifier -- so a
    provider migration cannot make an old object's evidence lie.
    """

    concept_id: str
    provider: str
    provider_series_id: str
    observation_date: date
    value: float | None


class Relation(BaseModel):
    """A typed reference to something worth exploring next.

    Deliberately minimal: a kind and a target identifier. This is not a
    graph database and not an ontology -- it exists so a future surface
    can answer "what should I look at next?" without scraping prose or
    re-deriving domain relationships.
    """

    kind: RelationKind
    target: str


class IntelligenceEnvelope(BaseModel):
    """The fields every intelligence object has, whatever its type."""

    #: Deterministic and semantic -- see `app/services/intelligence/identity.py`.
    #: Never a database id, never a UUID, never derived from prose.
    id: str
    type: IntelligenceType
    world: World
    #: Every MacroChipz concept this object concerns. Source-neutral
    #: (#38); never a provider identifier.
    concepts: list[str]

    #: The economic period this is ABOUT -- an observation month, a
    #: release date, a curve as-of date.
    effective_period: date
    #: When MACROCHIPZ recorded or detected this. A system time, always
    #: real, never a stand-in for anything else.
    recorded_at: datetime
    #: When the PROVIDER published it.
    #:
    #: Almost always `None`, and that is the honest answer rather than a
    #: gap. This project's release calendar carries a scheduled DATE, and
    #: its own client documentation is explicit that a release date is
    #: not proof the data was published. `created_at` is never
    #: substituted here.
    published_at: datetime | None = None

    knowledge_basis: KnowledgeBasis
    basis: IntelligenceBasis
    #: Present if and only if `basis == "METHODOLOGY_DERIVED"`.
    methodology: MethodologyRef | None = None

    evidence: list[EvidenceRef] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    #: What this object does NOT establish. Required rather than
    #: optional, because optional fields get omitted and this is where
    #: the honesty lives.
    limitations: list[str] = Field(default_factory=list)

    contract_version: str = INTELLIGENCE_CONTRACT_VERSION


class ReleaseProcessedPayload(BaseModel):
    """A curated economic release that MacroChipz checked and processed.

    A SOURCE FACT: data arrived and was written. It says nothing about
    what the economy did -- the consequences, if any, appear as separate
    `ANALYSIS_CHANGE` objects.
    """

    release_name: str
    provider: str
    provider_release_id: str
    scheduled_date: date
    status: str
    observation_changes: int
    new_observations: int
    revised_observations: int


#: What MacroChipz can HONESTLY claim to know about an observation's
#: history (#43).
#:
#: These are deliberately three states rather than one "has history"
#: flag, because they license completely different sentences:
#:
#: - `FIRST_OBSERVATION` -- MacroChipz learned a value. **Not a
#:   revision.** There was no earlier value to change.
#: - `PROSPECTIVE_REVISION` -- MacroChipz held value A, then observed
#:   the provider publish B. The only case where "originally reported"
#:   is a claim MacroChipz can actually prove.
#: - `BACKFILLED_BASELINE` -- the value was imported when point-in-time
#:   tracking began (#31 backfilled 1,072 observations). MacroChipz
#:   knows the value as of that moment and **cannot** say what earlier
#:   provider vintages were. Presenting this as an "original value"
#:   would be inventing economic history.
RevisionKnowledge = Literal["FIRST_OBSERVATION", "PROSPECTIVE_REVISION", "BACKFILLED_BASELINE"]


class ObservationChangePayload(BaseModel):
    """One observation MacroChipz saw arrive or change.

    `change_type == "REVISED"` is the revision case Increment #43 will
    make a first-class experience. The contract represents it fully
    today; the DATA does not exist yet -- in the current database all
    358 recorded observation changes are `NEW` and not one `REVISED`
    event has ever been captured. That is a fact about how young the
    pipeline is, not a gap in this model.
    """

    change_type: Literal["NEW", "REVISED"]
    #: ADDITIVE (#43), and the one thing a surface cannot honestly
    #: infer for itself: `change_type` alone cannot distinguish a
    #: revision MacroChipz WATCHED happen from a value it merely
    #: imported at migration time. Defaults to the conservative state,
    #: so an object built before #43 never claims to know an original
    #: value it never saw.
    revision_knowledge: RevisionKnowledge = "BACKFILLED_BASELINE"
    #: Whether `previous_value` is a value MacroChipz genuinely
    #: RECORDED before the change, rather than absent or reconstructed.
    original_value_known: bool = False
    #: The value MacroChipz previously held. `None` for a NEW
    #: observation -- never a fabricated zero.
    previous_value: float | None
    new_value: float | None
    #: `new_value - previous_value` when both are present; `None`
    #: otherwise. Never computed against a substituted default.
    delta: float | None
    observation_date: date
    #: Who actually supplied it, and their own identifier (#38).
    provider: str
    provider_series_id: str
    series_title: str | None
    units: str | None


class AnalysisChangePayload(BaseModel):
    """A change a frozen methodology concluded, recorded during release
    processing.

    `change_class` separates economic changes from data-coverage
    changes -- see `ChangeClass`.
    """

    component: str
    event_type: str
    change_class: ChangeClass
    field: str
    previous_value: str | None
    current_value: str | None
    delta: float | None
    evaluation_period: date


class VisualEvidencePoint(BaseModel):
    """One observed value on one date. Nothing else: no label, no
    colour, no coordinate, no flag for how it should be drawn."""

    observation_date: date
    value: float


class TimeSeriesVisualEvidence(BaseModel):
    """The bounded observation series behind an intelligence object, so
    a surface can SHOW the movement the object describes (#40C).

    This is EVIDENCE, not a chart. It carries economic facts in
    canonical units and says nothing about presentation -- no pixels,
    no colours, no axis configuration, no component options. A surface
    decides how to draw it; two surfaces drawing it differently are
    still drawing the same facts.

    Why it belongs in the intelligence object rather than being fetched
    separately: a chart assembled from a second query is a second
    account of reality, and it can disagree with the object it sits
    under. These points come from the same canonical service, under the
    same methodology, in the same read as the rest of the object.

    `points` contains ONLY published observations. A date the provider
    published no value for is absent, never interpolated, carried
    forward or zero-filled -- so `len(points)` may be smaller than
    `requested_sessions`, which is a fact about the record and is
    reported rather than hidden.

    ONE SUBTLETY, DELIBERATE. A series of N published sessions is not
    the same span as `rates_v1.0`'s N-session CHANGE: a 63-session
    change compares the latest observation with the one 63 sessions
    BEFORE it, which spans 64 observations. So the first point here is
    one session later than the 63-session change's `from_date`, and
    subtracting the chart's endpoints will not reproduce that change
    exactly. This is not an off-by-one to be corrected -- the two
    answer different questions -- which is why a surface should caption
    the series with its own real date range rather than implying it
    matches a change window.
    """

    kind: Literal["TIME_SERIES"] = "TIME_SERIES"
    #: Source-neutral concept identity (#38), never a provider series id.
    concept_id: str
    #: Canonical unit of `value`, as the methodology defines it.
    unit: str
    #: How many published sessions were asked for.
    requested_sessions: int
    #: How many are actually present. Equal to `len(points)`.
    available_sessions: int
    #: Chronologically ascending, ending at the object's effective date.
    points: list[VisualEvidencePoint]


class RatesMovementPayload(BaseModel):
    """One canonical Treasury series' latest level and its own
    session-counted changes under `rates_v1.0`.

    **This carries no significance claim, deliberately.** `rates_v1.0`
    defines no notability threshold, so there is no deterministic rule
    that would make one movement "meaningful" and another not. What is
    offered is the change and its position in the series' own history;
    deciding what is worth showing belongs to a surface, or to a future
    Radar detector with a pre-registered threshold -- never to this
    layer inventing one.
    """

    series_title: str
    latest_value: float | None
    #: Session-COUNTED windows, never calendar days -- `rates_v1.0`'s own
    #: semantics, preserved verbatim.
    changes: list["RatesChangeRef"]
    historical_percentile_rank: float | None
    historical_magnitude_percentile_rank: float | None
    historical_observation_count: int
    #: ADDITIVE (#40C), and optional on purpose: a consumer written
    #: against the original `intelligence_v1` payload is unaffected, so
    #: this is not a breaking change and
    #: `INTELLIGENCE_CONTRACT_VERSION` is deliberately NOT bumped. It is
    #: `None` when no usable history exists for the series.
    visual_evidence: TimeSeriesVisualEvidence | None = None


class RatesChangeRef(BaseModel):
    window: str
    sessions: int
    available: bool
    change_basis_points: float | None
    from_date: date | None
    from_value: float | None


class ReleaseProcessedIntelligence(IntelligenceEnvelope):
    type: Literal["RELEASE_PROCESSED"] = "RELEASE_PROCESSED"
    payload: ReleaseProcessedPayload


class ObservationChangeIntelligence(IntelligenceEnvelope):
    type: Literal["OBSERVATION_CHANGE"] = "OBSERVATION_CHANGE"
    payload: ObservationChangePayload


class AnalysisChangeIntelligence(IntelligenceEnvelope):
    type: Literal["ANALYSIS_CHANGE"] = "ANALYSIS_CHANGE"
    payload: AnalysisChangePayload


class RatesMovementIntelligence(IntelligenceEnvelope):
    type: Literal["RATES_MOVEMENT"] = "RATES_MOVEMENT"
    payload: RatesMovementPayload


IntelligenceObject = Annotated[
    Union[
        ReleaseProcessedIntelligence,
        ObservationChangeIntelligence,
        AnalysisChangeIntelligence,
        RatesMovementIntelligence,
    ],
    Field(discriminator="type"),
]


class IntelligenceListResponse(BaseModel):
    """A bounded, deterministically ordered collection.

    Ordering is `effective_period DESC, recorded_at DESC, id ASC` --
    time, then a total tiebreak on the stable id. There is no relevance
    ordering, because there is no defensible deterministic definition of
    relevance in the engine today.
    """

    items: list[IntelligenceObject]
    total: int
    limit: int
    offset: int
    contract_version: str = INTELLIGENCE_CONTRACT_VERSION


RatesMovementPayload.model_rebuild()
