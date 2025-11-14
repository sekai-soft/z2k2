from fastapi import FastAPI, HTTPException, Query
from typing import Optional
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from z2k2 import twitter_client
from z2k2.twitter_client import TwitterClient, TwitterAPIError, RateLimitError
from z2k2.twitter_parser import parse_user_from_graphql, parse_profile_from_graphql
from z2k2.models import Profile, User
from z2k2.session_manager import SessionManager
from z2k2.postgres_cache import PostgresCache

if os.path.exists('.dev.env'):
    load_dotenv('.dev.env')

# Get mandatory cache configuration from environment variables
cache_ttl = int(os.environ["CACHE_TTL_SECONDS"])
cache_ttl_jitter = int(os.environ["CACHE_TTL_JITTER_SECONDS"])

# Initialize session manager
# Sessions will be rotated for each request
session_manager = SessionManager("sessions.jsonl")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Lifespan event handler - runs on startup and shutdown."""
    # Startup: Initialize database and cache
    from z2k2.database import _init_db
    _init_db()

    # Initialize cache for API responses
    twitter_client._cache = PostgresCache(cache_ttl, cache_ttl_jitter)

    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="z2k2",
    description="API server for selected social networks",
    version="0.1.0",
    lifespan=lifespan
)


async def get_user_data(username: str) -> User:
    """
    Helper function to get user data by username.

    Args:
        username: Twitter username (without @)

    Returns:
        User object

    Raises:
        HTTPException: 404 if user not found
    """
    session = session_manager.get_session()
    client = TwitterClient(
        oauth_token=session.oauth_token,
        oauth_token_secret=session.oauth_token_secret
    )

    try:
        user_response = await client.get_user_by_screen_name(username)
        return parse_user_from_graphql(user_response)
    finally:
        await client.close()


@app.get("/")
def read_root():
    return {
        "message": "z2k2 API",
        "docs": "/docs",
        "endpoints": {
            "profile": "/twitter/profile/{username}",
            "user_status": "/twitter/profile/{username}/_status",
        }
    }


async def get_user_tweets_data(user_id: str, cursor: Optional[str] = None):
    """
    Helper function to get user tweets.

    Args:
        user_id: Twitter user ID
        cursor: Optional pagination cursor

    Returns:
        Parsed tweets response
    """
    session = session_manager.get_session()
    client = TwitterClient(
        oauth_token=session.oauth_token,
        oauth_token_secret=session.oauth_token_secret
    )

    try:
        return await client.get_user_tweets(user_id, cursor)
    finally:
        await client.close()


@app.get("/twitter/profile/{username}")
async def get_profile_timeline(
    username: str,
    cursor: Optional[str] = Query(None, description="Pagination cursor")
) -> Profile:
    """
    Get user profile and timeline.

    Args:
        username: Twitter username (without @)
        cursor: Optional pagination cursor for loading more tweets

    Returns:
        Profile with user data and timeline of tweets

    Raises:
        HTTPException: On API errors or user not found
    """
    try:
        user = await get_user_data(username)
        if not user:
            raise HTTPException(404, f'User @{username} is absent')

        tweets_response = await get_user_tweets_data(user.id, cursor)
        profile = parse_profile_from_graphql(tweets_response)
        profile.user = user

        return profile
    except HTTPException:
        raise
    except RateLimitError:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    except TwitterAPIError as e:
        raise HTTPException(status_code=502, detail=f"Twitter API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/twitter/profile/{handle}/_status")
async def get_user_status(handle: str) -> dict:
    """
    Get user account status including protected and suspended flags.

    Args:
        handle: Twitter username (without @)

    Returns:
        Dictionary with protected and suspended boolean statuses

    Raises:
        HTTPException: On API errors or user not found
    """
    user = await get_user_data(handle)
    if not user:
        return {
            "absent": True
        }

    return {
        "protected": user.protected,
        "suspended": user.suspended
    }
