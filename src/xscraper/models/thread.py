"""
X Thread Scraper - Data Models
==============================

This module defines the core data structures used throughout the scraper.
All models use dataclasses for clean serialization and type safety.

Thread Structure:
    Thread
    ├── tweets: List[Tweet]
    │   ├── content
    │   ├── media: List[Media]
    │   └── metrics: TweetMetrics
    └── author: Author

Serialization:
    All models support JSON and dict serialization via to_dict() and to_json()
"""

import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class MediaType(Enum):
    """Types of media that can be attached to tweets."""
    PHOTO = "photo"
    VIDEO = "video"
    GIF = "animated_gif"
    POLL = "poll"


class VerificationStatus(Enum):
    """User verification status types."""
    NONE = "none"
    BLUE = "blue"
    BUSINESS = "business"
    GOVERNMENT = "government"


@dataclass
class TweetMetrics:
    """Engagement metrics for a tweet."""
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quotes: int = 0
    bookmarks: int = 0
    impressions: int = 0
    
    def to_dict(self) -> Dict[str, int]:
        return asdict(self)
    
    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate based on impressions."""
        if self.impressions == 0:
            return 0.0
        total_engagement = self.likes + self.retweets + self.replies + self.quotes
        return (total_engagement / self.impressions) * 100


@dataclass
class Media:
    """Media attachment representation."""
    media_id: str
    media_type: MediaType
    url: str
    preview_url: Optional[str] = None
    alt_text: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_ms: Optional[int] = None  # For video/gif
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["media_type"] = self.media_type.value
        return data


@dataclass
class Author:
    """Twitter/X user representation."""
    user_id: str
    username: str
    display_name: str
    profile_image_url: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    tweet_count: int = 0
    created_at: Optional[datetime] = None
    verification_status: VerificationStatus = VerificationStatus.NONE
    is_protected: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        data = {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "profile_image_url": self.profile_image_url,
            "bio": self.bio,
            "location": self.location,
            "website": self.website,
            "followers_count": self.followers_count,
            "following_count": self.following_count,
            "tweet_count": self.tweet_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "verification_status": self.verification_status.value,
            "is_protected": self.is_protected
        }
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Author":
        """Create Author from dictionary."""
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        
        verification = VerificationStatus.NONE
        if data.get("verification_status"):
            try:
                verification = VerificationStatus(data["verification_status"])
            except ValueError:
                pass
        
        return cls(
            user_id=data.get("user_id", ""),
            username=data.get("username", ""),
            display_name=data.get("display_name", ""),
            profile_image_url=data.get("profile_image_url"),
            bio=data.get("bio"),
            location=data.get("location"),
            website=data.get("website"),
            followers_count=data.get("followers_count", 0),
            following_count=data.get("following_count", 0),
            tweet_count=data.get("tweet_count", 0),
            created_at=created_at,
            verification_status=verification,
            is_protected=data.get("is_protected", False)
        )


@dataclass
class Tweet:
    """Individual tweet representation."""
    tweet_id: str
    conversation_id: str
    text: str
    author: Optional[Author] = None
    author_id: Optional[str] = None
    created_at: Optional[datetime] = None
    metrics: TweetMetrics = field(default_factory=TweetMetrics)
    media: List[Media] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    in_reply_to_tweet_id: Optional[str] = None
    in_reply_to_user_id: Optional[str] = None
    quoted_tweet_id: Optional[str] = None
    retweeted_tweet_id: Optional[str] = None
    language: Optional[str] = None
    source: Optional[str] = None
    is_sensitive: bool = False
    thread_position: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tweet to dictionary."""
        return {
            "tweet_id": self.tweet_id,
            "conversation_id": self.conversation_id,
            "text": self.text,
            "author": self.author.to_dict() if self.author else None,
            "author_id": self.author_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metrics": self.metrics.to_dict(),
            "media": [m.to_dict() for m in self.media],
            "hashtags": self.hashtags,
            "mentions": self.mentions,
            "urls": self.urls,
            "in_reply_to_tweet_id": self.in_reply_to_tweet_id,
            "in_reply_to_user_id": self.in_reply_to_user_id,
            "quoted_tweet_id": self.quoted_tweet_id,
            "retweeted_tweet_id": self.retweeted_tweet_id,
            "language": self.language,
            "source": self.source,
            "is_sensitive": self.is_sensitive,
            "thread_position": self.thread_position
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize tweet to JSON."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tweet":
        """Create Tweet from dictionary."""
        author = None
        if data.get("author"):
            author = Author.from_dict(data["author"])
        
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        
        metrics = TweetMetrics(**data.get("metrics", {}))
        
        return cls(
            tweet_id=data.get("tweet_id", ""),
            conversation_id=data.get("conversation_id", ""),
            text=data.get("text", ""),
            author=author,
            author_id=data.get("author_id"),
            created_at=created_at,
            metrics=metrics,
            media=[],  # Would need Media.from_dict
            hashtags=data.get("hashtags", []),
            mentions=data.get("mentions", []),
            urls=data.get("urls", []),
            in_reply_to_tweet_id=data.get("in_reply_to_tweet_id"),
            in_reply_to_user_id=data.get("in_reply_to_user_id"),
            quoted_tweet_id=data.get("quoted_tweet_id"),
            retweeted_tweet_id=data.get("retweeted_tweet_id"),
            language=data.get("language"),
            source=data.get("source"),
            is_sensitive=data.get("is_sensitive", False),
            thread_position=data.get("thread_position")
        )
    
    @property
    def has_media(self) -> bool:
        """Check if tweet has media attachments."""
        return len(self.media) > 0
    
    @property
    def is_reply(self) -> bool:
        """Check if tweet is a reply."""
        return self.in_reply_to_tweet_id is not None
    
    @property
    def is_quote(self) -> bool:
        """Check if tweet is a quote tweet."""
        return self.quoted_tweet_id is not None
    
    @property
    def is_retweet(self) -> bool:
        """Check if tweet is a retweet."""
        return self.retweeted_tweet_id is not None


@dataclass
class Thread:
    """
    Complete thread representation containing multiple tweets.
    
    A thread is a series of tweets from the same author that form
    a connected narrative. This class represents the full thread
    structure including metadata and all constituent tweets.
    """
    thread_id: str
    created_at: Optional[datetime]
    tweets: List[Tweet] = field(default_factory=list)
    author: Optional[Author] = None
    title: Optional[str] = None  # First line or custom title
    total_tweets: int = 0
    total_likes: int = 0
    total_retweets: int = 0
    total_replies: int = 0
    is_complete: bool = True
    
    def __post_init__(self):
        """Calculate aggregate metrics after initialization."""
        if self.tweets:
            self.total_tweets = len(self.tweets)
            self.total_likes = sum(t.metrics.likes for t in self.tweets)
            self.total_retweets = sum(t.metrics.retweets for t in self.tweets)
            self.total_replies = sum(t.metrics.replies for t in self.tweets)
            
            if not self.author and self.tweets[0].author:
                self.author = self.tweets[0].author
            
            if not self.title and self.tweets:
                # Use first 100 chars of first tweet as title
                first_text = self.tweets[0].text
                self.title = first_text[:100] + "..." if len(first_text) > 100 else first_text
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert thread to dictionary."""
        return {
            "thread_id": self.thread_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "author": self.author.to_dict() if self.author else None,
            "title": self.title,
            "total_tweets": self.total_tweets,
            "total_likes": self.total_likes,
            "total_retweets": self.total_retweets,
            "total_replies": self.total_replies,
            "is_complete": self.is_complete,
            "tweets": [t.to_dict() for t in self.tweets]
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize thread to JSON."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def to_markdown(self) -> str:
        """Export thread as formatted markdown."""
        lines = []
        
        if self.author:
            lines.append(f"# Thread by @{self.author.username}")
            lines.append(f"**{self.author.display_name}**")
            lines.append("")
        
        lines.append(f"*{self.total_tweets} tweets • {self.total_likes} likes • {self.total_retweets} retweets*")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        for i, tweet in enumerate(self.tweets, 1):
            lines.append(f"### {i}/{self.total_tweets}")
            lines.append("")
            lines.append(tweet.text)
            lines.append("")
            
            if tweet.media:
                for media in tweet.media:
                    lines.append(f"![{media.alt_text or 'media'}]({media.url})")
                lines.append("")
            
            lines.append(f"*{tweet.metrics.likes} ❤️ • {tweet.metrics.retweets} 🔄 • {tweet.metrics.replies} 💬*")
            lines.append("")
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Thread":
        """Create Thread from dictionary."""
        author = None
        if data.get("author"):
            author = Author.from_dict(data["author"])
        
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        
        tweets = [Tweet.from_dict(t) for t in data.get("tweets", [])]
        
        return cls(
            thread_id=data.get("thread_id", ""),
            created_at=created_at,
            tweets=tweets,
            author=author,
            title=data.get("title"),
            total_tweets=data.get("total_tweets", 0),
            total_likes=data.get("total_likes", 0),
            total_retweets=data.get("total_retweets", 0),
            total_replies=data.get("total_replies", 0),
            is_complete=data.get("is_complete", True)
        )
    
    def get_tweet_by_id(self, tweet_id: str) -> Optional[Tweet]:
        """Find a specific tweet in the thread by ID."""
        for tweet in self.tweets:
            if tweet.tweet_id == tweet_id:
                return tweet
        return None
    
    def get_all_media(self) -> List[Media]:
        """Get all media from all tweets in the thread."""
        all_media = []
        for tweet in self.tweets:
            all_media.extend(tweet.media)
        return all_media
    
    def get_all_urls(self) -> List[str]:
        """Get all URLs mentioned in the thread."""
        all_urls = []
        for tweet in self.tweets:
            all_urls.extend(tweet.urls)
        return list(set(all_urls))
    
    def get_all_hashtags(self) -> List[str]:
        """Get all unique hashtags from the thread."""
        all_hashtags = []
        for tweet in self.tweets:
            all_hashtags.extend(tweet.hashtags)
        return list(set(all_hashtags))
