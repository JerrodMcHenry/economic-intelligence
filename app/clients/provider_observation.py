"""The shape both first-party provider clients return (Increment #56A)."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class FirstPartyObservation:
    """One monthly value exactly as the provider published it.

    `value is None` means the provider published the period as
    unavailable. `footnotes` keeps the provider's own codes (for example
    BLS `P` for preliminary, `X` for unavailable) for diagnosis; nothing
    downstream interprets them.
    """

    period: date
    value: float | None
    footnotes: tuple[str, ...] = ()
