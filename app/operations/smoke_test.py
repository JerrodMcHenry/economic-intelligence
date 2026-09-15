"""Read-only post-deploy smoke test. See
docs/product/production-reliability-deployment-v1.md (#26B) §48/§39.

    python -m app.operations.smoke_test [--base-url http://localhost:8000]

GET-only -- issues no `POST`/`PUT`/`DELETE` of any kind, triggers no
maintenance sweep, no release processing, no FRED/OpenAI call (every
route checked below is a database-backed read path; see #26B §40).
Never mutates anything, anywhere.

Checks the exact minimum suite #26B §48 froze: `/health`, `/readiness`,
both canonical monitor endpoints, `/since-last-visit`, and the releases
endpoint Overview itself calls. A `200` carrying an honest
`INSUFFICIENT_DATA`/empty-content response is an ACCEPTABLE outcome on
a freshly migrated, not-yet-bootstrapped environment (#26B §39: cold-
start bootstrap completeness is #26F's own separate concern, never
this command's) -- only an unexpected `5xx`, an unready `/readiness`,
or any other non-2xx status fails this smoke test.

Safety: never prints a connection string, host, username, or password
-- the base URL argument itself is the one thing this script does
print, and it is a public API endpoint address, never a secret
(production-reliability-deployment-v1.md #26B §33: "Public API base
URLs are configuration, not secrets").
"""

import argparse
import sys

import httpx

_ROUTES = (
    "/health",
    "/readiness",
    "/api/v1/monitors/inflation",
    "/api/v1/monitors/labor",
    "/api/v1/since-last-visit",
    "/api/v1/releases",
)

_TIMEOUT_SECONDS = 10.0


def _check_route(client: httpx.Client, path: str) -> tuple[bool, str]:
    try:
        response = client.get(path, timeout=_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        return False, f"{path}: could not connect ({type(exc).__name__})"

    status = response.status_code

    if path == "/readiness":
        # An unready instance is a genuine smoke-test FAILURE -- a
        # release is not successfully smoke-tested if the very
        # instance it just deployed reports itself unsafe to route
        # traffic to (#26B §14-16).
        if status != 200:
            return False, f"{path}: not ready ({status})"
        return True, f"{path}: {status} ready"

    if status >= 500:
        return False, f"{path}: unexpected {status}"
    if status >= 400:
        return False, f"{path}: unexpected {status}"

    # A 200 here may honestly carry INSUFFICIENT_DATA/empty content on
    # a fresh environment -- acceptable (#26B §39), not inspected
    # further by this command.
    return True, f"{path}: {status}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.operations.smoke_test",
        description="Read-only post-deploy smoke test (docs/product/production-reliability-deployment-v1.md #26B §48).",
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="The deployed API's own base URL.")
    args = parser.parse_args(argv)

    print(f"Smoke testing: {args.base_url}")
    failures: list[str] = []
    with httpx.Client(base_url=args.base_url) as client:
        for path in _ROUTES:
            ok, message = _check_route(client, path)
            print(message)
            if not ok:
                failures.append(message)

    if failures:
        print(f"Smoke test FAILED: {len(failures)} of {len(_ROUTES)} checks failed.", file=sys.stderr)
        return 1

    print(f"Smoke test passed: {len(_ROUTES)} of {len(_ROUTES)} checks succeeded.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
