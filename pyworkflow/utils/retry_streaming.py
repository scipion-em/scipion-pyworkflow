

import logging
import os
import time
import random
import sqlite3
from functools import wraps

from pyworkflow.utils import yellowStr, redStr

logger = logging.getLogger(__name__)

# Stream state constants (mirrors pyworkflow.object.Set)
_STREAM_OPEN = 1
_STREAM_CLOSED = 2
_STREAM_STATE_KEY = '_streamState'

# Tri-state result of an independent stream-state probe.
#   OPEN    -> the producer definitively reported the stream as open
#   CLOSED  -> the producer definitively reported the stream as closed
#   UNKNOWN -> we could NOT determine the state (DB locked/busy, property not
#              written yet, transient error). This is NOT "closed": treating a
#              transient lock as "closed" would make a consumer finalise its
#              output prematurely and miss items that are still being produced.
STREAM_STATE_OPEN = 'open'
STREAM_STATE_CLOSED = 'closed'
STREAM_STATE_UNKNOWN = 'unknown'


def safeStreamOpenState(setObj,
                        max_attempts: int = 5,
                        initial_delay: float = 0.1,
                        backoff_factor: float = 1.7,
                        max_delay: float = 2.0,
                        jitter: float = 0.05):
    """Probe a Set's stream state using an independent, read-only connection.

    Opens a short-lived, read-only connection to the Set's backing SQLite file
    and queries ONLY the ``_streamState`` property. This avoids:
      - Reusing the Set's internal mapper connection (no mapper contention)
      - Holding protocol-level locks during the check
      - The heavyweight ``loadAllProperties()`` call that reads ALL properties

    Safe to call from any thread while the producer may be writing concurrently
    (it is a read-only connection and tolerates DELETE journal mode).

    Returns one of ``STREAM_STATE_OPEN`` / ``STREAM_STATE_CLOSED`` /
    ``STREAM_STATE_UNKNOWN``. Lock/busy errors are retried with bounded
    exponential backoff + jitter; if they cannot be resolved the result is
    UNKNOWN (transient) rather than CLOSED, so the caller never finalises a
    stream just because the producer happened to hold a write lock.
    """
    dbPath = getattr(setObj, 'getFileName', lambda: None)()
    if not dbPath or not os.path.exists(dbPath):
        # The backing file does not exist yet: we simply do not know.
        return STREAM_STATE_UNKNOWN

    delay = float(initial_delay)
    attempts = 0
    while True:
        try:
            conn = sqlite3.connect(f"file:{dbPath}?mode=ro", uri=True, timeout=max_delay)
            try:
                row = conn.execute(
                    "SELECT value FROM Properties WHERE key=?",
                    (_STREAM_STATE_KEY,)
                ).fetchone()
            finally:
                conn.close()
            if row is None:
                # Property not written yet (producer created the DB but has not
                # committed its stream state). Unknown, NOT closed.
                return STREAM_STATE_UNKNOWN
            return STREAM_STATE_OPEN if int(row[0]) == _STREAM_OPEN else STREAM_STATE_CLOSED
        except sqlite3.OperationalError as exc:
            if is_sqlite_lock_error(exc):
                attempts += 1
                if attempts >= max_attempts:
                    logger.debug("safeStreamOpenState: DB busy after %d attempts "
                                 "for %s; reporting UNKNOWN" % (attempts, dbPath))
                    return STREAM_STATE_UNKNOWN
                time.sleep(delay + random.uniform(0.0, jitter))
                delay = min(delay * backoff_factor, max_delay)
                continue
            # Non-lock operational error (e.g. malformed/missing table): unknown.
            return STREAM_STATE_UNKNOWN
        except Exception:
            return STREAM_STATE_UNKNOWN


def safeIsStreamOpen(setObj) -> bool:
    """Backwards-compatible boolean probe of a Set's stream state.

    Returns False ONLY when the producer definitively reported the stream as
    closed. A transient lock/busy condition or a not-yet-written state returns
    True (treated as still open) so consumers keep polling instead of
    finalising prematurely.
    """
    return safeStreamOpenState(setObj) != STREAM_STATE_CLOSED


def refreshStreamState(setObj) -> None:
    """Update the in-memory stream state of a Set from the database.

    Uses :func:`safeStreamOpenState` to read the current state from an
    independent read-only connection and patches the in-memory
    ``_streamState`` attribute so subsequent ``setObj.isStreamOpen()`` calls
    return the fresh value without needing ``loadAllProperties()``.

    Conservative finalisation rule: the in-memory state is downgraded to
    CLOSED only on a *definitive* on-disk read. On an UNKNOWN (transient) probe
    we keep the stream OPEN whenever the backing DB exists, so a momentary lock
    can never make a downstream consumer stop early and drop items. This method
    never raises.
    """
    from pyworkflow.object import Set
    state = safeStreamOpenState(setObj)
    if state == STREAM_STATE_CLOSED:
        setObj.setStreamState(Set.STREAM_CLOSED)
    elif state == STREAM_STATE_OPEN:
        setObj.setStreamState(Set.STREAM_OPEN)
    else:
        # UNKNOWN/transient: never finalise on uncertainty. If the producer's
        # DB exists, assume it is still streaming and keep polling.
        dbPath = getattr(setObj, 'getFileName', lambda: None)()
        if dbPath and os.path.exists(dbPath):
            setObj.setStreamState(Set.STREAM_OPEN)
        # else: leave the current in-memory state untouched.


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
