# Economic Intelligence

Economic Intelligence is a full-stack application for retrieving, transforming, comparing, and analyzing macroeconomic data.

The project is designed around a core engineering principle: **deterministic software owns canonical calculations and application behavior**. AI capabilities are added only where probabilistic behavior provides clear value and cannot compromise the correctness of the underlying system.

> **Status:** Active development. Not yet deployed.

## What It Does

Economic Intelligence provides a structured API and user interface for working with economic time-series data.

Current capabilities include:

- Retrieve economic data from FRED
- Persist observations and series metadata in PostgreSQL
- Query historical observations
- Transform time-series data
  - Absolute change
  - Percent change
  - Moving averages
- Compare multiple economic series
- Align observations by date
- Calculate spreads
- Calculate Pearson correlation
- Compose transformations and analysis through a deterministic pipeline
- Present canonical backend results through a frontend client

## Architecture

The application separates responsibilities across distinct layers:

```text
Frontend
    ↓
FastAPI API
    ↓
Service Layer
    ↓
Domain Logic
    ↓
Repository Layer
    ↓
PostgreSQL
```

External economic data is retrieved through the FRED API.

The domain layer contains pure functions for economic transformations and analysis. The frontend does not perform economic calculations and instead renders canonical results produced by the backend.

Detailed architecture documentation is available in:

`docs/architecture/current-architecture.md`

## Engineering Principles

### Deterministic Core

Economic calculations, validation, state transitions, and canonical application behavior remain deterministic and testable.

AI/LLM outputs are not permitted to control authoritative calculations or application state.

### AI as an Optional Layer

AI capabilities are intentionally introduced only after the deterministic system can function independently.

Potential AI functionality is constrained to appropriate probabilistic tasks such as:

- Explaining economic results
- Summarizing deterministic analysis
- Interpreting user intent into validated schemas
- Generating non-authoritative insights

This architecture allows AI components to fail without compromising the correctness of the underlying economic analysis.

### Backend-Owned Business Logic

The FastAPI backend is the source of truth for application behavior.

The frontend acts as a presentation client and does not independently calculate economic metrics.

## Tech Stack

### Backend

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic
- httpx

### Frontend

- Node.js 24 LTS (exact version pinned in `.nvmrc`)
- TypeScript
- React
- Vite

### External Data

- Federal Reserve Economic Data (FRED)

## API Capabilities

Examples of currently implemented API functionality include:

### Historical Observations

`GET /api/v1/series/{series_id}/observations`

Retrieve stored historical observations for an economic series.

### Data Synchronization

`POST /api/v1/series/{series_id}/sync`

Retrieve observations from FRED and persist them locally.

### Transformations

`GET /api/v1/series/{series_id}/transform`

Apply deterministic transformations to a time series.

Supported transformations include:

- Absolute change
- Percent change
- Moving average

### Series Comparison

`GET /api/v1/analysis/compare`

Align two economic series and calculate comparative metrics including spread and Pearson correlation.

### Analysis Pipeline

`POST /api/v1/analysis/pipeline`

Compose transformations and comparative analysis into a single deterministic workflow.

## Reliability and Validation

The application includes explicit handling for:

- External provider failures
- Authentication failures
- Database availability errors
- Database integrity conflicts
- Invalid transformation parameters
- Invalid date ranges
- Request validation failures

Domain calculations are implemented as pure functions where practical, keeping economic logic independently testable from infrastructure.

## Documentation

Engineering decisions are documented alongside the codebase.

Key documentation includes:

- `docs/architecture/current-architecture.md`
- `docs/architecture/request-flows.md`
- Architecture Decision Records (ADRs)
- `ENGINEERING_JOURNAL.md`

The engineering journal records incremental implementation decisions, tradeoffs, failures, and lessons learned throughout development.

## Local Development

### Backend

Install dependencies and start the API:

```bash
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

FastAPI serves the API at:

```text
http://localhost:8000
```

### Frontend

The frontend's Node.js runtime is pinned in the repository-root `.nvmrc`
(currently `24.21.0`, Node 24 LTS). That single file is the runtime contract
for local development, GitHub Actions CI (`actions/setup-node`'s
`node-version-file`), and Render's Static Site build. `frontend/package.json`
declares the supported range (`engines.node: ^24.15.0`, the floor required by
the locked `jsdom`), and `frontend/.npmrc` sets `engine-strict=true`, so
`npm ci` fails immediately on an unsupported Node rather than later inside
the test runner. With nvm or fnm, run `nvm use` / `fnm use`.

Install dependencies and start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Vite serves the application at:

```text
http://localhost:5173
```

The development server proxies `/api/*` requests to the FastAPI backend at `http://localhost:8000`.

Start the backend before starting the frontend.

No CORS configuration is required for local development because API requests are proxied through the Vite development server.

See `docs/architecture/current-architecture.md` for additional architecture and request-flow details.

## Project Goals

Economic Intelligence is both a working application and an engineering project focused on building reliable data and AI-enabled systems.

The project emphasizes:

- Clear system boundaries
- Deterministic business logic
- Explicit failure behavior
- Validated data contracts
- Testable domain logic
- Documented architectural decisions
- Safe integration of probabilistic AI components

As development continues, AI functionality will be introduced as an optional layer around the deterministic core rather than as a dependency for canonical application behavior.
