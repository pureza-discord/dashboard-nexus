"""Shared scraper utilities: delays, circuit breaker, retry, and helpers.

Moved from root utils.py to keep all scraper-related code inside the
server package, avoiding broken root-level imports.
"""

import asyncio
import os
import random
import time
from typing import Callable, Coroutine


def _get_delay_range(min_s: float | None, max_s: float | None) -> tuple[float, float]:
    """Resolve delay range from arguments or env vars."""
    if min_s is None:
        min_s = float(os.getenv("DELAY_MIN", "1.8"))
    if max_s is None:
        max_s = float(os.getenv("DELAY_MAX", "6"))
    return min_s, max_s


async def random_delay(min_s: float | None = None, max_s: float | None = None) -> None:
    """Random async sleep to reduce scraping detection patterns."""
    min_s, max_s = _get_delay_range(min_s, max_s)
    await asyncio.sleep(random.uniform(min_s, max_s))


def clamp(value: int, min_value: int, max_value: int) -> int:
    """Clamp an integer between min and max bounds."""
    return max(min_value, min(value, max_value))


def add_observacao(lead: dict, obs: str) -> None:
    """Append a unique observation tag to a lead's 'observacoes' field."""
    observacoes = lead.get("observacoes", "")
    obs_set = {o.strip() for o in observacoes.split(",") if o.strip()}
    obs_set.add(obs)
    lead["observacoes"] = ",".join(sorted(obs_set))


class CircuitBreaker:
    """Simple circuit breaker to prevent continuous error loops.

    Opens after `fail_threshold` consecutive failures.
    Re-closes after `cooloff_s` seconds.
    """

    def __init__(self, fail_threshold: int = 5, cooloff_s: int = 60) -> None:
        self.fail_threshold = fail_threshold
        self.cooloff_s = cooloff_s
        self.fail_count = 0
        self.open_until = 0.0

    def allow(self) -> bool:
        if self.open_until == 0:
            return True
        return time.time() >= self.open_until

    def record_success(self) -> None:
        self.fail_count = 0
        self.open_until = 0.0

    def record_failure(self) -> None:
        self.fail_count += 1
        if self.fail_count >= self.fail_threshold:
            self.open_until = time.time() + self.cooloff_s


async def retry_async(
    action: Callable[[], Coroutine],
    retries: int = 3,
    min_s: float = 1.8,
    max_s: float = 6,
    breaker: CircuitBreaker | None = None,
) -> object:
    """Retry an async callable with exponential backoff and circuit breaker."""
    last_error = None
    for attempt in range(retries):
        if breaker is not None and not breaker.allow():
            raise RuntimeError("Circuit breaker open — too many recent failures")
        try:
            result = await action()
            if breaker is not None:
                breaker.record_success()
            return result
        except Exception as exc:
            last_error = exc
            if breaker is not None:
                breaker.record_failure()
            await random_delay(
                min_s=min_s * (1.5 ** attempt),
                max_s=max_s * (1.5 ** attempt),
            )
    if last_error:
        raise last_error
    return None
