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


settings = Settings()
