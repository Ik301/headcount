"""Abuse limits for the public API: per-IP sliding-window rate limits and a bounded-concurrency gate.

Pure stdlib so CI (light deps) can test it. Wired up in src/api/app.py.
"""
import threading
import time
from collections import deque

LOOPBACK = {"127.0.0.1", "::1", "localhost"}


class RateLimiter:
    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            if len(self._hits) > 5000:  # drop idle keys so memory stays bounded
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
                    self._hits.pop(k, None)
            return True


def client_key(headers, host: str | None) -> tuple[str, bool]:
    """(rate-limit key, exempt). Cloudflare sets CF-Connecting-IP; a loopback request without it is the local poller."""
    cf = (headers.get("cf-connecting-ip") or "").strip()
    if cf:
        return cf, False
    host = host or "unknown"
    return host, host in LOOPBACK


class Busy(Exception):
    """Analysis capacity is full."""


GATE = threading.BoundedSemaphore(3)


def acquire_gate(timeout: float = 60.0) -> None:
    if not GATE.acquire(timeout=timeout):
        raise Busy("busy, try again")


def release_gate() -> None:
    GATE.release()
