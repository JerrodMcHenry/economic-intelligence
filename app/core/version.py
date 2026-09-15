"""This application's own build/version identifier, for Increment
#26C's `/readiness` route (docs/product/production-reliability-deployment-v1.md
§18). Not a secret and not sensitive -- a short git commit hash, the
same class of information already public in this repository's own git
history; never a connection string, host, or credential.

Resolution order: an `APP_VERSION` environment variable, intended to be
set at build time by a future deployment pipeline (#26D, not built by
this increment) -- this module has no opinion about how that value
gets set, only how it is read. Falling back, for local development
only, to a best-effort `git rev-parse --short HEAD` against this
repository's own working tree; `"unknown"` if neither is available
(e.g. a packaged build artifact with no `.git` directory and no
`APP_VERSION` set).
"""

import os
import subprocess
from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@lru_cache(maxsize=1)
def application_version() -> str:
    env_value = os.environ.get("APP_VERSION")
    if env_value:
        return env_value

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"
