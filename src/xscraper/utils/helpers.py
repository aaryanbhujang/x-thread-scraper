"""
X Thread Scraper - Utility Functions
====================================

Helper utilities for common operations across the scraper.
Includes URL parsing, validation, and text processing.
"""

import re
import hashlib
from typing import Optional, List, Tuple, Dict, Any
from urllib.parse import urlparse, parse_qs
from datetime import datetime


# URL patterns for X/Twitter
X_URL_PATTERNS = [
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/(\w+)/status/(\d+)",
    r"https?://(?:mobile\.)?(?:twitter\.com|x\.com)/(\w+)/status/(\d+)",
]

# Tweet ID pattern
TWEET_ID_PATTERN = r"^\d{10,20}$"


def validate_thread_url(url: str) -> bool:
    """
    Validate if a URL is a valid X/Twitter thread URL.
    
    Args:
        url: URL string to validate
    
    Returns:
        True if valid X thread URL, False otherwise
    
    Examples:
        >>> validate_thread_url("https://x.com/user/status/1234567890")
        True
        >>> validate_thread_url("https://example.com")
        False
    """
    if not url or not isinstance(url, str):
        return False
    
    for pattern in X_URL_PATTERNS:
        if re.match(pattern, url):
            return True
    
    return False


def extract_thread_id(url: str) -> Optional[str]:
    """
    Extract the thread/tweet ID from a X/Twitter URL.
    
    Args:
        url: X/Twitter status URL
    
    Returns:
        Thread ID as string, or None if not found
    
    Examples:
        >>> extract_thread_id("https://x.com/user/status/1234567890")
        "1234567890"
        >>> extract_thread_id("invalid-url")
        None
    """
    if not url:
        return None
    
    for pattern in X_URL_PATTERNS:
        match = re.match(pattern, url)
        if match:
            return match.group(2)
    
    # Try direct ID
    if re.match(TWEET_ID_PATTERN, str(url)):
        return str(url)
    
    return None


def extract_username_from_url(url: str) -> Optional[str]:
    """
    Extract username from a X/Twitter URL.
    
    Args:
        url: X/Twitter URL
    
    Returns:
        Username without @ symbol, or None if not found
    """
    if not url:
        return None
    
    for pattern in X_URL_PATTERNS:
        match = re.match(pattern, url)
        if match:
            return match.group(1)
    
    return None


def validate_tweet_id(tweet_id: str) -> bool:
    """
    Validate if a string is a valid tweet ID.
    
    Tweet IDs are numeric strings of 10-20 digits (snowflake IDs).
    
    Args:
        tweet_id: String to validate
    
    Returns:
        True if valid tweet ID format
    """
    if not tweet_id:
        return False
    
    return bool(re.match(TWEET_ID_PATTERN, str(tweet_id)))


def parse_tweet_text(text: str) -> Dict[str, List[str]]:
    """
    Parse tweet text to extract mentions, hashtags, and URLs.
    
    Args:
        text: Raw tweet text
    
    Returns:
        Dict with 'mentions', 'hashtags', 'urls' lists
    """
    result = {
        "mentions": [],
        "hashtags": [],
        "urls": [],
        "cashtags": []
    }
    
    if not text:
        return result
    
    # Extract mentions (@username)
    mentions = re.findall(r"@(\w+)", text)
    result["mentions"] = list(set(mentions))
    
    # Extract hashtags (#tag)
    hashtags = re.findall(r"#(\w+)", text)
    result["hashtags"] = list(set(hashtags))
    
    # Extract URLs
    url_pattern = r"https?://[^\s<>\"{}|\\^`\[\]]+"
    urls = re.findall(url_pattern, text)
    result["urls"] = list(set(urls))
    
    # Extract cashtags ($SYMBOL)
    cashtags = re.findall(r"\$([A-Z]+)", text)
    result["cashtags"] = list(set(cashtags))
    
    return result


def clean_text(text: str) -> str:
    """
    Clean tweet text by removing extra whitespace and normalizing.
    
    Args:
        text: Raw text to clean
    
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = " ".join(text.split())
    
    # Remove zero-width characters
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    
    return text.strip()


def truncate_text(text: str, max_length: int = 280, ellipsis: str = "...") -> str:
    """
    Truncate text to maximum length with ellipsis.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including ellipsis
        ellipsis: String to append when truncated
    
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text or ""
    
    return text[:max_length - len(ellipsis)] + ellipsis


def generate_hash(data: str, algorithm: str = "sha256") -> str:
    """
    Generate a hash of the input data.
    
    Args:
        data: String data to hash
        algorithm: Hash algorithm (md5, sha1, sha256)
    
    Returns:
        Hex digest of hash
    """
    if algorithm == "md5":
        return hashlib.md5(data.encode()).hexdigest()
    elif algorithm == "sha1":
        return hashlib.sha1(data.encode()).hexdigest()
    else:
        return hashlib.sha256(data.encode()).hexdigest()


def format_count(count: int) -> str:
    """
    Format a count number for display (e.g., 1.2K, 3.5M).
    
    Args:
        count: Number to format
    
    Returns:
        Formatted string
    """
    if count < 1000:
        return str(count)
    elif count < 1_000_000:
        return f"{count / 1000:.1f}K"
    elif count < 1_000_000_000:
        return f"{count / 1_000_000:.1f}M"
    else:
        return f"{count / 1_000_000_000:.1f}B"


def parse_twitter_datetime(datetime_str: str) -> Optional[datetime]:
    """
    Parse X/Twitter datetime format to datetime object.
    
    X API uses ISO 8601 format: "2024-01-15T10:30:00.000Z"
    
    Args:
        datetime_str: Datetime string from API
    
    Returns:
        datetime object or None if parsing fails
    """
    if not datetime_str:
        return None
    
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%a %b %d %H:%M:%S %z %Y",  # Legacy format
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    return None


def build_thread_url(username: str, tweet_id: str) -> str:
    """
    Build a X/Twitter thread URL from username and tweet ID.
    
    Args:
        username: Twitter username (without @)
        tweet_id: Tweet/thread ID
    
    Returns:
        Full thread URL
    """
    return f"https://x.com/{username}/status/{tweet_id}"


def calculate_engagement_rate(
    likes: int,
    retweets: int,
    replies: int,
    impressions: int
) -> float:
    """
    Calculate engagement rate as percentage.
    
    Args:
        likes: Number of likes
        retweets: Number of retweets
        replies: Number of replies
        impressions: Number of impressions
    
    Returns:
        Engagement rate as percentage
    """
    if impressions <= 0:
        return 0.0
    
    total_engagement = likes + retweets + replies
    return (total_engagement / impressions) * 100


def estimate_read_time(text: str, words_per_minute: int = 200) -> int:
    """
    Estimate reading time for text in seconds.
    
    Args:
        text: Text to estimate
        words_per_minute: Reading speed
    
    Returns:
        Estimated seconds to read
    """
    if not text:
        return 0
    
    word_count = len(text.split())
    minutes = word_count / words_per_minute
    return max(1, int(minutes * 60))


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split a list into chunks of specified size.
    
    Args:
        lst: List to chunk
        chunk_size: Size of each chunk
    
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
