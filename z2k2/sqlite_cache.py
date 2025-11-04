"""
Generic SQLite-based cache with TTL support.
"""

import sqlite3
import json
import time
from typing import Optional, Dict, Any, Callable
from functools import wraps


class SqliteCache:
    """
    Generic SQLite-based cache with automatic expiration.

    Stores key-value pairs with timestamps and automatically
    expires entries older than the specified TTL.
    """

    def __init__(self, db_path: str, ttl: int):
        """
        Initialize cache.

        Args:
            db_path: Path to SQLite database file
            ttl: Time-to-live in seconds
        """
        self.db_path = db_path
        self.ttl = ttl
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    timestamp INTEGER NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT value, timestamp FROM cache WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            value, timestamp = row
            current_time = int(time.time())

            # Check if cache entry is expired
            if current_time - timestamp > self.ttl:
                # Delete expired entry
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                return None

            return json.loads(value)
        finally:
            conn.close()

    def set(self, key: str, value: Dict[str, Any]):
        """
        Set cache value with current timestamp.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
        """
        conn = sqlite3.connect(self.db_path)
        try:
            timestamp = int(time.time())
            value_json = json.dumps(value)

            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, timestamp) VALUES (?, ?, ?)",
                (key, value_json, timestamp)
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, key: str):
        """
        Delete a specific cache entry.

        Args:
            key: Cache key to delete
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
        finally:
            conn.close()

    def clear_expired(self):
        """Clear all expired cache entries."""
        conn = sqlite3.connect(self.db_path)
        try:
            current_time = int(time.time())
            conn.execute(
                "DELETE FROM cache WHERE ? - timestamp > ?",
                (current_time, self.ttl)
            )
            conn.commit()
        finally:
            conn.close()

    def clear_all(self):
        """Clear all cache entries."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM cache")
            conn.commit()
        finally:
            conn.close()


def cached(cache_getter: Callable[[], SqliteCache], key_fn: Callable):
    """
    Decorator to cache async method results.

    Args:
        cache_getter: Callable that returns the SqliteCache instance (evaluated at runtime)
        key_fn: Function that takes method args/kwargs and returns cache key

    Example:
        cache = SqliteCache(".cache.db", 3600)

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
