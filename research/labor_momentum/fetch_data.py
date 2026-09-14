"""One-off data acquisition for the Labor Momentum Methodology
Validation (Increment #20A.1).

Deliberately does NOT reuse `app.clients.fred.FREDClient` the way
`research/inflation_momentum/fetch_data.py` does -- that client
requires a configured `FRED_API_KEY`, and this increment's own
instructions are explicit: prefer a public download over anything
that would need a project secret when one is available. FRED's own
`fredgraph.csv` endpoint (the same CSV export used by the "Download"
button on any FRED series page) requires no API key and returns the
identical, authoritative, latest-revised observation history FRED's
API would. This script never reads `.env`, never touches
`app.core.config.settings`, and never prints anything resembling a
credential.

Writes raw CSV straight through to `data/<SERIES_ID>.csv` -- no
transformation, no filtering, so the cached file is byte-for-byte what
FRED served. `data/` is gitignored (see `.gitignore`): this script is
how it gets regenerated, the same "regenerable, not committed"
discipline `research/inflation_momentum/` already established.

Run manually:
    .venv/bin/python research/labor_momentum/fetch_data.py
"""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

DATA_DIR = Path(__file__).resolve().parent / "data"
SERIES_IDS = ("PAYEMS", "UNRATE")
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def fetch_series_csv(series_id: str) -> str:
    url = FRED_CSV_URL.format(series_id=series_id)
    with urlopen(url, timeout=30) as response:  # noqa: S310 -- fixed https FRED host, not user input
        return response.read().decode("utf-8")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for series_id in SERIES_IDS:
        csv_text = fetch_series_csv(series_id)
        out_path = DATA_DIR / f"{series_id}.csv"
        out_path.write_text(csv_text)
        row_count = csv_text.count("\n") - 1  # header line excluded
        print(f"{series_id}: wrote {out_path} ({row_count} observations)")


if __name__ == "__main__":
    main()
