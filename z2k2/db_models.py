"""
Database models for z2k2.
"""

from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Cache(Base):
    """
    Cache model for storing API responses with TTL.

    Stores key-value pairs with timestamps for automatic expiration.
    """
    __tablename__ = "cache"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    timestamp = Column(Integer, nullable=False)
