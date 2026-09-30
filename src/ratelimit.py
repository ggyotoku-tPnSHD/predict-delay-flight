import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

WINDOW_SECONDS = 60


class SlidingWindow:
    """Counts requests per key over the last WINDOW_SECONDS. In-memory, so it assumes one server process."""

    def __init__(self, limit: int):
        self.limit = limit
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and q[0] <= now - WINDOW_SECONDS:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            # Drop idle keys so memory doesn't grow with every visitor ever seen.
            if len(self.hits) > 10_000:
                for k in [k for k, v in self.hits.items() if not v]:
                    del self.hits[k]
            return True


def client_ip(request: Request) -> str:
    # Render sits behind Cloudflare, which overwrites CF-Connecting-IP with the real client address.
    # X-Forwarded-For is only a fallback: Render appends to it, so its first entry can be forged
    # (verified on the live service), which is why a global limit backs up the per-IP one.
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limiter(name: str, per_ip: int, global_limit: int):
    per_ip_window = SlidingWindow(int(os.environ.get(f"RATE_{name}_PER_IP", per_ip)))
    global_window = SlidingWindow(int(os.environ.get(f"RATE_{name}_GLOBAL", global_limit)))

    def dependency(request: Request):
        if not per_ip_window.allow(client_ip(request)):
            raise HTTPException(429, "Too many requests. Please wait a minute and try again.",
                                headers={"Retry-After": str(WINDOW_SECONDS)})
        if not global_window.allow("all"):
            raise HTTPException(429, "The demo is busy right now. Please try again in a minute.",
                                headers={"Retry-After": str(WINDOW_SECONDS)})

    return dependency
