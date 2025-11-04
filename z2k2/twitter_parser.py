"""
Twitter GraphQL response parser.
Converts Twitter API responses to our Pydantic models.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .models import (
    User, Tweet, Timeline, Profile, TweetStats,
    VerifiedType, Video, VideoVariant,
    Gif
)


def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse Twitter timestamp to datetime."""
    try:
        # Twitter uses ISO 8601 format
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except:
        return datetime.now()


def parse_verified_type(user_data: Dict[str, Any]) -> VerifiedType:
    """Parse user verification type."""
    legacy = user_data.get("legacy", {})
    verified = legacy.get("verified", False)

    if verified:
        # Check if it's a business or government account
        verified_type = user_data.get("verified_type", "")
        if verified_type == "Business":
            return VerifiedType.BUSINESS
        elif verified_type == "Government":
            return VerifiedType.GOVERNMENT
        else:
            return VerifiedType.BLUE
    return VerifiedType.NONE


def parse_user(user_data: Dict[str, Any]) -> User:
    """
    Parse user data from GraphQL response.

    Args:
        user_data: User data from Twitter GraphQL API

    Returns:
        User model
    """
    legacy = user_data.get("legacy", {})
    rest_id = user_data.get("rest_id", "")

    # Parse join date
    created_at = legacy.get("created_at", "")
    join_date = parse_timestamp(created_at) if created_at else datetime.now()

    return User(
        id=rest_id,
        username=legacy.get("screen_name", ""),
        fullname=legacy.get("name", ""),
        location=legacy.get("location", ""),
        website=legacy.get("url", ""),
        bio=legacy.get("description", ""),
        user_pic=legacy.get("profile_image_url_https", "").replace("_normal", "_400x400"),
        banner=legacy.get("profile_banner_url", ""),
        pinned_tweet=int(legacy.get("pinned_tweet_ids_str", ["0"])[0]) if legacy.get("pinned_tweet_ids_str") else 0,
        following=legacy.get("friends_count", 0),
        followers=legacy.get("followers_count", 0),
        tweets=legacy.get("statuses_count", 0),
        likes=legacy.get("favourites_count", 0),
        media=legacy.get("media_count", 0),
        verified_type=parse_verified_type(user_data),
        protected=legacy.get("protected", False),
        suspended=user_data.get("__typename") == "UserUnavailable",
        join_date=join_date
    )


def parse_tweet_stats(legacy: Dict[str, Any]) -> TweetStats:
    """Parse tweet engagement statistics."""
    return TweetStats(
        replies=legacy.get("reply_count", 0),
        retweets=legacy.get("retweet_count", 0),
        likes=legacy.get("favorite_count", 0),
        quotes=legacy.get("quote_count", 0)
    )


def parse_tweet(tweet_data: Dict[str, Any], user: Optional[User] = None) -> Optional[Tweet]:
    """
    Parse tweet data from GraphQL response.

    Args:
        tweet_data: Tweet data from Twitter GraphQL API
        user: Optional user object (if already parsed)

    Returns:
        Tweet model or None if unavailable
    """
    # Handle different tweet result types
    if "tweet" in tweet_data:
        tweet_data = tweet_data["tweet"]

    if not tweet_data or tweet_data.get("__typename") == "TweetUnavailable":
        return None

    legacy = tweet_data.get("legacy", {})
    rest_id = tweet_data.get("rest_id", "0")

    # Parse user if not provided
    if not user:
        user_data = tweet_data.get("core", {}).get("user_results", {}).get("result", {})
        if user_data:
            user = parse_user(user_data)
        else:
            # Fallback to minimal user
            user = User(
                id="0",
                username="unknown",
                fullname="Unknown",
                join_date=datetime.now()
            )

    # Parse timestamp
    created_at = legacy.get("created_at", "")
    tweet_time = parse_timestamp(created_at) if created_at else datetime.now()

    # Parse media
    photos = []
    videos = []
    gif = None
    media_entities = legacy.get("extended_entities", {}).get("media", [])

    for media in media_entities:
        media_type = media.get("type", "")
        if media_type == "photo":
            photos.append(media.get("media_url_https", ""))
        elif media_type == "video":
            video_info = media.get("video_info", {})
            variants = [
                VideoVariant(
                    content_type=v.get("content_type", "video/mp4"),
                    url=v.get("url", ""),
                    bitrate=v.get("bitrate", 0)
                )
                for v in video_info.get("variants", [])
            ]
            videos.append(Video(
                duration_ms=video_info.get("duration_millis", 0),
                thumb=media.get("media_url_https", ""),
                variants=variants
            ))
        elif media_type == "animated_gif":
            video_info = media.get("video_info", {})
            variants = video_info.get("variants", [])
            if variants:
                gif = Gif(
                    url=variants[0].get("url", ""),
                    thumb=media.get("media_url_https", "")
                )

    # Get text (full_text or extended tweet text)
    text = legacy.get("full_text", "")
    if not text:
        text = legacy.get("text", "")

    return Tweet(
        id=int(rest_id) if rest_id.isdigit() else 0,
        thread_id=int(legacy.get("conversation_id_str", "0")) if legacy.get("conversation_id_str", "0").isdigit() else 0,
        reply_id=int(legacy.get("in_reply_to_status_id_str", "0")) if legacy.get("in_reply_to_status_id_str") else 0,
        user=user,
        text=text,
        time=tweet_time,
        reply=[legacy.get("in_reply_to_screen_name")] if legacy.get("in_reply_to_screen_name") else [],
        pinned=False,  # Will be set by the caller if needed
        has_thread=legacy.get("self_thread", {}).get("id_str") is not None,
        available=True,
        source=legacy.get("source", ""),
        stats=parse_tweet_stats(legacy),
        photos=photos,
        videos=videos,
        gif=gif
    )


def parse_timeline_tweets(timeline_data: Dict[str, Any]) -> List[Tweet]:
    """
    Parse timeline tweets from GraphQL response.

    Args:
        timeline_data: Timeline data from Twitter GraphQL API

    Returns:
        List of tweets
    """
    tweets = []

    # Navigate to timeline instructions
    timeline = timeline_data.get("data", {}).get("user", {}).get("result", {}).get("timeline_v2", {})
    instructions = timeline.get("timeline", {}).get("instructions", [])

    for instruction in instructions:
        if instruction.get("type") == "TimelineAddEntries":
            entries = instruction.get("entries", [])

            for entry in entries:
                content = entry.get("content", {})
                entry_type = content.get("entryType", "")

                if entry_type == "TimelineTimelineItem":
                    # Single tweet
                    item_content = content.get("itemContent", {})
                    tweet_results = item_content.get("tweet_results", {})
                    result = tweet_results.get("result", {})

                    tweet = parse_tweet(result)
                    if tweet:
                        tweets.append(tweet)

                elif entry_type == "TimelineTimelineModule":
                    # Thread or conversation
                    items = content.get("items", [])
                    for item in items:
                        item_content = item.get("item", {}).get("itemContent", {})
                        tweet_results = item_content.get("tweet_results", {})
                        result = tweet_results.get("result", {})

                        tweet = parse_tweet(result)
                        if tweet:
                            tweets.append(tweet)

    return tweets


def parse_user_from_graphql(graphql_response: Dict[str, Any]) -> Optional[User]:
    """
    Parse user from UserByScreenName GraphQL response.

    Args:
        graphql_response: Full GraphQL response

    Returns:
        User model or None
    """
    user_data = graphql_response.get("data", {}).get("user", {}).get("result", {})
    if not user_data:
        return None

    return parse_user(user_data)


def parse_timeline_from_graphql(
    graphql_response: Dict[str, Any],
    user: Optional[User] = None
) -> Timeline:
    """
    Parse complete timeline from GraphQL response.

    Args:
        graphql_response: Full GraphQL response
        user: Optional user object

    Returns:
        Timeline model
    """
    tweets = parse_timeline_tweets(graphql_response)

    # Group tweets (nitter groups tweets in nested lists for threads)
    # For simplicity, we'll just wrap each tweet in its own list
    content = [[tweet] for tweet in tweets]

    # Extract pagination cursors
    timeline = graphql_response.get("data", {}).get("user", {}).get("result", {}).get("timeline_v2", {})
    instructions = timeline.get("timeline", {}).get("instructions", [])

    top_cursor = ""
    bottom_cursor = ""

    for instruction in instructions:
        if instruction.get("type") == "TimelineAddEntries":
            entries = instruction.get("entries", [])
            for entry in entries:
                entry_id = entry.get("entryId", "")
                if "cursor-top" in entry_id:
                    content_item = entry.get("content", {})
                    top_cursor = content_item.get("value", "")
                elif "cursor-bottom" in entry_id:
                    content_item = entry.get("content", {})
                    bottom_cursor = content_item.get("value", "")

    return Timeline(
        content=content,
        top=top_cursor,
        bottom=bottom_cursor,
        beginning=len(tweets) == 0
    )


def parse_profile_from_graphql(graphql_response: Dict[str, Any]) -> Profile:
    """
    Parse complete profile with timeline from GraphQL response.

    Args:
        graphql_response: Full GraphQL response

    Returns:
        Profile model
    """
    # Parse user
    user_data = graphql_response.get("data", {}).get("user", {}).get("result", {})
    parsed_user = parse_user(user_data) if user_data else User(
        id="0",
        username="unknown",
        fullname="Unknown",
        join_date=datetime.now()
    )

    # Parse timeline
    timeline = parse_timeline_from_graphql(graphql_response, parsed_user)

    # TODO: Parse pinned tweet if present
    pinned = None

    return Profile(
        user=parsed_user,
        pinned=pinned,
        tweets=timeline
    )
