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


def _parse_timestamp(timestamp_str: str) -> datetime:
    """Parse Twitter timestamp to datetime."""
    try:
        # Twitter uses ISO 8601 format
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except:
        return datetime.now()


def _parse_verified_type(user_data: Dict[str, Any]) -> VerifiedType:
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


def _parse_user(user_data: Dict[str, Any]) -> User:
    """
    Parse user data from GraphQL response.

    Based on nitter's parseUser implementation.

    Args:
        user_data: User data from Twitter GraphQL API (user_result.result or user_results.result)

    Returns:
        User model
    """
    legacy = user_data.get("legacy", {})
    rest_id = user_data.get("rest_id", "")

    # Parse join date
    created_at = legacy.get("created_at", "")
    join_date = _parse_timestamp(created_at) if created_at else datetime.now()

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
        verified_type=_parse_verified_type(user_data),
        protected=legacy.get("protected", False),
        suspended=user_data.get("__typename") == "UserUnavailable",
        join_date=join_date
    )


def _parse_tweet_stats(legacy: Dict[str, Any]) -> TweetStats:
    """Parse tweet engagement statistics."""
    return TweetStats(
        replies=legacy.get("reply_count", 0),
        retweets=legacy.get("retweet_count", 0),
        likes=legacy.get("favorite_count", 0),
        quotes=legacy.get("quote_count", 0)
    )


def _parse_tweet(tweet_data: Dict[str, Any]) -> Optional[Tweet]:
    """
    Parse tweet data from GraphQL response.

    Based on nitter's parseGraphTweet implementation.

    Args:
        tweet_data: Tweet data from Twitter GraphQL API

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

    # Parse user from core field (nitter: parseGraphUser(js{"core"}))
    # Try user_result first, then fall back to user_results
    core = tweet_data.get("core", {})
    user_data = core.get("user_result", {}).get("result", {})
    if not user_data:
        user_data = core.get("user_results", {}).get("result", {})

    if user_data:
        user = _parse_user(user_data)
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
    tweet_time = _parse_timestamp(created_at) if created_at else datetime.now()

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
        stats=_parse_tweet_stats(legacy),
        photos=photos,
        videos=videos,
        gif=gif
    )


def _parse_timeline_tweets(timeline_data: Dict[str, Any]) -> List[Tweet]:
    """
    Parse timeline tweets from GraphQL response.

    Based on nitter's parseGraphTimeline implementation.

    Args:
        timeline_data: Timeline data from Twitter GraphQL API

    Returns:
        List of tweets
    """
    tweets = []

    # Navigate to timeline instructions
    # Actual structure: data.user_result.result.timeline_response.timeline
    user_result = timeline_data.get("data", {}).get("user_result", {}).get("result", {})
    timeline_response = user_result.get("timeline_response", {})
    timeline = timeline_response.get("timeline", {})
    instructions = timeline.get("instructions", [])

    for instruction in instructions:
        # Handle different instruction types
        typename = instruction.get("__typename", "")

        # Handle pinned tweets (nitter: entry → content → content → tweetResult → result)
        if typename == "TimelinePinEntry":
            entry = instruction.get("entry", {})
            content = entry.get("content", {})
            tweet_content = content.get("content", {})
            tweet_result = tweet_content.get("tweetResult", {})
            result = tweet_result.get("result", {})
            tweet = _parse_tweet(result)  # Don't pass user - it's in tweet's core field
            if tweet:
                tweet.pinned = True
                tweets.append(tweet)

        # Handle regular entries - use __typename not type
        elif typename == "TimelineAddEntries":
            entries = instruction.get("entries", [])

            for entry in entries:
                content = entry.get("content", {})
                # Use __typename instead of entryType
                content_typename = content.get("__typename", "")

                if content_typename == "TimelineTimelineItem":
                    # Single tweet (nitter: content → content → tweetResult → result)
                    tweet_content = content.get("content", {})
                    tweet_result = tweet_content.get("tweetResult", {})
                    result = tweet_result.get("result", {})

                    tweet = _parse_tweet(result)  # User is extracted from tweet's core field
                    if tweet:
                        tweets.append(tweet)

                elif content_typename == "TimelineTimelineModule":
                    # Thread or conversation (nitter handles these as conversationThread)
                    items = content.get("items", [])
                    for item in items:
                        item_content = item.get("item", {}).get("itemContent", {})
                        if item_content.get("__typename") == "TimelineTweet":
                            tweet_result = item_content.get("tweetResult", {})
                            result = tweet_result.get("result", {})
                            tweet = _parse_tweet(result)
                            if tweet:
                                tweets.append(tweet)

                # Skip cursor entries - they're handled separately for pagination
                elif content_typename == "TimelineTimelineCursor":
                    pass

    return tweets


def parse_user_from_graphql(graphql_response: Dict[str, Any]) -> Optional[User]:
    """
    Parse user from UserByScreenName GraphQL response.

    Args:
        graphql_response: Full GraphQL response

    Returns:
        User model or None
    """
    # The actual response structure is data.user_result.result (not data.user.result)
    user_data = graphql_response.get("data", {}).get("user_result", {}).get("result", {})
    if not user_data:
        return None

    return _parse_user(user_data)


def _parse_timeline_from_graphql(graphql_response: Dict[str, Any]) -> Timeline:
    """
    Parse complete timeline from GraphQL response.

    Args:
        graphql_response: Full GraphQL response

    Returns:
        Timeline model
    """
    tweets = _parse_timeline_tweets(graphql_response)

    # Group tweets into nested lists (nitter groups related tweets together for threads)
    # Currently wrapping each tweet individually; could be enhanced to group thread tweets
    content = [[tweet] for tweet in tweets]

    # Extract pagination cursors
    user_result = graphql_response.get("data", {}).get("user_result", {}).get("result", {})
    timeline_response = user_result.get("timeline_response", {})
    timeline = timeline_response.get("timeline", {})
    instructions = timeline.get("instructions", [])

    top_cursor = ""
    bottom_cursor = ""

    for instruction in instructions:
        # Use __typename instead of type
        if instruction.get("__typename") == "TimelineAddEntries":
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
    # Parse user from tweets response
    user_result = graphql_response.get("data", {}).get("user_result", {}).get("result", {})
    user = _parse_user(user_result) if user_result else None

    # Parse timeline (user will be extracted from each tweet's core field)
    # Pinned tweets are handled in the timeline with pinned=True flag
    timeline = _parse_timeline_from_graphql(graphql_response)

    # Extract pinned tweet from timeline if present
    pinned = None
    for tweet_group in timeline.content:
        for tweet in tweet_group:
            if tweet.pinned:
                pinned = tweet
                break
        if pinned:
            break

    # Ensure we have a user object
    if not user:
        user = User(
            id="0",
            username="unknown",
            fullname="Unknown",
            join_date=datetime.now()
        )

    return Profile(
        user=user,
        pinned=pinned,
        tweets=timeline
    )
