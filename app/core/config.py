"""Application configuration.

Reads settings from environment variables (optionally populated from a
local .env file for development). Nothing here should ever hold a real
secret value directly in source code.
"""

import os

from dotenv import load_dotenv

# Populate os.environ from a local .env file if one is present.
# No-op (and safe) if the file doesn't exist, e.g. in production.
load_dotenv()


class Settings:
    """Minimal settings container backed by environment variables."""

    fred_api_key: str | None = os.environ.get("FRED_API_KEY")
    fred_timeout_seconds: float = 10.0

    # The U.S. Treasury interest-rate XML feeds (Increment #29) are
    # unauthenticated public government data -- there is deliberately no
    # API key here to configure, read, or leak. Only a timeout.
    # 30s, not the 10s used for FRED: the Treasury feeds are served by a
    # noticeably slower stack, and a 15s default was observed timing out
    # against the live feed during #29's own verification.
    treasury_timeout_seconds: float = 30.0

    database_url: str | None = os.environ.get("DATABASE_URL")

    # No hardcoded default: the model is not baked into architecture, so an
    # unset OPENAI_MODEL means AI features are simply not configured, the
    # same way an unset FRED_API_KEY/DATABASE_URL disables their features.
    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY")
    openai_model: str | None = os.environ.get("OPENAI_MODEL")
    openai_timeout_seconds: float = 30.0


settings = Settings()
