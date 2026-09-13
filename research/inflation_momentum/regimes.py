"""Descriptive historical period windows for the responsiveness/turn
analysis (Section 10 of the research brief).

These are NOT hindsight-optimized "ground truth" turning-point labels.
They are widely-documented, dated-in-advance-of-this-study calendar
windows (textbook U.S. macroeconomic history) used only to observe how
each candidate methodology behaved during broad periods independently
known for particular inflation dynamics -- never to grade a candidate
against a manufactured "correct answer", and never tuned to make any
candidate look better or worse.

Coverage is reported, not assumed: a study run checks each series'
actual `first_observation`/`last_observation` against a regime's dates
and reports the true overlap rather than fabricating history a series
doesn't have (e.g. PCEPI/PCEPILFE start in 1959, so pre-1959 regimes
have zero PCE coverage and this is reported plainly).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Regime:
    name: str
    start: date
    end: date
    note: str


REGIMES: list[Regime] = [
    Regime("1970s Inflation Shocks", date(1973, 1, 1), date(1975, 12, 31),
           "First oil shock era (OPEC embargo, 1973-1974)."),
    Regime("Late-1970s Second Oil Shock", date(1978, 1, 1), date(1980, 12, 31),
           "Iranian Revolution oil shock; inflation accelerating into the 1980 peak."),
    Regime("Volcker Disinflation", date(1980, 1, 1), date(1983, 12, 31),
           "Federal Reserve tightening under Chairman Volcker; inflation falling from double digits."),
    Regime("1990s Price Stability", date(1992, 1, 1), date(1999, 12, 31),
           "Extended period of low, stable inflation."),
    Regime("2001 Recession", date(2001, 1, 1), date(2001, 12, 31),
           "Dot-com bust recession (NBER-dated Mar-Nov 2001)."),
    Regime("2008 Financial Crisis / Deflation Shock", date(2008, 6, 1), date(2009, 12, 31),
           "Global financial crisis; commodity price collapse; brief outright deflation."),
    Regime("2010s Low-Inflation Environment", date(2010, 1, 1), date(2019, 12, 31),
           "Extended below/near-target inflation following the financial crisis recovery."),
    Regime("COVID Collapse", date(2020, 2, 1), date(2020, 6, 30),
           "Pandemic demand shock; brief disinflation/deflation in several components."),
    Regime("2021-2022 Inflation Surge", date(2021, 1, 1), date(2022, 6, 30),
           "Post-pandemic reopening, fiscal stimulus, and supply-chain-driven inflation surge."),
    Regime("2022-2024 Disinflation", date(2022, 7, 1), date(2024, 12, 31),
           "Federal Reserve tightening cycle; inflation declining from 2022 peaks."),
    Regime("2025-Latest Available", date(2025, 1, 1), date(2026, 12, 31),
           "Most recent available observations at the time of this study."),
]


def regime_coverage(regime: Regime, series_first: date | None, series_last: date | None) -> dict:
    """How much of `regime`'s window a series actually has data for --
    reported honestly, never assumed or fabricated."""
    if series_first is None or series_last is None:
        return {"regime": regime.name, "has_any_coverage": False, "coverage_note": "series has no observations at all"}
    overlap_start = max(regime.start, series_first)
    overlap_end = min(regime.end, series_last)
    has_coverage = overlap_start <= overlap_end
    if not has_coverage:
        return {
            "regime": regime.name,
            "has_any_coverage": False,
            "coverage_note": f"series data ({series_first}..{series_last}) does not overlap this regime's window",
        }
    full_coverage = overlap_start == regime.start and overlap_end == regime.end
    return {
        "regime": regime.name,
        "has_any_coverage": True,
        "full_coverage": full_coverage,
        "covered_start": overlap_start.isoformat(),
        "covered_end": overlap_end.isoformat(),
    }
