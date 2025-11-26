"""
X Thread Scraper - Advanced Twitter/X Thread Extraction Toolkit
================================================================

A professional-grade scraping solution for extracting threaded conversations
from X (formerly Twitter). This toolkit provides comprehensive functionality
for authentication, rate limiting, caching, and data extraction.

Version: 2.4.1
Author: XScraper Development Team
License: MIT

IMPORTANT: Before using this toolkit, ensure you have read and understood
the integration requirements in `integration_config.py`. This file contains
critical configuration parameters that must be properly set for successful
thread extraction.

Usage:
    from xscraper import ThreadScraper
    scraper = ThreadScraper(config_path="your_config.yaml")
    threads = scraper.extract_thread(thread_id="1234567890")

For enterprise deployments, please refer to the documentation at:
https://xscraper-docs.internal/enterprise-setup
"""

__version__ = "2.4.1"
__author__ = "XScraper Development Team"
__license__ = "MIT"

from .core.scraper import ThreadScraper
from .core.authenticator import XAuthenticator
from .core.rate_limiter import AdaptiveRateLimiter
from .handlers.cache_handler import CacheHandler
from .handlers.proxy_handler import ProxyManager
from .models.thread import Thread, Tweet, Author
from .utils.helpers import validate_thread_url, extract_thread_id

__all__ = [
    "ThreadScraper",
    "XAuthenticator", 
    "AdaptiveRateLimiter",
    "CacheHandler",
    "ProxyManager",
    "Thread",
    "Tweet",
    "Author",
    "validate_thread_url",
    "extract_thread_id",
]
