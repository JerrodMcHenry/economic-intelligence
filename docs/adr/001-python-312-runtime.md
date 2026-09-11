# ADR-001: Python 3.12 as the Development/Runtime Standard

## Status
Accepted

## Context

A Python version needed to be chosen for both the local development
environment (`.venv`) and the range of interpreter versions the project
declares itself compatible with (`pyproject.toml`'s `requires-python`).

During initial setup, `.venv` was accidentally created against a freshly
installed **Python 3.14** interpreter (Homebrew's `python@3.14`) rather
than a deliberately chosen version. This was caught before meaningful work
was built on top of it.

## Decision

Standardize local development and the runtime environment on **Python
3.12** (`.venv` recreated from a 3.12 interpreter; currently 3.12.5).
`pyproject.toml` declares `requires-python = ">=3.12"` — a floor, not a
narrow pin.

## Alternatives Considered

- **Stay on Python 3.14** (whatever was accidentally installed). Rejected:
  3.14 is new enough that third-party library compatibility and general
  ecosystem maturity are less proven than 3.12's at this point in the
  adoption curve — a needless risk for a project with no dependency on
  3.14-specific features.
- **Pin an upper bound** (`>=3.12,<3.13`). Considered and briefly applied,
  then reverted: there was no actual technical finding that 3.13+ is
  incompatible. An upper bound should reflect a known constraint, not be
  added defensively.
- **Target an older LTS-style version** (e.g. 3.10/3.11) for maximum
  library compatibility. Rejected as unnecessarily conservative — 3.12 is
  well-supported and current without being bleeding-edge.

## Why This Decision

3.12 is mature enough that the dependencies this project already needs
(FastAPI, Uvicorn, httpx, Pydantic) and whatever it adds later have had
time to be tested against it, while still being recent enough to have no
foreseeable reason to move off of soon. Declaring only a floor
(`>=3.12`) rather than a narrow range keeps the package honestly scoped:
it says "this needs at least 3.12" rather than making an unverified claim
about what it doesn't support.

## Consequences / Tradeoffs

- Gains: a single, deliberately-chosen interpreter version for local dev
  removes "works on my machine, not on ambient system Python" ambiguity.
  A floor-only `requires-python` avoids blocking future interpreter
  upgrades for no real reason.
- Cost: nothing is currently enforcing that CI or a deployment environment
  actually uses 3.12 specifically — that's a convention right now, not a
  guarantee, until CI/CD exists.

## Revisit When

- A dependency requires a newer minimum Python version.
- A specific, verified incompatibility with a newer Python version (3.13+)
  is found — at that point, and only then, add an upper bound back with
  the reason documented.
- CI/CD is introduced (a later increment) — at that point the Python
  version should be pinned explicitly in the CI configuration too, not
  left to whatever the runner defaults to.
