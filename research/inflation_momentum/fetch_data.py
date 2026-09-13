"""One-off data acquisition for the Inflation Momentum Methodology Study.

Reuses the existing production FRED boundary (`app.clients.fred.FREDClient`)
directly rather than duplicating HTTP/auth/error-handling logic -- but
writes fetched data to research-local JSON files, NEVER to the
production PostgreSQL database. This keeps the research harness fully
isolated from production runtime behavior: no `session_scope()`, no
`SeriesRepository`, no write path of any kind.

Run manually, once (or whenever the cache needs refreshing):

    .venv/bin/python research/inflation_momentum/fetch_data.py

The study itself (study.py) reads only from the cached JSON files this
script produces -- never re-fetches live data on every run, which is
what makes repeated study runs deterministic and offline (see
Reproducibility in STUDY_RESULTS.md).

No API key is ever read, printed, or logged by this script -- it flows
straight from `app.core.config.settings` into `FREDClient`, exactly as
the production sync endpoint already does.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.clients.fred import FREDError  # noqa: E402
from app.clients.fred import FREDClient
from app.core.config import settings  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent / "data"

# The four canonical series for this study (Section 2 of the research brief).
SERIES_IDS = ["CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE"]

# FRED's own documented maximum; comfortably covers full history for
# monthly series going back to the 1940s-1950s (under 1000 monthly
# observations total for any of these four).
FETCH_LIMIT = 100_000


def fetch_series(client: FREDClient, series_id: str) -> dict:
    """Fetch full metadata + full observation history for one series,
    using only the existing FREDClient methods -- no new HTTP logic."""
    info = client.get_series_info(series_id)
    raw_observations = client.get_observations(series_id, limit=FETCH_LIMIT)
    # FRED returns newest-first; store chronologically, matching the
    # convention EconomicDataService.get_series already uses.
    observations = list(reversed(raw_observations))
    return {
        "series_id": info.get("id", series_id),
        "title": info.get("title"),
        "units": info.get("units"),
        "frequency": info.get("frequency"),
        "seasonal_adjustment": info.get("seasonal_adjustment"),
        "observation_start_reported_by_fred": info.get("observation_start"),
        "observation_end_reported_by_fred": info.get("observation_end"),
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "observations": [{"date": obs["date"], "value": obs["value"]} for obs in observations],
    }


def main() -> None:
    if not settings.fred_api_key:
        print("FRED_API_KEY is not configured. Cannot fetch data. Nothing was written.")
        sys.exit(1)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = FREDClient(api_key=settings.fred_api_key, timeout=settings.fred_timeout_seconds)

    for series_id in SERIES_IDS:
        try:
            data = fetch_series(client, series_id)
        except FREDError as exc:
            print(f"FAILED to fetch {series_id}: {type(exc).__name__} (not the exception message, to avoid "
                  f"accidentally logging any upstream detail beyond what's needed)")
            sys.exit(1)

        out_path = DATA_DIR / f"{series_id}.json"
        out_path.write_text(json.dumps(data, indent=2))
        n = len(data["observations"])
        first = data["observations"][0]["date"] if n else None
        last = data["observations"][-1]["date"] if n else None
        print(f"{series_id}: {n} observations, {first} .. {last} -> {out_path}")


if __name__ == "__main__":
    main()
