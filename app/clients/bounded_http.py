"""One bounded HTTP transport for the first-party statistical providers
(Increment #56A: BLS and BEA).

Every guarantee a provider client needs, in one place so the two clients
cannot drift apart:

- **A timeout** on every request.
- **A byte cap enforced while streaming.** The body is counted as it
  arrives and abandoned the moment it exceeds the cap, so a broken or
  hostile upstream cannot exhaust memory. (`CensusClient` checks size
  after buffering, which is acceptable at its 8 MB bound; BEA's keyless
  file is ~37 MB, so here the bound has to hold before the bytes do.)
- **A narrow retry.** Only a timeout, a transport failure or a 5xx is
  retried, and only `max_attempts - 1` times -- the request is a pure
  read, and those are the failures that are plausibly transient. A 4xx
  and a malformed body are never retried. A 429 is never retried either:
  BEA locks a caller out for a minute and BLS counts every attempt
  against a daily quota, so an immediate retry can only make it worse.
- **Errors that carry no request.** Every error is raised `from None` and
  names the provider and a status, never a URL, a body or a credential.
  httpx exceptions render the full request URL; chaining one would put
  it in any traceback this reaches.
- **No redirects followed.** These clients only ever read URLs they
  built from constants.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import httpx


class ProviderError(Exception):
    """Base class. `provider` is a constant such as "BLS", never input."""

    def __init__(self, provider: str, message: str):
        super().__init__(f"{provider}: {message}")
        self.provider = provider


class ProviderTimeoutError(ProviderError):
    """No response within the timeout, after every allowed attempt."""


class ProviderUnavailableError(ProviderError):
    """Unreachable, or a 5xx after every allowed attempt."""


class ProviderRateLimitedError(ProviderError):
    """The provider refused for quota or rate reasons. Never retried."""


class ProviderResponseError(ProviderError):
    """A response arrived but cannot be trusted: an unexpected status,
    a body over the byte cap, or content that does not parse into the
    documented shape. Never retried -- it would fail identically."""


@dataclass(frozen=True)
class BoundedResponse:
    status_code: int
    headers: httpx.Headers
    body: bytes

    def json(self, provider: str) -> Any:
        import json

        try:
            return json.loads(self.body)
        except ValueError:
            raise ProviderResponseError(provider, "response is not valid JSON") from None


def request(
    provider: str,
    method: str,
    url: str,
    *,
    max_bytes: int,
    timeout: float,
    max_attempts: int = 2,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> BoundedResponse:
    """Perform one bounded request and return its complete body."""
    with _stream(provider, method, url, max_bytes=max_bytes, timeout=timeout, max_attempts=max_attempts,
                 json_body=json_body, headers=headers) as (response, chunks):
        return BoundedResponse(response.status_code, response.headers, b"".join(chunks))


@contextmanager
def stream_lines(
    provider: str,
    url: str,
    *,
    max_bytes: int,
    timeout: float,
    max_attempts: int = 2,
) -> Iterator[tuple[httpx.Headers, Iterator[str]]]:
    """Stream a text body line by line, under the same byte cap.

    For a large file where the caller keeps only a few lines (BEA's
    `NipaDataM.txt`: ~1.5 million lines, of which MacroChipz wants ~250).
    Retries apply only to reaching the response; once lines are flowing,
    a failure is raised rather than silently restarting mid-file.
    """
    with _stream(provider, "GET", url, max_bytes=max_bytes, timeout=timeout, max_attempts=max_attempts) as (
        response,
        chunks,
    ):
        yield response.headers, _decode_lines(provider, chunks)


def _decode_lines(provider: str, chunks: Iterator[bytes]) -> Iterator[str]:
    pending = b""
    for chunk in chunks:
        pending += chunk
        *complete, pending = pending.split(b"\n")
        for raw in complete:
            yield _decode(provider, raw)
    if pending:
        yield _decode(provider, pending)


def _decode(provider: str, raw: bytes) -> str:
    try:
        return raw.decode("utf-8").rstrip("\r")
    except UnicodeDecodeError:
        raise ProviderResponseError(provider, "response is not valid UTF-8 text") from None


@contextmanager
def _stream(
    provider: str,
    method: str,
    url: str,
    *,
    max_bytes: int,
    timeout: float,
    max_attempts: int,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
):
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    for attempt in range(1, max_attempts + 1):
        client = httpx.Client(timeout=timeout, follow_redirects=False)
        try:
            response_cm = client.stream(method, url, json=json_body, headers=headers)
            try:
                response = response_cm.__enter__()
            except httpx.TimeoutException:
                client.close()
                if attempt < max_attempts:
                    continue
                raise ProviderTimeoutError(provider, f"timed out after {max_attempts} attempt(s)") from None
            except httpx.HTTPError:
                client.close()
                if attempt < max_attempts:
                    continue
                raise ProviderUnavailableError(provider, f"unreachable after {max_attempts} attempt(s)") from None

            if response.status_code >= 500 and attempt < max_attempts:
                response_cm.__exit__(None, None, None)
                client.close()
                continue

            try:
                _raise_for_status(provider, response.status_code, max_attempts)
                _raise_if_declared_too_large(provider, response, max_bytes)
                yield response, _capped_chunks(provider, response, max_bytes)
            finally:
                response_cm.__exit__(None, None, None)
            return
        finally:
            client.close()


def _raise_for_status(provider: str, status: int, max_attempts: int) -> None:
    if status == 429:
        raise ProviderRateLimitedError(provider, "rate limited (HTTP 429)")
    if status >= 500:
        raise ProviderUnavailableError(provider, f"HTTP {status} after {max_attempts} attempt(s)")
    if status >= 300:
        # Includes redirects, which are never followed.
        raise ProviderResponseError(provider, f"unexpected HTTP {status}")


def _raise_if_declared_too_large(provider: str, response: httpx.Response, max_bytes: int) -> None:
    declared = response.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise ProviderResponseError(provider, f"response exceeds the {max_bytes}-byte bound")


def _capped_chunks(provider: str, response: httpx.Response, max_bytes: int) -> Iterator[bytes]:
    received = 0
    try:
        for chunk in response.iter_bytes():
            received += len(chunk)
            if received > max_bytes:
                raise ProviderResponseError(provider, f"response exceeds the {max_bytes}-byte bound")
            yield chunk
    except httpx.TimeoutException:
        raise ProviderTimeoutError(provider, "timed out while reading the response") from None
    except httpx.HTTPError:
        raise ProviderUnavailableError(provider, "connection failed while reading the response") from None
