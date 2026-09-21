"""Stable identity for Structured Intelligence Objects (Increment #39).

An intelligence id must survive things a database id does not: the
object is generated on read, so there is no row to carry an
auto-increment; permanent URLs and follow/notification delivery will
eventually depend on the same object resolving to the same id forever;
and two surfaces generating the same intelligence must agree without
coordinating.

So identity is derived from SEMANTIC FACTS, never from:

- a database auto-increment (the object is not stored)
- a UUID generated per request (it would change every read)
- UI position or ordering (presentation does not define identity)
- prose (a wording change must not mint a new object)

## Format

    {type-prefix}:{dimension}:{dimension}:...

Readable, and deliberately NOT a hash of the whole object -- a hash
would change whenever any field changed, including one that does not
affect what the object IS. Only identity-bearing dimensions appear.

## Stability rules

An id is stable as long as its dimensions are. Specifically:

- **A value correction does not change the id.** Revising an
  observation's value produces a new `OBSERVATION_CHANGE` event with its
  own `detected_at`, so the two are distinct objects rather than one
  mutating object. That is the correct semantics: MacroChipz detected
  two different things at two different times.
- **A methodology version change DOES change the id** for
  methodology-derived objects, because a conclusion reached under a
  different methodology is a different conclusion. This is why
  `methodology_id` is an identity dimension for `ANALYSIS_CHANGE` but
  absent from source-fact ids.
- **A provider migration does NOT change the id**, because ids are
  keyed on concept identity (#38), never on the provider's series
  identifier. An object about core PCE stays the same object when its
  source moves from FRED to BEA.

## Collision rules

Within a type, the listed dimensions are jointly unique:

- `RELEASE_PROCESSED` -- one per (provider, provider release, scheduled
  date). A re-check of the same occurrence updates the same object
  rather than minting a second one.
- `OBSERVATION_CHANGE` -- one per (concept, observation date, detection
  instant). Two detections of the same observation at different times
  are genuinely two events.
- `ANALYSIS_CHANGE` -- one per (methodology, component, field,
  evaluation period, event type). The event type is included because a
  component can legitimately record both an availability change and an
  economic change for the same period.
- `RATES_MOVEMENT` -- one per (concept, as-of date).

Colons separate dimensions, so any dimension containing a colon would
be ambiguous. `_segment` rejects that rather than silently producing a
colliding id.
"""

from datetime import date, datetime, timezone

_SEPARATOR = ":"


class IntelligenceIdentityError(ValueError):
    """A dimension that cannot be encoded unambiguously. Always a
    programming error -- never something to work around by escaping."""


def _segment(value: str | date | datetime | None, *, field: str) -> str:
    if value is None:
        raise IntelligenceIdentityError(f"Intelligence id dimension {field!r} must not be None")
    if isinstance(value, datetime):
        # A COMPACT UTC timestamp, microsecond precision:
        # `20260919T184627419986Z`. Deliberately not `isoformat()` --
        # that contains colons, which are this format's own separator,
        # and the guard below rightly refuses it. Two detections inside
        # the same microsecond would collide, which is not reachable:
        # each is written by its own check run.
        text = value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + "Z"
    elif isinstance(value, date):
        text = value.isoformat()
    else:
        text = str(value).strip()

    if not text:
        raise IntelligenceIdentityError(f"Intelligence id dimension {field!r} must not be empty")
    if _SEPARATOR in text:
        raise IntelligenceIdentityError(
            f"Intelligence id dimension {field!r} contains {_SEPARATOR!r} ({text!r}), which would make "
            f"the id ambiguous. Identity dimensions must not contain the separator."
        )
    return text


def release_processed_id(provider: str, provider_release_id: str, scheduled_date: date) -> str:
    return _SEPARATOR.join(
        (
            "release",
            _segment(provider, field="provider"),
            _segment(provider_release_id, field="provider_release_id"),
            _segment(scheduled_date, field="scheduled_date"),
        )
    )


def observation_change_id(concept_id: str, observation_date: date, detected_at: datetime) -> str:
    return _SEPARATOR.join(
        (
            "observation",
            _segment(concept_id, field="concept_id"),
            _segment(observation_date, field="observation_date"),
            _segment(detected_at, field="detected_at"),
        )
    )


def analysis_change_id(
    methodology_id: str, component: str, field_name: str, evaluation_period: date, event_type: str
) -> str:
    return _SEPARATOR.join(
        (
            "analysis",
            _segment(methodology_id, field="methodology_id"),
            _segment(component, field="component"),
            _segment(field_name, field="field"),
            _segment(evaluation_period, field="evaluation_period"),
            _segment(event_type, field="event_type"),
        )
    )


def rates_movement_id(concept_id: str, as_of_date: date) -> str:
    return _SEPARATOR.join(
        (
            "rates",
            _segment(concept_id, field="concept_id"),
            _segment(as_of_date, field="as_of_date"),
        )
    )
