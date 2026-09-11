# Request Flows

Runtime flows through the system as it exists today. See
[`current-architecture.md`](current-architecture.md) for the static
component picture.

## Flow 1 — Health Check

```mermaid
sequenceDiagram
    participant C as Client
    participant U as Uvicorn
    participant F as FastAPI app (app/main.py)

    C->>U: GET /health
    U->>F: dispatch request
    F->>F: health()
    F-->>C: 200 {"status": "ok"}
```

No dependencies, no I/O, no configuration involved — this route exists to
answer "is the process up" independent of anything else.

## Flow 2 — Economic Series Request (success path)

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/series.py)
    participant S as EconomicDataService
    participant FC as FREDClient
    participant FRED as FRED REST API

    C->>R: GET /api/v1/series/UNRATE
    R->>R: settings.fred_api_key present?
    R->>S: get_series("UNRATE")
    S->>FC: get_series_info("UNRATE")
    FC->>FRED: GET /fred/series?series_id=UNRATE&api_key=...
    FRED-->>FC: 200 {"seriess": [{"title": "Unemployment Rate", "units": "Percent", ...}]}
    FC-->>S: series metadata dict
    S->>FC: get_observations("UNRATE", limit=10)
    FC->>FRED: GET /fred/series/observations?series_id=UNRATE&limit=10&sort_order=desc
    FRED-->>FC: 200 {"observations": [{"date": "...", "value": "4.1"}, ...]}
    FC-->>S: raw observations (newest first)
    S->>S: parse values ("." -> null), reverse to chronological order
    S-->>R: SeriesResponse
    R-->>C: 200 JSON (our contract, not FRED's)
```

Two separate FRED requests happen per series lookup — one for metadata
(title, units), one for observations — each going through the same
`FREDClient._get` request path (timeout, error translation) independently.

## Flow 3 — Failure Scenarios

All failures below funnel through the same shape: `FREDClient` raises one
of a small set of typed exceptions, and `app/api/series.py` is the single
place that maps each one to an HTTP status code. Nothing upstream of the
route (the service, the client) ever produces an HTTP response directly.

| Scenario | Where it originates | Exception | Where translated | HTTP status |
|---|---|---|---|---|
| Nonexistent series ID | FRED responds `400`, `error_message` mentions the series | `FREDSeriesNotFoundError` | `app/api/series.py` | `404` |
| `FRED_API_KEY` not configured | Checked in the route before a client is built | *(none raised — early return)* | `app/api/series.py` | `503` |
| FRED rejects the API key | FRED responds `400`, `error_message` mentions `api_key` | `FREDAuthError` | `app/api/series.py` | `503` |
| Upstream request exceeds timeout | `httpx.TimeoutException` inside `FREDClient._get` | `FREDTimeoutError` | `app/api/series.py` | `504` |
| Network failure / malformed FRED response | `httpx.HTTPError`, JSON decode failure, or missing expected fields | `FREDUpstreamError` | `app/api/series.py` | `502` |

### Nonexistent series

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant S as EconomicDataService
    participant FC as FREDClient
    participant FRED as FRED REST API

    C->>R: GET /api/v1/series/NOTREALSERIES123
    R->>S: get_series(...)
    S->>FC: get_series_info(...)
    FC->>FRED: GET /fred/series?series_id=NOTREALSERIES123&...
    FRED-->>FC: 400 {"error_message": "...series does not exist."}
    FC->>FC: raise FREDSeriesNotFoundError
    FC-->>S: (exception propagates)
    S-->>R: (exception propagates)
    R->>R: except FREDSeriesNotFoundError
    R-->>C: 404 {"detail": "Series 'NOTREALSERIES123' was not found."}
```

### Missing FRED configuration

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route

    C->>R: GET /api/v1/series/UNRATE
    R->>R: settings.fred_api_key is None
    R-->>C: 503 {"detail": "FRED integration is not configured on this server."}
```

No `FREDClient` is even constructed in this case — the route short-circuits
before any FRED call would be attempted.

### Bad FRED credentials

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant FC as FREDClient
    participant FRED as FRED REST API

    C->>R: GET /api/v1/series/UNRATE
    R->>FC: get_series_info(...)  (via the service)
    FC->>FRED: GET /fred/series?...&api_key=<rejected>
    FRED-->>FC: 400 {"error_message": "...api_key is not registered..."}
    FC->>FC: raise FREDAuthError
    FC-->>R: (exception propagates through the service)
    R->>R: except FREDAuthError
    R-->>C: 503 {"detail": "Economic data integration is currently unavailable."}
```

The client-facing message is deliberately generic: FRED's raw
`error_message` and the fact that the failure is credential-related are
never exposed to the API consumer.

### Upstream timeout

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant FC as FREDClient
    participant FRED as FRED REST API

    C->>R: GET /api/v1/series/UNRATE
    R->>FC: get_series_info(...)  (via the service)
    FC->>FRED: GET /fred/series?...
    Note over FC,FRED: no response within timeout (10s default)
    FC->>FC: httpx.TimeoutException -> raise FREDTimeoutError
    FC-->>R: (exception propagates through the service)
    R->>R: except FREDTimeoutError
    R-->>C: 504 {"detail": "Upstream FRED request timed out."}
```
