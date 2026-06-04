

import time
import random
import sqlite3
from functools import wraps

from pyworkflow.utils import yellowStr, redStr


def is_sqlite_lock_error(exc: Exception) -> bool:
    """Return True if exc is a SQLite OperationalError indicating locked/busy DB."""
    if isinstance(exc, sqlite3.OperationalError):
        msg = str(exc).lower()
        # Cover common variants reported by SQLite
        return (
            "database is locked" in msg or
            "database is busy" in msg or
            "locked" in msg or
            "busy" in msg
        )
    return False

def retry_on_sqlite_lock(
    max_attempts: int = 15,
    initial_delay: float = 0.25,
    backoff_factor: float = 1.7,
    max_delay: float = 10,
    jitter: float = 0.05,
    log=None,
    predicate=is_sqlite_lock_error,
):
    """
    Decorator that retries the wrapped function when SQLite signals lock/busy.

    Behavior:
      - Exponential backoff with small jitter to avoid retry synchronization.
      - Only retries when predicate(exc) is True (i.e., lock/busy by default).
      - Propagates any non-retriable exceptions immediately.
      - If max attempts are exhausted, re-raises the original exception.

    Parameters:
      max_attempts   Max number of tries (including the first call).
      initial_delay  Initial sleep before the first retry (seconds).
      backoff_factor Multiply delay on each retry.
      max_delay      Cap the delay (seconds).
      jitter         Random noise added to delay (seconds).
      log            Optional logger (e.g., logging.getLogger(__name__)).
      predicate      Function deciding whether the exception should be retried.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            delay = float(initial_delay)
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if predicate(exc):
                        attempts += 1
                        who = getattr(func, "__qualname__", func.__name__)
                        if log:
                            if attempts == 1:
                                log.error(yellowStr(f"[{who}] SQLite locked/busy; retrying up to {max_attempts} attempts"))
                            log.error(yellowStr(f"[{who}] attempt {attempts}/{max_attempts} -> {exc}; sleeping {delay:.2f}s"))
                        if attempts >= max_attempts:
                            if log:
                                log.error(redStr(f"[{who}] exhausted retries; raising"))
                            raise
                        sleep_for = delay + random.uniform(0.0, jitter)
                        time.sleep(sleep_for)
                        delay = min(delay * backoff_factor, max_delay)
                        continue
                    # Not a lock/busy error -> propagate
                    raise
        return wrapper
    return decorator
