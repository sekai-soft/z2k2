"""
Twitter data models for RSS feed generation.
Ported from nitter (Nim) to Python.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class VerifiedType(str, Enum):
    """User verification status."""
    NONE = "None"
    BLUE = "Blue"
    BUSINESS = "Business"
    GOVERNMENT = "Government"


class VideoType(str, Enum):
    """Video content types."""
    M3U8 = "application/x-mpegURL"
    MP4 = "video/mp4"
    VMAP = "video/vmap"


class CardKind(str, Enum):
    """Types of tweet cards."""
    AMPLIFY = "amplify"
    APP = "app"
    APP_PLAYER = "appplayer"
    PLAYER = "player"
    SUMMARY = "summary"
    SUMMARY_LARGE = "summary_large_image"
    PROMO_WEBSITE = "promo_website"
    PROMO_VIDEO = "promo_video_website"
    PROMO_VIDEO_CONVO = "promo_video_convo"
    PROMO_IMAGE_CONVO = "promo_image_convo"
    PROMO_IMAGE_APP = "promo_image_app"
    STORE_LINK = "direct_store_link_app"
    LIVE_EVENT = "live_event"
    BROADCAST = "broadcast"
    PERISCOPE = "periscope_broadcast"
    UNIFIED = "unified_card"
    MOMENT = "moment"
    MESSAGE_ME = "message_me"
    VIDEO_DIRECT_MESSAGE = "video_direct_message"
    IMAGE_DIRECT_MESSAGE = "image_direct_message"
    AUDIOSPACE = "audiospace"
    NEWSLETTER_PUBLICATION = "newsletter_publication"
    JOB_DETAILS = "job_details"
    HIDDEN = "hidden"
    UNKNOWN = "unknown"


class User(BaseModel):
    """Twitter user profile."""
    id: str
    username: str
    fullname: str
    location: str = ""
    website: str = ""
    bio: str = ""
    user_pic: str = Field(default="", alias="userPic")
    banner: str = ""
    pinned_tweet: int = Field(default=0, alias="pinnedTweet")
    following: int = 0
    followers: int = 0
    tweets: int = 0
    likes: int = 0
    media: int = 0
    verified_type: VerifiedType = Field(default=VerifiedType.NONE, alias="verifiedType")
    protected: bool = False
    suspended: bool = False
    join_date: datetime = Field(alias="joinDate")

    class Config:
        populate_by_name = True


class VideoVariant(BaseModel):
    """Video quality variant."""
    content_type: VideoType = Field(alias="contentType")
    url: str
    bitrate: int = 0
    resolution: int = 0

    class Config:
        populate_by_name = True


class Video(BaseModel):
    """Video metadata."""
    duration_ms: int = Field(default=0, alias="durationMs")
    url: str = ""
    thumb: str = ""
    views: str = ""
    available: bool = True
    reason: str = ""
    title: str = ""
    description: str = ""
    playback_type: VideoType = Field(default=VideoType.MP4, alias="playbackType")
    variants: List[VideoVariant] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class Gif(BaseModel):
    """GIF metadata."""
    url: str
    thumb: str


class Card(BaseModel):
    """Tweet card (link preview)."""
    kind: CardKind
    url: str = ""
    title: str = ""
    dest: str = ""
    text: str = ""
    image: str = ""
    video: Optional[Video] = None


class Poll(BaseModel):
    """Tweet poll."""
    options: List[str] = Field(default_factory=list)
    values: List[int] = Field(default_factory=list)
    votes: int = 0
    leader: int = 0
    status: str = ""


class TweetStats(BaseModel):
    """Tweet engagement statistics."""
    replies: int = 0
    retweets: int = 0
    likes: int = 0
    quotes: int = 0


class Tweet(BaseModel):
    """Twitter tweet/post."""
    id: int
    thread_id: int = Field(default=0, alias="threadId")
    reply_id: int = Field(default=0, alias="replyId")
    user: User
    text: str
    time: datetime
    reply: List[str] = Field(default_factory=list)
    pinned: bool = False
    has_thread: bool = Field(default=False, alias="hasThread")
    available: bool = True
    tombstone: str = ""
    location: str = ""
    source: str = ""
    stats: TweetStats
    retweet: Optional["Tweet"] = None
    attribution: Optional[User] = None
    media_tags: List[User] = Field(default_factory=list, alias="mediaTags")
    quote: Optional["Tweet"] = None
    card: Optional[Card] = None
    poll: Optional[Poll] = None
    gif: Optional[Gif] = None
    video: Optional[Video] = None
    photos: List[str] = Field(default_factory=list)
    videos: List[Video] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class Timeline(BaseModel):
    """Timeline of tweets with pagination."""
    content: List[List[Tweet]] = Field(default_factory=list)
    top: str = ""
    bottom: str = ""
    beginning: bool = False


class Profile(BaseModel):
    """User profile with timeline."""
    user: User
    pinned: Optional[Tweet] = None
    tweets: Timeline


class TwitterList(BaseModel):
    """Twitter list."""
    id: str
    name: str
    user_id: str = Field(alias="userId")
    username: str
    description: str = ""
    members: int = 0
    banner: str = ""

    class Config:
        populate_by_name = True


class Url(BaseModel):
    """URL entity in tweet text."""
    url: str
    expanded_url: str = Field(alias="expandedUrl")
    display_url: str = Field(alias="displayUrl")
    indices: List[int] = Field(default_factory=lambda: [0, 0])

    class Config:
        populate_by_name = True


# Update forward references
Tweet.model_rebuild()
