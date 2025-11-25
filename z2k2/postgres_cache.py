"""
Generic PostgreSQL-based cache with TTL support.
"""

import json
import time
from typing import Optional, Dict, Any, Callable
from functools import wraps
from z2k2.database import get_db_context
from z2k2.db_models import Cache


class PostgresCache:
    """
    Generic PostgreSQL-based cache with automatic expiration.

    Stores key-value pairs with timestamps and automatically
    expires entries older than the specified TTL.
    """

    def __init__(self, ttl: int):
        """
        Initialize cache.

        Args:
            ttl: Time-to-live in seconds
        """
        self.ttl = ttl

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with get_db_context() as db:
            cache_entry = db.query(Cache).filter(Cache.key == key).first()

            if cache_entry is None:
                return None

            current_time = int(time.time())

            # Check if cache entry is expired
            if current_time - cache_entry.timestamp > self.ttl:
                # Delete expired entry
                db.delete(cache_entry)
                db.commit()
                return None

            return json.loads(cache_entry.value)

    def set(self, key: str, value: Dict[str, Any]):
        """
        Set cache value with current timestamp.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
        """
        with get_db_context() as db:
            timestamp = int(time.time())
            value_json = json.dumps(value)

            # Check if entry exists
            cache_entry = db.query(Cache).filter(Cache.key == key).first()

            if cache_entry:
                # Update existing entry
                cache_entry.value = value_json
                cache_entry.timestamp = timestamp
            else:
                # Create new entry
                cache_entry = Cache(
                    key=key,
                    value=value_json,
                    timestamp=timestamp
                )
                db.add(cache_entry)

            db.commit()

    def delete(self, key: str):
        """
        Delete a specific cache entry.

        Args:
            key: Cache key to delete
        """
        with get_db_context() as db:
            cache_entry = db.query(Cache).filter(Cache.key == key).first()
            if cache_entry:
                db.delete(cache_entry)
                db.commit()

    def clear_expired(self):
        """Clear all expired cache entries."""
        with get_db_context() as db:
            current_time = int(time.time())
            db.query(Cache).filter(
                current_time - Cache.timestamp > self.ttl
            ).delete(synchronize_session=False)
            db.commit()

    def clear_all(self):
        """Clear all cache entries."""
        with get_db_context() as db:
            db.query(Cache).delete(synchronize_session=False)
            db.commit()


def cached(cache_getter: Callable[[], PostgresCache], key_fn: Callable):
    """
    Decorator to cache async method results.

    Args:
        cache_getter: Callable that returns the PostgresCache instance (evaluated at runtime)
        key_fn: Function that takes method args/kwargs and returns cache key

    Example:
        cache = PostgresCache(3600)

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
