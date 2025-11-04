from fastapi import FastAPI, HTTPException, Query
from typing import Optional
from contextlib import asynccontextmanager
from z2k2.twitter_client import TwitterClient, TwitterAPIError, RateLimitError
from z2k2.twitter_parser import parse_user_from_graphql, parse_profile_from_graphql
from z2k2.models import Profile
from z2k2.session_manager import SessionManager

# Initialize session manager
# Sessions will be rotated for each request
session_manager = SessionManager()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print(f"Session manager initialized with {session_manager.session_count()} session(s)")
    yield
    # Shutdown - nothing to cleanup since we create clients per-request


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
    # Get a session from the session manager (round-robin)
    session = session_manager.get_session()

    # Create a new Twitter client with the session credentials
    client = TwitterClient(
        oauth_token=session.oauth_token,
        oauth_token_secret=session.oauth_token_secret
    )

    try:
        # First, get user data by username
        user_response = await client.get_user_by_screen_name(username)
        user = parse_user_from_graphql(user_response)

        if not user:
            raise HTTPException(status_code=404, detail=f"User @{username} not found")

        if user.suspended:
            raise HTTPException(status_code=403, detail=f"User @{username} is suspended")

        # Then get user's tweets
        tweets_response = await client.get_user_tweets(user.id, cursor)

        # Parse the complete profile with timeline
        profile = parse_profile_from_graphql(tweets_response)

        # Update user data from the first call (tweets response may have stale user info)
        profile.user = user

        return profile

    except RateLimitError:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    except TwitterAPIError as e:
        raise HTTPException(status_code=502, detail=f"Twitter API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        # Always close the client after the request
        await client.close()
