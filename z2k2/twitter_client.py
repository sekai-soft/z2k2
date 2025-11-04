"""
Twitter GraphQL API client.
Ported from nitter to Python.
"""

import httpx
import json
from typing import Optional, Dict, Any
from urllib.parse import urlencode
from authlib.integrations.httpx_client import OAuth1Auth

# Twitter API constants
_CONSUMER_KEY = "3nVuSoBZnx6U4vzUxf5w"
_CONSUMER_SECRET = "Bcs59EFbbsdF6Sl9Ng71smgStWEGwXXKSjYvPVt7qys"

# GraphQL endpoints
_GRAPHQL_BASE = "https://api.x.com/graphql"

_GRAPH_USER = f"{_GRAPHQL_BASE}/u7wQyGi6oExe8_TRWGMq4Q/UserResultByScreenNameQuery"
_GRAPH_USER_TWEETS = f"{_GRAPHQL_BASE}/JLApJKFY0MxGTzCoK6ps8Q/UserWithProfileTweetsQueryV2"

# GraphQL features (enable/disable various Twitter API features)
_GQL_FEATURES = {
    "android_graphql_skip_api_media_color_palette": False,
    "blue_business_profile_image_shape_enabled": False,
    "creator_subscriptions_subscription_count_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "freedom_of_speech_not_reach_fetch_enabled": False,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": False,
    "hidden_profile_likes_enabled": False,
    "highlights_tweets_tab_ui_enabled": False,
    "interactive_text_enabled": False,
    "longform_notetweets_consumption_enabled": True,
    "longform_notetweets_inline_media_enabled": False,
    "longform_notetweets_richtext_consumption_enabled": True,
    "longform_notetweets_rich_text_read_enabled": False,
    "responsive_web_edit_tweet_api_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": False,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_text_conversations_enabled": False,
    "responsive_web_twitter_article_tweet_consumption_enabled": False,
    "responsive_web_twitter_blue_verified_badge_is_enabled": True,
    "rweb_lists_timeline_redesign_enabled": True,
    "spaces_2022_h2_clipping": True,
    "spaces_2022_h2_spaces_communities": True,
    "standardized_nudges_misinfo": False,
    "subscriptions_verification_info_enabled": True,
    "subscriptions_verification_info_reason_enabled": True,
    "subscriptions_verification_info_verified_since_enabled": True,
    "super_follow_badge_privacy_enabled": False,
    "super_follow_exclusive_tweet_notifications_enabled": False,
    "super_follow_tweet_api_enabled": False,
    "super_follow_user_api_enabled": False,
    "tweet_awards_web_tipping_enabled": False,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
    "tweetypie_unmention_optimization_enabled": False,
    "unified_cards_ad_metadata_container_dynamic_card_content_query_enabled": False,
    "verified_phone_label_enabled": False,
    "vibe_api_enabled": False,
    "view_counts_everywhere_api_enabled": False,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": False,
    "responsive_web_jetfuel_frame": False,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_image_annotation_enabled": False,
    "rweb_tipjar_consumption_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "c9s_tweet_anatomy_moderator_badge_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": False,
    "rweb_video_timestamps_enabled": False,
    "responsive_web_grok_share_attachment_enabled": False,
    "articles_preview_enabled": False,
    "immersive_video_status_linkable_timestamps": False,
    "articles_api_enabled": False,
    "responsive_web_grok_analysis_button_from_backend": False
}


class TwitterAPIError(Exception):
    """Twitter API error."""
    def __init__(self, message: str, status_code: Optional[int]):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(TwitterAPIError):
    """Rate limit exceeded."""
    pass


class TwitterClient:
    """
    Twitter GraphQL API client.

    Implements OAuth 1.0a authentication based on nitter's implementation.
    Requires valid Twitter OAuth tokens from sessions.jsonl.
    """

    def __init__(self, oauth_token: str, oauth_token_secret: str):
        """
        Initialize Twitter client.

        Args:
            oauth_token: OAuth token from Twitter session
            oauth_token_secret: OAuth token secret from Twitter session
        """
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret

        # Create OAuth 1.0 auth handler with HMAC-SHA1 signature (nitter's method)
        self.auth = OAuth1Auth(
            client_id=_CONSUMER_KEY,
            client_secret=_CONSUMER_SECRET,
            token=oauth_token,
            token_secret=oauth_token_secret,
            signature_method="HMAC-SHA1",
        )

        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        """
        Generate request headers for Twitter API.

        Based on nitter's implementation from apiutils.nim.
        Note: OAuth 1.0 authorization header is added automatically by OAuth1Auth.
        """
        return {
            "authority": "api.x.com",
            "content-type": "application/json",
            "x-twitter-active-user": "yes",
            "accept": "*/*",
            "accept-encoding": "gzip",
            "accept-language": "en-US,en;q=0.9",
            "connection": "keep-alive",
            "DNT": "1",
        }

    async def _fetch(self, url: str, params: Dict[str, str]) -> Dict[str, Any]:
        """
        Fetch data from Twitter GraphQL API.

        Args:
            url: GraphQL endpoint URL
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            TwitterAPIError: On API errors
            RateLimitError: On rate limit
        """
        query_string = urlencode(params)
        full_url = f"{url}?{query_string}"

        headers = self._get_headers()

        try:
            # Use OAuth 1.0 auth for signing the request
            response = await self.client.get(full_url, headers=headers, auth=self.auth)

            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded", 429)

            if response.status_code == 503:
                raise TwitterAPIError("Service unavailable", None)

            response.raise_for_status()

            data = response.json()

            # Check for errors in response
            if "errors" in data:
                error_msg = ", ".join([e.get("message", str(e)) for e in data["errors"]])
                raise TwitterAPIError(f"Twitter API error: {error_msg}", None)

            return data

        except httpx.HTTPStatusError as e:
            raise TwitterAPIError(
                f"{e.response.status_code}: {e.response.text if e.response.text else 'HTTP error'}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            raise TwitterAPIError(f"Request error: {str(e)}", None)

    async def get_user_by_screen_name(self, username: str) -> Dict[str, Any]:
        """
        Get user data by username (screen name).

        Args:
            username: Twitter username

        Returns:
            User data from GraphQL API
        """
        variables = json.dumps({"screen_name": username})
        params = {
            "variables": variables,
            "features": json.dumps(_GQL_FEATURES)
        }
        return await self._fetch(_GRAPH_USER, params)

    async def get_user_tweets(
        self,
        user_id: str,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get user's tweets (posts only, no replies).

        Args:
            user_id: Twitter user ID
            cursor: Pagination cursor

        Returns:
            Timeline data from GraphQL API
        """
        variables = {
            "rest_id": user_id,  # API expects rest_id, not userId
            "count": 20,
            "includePromotedContent": False,
            "withDownvotePerspective": False,
            "withReactionsMetadata": False,
            "withReactionsPerspective": False,
            "withVoice": False,
            "withV2Timeline": True
        }

        if cursor:
            variables["cursor"] = cursor

        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(_GQL_FEATURES)
        }
        return await self._fetch(_GRAPH_USER_TWEETS, params)
