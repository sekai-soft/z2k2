from fastapi import FastAPI, HTTPException, Query
from typing import Optional
from contextlib import asynccontextmanager
from z2k2.twitter_client import TwitterClient, TwitterAPIError, RateLimitError
from z2k2.twitter_parser import parse_user_from_graphql, parse_profile_from_graphql
from z2k2.models import Profile

# Twitter client instance
# TODO: Implement proper session management and token rotation
twitter_client = TwitterClient()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    yield
    # Shutdown
    await twitter_client.close()


app = FastAPI(
    title="z2k2",
    description="API and RSS server for selected social networks",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/")
def read_root():
    return {
        "message": "z2k2 API",
        "docs": "/docs",
        "endpoints": {
            "profile": "/@{username}",
        }
    }


@app.get("/@{username}")
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
        # First, get user data by username
        user_response = await twitter_client.get_user_by_screen_name(username)
        user = parse_user_from_graphql(user_response)

        if not user:
            raise HTTPException(status_code=404, detail=f"User @{username} not found")

        if user.suspended:
            raise HTTPException(status_code=403, detail=f"User @{username} is suspended")

        # Then get user's tweets
        tweets_response = await twitter_client.get_user_tweets(user.id, cursor)

        # Parse the complete profile with timeline
        profile = parse_profile_from_graphql(tweets_response)

        # Update user data from the first call
        profile.user = user

        return profile

    except RateLimitError:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    except TwitterAPIError as e:
        raise HTTPException(status_code=502, detail=f"Twitter API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
