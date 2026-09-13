# economic-intelligence

## Backend

```
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

FastAPI serves the API at `http://localhost:8000` (see `docs/architecture/current-architecture.md`).

## Frontend

```
cd frontend
npm install
npm run dev
```

Vite serves the app at `http://localhost:5173` and proxies `/api/*`
requests to the backend at `http://localhost:8000` (see
`frontend/vite.config.ts`) — start the backend first. No CORS
configuration is required for local development; see
`docs/architecture/current-architecture.md` for why.

The frontend is a presentation client only: it consumes canonical
JSON from the FastAPI backend and performs no economic calculations of
its own. See `frontend/.env.example` for the (non-secret) API base URL
configuration used in production builds.
