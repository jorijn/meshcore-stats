"""Retry logic and circuit breaker state management."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional, TypeVar

from .env import get_config
from . import log

T = TypeVar("T")


class CircuitBreaker:
    """
    Simple circuit breaker for remote requests.
    State is persisted to JSON file.
    """

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.consecutive_failures = 0
        self.cooldown_until: float = 0
        self.last_success: float = 0
        self._load()

    def _load(self) -> None:
        """Load state from file."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self.consecutive_failures = data.get("consecutive_failures", 0)
                self.cooldown_until = data.get("cooldown_until", 0)
                self.last_success = data.get("last_success", 0)
            except (json.JSONDecodeError, OSError) as e:
                log.warn(f"Failed to load circuit breaker state: {e}")

    def _save(self) -> None:
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "consecutive_failures": self.consecutive_failures,
            "cooldown_until": self.cooldown_until,
            "last_success": self.last_success,
        }
        self.state_file.write_text(json.dumps(data, indent=2))

    def is_open(self) -> bool:
        """Check if circuit is open (in cooldown)."""
        return time.time() < self.cooldown_until

    def cooldown_remaining(self) -> int:
        """Return seconds remaining in cooldown, or 0 if not in cooldown."""
        remaining = self.cooldown_until - time.time()
        return max(0, int(remaining))

    def record_success(self) -> None:
        """Record a successful call."""
        self.consecutive_failures = 0
        self.last_success = time.time()
        self._save()

    def record_failure(self, max_failures: int, cooldown_s: int) -> None:
        """Record a failed call and potentially open the circuit."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= max_failures:
            self.cooldown_until = time.time() + cooldown_s
            log.warn(
                f"Circuit breaker opened: {self.consecutive_failures} failures, "
                f"cooldown for {cooldown_s}s"
            )
        self._save()

    def to_dict(self) -> dict:
        """Return state as dict for snapshot."""
        return {
            "consecutive_failures": self.consecutive_failures,
            "cooldown_until": self.cooldown_until,
            "last_success": self.last_success,
            "is_open": self.is_open(),
            "cooldown_remaining_s": self.cooldown_remaining(),
        }


async def with_retries(
    fn: Callable[[], Coroutine[Any, Any, T]],
    attempts: int = 2,
    backoff_s: float = 4.0,
    name: str = "operation",
) -> tuple[bool, Optional[T], Optional[Exception]]:
    """
    Execute async function with retries.

    Args:
        fn: Async function to call
        attempts: Max number of attempts
        backoff_s: Seconds to wait between retries
        name: Name for logging

    Returns:
        (success, result, last_exception)
    """
    last_exception: Optional[Exception] = None

    for attempt in range(1, attempts + 1):
        try:
            result = await fn()
            if attempt > 1:
                log.info(f"{name}: succeeded on attempt {attempt}/{attempts}")
            return (True, result, None)
        except Exception as e:
            last_exception = e
            log.info(f"{name}: attempt {attempt}/{attempts} failed: {e}")
            if attempt < attempts:
                log.debug(f"{name}: retrying in {backoff_s}s...")
                await asyncio.sleep(backoff_s)

    return (False, None, last_exception)


def get_repeater_circuit_breaker() -> CircuitBreaker:
    """Get the circuit breaker for repeater requests."""
    cfg = get_config()
    state_file = cfg.state_dir / "repeater_circuit.json"
    return CircuitBreaker(state_file)
