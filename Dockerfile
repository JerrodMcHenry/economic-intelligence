# Increment #26D — one production-oriented image, reused unmodified for
# all three application entry points this project has (web, migration,
# maintenance/manual release processing) — never three subtly divergent
# images. See docs/product/production-reliability-deployment-v1.md
# (#26B) §4/§40-41 and docs/runbook/production-release-runbook.md.
#
# Increment #55A: built and exercised by CI on every push --
# `.github/workflows/container.yml` builds this exact file, migrates an
# isolated PostgreSQL, starts the web command in production mode and
# checks /health, /readiness and the access boundary. No development
# machine used for this project has a Docker daemon, so that workflow is
# where this image is verified.
#
# Increment #55A: the image also carries the built frontend. A restricted
# deployment must authenticate EVERY response, and a separate static
# site cannot (docs/adr/042-restricted-demo-access-gate.md), so the web
# process serves `frontend/build/client` behind the same access gate as
# the API.

# ---------------------------------------------------------------------
# Stage 1: build the frontend. Discarded after its output is copied --
# Node, node_modules and the frontend sources never reach the final
# image. The Node version is the repository's single runtime contract
# (/.nvmrc); tests/test_release_architecture.py pins the two together.
# ---------------------------------------------------------------------
ARG NODE_VERSION=24.21.0
FROM node:${NODE_VERSION}-slim AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Same-origin build: an empty API base makes every browser call relative
# to the page's own origin (frontend/src/api/client.ts), which is this
# process. No site URL: behind authentication there is nothing for a
# crawler to index, so no sitemap or absolute canonical is generated.
# Both are cleared explicitly so a platform-injected build argument can
# never change what this stage produces.
RUN VITE_API_BASE_URL= VITE_SITE_URL= npm run build

# ---------------------------------------------------------------------
# Stage 2: the production image.
#
# Pins Python 3.12, matching this repository's own frozen
# `requires-python = ">=3.12"` (pyproject.toml) and the exact local
# development interpreter (Python 3.12.5) this whole project has been
# built and tested against all session.
# ---------------------------------------------------------------------
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
# Increment #55A: the built frontend, served by the web command behind
# the access gate (app/web/frontend.py).
COPY --from=frontend /frontend/build/client ./frontend_dist
ENV FRONTEND_DIST_DIR=/app/frontend_dist

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
