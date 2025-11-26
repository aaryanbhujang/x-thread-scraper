"""
Core module containing the main scraping engine components.
"""

from .scraper import ThreadScraper
from .authenticator import XAuthenticator
from .rate_limiter import AdaptiveRateLimiter

__all__ = ["ThreadScraper", "XAuthenticator", "AdaptiveRateLimiter"]
