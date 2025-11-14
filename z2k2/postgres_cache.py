"""
Generic PostgreSQL-based cache with TTL support.
"""

import json
import time
import random
from typing import Optional, Dict, Any, Callable
from functools import wraps
from z2k2.database import _get_db_context
from z2k2.db_models import _CacheEntry


class PostgresCache:
    """
    Generic PostgreSQL-based cache with automatic expiration.

    Stores key-value pairs with timestamps and automatically
    expires entries older than the specified TTL.
    """

    def __init__(self, ttl: int, ttl_jitter: int):
        """
        Initialize cache.

        Args:
            ttl: Time-to-live in seconds
            ttl_jitter: Maximum jitter in seconds to randomize expiration.
                        For example, 360 means ±360 seconds (±6 minutes).
        """
        self.ttl = ttl
        self.ttl_jitter = ttl_jitter

    def _get_effective_ttl(self) -> int:
        """
        Get TTL with randomized jitter to prevent cache stampede.

        Returns:
            Effective TTL with random jitter applied
        """
        if self.ttl_jitter == 0:
            return self.ttl

        # Apply jitter: TTL ± jitter_seconds
        # For example, with ttl=3600 and jitter=360:
        # Result will be between 3240 and 3960 seconds
        return int(self.ttl + random.uniform(-self.ttl_jitter, self.ttl_jitter))

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with _get_db_context() as db:
            entry = db.query(_CacheEntry).filter(_CacheEntry.key == key).first()

            if entry is None:
                return None

            current_time = int(time.time())

            # Check if cache entry is expired using randomized TTL
            effective_ttl = self._get_effective_ttl()
            if current_time - entry.timestamp > effective_ttl:
                # Delete expired entry
                db.delete(entry)
                db.commit()
                return None

            return json.loads(entry.value)

    def set(self, key: str, value: Dict[str, Any]):
        """
        Set cache value with current timestamp.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
        """
        with _get_db_context() as db:
            timestamp = int(time.time())
            value_json = json.dumps(value)

            # Check if entry exists
            entry = db.query(_CacheEntry).filter(_CacheEntry.key == key).first()

            if entry:
                # Update existing entry
                entry.value = value_json
                entry.timestamp = timestamp
            else:
                # Create new entry
                entry = _CacheEntry(
                    key=key,
                    value=value_json,
                    timestamp=timestamp
                )
                db.add(entry)

            db.commit()

    def delete(self, key: str):
        """
        Delete a specific cache entry.

        Args:
            key: Cache key to delete
        """
        with _get_db_context() as db:
            db.query(_CacheEntry).filter(_CacheEntry.key == key).delete()
            db.commit()

    def clear_expired(self):
        """
        Clear all expired cache entries.

        Uses maximum TTL (with positive jitter) to ensure we only delete
        entries that are guaranteed to be expired.
        """
        with _get_db_context() as db:
            current_time = int(time.time())
            # Use maximum possible TTL to avoid deleting entries that might still be valid
            max_ttl = self.ttl + self.ttl_jitter
            cutoff_time = current_time - max_ttl

            db.query(_CacheEntry).filter(_CacheEntry.timestamp < cutoff_time).delete()
            db.commit()

    def clear_all(self):
        """Clear all cache entries."""
        with _get_db_context() as db:
            db.query(_CacheEntry).delete()
            db.commit()


def cached(cache_getter: Callable[[], PostgresCache], key_fn: Callable):
    """
    Decorator to cache async method results.

    Args:
        cache_getter: Callable that returns the PostgresCache instance (evaluated at runtime)
        key_fn: Function that takes method args/kwargs and returns cache key

    Example:
        cache = PostgresCache(3600, 360)

        @cached(lambda: cache, lambda username: f"user_{username}")
        async def get_user(self, username: str):
            return await fetch_user(username)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get cache instance at runtime (not decoration time)
            cache_instance = cache_getter()

            # Generate cache key
            # Skip 'self' argument if it's a method
            func_args = args[1:] if args and hasattr(args[0], func.__name__) else args
            key = key_fn(*func_args, **kwargs)

            # Try to get from cache
            cached_value = cache_instance.get(key)
            if cached_value is not None:
                return cached_value

            # Call original function
            result = await func(*args, **kwargs)

            # Store in cache
            cache_instance.set(key, result)

            return result
        return wrapper
    return decorator
