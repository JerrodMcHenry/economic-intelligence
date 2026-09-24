"""Container-level checks for the production image (Increment #55A).

Run by `.github/workflows/container.yml` against the REAL image, started
with the web command in production mode. Standard library only, so it
runs on a bare CI runner -- and, unchanged, against any locally started
instance:

    ACCESS_PASSWORD=... OPERATOR_TOKEN=... python .github/scripts/verify_container.py \
        --base-url http://localhost:10000 --expect-version <sha>

    python .github/scripts/verify_container.py --base-url ... --misconfigured

Credentials come from the environment, never argv. No value is ever
printed: failures name the path, the status and what was expected.
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 15


def request(base_url, path, method="GET", auth=None, headers=None):
    req = urllib.request.Request(base_url + path, method=method, headers=dict(headers or {}))
    if auth:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            return response.status, _headers(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, _headers(error.headers), error.read()


def _headers(message):
    """Header names are case-insensitive; uvicorn sends them lowercase."""
    return {name.lower(): value for name, value in message.items()}


class Checks:
    def __init__(self):
        self.failures = []
        self.count = 0

    def expect(self, condition, description):
        self.count += 1
        print(("PASS " if condition else "FAIL ") + description)
        if not condition:
            self.failures.append(description)


def verify_configured(base_url, expect_version):
    checks = Checks()
    auth = (os.environ.get("ACCESS_USERNAME") or "macrochipz", os.environ["ACCESS_PASSWORD"])
    operator_token = os.environ["OPERATOR_TOKEN"]

    # --- The boundary: only /health is open ---------------------------
    status, headers, body = request(base_url, "/health")
    checks.expect(status == 200 and json.loads(body) == {"status": "ok"}, "anonymous /health -> 200 {status: ok}")
    checks.expect(headers.get("strict-transport-security") == "max-age=31536000", "production responses carry HSTS")

    for path in (
        "/readiness",
        "/api/v1/monitors/inflation",
        "/api/v1/monitors/labor",
        "/api/v1/monitors/rates",
        "/api/v1/housing",
        "/api/v1/intelligence",
        "/",
        "/inflation",
        "/jobs",
        "/intelligence/probe",
        "/sitemap.xml",
        "/robots.txt",
    ):
        status, headers, _ = request(base_url, path)
        checks.expect(
            status == 401 and headers.get("www-authenticate", "").startswith("Basic "),
            f"anonymous {path} -> 401 with a Basic challenge (got {status})",
        )

    status, _, _ = request(base_url, "/readiness", auth=(auth[0], "definitely-not-the-password"))
    checks.expect(status == 401, f"wrong password -> 401 (got {status})")

    # --- Authenticated ----------------------------------------------
    status, _, body = request(base_url, "/readiness", auth=auth)
    readiness = json.loads(body) if status == 200 else {}
    checks.expect(status == 200 and readiness.get("ready") is True, f"/readiness -> 200 ready (got {status})")
    if expect_version:
        checks.expect(readiness.get("version") == expect_version, "/readiness reports the built commit as its version")

    for path in (
        "/api/v1/monitors/inflation",
        "/api/v1/monitors/labor",
        "/api/v1/monitors/rates",
        "/api/v1/housing",
        "/api/v1/releases",
        "/api/v1/since-last-visit",
        "/api/v1/intelligence?limit=5",
        "/api/v1/analyst/availability",
    ):
        status, headers, _ = request(base_url, path, auth=auth)
        checks.expect(status == 200, f"{path} -> 200 (got {status})")

    status, _, body = request(base_url, "/api/v1/analyst/availability", auth=auth)
    checks.expect(status == 200 and json.loads(body).get("available") is False, "Analyst reports itself unavailable")

    for path in ("/", "/inflation", "/jobs", "/rates", "/housing", "/revisions", "/explain/cpi-vs-pce"):
        status, headers, body = request(base_url, path, auth=auth)
        checks.expect(
            status == 200
            and headers.get("content-type", "").startswith("text/html")
            and "default-src 'self'" in headers.get("content-security-policy", ""),
            f"frontend {path} -> 200 HTML with CSP (got {status})",
        )

    status, _, _ = request(base_url, "/api/v1/not-a-route", auth=auth)
    checks.expect(status == 404, f"unknown API path -> 404, never the HTML shell (got {status})")
    for path in ("/docs", "/openapi.json"):
        status, _, _ = request(base_url, path, auth=auth)
        checks.expect(status in (200, 404), f"{path} reachable only as the SPA or 404 (got {status})")
        if status == 200:
            _, headers, body = request(base_url, path, auth=auth)
            checks.expect(b"swagger" not in body.lower() and b'"openapi"' not in body, f"{path} is not API documentation")

    status, _, _ = request(base_url, "/api/v1/ai/query", method="POST", auth=auth, headers={"Content-Type": "application/json"})
    checks.expect(status in (404, 405), f"legacy AI route is not mounted (got {status})")

    # The operator boundary sits BENEATH the access gate: reviewer
    # credentials alone must not trigger ingestion.
    status, _, _ = request(base_url, "/api/v1/rates/sync", method="POST", auth=auth)
    checks.expect(status == 401, f"sync without operator token -> 401 (got {status})")
    status, _, _ = request(base_url, "/api/v1/rates/sync", method="POST", auth=auth, headers={"X-Operator-Token": "wrong"})
    checks.expect(status == 401, f"sync with wrong operator token -> 401 (got {status})")
    status, _, _ = request(base_url, "/api/v1/rates/sync", method="POST", headers={"X-Operator-Token": operator_token})
    checks.expect(status == 401, f"operator token without access credentials -> 401 (got {status})")

    return checks


def verify_misconfigured(base_url):
    """Production with ACCESS_PASSWORD and OPERATOR_TOKEN unset: the
    site must be unavailable, never open."""
    checks = Checks()
    status, _, _ = request(base_url, "/health")
    checks.expect(status == 200, f"/health still answers (got {status})")
    for path in ("/", "/api/v1/monitors/inflation", "/sitemap.xml", "/readiness"):
        status, _, _ = request(base_url, path)
        checks.expect(status == 503, f"{path} -> 503 fail-closed (got {status})")
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expect-version", default="")
    parser.add_argument("--misconfigured", action="store_true")
    args = parser.parse_args()

    checks = verify_misconfigured(args.base_url) if args.misconfigured else verify_configured(args.base_url, args.expect_version)
    if checks.failures:
        print(f"{len(checks.failures)} of {checks.count} container checks FAILED", file=sys.stderr)
        return 1
    print(f"All {checks.count} container checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
