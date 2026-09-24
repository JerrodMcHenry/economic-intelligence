"""Serve the built frontend from the API process (Increment #55A).

Until #55A the plan was a separate Render Static Site. A static site
cannot require authentication (ADR-042), so for a restricted deployment
it would publish every page, share page and sitemap to anyone. Serving
`frontend/build/client` from this process puts the frontend behind the
same `AccessGateMiddleware` as the API, and makes every browser call
same-origin -- no CORS, and `connect-src 'self'` is the whole CSP story.

Resolution, in order, mirroring what a static host does for a React
Router `ssr: false` build:

1. `/api/...` never falls through to HTML: an unknown API path is a JSON
   404, not an application shell.
2. An existing file is served (`/assets/…`, `/favicon.svg`).
3. A prerendered directory is served by its `index.html` (`/rates`).
4. A path whose last segment looks like a file (`.js`, `.png`) and does
   not exist is a 404 -- never HTML standing in for a missing script.
5. Anything else gets `__spa-fallback.html`, React Router's SPA-mode
   shell, which renders the route (or the app's own 404 page) client-
   side. NOT `index.html`: that is the prerendered home page and does
   not hydrate on other paths (React Router changelog, "SPA Mode"
   fallback for `ssr:false` prerendering).
"""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

SPA_FALLBACK = "__spa-fallback.html"

#: The CSP the frontend needs, set on every HTML response
#: (`docs/operations/production-deployment-v1.md` §12, where the static
#: host was to own it -- this process is now that host). `'unsafe-inline'`
#: in `script-src` is required by React Router's inline hydration scripts
#: and the pre-paint theme bootstrap; recorded there as a known weakening.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)

# The slim base image has no /etc/mime.types; register what the build
# emits so `X-Content-Type-Options: nosniff` never meets a wrong type.
for _extension, _type in {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".json": "application/json",
    ".txt": "text/plain",
    ".xml": "application/xml",
}.items():
    mimetypes.add_type(_type, _extension)


def build_frontend_router(dist_dir: str | Path) -> APIRouter:
    root = Path(dist_dir).resolve()
    router = APIRouter(include_in_schema=False)

    @router.api_route("/{requested_path:path}", methods=["GET", "HEAD"])
    def serve_frontend(requested_path: str) -> FileResponse:
        if requested_path == "api" or requested_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        target = _resolve(root, requested_path)
        if target is None:
            raise HTTPException(status_code=404, detail="Not Found")
        return _file_response(root, target)

    return router


def _resolve(root: Path, requested_path: str) -> Path | None:
    segments = [segment for segment in requested_path.split("/") if segment]
    # No dotfiles, no traversal: rejected by shape before touching disk.
    if any(segment.startswith(".") for segment in segments):
        return None

    candidate = root.joinpath(*segments).resolve() if segments else root
    if not candidate.is_relative_to(root):
        return None
    if candidate.is_file():
        return candidate
    if (candidate / "index.html").is_file():
        return candidate / "index.html"
    if segments and "." in segments[-1]:
        return None
    return root / SPA_FALLBACK


def _file_response(root: Path, target: Path) -> FileResponse:
    headers: dict[str, str] = {}
    if target.relative_to(root).parts[:1] == ("assets",):
        # Content-hashed filenames: safe to keep for a year. `private`
        # because everything here is behind authentication and must
        # never sit in a shared cache.
        headers["Cache-Control"] = "private, max-age=31536000, immutable"
    else:
        headers["Cache-Control"] = "private, no-cache"
    if target.suffix == ".html":
        headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return FileResponse(target, headers=headers)
