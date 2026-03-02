import logging
import random
import time
from functools import wraps

logger = logging.getLogger(__name__)


def db_retry(max_retries=3, base_wait=0.5):
    """Retry a function on SQLite 'database is locked' errors with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                        wait_time = (attempt + 1) * base_wait + random.uniform(0, 0.2)
                        logger.warning(
                            f"Database locked in {func.__name__} — "
                            f"retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                    else:
                        raise
        return wrapper
    return decorator
