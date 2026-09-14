"""Descriptive historical period windows for the Labor Momentum
Methodology Validation -- NOT hindsight-optimized ground truth, NOT
target labels. Used only to organize the regime-review report and to
overlay NBER recession context on results; never to score, tune, or
select a threshold.

NBER recession dates are the NBER Business Cycle Dating Committee's own
published turning points (well-established, stable historical record,
not re-derived here). They answer "was the whole economy in an
NBER-defined recession this month" -- a different, broader question
than "what does labor_v1.0 classify," and are shown as CONTEXT ONLY per
the #20A.1 brief (never as a label the methodology is scored against).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date

from research.labor_momentum.methodology import month_range


@dataclass(frozen=True)
class Window:
    name: str
    start: Date
    end: Date


# Analytical windows named explicitly by the #20A.1 brief -- overlapping
# on purpose (they are lenses on the same history, not partitions).
ANALYTICAL_WINDOWS: tuple[Window, ...] = (
    Window("full_history", Date(1990, 1, 1), Date(2026, 8, 1)),
    Window("2000_2003", Date(2000, 1, 1), Date(2003, 12, 1)),
    Window("2007_2010", Date(2007, 1, 1), Date(2010, 12, 1)),
    Window("2015_2019", Date(2015, 1, 1), Date(2019, 12, 1)),
    Window("2020_2022", Date(2020, 1, 1), Date(2022, 12, 1)),
    Window("2022_latest", Date(2022, 1, 1), Date(2026, 8, 1)),
)

# NBER-defined recessions since 1990 (context overlay only).
NBER_RECESSIONS: tuple[Window, ...] = (
    Window("1990-1991 recession", Date(1990, 7, 1), Date(1991, 3, 1)),
    Window("2001 recession", Date(2001, 3, 1), Date(2001, 11, 1)),
    Window("2007-2009 recession", Date(2007, 12, 1), Date(2009, 6, 1)),
    Window("COVID recession", Date(2020, 2, 1), Date(2020, 4, 1)),
)

# The extreme COVID window named explicitly by the #20A.1 brief, for
# sensitivity reporting ONLY -- never removed from the canonical
# monthly sequence (see study.py).
COVID_EXTREME_WINDOW = Window("covid_extreme", Date(2020, 3, 1), Date(2021, 6, 1))

# Named regimes for the month-by-month/summarized regime review.
REGIME_REVIEW_WINDOWS: tuple[Window, ...] = (
    Window("2001 recession", Date(2001, 1, 1), Date(2002, 6, 1)),
    Window("2007-2009 recession", Date(2007, 10, 1), Date(2009, 12, 1)),
    Window("2015-2016 slowdown", Date(2015, 6, 1), Date(2016, 12, 1)),
    Window("2018-2019 late-cycle", Date(2018, 1, 1), Date(2019, 12, 1)),
    Window("COVID collapse", Date(2020, 1, 1), Date(2020, 6, 1)),
    Window("COVID rehiring surge", Date(2020, 7, 1), Date(2022, 6, 1)),
    Window("2022-2024 normalization", Date(2022, 7, 1), Date(2024, 12, 1)),
    Window("latest available", Date(2025, 1, 1), Date(2026, 8, 1)),
)


def months_in_window(window: Window) -> list[Date]:
    return month_range(window.start, window.end)


def in_any_window(t: Date, windows: tuple[Window, ...]) -> str | None:
    """The first window's name containing `t`, or None -- used to tag
    a month as NBER-recession-context or COVID-extreme-context without
    the caller needing to search the tuple itself."""
    for window in windows:
        if window.start <= t <= window.end:
            return window.name
    return None
