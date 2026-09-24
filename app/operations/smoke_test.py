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

Restricted deployments (#55A): with `--restricted`, credentials are
read from the operator's own `ACCESS_USERNAME`/`ACCESS_PASSWORD`
environment variables -- never a command-line argument, which would
land in shell history and `ps` output -- and sent as HTTP Basic auth.
The run then also PROVES the boundary rather than assuming it: an
anonymous request for economic data, the frontend and the sitemap must
each be refused, `/health` must stay open, and the authenticated
frontend must return HTML. The Rates and Housing reads are checked
alongside the original Inflation/Labor suite, since all four worlds ship.

Safety: never prints a connection string, host, username, or password
-- the base URL argument itself is the one thing this script does
print, and it is a public API endpoint address, never a secret
(production-reliability-deployment-v1.md #26B §33: "Public API base
URLs are configuration, not secrets").
"""

import argparse
import os
import sys

import httpx

_ROUTES = (
    "/health",
    "/readiness",
    "/api/v1/monitors/inflation",
    "/api/v1/monitors/labor",
    "/api/v1/since-last-visit",
    "/api/v1/releases",
    "/api/v1/monitors/rates",
    "/api/v1/housing",
)

#: Must be refused without credentials on a restricted deployment:
#: economic data, the frontend shell, and generated metadata.
_MUST_BE_GATED = ("/api/v1/monitors/inflation", "/", "/sitemap.xml")

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
    parser.add_argument(
        "--restricted",
        action="store_true",
        help="Authenticate with ACCESS_USERNAME/ACCESS_PASSWORD from the environment and verify the access boundary.",
    )
    args = parser.parse_args(argv)

    auth: httpx.BasicAuth | None = None
    if args.restricted:
        password = os.environ.get("ACCESS_PASSWORD")
        if not password:
            print("--restricted requires ACCESS_PASSWORD in the environment.", file=sys.stderr)
            return 2
        auth = httpx.BasicAuth(os.environ.get("ACCESS_USERNAME") or "macrochipz", password)

    print(f"Smoke testing: {args.base_url}")
    results: list[tuple[bool, str]] = []
    if args.restricted:
        with httpx.Client(base_url=args.base_url) as anonymous:
            results.extend(_check_boundary(anonymous))
    with httpx.Client(base_url=args.base_url, auth=auth) as client:
        results.extend(_check_route(client, path) for path in _ROUTES)
        if args.restricted:
            results.append(_check_frontend(client))

    failures = [message for ok, message in results if not ok]
    for _, message in results:
        print(message)

    if failures:
        print(f"Smoke test FAILED: {len(failures)} of {len(results)} checks failed.", file=sys.stderr)
        return 1

    print(f"Smoke test passed: {len(results)} of {len(results)} checks succeeded.")
    return 0


def _check_boundary(anonymous: httpx.Client) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []
    for path in _MUST_BE_GATED:
        try:
            status = anonymous.get(path, timeout=_TIMEOUT_SECONDS).status_code
        except httpx.HTTPError as exc:
            results.append((False, f"anonymous {path}: could not connect ({type(exc).__name__})"))
            continue
        results.append((status == 401, f"anonymous {path}: {status} (expected 401)"))
    try:
        status = anonymous.get("/health", timeout=_TIMEOUT_SECONDS).status_code
    except httpx.HTTPError as exc:
        return [*results, (False, f"anonymous /health: could not connect ({type(exc).__name__})")]
    results.append((status == 200, f"anonymous /health: {status} (expected 200)"))
    return results


def _check_frontend(client: httpx.Client) -> tuple[bool, str]:
    try:
        response = client.get("/", timeout=_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        return False, f"/ (frontend): could not connect ({type(exc).__name__})"
    is_html = response.headers.get("content-type", "").startswith("text/html")
    return response.status_code == 200 and is_html, f"/ (frontend): {response.status_code} {'html' if is_html else 'not html'}"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
