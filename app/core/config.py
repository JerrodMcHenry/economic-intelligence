"""Application configuration.

Reads settings from environment variables (optionally populated from a
local .env file for development). Nothing here should ever hold a real
secret value directly in source code.

Increment #34 adds a single, explicit `ENVIRONMENT` setting and derives
every production-behaviour decision from it here, in one place. The
alternative -- scattered `if os.environ.get("ENV") == "production"`
comparisons at each call site -- is how a development default silently
becomes a production one: each site is individually plausible, and no
single file tells you what the deployment actually does.

**Development defaults must never be silently unsafe in production.**
The rule applied throughout: where a setting is required for a control
to work, the development default is permissive and the PRODUCTION
default is closed. `is_production` decides which, and
`production_configuration_errors()` reports, at startup, anything
production needs and does not have.
"""

import os

from dotenv import load_dotenv

# Populate os.environ from a local .env file if one is present.
# No-op (and safe) if the file doesn't exist, e.g. in production.
load_dotenv()

#: The one recognised production marker. Anything else -- unset,
#: "development", "test", a typo -- is treated as NOT production, which
#: is the safe direction: a typo yields a permissive local app that
#: obviously is not production, never a production app silently running
#: with development defaults.
PRODUCTION_ENVIRONMENT = "production"

#: Shortest `ACCESS_PASSWORD` accepted. Anything shorter is treated as
#: unset (the gate then refuses everyone). The password is shared with a
#: handful of reviewers and is guessable online only through the
#: rate-limited gate, so length is the property that matters.
MIN_ACCESS_PASSWORD_LENGTH = 16


def _split_csv(raw: str | None) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


#: The driver this application installs (`psycopg[binary]`, i.e.
#: psycopg 3). See `_normalise_database_url`.
_DATABASE_DRIVER_SCHEME = "postgresql+psycopg://"


def _normalise_database_url(raw: str | None) -> str | None:
    """Point a driverless Postgres URL at the driver actually installed.

    Increment #54A. Managed Postgres providers (Render's
    `connectionString` included) hand out `postgresql://` or the older
    `postgres://`. SQLAlchemy maps the first to psycopg2, which this
    image does not install, and does not recognise the second at all --
    so a platform-issued URL made every database route return 500 and
    the pre-deploy migration fail. Rewriting only the scheme keeps the
    platform's value authoritative rather than asking an operator to
    hand-edit a credential. A URL that already names a driver is
    returned unchanged.
    """
    if not raw:
        return raw
    for scheme in ("postgresql://", "postgres://"):
        if raw.startswith(scheme):
            return _DATABASE_DRIVER_SCHEME + raw[len(scheme) :]
    return raw


class Settings:
    """Minimal settings container backed by environment variables."""

    # -----------------------------------------------------------------
    # Deployment mode
    # -----------------------------------------------------------------

    #: `production` enables the closed defaults below. Unset means local
    #: development.
    environment: str = (os.environ.get("ENVIRONMENT") or "development").strip().lower()

    #: Emitted by `/readiness` and useful in logs; `.git` is excluded
    #: from the image, so production should pass this as a build arg.
    app_version: str | None = os.environ.get("APP_VERSION")

    @property
    def is_production(self) -> bool:
        return self.environment == PRODUCTION_ENVIRONMENT

    # -----------------------------------------------------------------
    # Providers
    # -----------------------------------------------------------------

    fred_api_key: str | None = os.environ.get("FRED_API_KEY")
    fred_timeout_seconds: float = 10.0

    # The U.S. Treasury interest-rate XML feeds (Increment #29) are
    # unauthenticated public government data -- there is deliberately no
    # API key here to configure, read, or leak. Only a timeout.
    # 30s, not the 10s used for FRED: the Treasury feeds are served by a
    # noticeably slower stack, and a 15s default was observed timing out
    # against the live feed during #29's own verification.
    treasury_timeout_seconds: float = 30.0

    # The U.S. Census Bureau Data API (Increment #45) requires a key:
    # an unkeyed request to the New Residential Construction dataset is
    # redirected to Census's own "Missing Key" page rather than served.
    # Read here and passed to `CensusClient`; never logged, never
    # rendered into an error message, never reported as a value by
    # `production_configuration_errors()` below.
    census_api_key: str | None = os.environ.get("CENSUS_API_KEY")

    # 60s, the longest provider timeout here, and measured rather than
    # guessed: the whole `resconst` history is a single ~1.5 MB response
    # (26,773 rows, 1959-01 onward), which is the request the initial
    # Housing baseline import makes. Routine syncs fetch a small recent
    # window and return in well under a second.
    census_timeout_seconds: float = 60.0

    @property
    def census_configured(self) -> bool:
        """Whether Housing ingestion is available on this deployment.

        A BOOLEAN, deliberately -- it is the only thing any caller
        outside `CensusClient` needs to know about the credential, and
        it is safe to log, return in a response, and put in a startup
        line.
        """
        return bool(self.census_api_key)

    database_url: str | None = _normalise_database_url(os.environ.get("DATABASE_URL"))

    # No hardcoded default: the model is not baked into architecture, so an
    # unset OPENAI_MODEL means AI features are simply not configured, the
    # same way an unset FRED_API_KEY/DATABASE_URL disables their features.
    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY")
    openai_model: str | None = os.environ.get("OPENAI_MODEL")
    openai_timeout_seconds: float = 30.0

    # -----------------------------------------------------------------
    # Database connection behaviour (Increment #34)
    # -----------------------------------------------------------------

    #: Seconds to wait for a TCP connection to Postgres. Without this,
    #: psycopg waits on the OS default (minutes), so a network partition
    #: blocks a worker thread rather than failing into the 503 every
    #: route already handles.
    database_connect_timeout_seconds: int = int(os.environ.get("DATABASE_CONNECT_TIMEOUT_SECONDS") or 10)

    #: Recycle pooled connections before a managed Postgres or an
    #: intermediary silently drops them. `pool_pre_ping` already repairs
    #: a dead connection; recycling avoids paying for that discovery.
    database_pool_recycle_seconds: int = int(os.environ.get("DATABASE_POOL_RECYCLE_SECONDS") or 1800)

    # -----------------------------------------------------------------
    # HTTP surface (Increment #34)
    # -----------------------------------------------------------------

    #: Exact allowed browser origins, comma-separated. Never a wildcard.
    #: Empty in development is fine -- the Vite dev server proxies `/api`
    #: same-origin, so no CORS is involved locally at all.
    cors_allowed_origins: list[str] = _split_csv(os.environ.get("CORS_ALLOWED_ORIGINS"))

    #: Largest accepted request body. Every legitimate request here is a
    #: small JSON document; the largest contracted field is the Analyst's
    #: own 500-character question.
    max_request_body_bytes: int = int(os.environ.get("MAX_REQUEST_BODY_BYTES") or 64 * 1024)

    #: Shared secret for the operator-only write endpoints (series/rates/
    #: release sync). Unset in development leaves them open, which is
    #: convenient and harmless on localhost; unset in PRODUCTION closes
    #: them entirely rather than leaving them open (see
    #: `app/api/operator.py`).
    operator_token: str | None = os.environ.get("OPERATOR_TOKEN")

    # -----------------------------------------------------------------
    # Restricted access (Increment #55A)
    # -----------------------------------------------------------------

    #: HTTP Basic credentials required for EVERY response except
    #: `/health` -- the API, the frontend, share pages and static files
    #: alike. See `app/api/access_gate.py` and ADR-042.
    access_username: str = (os.environ.get("ACCESS_USERNAME") or "macrochipz").strip()
    access_password: str | None = os.environ.get("ACCESS_PASSWORD")

    @property
    def access_gate_required(self) -> bool:
        """Production is ALWAYS restricted; there is deliberately no
        public switch while Inflation and Jobs depend on FRED data whose
        redistribution terms are unresolved. Locally the gate is off
        unless a password is set, so development is unchanged."""
        return self.is_production or bool(self.access_password)

    @property
    def access_password_usable(self) -> bool:
        """A password too short to resist guessing counts as absent, so a
        weak value fails CLOSED rather than protecting nothing."""
        return len(self.access_password or "") >= MIN_ACCESS_PASSWORD_LENGTH

    #: The built frontend (`frontend/build/client`), served by this same
    #: process so the access gate covers it. Set by the Docker image;
    #: unset locally, where Vite serves the frontend.
    frontend_dist_dir: str | None = os.environ.get("FRONTEND_DIST_DIR") or None

    # -----------------------------------------------------------------
    # Analyst cost controls (Increment #34)
    # -----------------------------------------------------------------

    #: Hard ceiling on generated tokens per Analyst answer. #33 caps the
    #: question at 500 characters but never bounded the output, so a
    #: single request's cost was open-ended at the top.
    analyst_max_output_tokens: int = int(os.environ.get("ANALYST_MAX_OUTPUT_TOKENS") or 700)

    #: Simple fixed-window rate limit for `POST /analyst/explain`.
    #: IN-PROCESS AND PER-INSTANCE -- see `app/api/rate_limit.py`. Valid
    #: only for the single-instance deployment the frozen architecture
    #: specifies (render-production-architecture-v1.md §9).
    analyst_rate_limit_requests: int = int(os.environ.get("ANALYST_RATE_LIMIT_REQUESTS") or 10)
    analyst_rate_limit_window_seconds: int = int(os.environ.get("ANALYST_RATE_LIMIT_WINDOW_SECONDS") or 60)

    # -----------------------------------------------------------------
    # Observability (Increment #34)
    # -----------------------------------------------------------------

    log_level: str = (os.environ.get("LOG_LEVEL") or "INFO").strip().upper()

    #: JSON lines in production (a log aggregator can parse them, and
    #: `extra` fields survive); human-readable locally.
    @property
    def log_format_json(self) -> bool:
        override = os.environ.get("LOG_FORMAT")
        if override:
            return override.strip().lower() == "json"
        return self.is_production

    # -----------------------------------------------------------------
    # Legacy surface (Increment #34)
    # -----------------------------------------------------------------

    #: The Increment-8 tool-calling AI path, superseded by the #33
    #: Analyst. Unmounted by default everywhere. Opt-in only, and never
    #: in production (`app/main.py` refuses to mount it there at all).
    enable_legacy_ai_route: bool = (os.environ.get("ENABLE_LEGACY_AI_ROUTE") or "").strip().lower() in {"1", "true", "yes"}

    #: Interactive API docs. Public in development, closed in production
    #: -- `/docs` there mostly serves to advertise the operator
    #: endpoints to a scanner.
    @property
    def expose_api_docs(self) -> bool:
        override = os.environ.get("EXPOSE_API_DOCS")
        if override:
            return override.strip().lower() in {"1", "true", "yes"}
        return not self.is_production


settings = Settings()


def production_configuration_errors(current: Settings | None = None) -> list[str]:
    """What production needs and does not have.

    Called once at import in `app/main.py` so a misconfigured production
    deployment fails loudly at startup instead of at the first request
    that happens to need the missing value. Returns messages naming
    VARIABLES ONLY -- never a value, so this is safe to log and safe to
    print in a deploy log.
    """
    active = current or settings
    if not active.is_production:
        return []

    errors: list[str] = []
    if not active.database_url:
        errors.append("DATABASE_URL is required in production.")
    if not active.cors_allowed_origins and not active.frontend_dist_dir:
        # Required only when the frontend lives on another origin. When
        # this process serves it (#55A), every browser call is
        # same-origin and no CORS header is ever needed.
        errors.append(
            "CORS_ALLOWED_ORIGINS is required in production: the frontend is served from a separate origin, "
            "so without it every browser request from the deployed UI fails."
        )
    if not active.access_password_usable:
        errors.append(
            f"ACCESS_PASSWORD is not set or is shorter than {MIN_ACCESS_PASSWORD_LENGTH} characters: "
            "every request except /health will be refused."
        )
    if active.frontend_dist_dir and not os.path.isfile(os.path.join(active.frontend_dist_dir, "index.html")):
        errors.append("FRONTEND_DIST_DIR does not contain a built frontend (index.html is missing).")
    if any(origin == "*" for origin in active.cors_allowed_origins):
        errors.append("CORS_ALLOWED_ORIGINS must name exact origins; '*' is never accepted.")
    if not active.operator_token:
        # Not fatal: absent, the operator endpoints close themselves.
        # Reported so the operator learns it from a startup line rather
        # than from a 503 mid-bootstrap.
        errors.append(
            "OPERATOR_TOKEN is not set: the operator sync endpoints will refuse every request in production."
        )
    return errors
