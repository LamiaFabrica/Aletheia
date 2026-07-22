"""
Robust retry utility for Medusa crawler and orchestrator modules.
Provides retry_with_backoff with exponential backoff, jitter, and configurable exception handling.
"""
import time
import random
import logging
from typing import Callable, Tuple, Type, Any

def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    jitter: float = 0.5,
    retry_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    logger: logging.Logger = None,
    *args,
    **kwargs
) -> Any:
    """
    Retry a function with exponential backoff and optional jitter.
    Args:
        func: The function to call.
        max_retries: Maximum number of attempts.
        base_delay: Initial delay in seconds.
        jitter: Maximum random jitter to add to delay.
        retry_exceptions: Tuple of exception types to retry on.
        logger: Optional logger for retry events.
        *args, **kwargs: Passed to func.
    Returns:
        The return value of func if successful.
    Raises:
        The last exception if all retries fail.
    """
    attempt = 0
    while attempt < max_retries:
        try:
            return func(*args, **kwargs)
        except retry_exceptions as e:
            attempt += 1
            if logger:
                logger.warning(f"Retry {attempt}/{max_retries} after error: {e}")
            if attempt >= max_retries:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            if jitter > 0:
                delay += random.uniform(0, jitter)
            time.sleep(delay) 