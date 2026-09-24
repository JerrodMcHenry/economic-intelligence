"""A minimal in-process rate limiter (Increment #34).

Scope, stated plainly because it is the whole point: **this is a
per-process, in-memory, fixed-window counter.** It is correct only for
the single-instance deployment the frozen architecture specifies
(`docs/product/render-production-architecture-v1.md` §9: "Instance
count: 1"). Two instances would each allow the configured budget.

That constraint is deliberate. The alternative -- Redis, or any shared
store -- would introduce a new network dependency, a new failure mode,
and a new thing to operate, in exchange for correctness this deployment
does not yet need. When the deployment grows past one instance, this
file is the place that has to change, and the docstring says so rather
than letting a future reader assume it was ever distributed.

It protects cost, not correctness: the Analyst is the only endpoint
where an anonymous caller can spend real money, and it is the only
endpoint this guards.
"""

import threading
import time
from collections import defaultdict, deque


class FixedWindowRateLimiter:
    """Allow `limit` events per `window_seconds` per key.

    A deque of timestamps per key, pruned on read. Memory is bounded by
    the number of distinct keys seen within a window; keys that fall
    idle are dropped when they next prune to empty, so a scan across
    many source addresses cannot grow this without bound for longer
    than one window.
    """

    def __init__(self, limit: int, window_seconds: int):
        self._limit = limit
        self._window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        """Record an attempt; return whether it is within budget."""
        moment = time.monotonic() if now is None else now
        cutoff = moment - self._window

        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()

            if not events:
                # Nothing left in the window -- drop the key entirely so
                # idle keys do not accumulate.
                self._events.pop(key, None)
                events = self._events[key]

            if len(events) >= self._limit:
                return False

            events.append(moment)
            return True

    def is_limited(self, key: str, now: float | None = None) -> bool:
        """Whether `key` has exhausted its budget, WITHOUT recording an
        attempt (#55A). The access gate needs this: it counts only
        failed logins, and it must refuse a locked-out client before
        checking credentials -- otherwise a correct guess would still
        be distinguishable from a wrong one."""
        moment = time.monotonic() if now is None else now
        with self._lock:
            events = self._events.get(key)
            if not events:
                return False
            return sum(1 for moment_seen in events if moment_seen > moment - self._window) >= self._limit

    def retry_after_seconds(self, key: str, now: float | None = None) -> int:
        """Whole seconds until the oldest event in the window expires --
        what a caller should wait before retrying."""
        moment = time.monotonic() if now is None else now
        with self._lock:
            events = self._events.get(key)
            if not events:
                return 0
            return max(1, int(self._window - (moment - events[0])) + 1)

    def reset(self) -> None:
        """Test-only: forget every recorded event."""
        with self._lock:
            self._events.clear()


def client_key(client_host: str | None, forwarded_for: str | None) -> str:
    """The rate-limit key for a request.

    Behind Render's proxy the socket peer is the proxy, so the caller's
    address arrives in `X-Forwarded-For`. Only the FIRST entry is used
    and it is never trusted for anything but bucketing: a caller can
    forge it to evade their own limit, which costs them nothing and
    gains them a different bucket. Defeating that needs infrastructure
    (a WAF or platform rate limit), not application code pretending a
    client-supplied header is authoritative.
    """
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return client_host or "unknown"
