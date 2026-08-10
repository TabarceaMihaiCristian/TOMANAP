"""Memory-bounded sliding-window abuse protection for entry endpoints."""

import asyncio
import math
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Result of one atomic rate-limit check."""

    allowed: bool
    retry_after_seconds: int


class RateLimiter(Protocol):
    """Common contract for local and distributed rate limiters."""

    async def check(self, key: str) -> RateLimitDecision:
        """Atomically admit or reject one request."""


class SlidingWindowRateLimiter:
    """Process-local limiter with LRU-bounded attacker-controlled keys."""

    def __init__(
        self,
        *,
        requests: int,
        window_seconds: float,
        max_keys: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if requests < 1 or window_seconds <= 0 or max_keys < 1:
            raise ValueError("Rate-limit bounds must be positive")
        self.requests = requests
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self.clock = clock
        self._windows: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = asyncio.Lock()

    @property
    def tracked_key_count(self) -> int:
        return len(self._windows)

    async def check(self, key: str) -> RateLimitDecision:
        """Atomically admit a request or return its minimum retry delay."""
        async with self._lock:
            now = self.clock()
            window = self._windows.get(key)
            if window is None:
                if len(self._windows) >= self.max_keys:
                    self._windows.popitem(last=False)
                window = deque()
                self._windows[key] = window
            else:
                self._windows.move_to_end(key)

            cutoff = now - self.window_seconds
            while window and window[0] <= cutoff:
                window.popleft()

            if len(window) >= self.requests:
                retry_after = max(1, math.ceil(self.window_seconds - (now - window[0])))
                return RateLimitDecision(False, retry_after)

            window.append(now)
            return RateLimitDecision(True, 0)
