"""
Database models for PostgreSQL cache.
"""

from sqlalchemy import Column, String, Integer, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class _CacheEntry(Base):
    """
    Cache entry model for storing key-value pairs with timestamps.

    Stores cached API responses with automatic expiration based on TTL.
    """
    __tablename__ = "cache"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    timestamp = Column(Integer, nullable=False, index=True)

    __table_args__ = (
        Index("idx_cache_timestamp", "timestamp"),
    )
