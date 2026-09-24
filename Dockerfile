# Increment #26D — one production-oriented image, reused unmodified for
# all three application entry points this project has (web, migration,
# maintenance/manual release processing) — never three subtly divergent
# images. See docs/product/production-reliability-deployment-v1.md
# (#26B) §4/§40-41 and docs/runbook/production-release-runbook.md.
#
# NOT build-verified in this development environment (no Docker daemon
# available here, honestly disclosed rather than pretended — see the
# runbook and #26D's own final report). Written to be correct by direct,
# careful review against this repository's own real dependency list and
# existing, already-verified local run commands (README.md), not
# guessed at.
#
# Pins Python 3.12, matching this repository's own frozen
# `requires-python = ">=3.12"` (pyproject.toml) and the exact local
# development interpreter (Python 3.12.5) this whole project has been
# built and tested against all session.
FROM python:3.12-slim

WORKDIR /app

# System build dependencies for psycopg[binary] and any C-extension
# wheels that lack a prebuilt manylinux wheel for this base image —
# removed from the final layer's own apt cache immediately after use,
# never left resident in the image.
# Increment #34: psycopg[binary] ships prebuilt manylinux wheels, so the
# compilers are needed only as a fallback. They are installed, used by
# `pip install` below, and then PURGED in the same image -- previously
# `build-essential` stayed resident, leaving a full toolchain in a
# production image for no runtime purpose.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Dependency-only layer first (better build-cache reuse across code
# changes that don't touch pyproject.toml) — production dependencies
# ONLY, never the `dev` extra (pytest is never installed in this
# image; pyproject.toml's own comment already states this discipline,
# restated here as the image's own behavior, not merely a hope).
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir . \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

# Increment #26C/#26D's own version-provenance mechanism
# (app/core/version.py): prefer a build-time-injected APP_VERSION over
# a `git rev-parse` fallback that would otherwise require a `.git`
# directory this image deliberately never copies in (see
# .dockerignore). Passed at build time: `docker build --build-arg
# APP_VERSION=<sha> .` — a future CI/CD pipeline's own job (#26D's
# runbook names this explicitly).
ARG APP_VERSION=""
ENV APP_VERSION=${APP_VERSION}

# Never baked into the image: DATABASE_URL, FRED_API_KEY,
# OPENAI_API_KEY, OPENAI_MODEL — every one of these is runtime-injected
# by the hosting platform's own environment/secret-store mechanism
# (production-reliability-deployment-v1.md §35), never an ENV/ARG in
# this file, and no .env file is ever copied in (.dockerignore).

# No default CMD assumption about which of the three entry points runs
# -- explicit here, overridden at `docker run`/deployment-manifest time
# for the other two:
#
#   Web (this image's own default):
#     docker run <image>
#
#   Migration (the deployment pipeline's own release phase --
#   production-reliability-deployment-v1.md §11/§12, ADR-027):
#     docker run <image> python -m app.operations.release preflight
#     docker run <image> python -m app.operations.release migrate
#
#   Maintenance (one bounded sweep -- #26D does NOT schedule this; see
#   #26E):
#     docker run <image> python -m app.operations.run_maintenance
#
#   Manual release processing (operator-invoked, one occurrence):
#     docker run <image> python -m app.operations.process_release --occurrence-id <id>
#
# The web command never runs a migration, never starts a scheduler, and
# never invokes maintenance -- app/main.py has, and must continue to
# have, zero awareness of any of them (enforced by
# tests/test_release_architecture.py).
# Increment #34: run as a non-root user. Nothing in this image needs
# root at runtime -- the application writes no files, binds an
# unprivileged port, and owns no system state.
RUN useradd --create-home --uid 10001 macrochipz \
    && chown -R macrochipz:macrochipz /app
USER macrochipz

# Increment #34, two changes required by the frozen deployment contract
# (docs/product/render-production-architecture-v1.md §9):
#
# - `$PORT`: the platform injects the port to bind and does not
#   guarantee detection of a fixed alternate one. Shell form so the
#   variable is expanded at container start, defaulting to 8000 so
#   local `docker run` is unchanged.
# - `--proxy-headers` with `--forwarded-allow-ips`: TLS terminates at
#   the platform edge, so without this the application sees the proxy's
#   address as the client and every request as plain HTTP. The allowed
#   set is configurable and defaults to `*`, which is correct ONLY
#   because this container is never exposed directly -- the platform is
#   always the sole ingress. Documented in the deployment guide.
#
# Increment #54A: both expansions are double-quoted. Unquoted, the
# `*` default is subject to pathname expansion by `sh`, so with
# FORWARDED_ALLOW_IPS unset it became the filenames in /app (`alembic
# alembic.ini app build pyproject.toml`) and uvicorn refused to start:
# "Got unexpected extra arguments". Found by the first real run of this
# CMD; pinned by tests/test_release_architecture.py, which executes it.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-*}\""]
