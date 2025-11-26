"""
X Thread Scraper - Adaptive Rate Limiter
=========================================

This module implements an intelligent rate limiting system that:
- Monitors API endpoint usage patterns
- Dynamically adjusts request rates based on response headers
- Implements exponential backoff on rate limit encounters
- Supports multiple rate limit windows (15min, 1hr, 24hr)

X API Rate Limits (as of API v2):
- App rate limit: 300 requests per 15-minute window (app-only)
- User rate limit: 900 requests per 15-minute window (user context)
- Tweet lookup: 300 requests per 15-minute window
- Search: 180 requests per 15-minute window
"""

import time
import threading
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from enum import Enum
import math


class RateLimitTier(Enum):
    """API rate limit tiers."""
    ESSENTIAL = "essential"
    ELEVATED = "elevated"
    ACADEMIC = "academic"
    ENTERPRISE = "enterprise"


@dataclass
class RateLimitConfig:
    """Configuration for rate limit behavior."""
    requests_per_window: int = 300
    window_seconds: int = 900  # 15 minutes
    max_concurrent: int = 10
    backoff_base: float = 1.0
    backoff_max: float = 300.0  # 5 minutes max
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1


@dataclass
class EndpointLimits:
    """Rate limit information for a specific endpoint."""
    endpoint: str
    limit: int
    remaining: int
    reset_time: datetime
    window_seconds: int = 900
    
    def is_exhausted(self) -> bool:
        """Check if rate limit is exhausted."""
        return self.remaining <= 0 and datetime.now() < self.reset_time
    
    def time_until_reset(self) -> float:
        """Get seconds until rate limit resets."""
        if datetime.now() >= self.reset_time:
            return 0
        return (self.reset_time - datetime.now()).total_seconds()


class SlidingWindowCounter:
    """
    Implements a sliding window rate counter for accurate request tracking.
    
    Unlike fixed window counters, this approach provides more accurate
    rate limiting by considering requests across window boundaries.
    """
    
    def __init__(self, window_seconds: int = 900, sub_windows: int = 15):
        self._window_seconds = window_seconds
        self._sub_window_seconds = window_seconds // sub_windows
        self._sub_windows = sub_windows
        self._buckets: deque = deque(maxlen=sub_windows)
        self._lock = threading.Lock()
        self._current_bucket_start: Optional[float] = None
        self._current_count = 0
    
    def _get_current_bucket_index(self) -> int:
        """Get the index of the current time bucket."""
        now = time.time()
        return int(now // self._sub_window_seconds) % self._sub_windows
    
    def _cleanup_old_buckets(self):
        """Remove buckets that have expired."""
        now = time.time()
        window_start = now - self._window_seconds
        
        while self._buckets:
            bucket_time, _ = self._buckets[0]
            if bucket_time < window_start:
                self._buckets.popleft()
            else:
                break
    
    def increment(self, count: int = 1):
        """Record new requests."""
        with self._lock:
            now = time.time()
            self._cleanup_old_buckets()
            self._buckets.append((now, count))
    
    def get_count(self) -> int:
        """Get the total request count in the current window."""
        with self._lock:
            self._cleanup_old_buckets()
            return sum(count for _, count in self._buckets)
    
    def get_rate(self) -> float:
        """Get the current request rate per second."""
        count = self.get_count()
        return count / self._window_seconds if self._window_seconds > 0 else 0


class ExponentialBackoff:
    """
    Implements exponential backoff with jitter for retry timing.
    
    Features:
    - Configurable base delay and maximum delay
    - Optional jitter to prevent thundering herd
    - Attempt tracking for progressive delays
    """
    
    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 300.0,
        multiplier: float = 2.0,
        jitter: float = 0.1
    ):
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._multiplier = multiplier
        self._jitter = jitter
        self._attempts = 0
        self._lock = threading.Lock()
    
    def get_delay(self) -> float:
        """Calculate the next delay with exponential backoff."""
        with self._lock:
            delay = self._base_delay * (self._multiplier ** self._attempts)
            delay = min(delay, self._max_delay)
            
            # Add jitter
            if self._jitter > 0:
                import random
                jitter_range = delay * self._jitter
                delay += random.uniform(-jitter_range, jitter_range)
            
            return max(0, delay)
    
    def record_failure(self):
        """Record a failure and increment the attempt counter."""
        with self._lock:
            self._attempts += 1
    
    def record_success(self):
        """Record a success and reset the attempt counter."""
        with self._lock:
            self._attempts = 0
    
    def reset(self):
        """Reset the backoff state."""
        with self._lock:
            self._attempts = 0
    
    @property
    def attempts(self) -> int:
        """Get the current attempt count."""
        with self._lock:
            return self._attempts


class AdaptiveRateLimiter:
    """
    Intelligent rate limiter that adapts to API response patterns.
    
    This limiter:
    - Tracks requests per endpoint using sliding windows
    - Parses rate limit headers from responses
    - Dynamically adjusts request rates based on remaining quota
    - Implements backoff strategies when limits are approached
    
    Usage:
        limiter = AdaptiveRateLimiter()
        
        # Before making a request
        wait_time = limiter.get_wait_time("/tweets/123")
        if wait_time > 0:
            time.sleep(wait_time)
        
        # After receiving a response
        limiter.update_from_headers(response.headers)
        limiter.record_request("/tweets/123")
    """
    
    # Default rate limits per endpoint pattern
    DEFAULT_LIMITS = {
        "/tweets": RateLimitConfig(requests_per_window=300, window_seconds=900),
        "/users": RateLimitConfig(requests_per_window=300, window_seconds=900),
        "/search": RateLimitConfig(requests_per_window=180, window_seconds=900),
        "/lists": RateLimitConfig(requests_per_window=75, window_seconds=900),
        "/graphql": RateLimitConfig(requests_per_window=50, window_seconds=900),
        "default": RateLimitConfig(requests_per_window=300, window_seconds=900)
    }
    
    # X API rate limit headers
    LIMIT_HEADER = "x-rate-limit-limit"
    REMAINING_HEADER = "x-rate-limit-remaining"
    RESET_HEADER = "x-rate-limit-reset"
    
    def __init__(
        self,
        tier: RateLimitTier = RateLimitTier.ESSENTIAL,
        custom_limits: Optional[Dict[str, RateLimitConfig]] = None
    ):
        self._tier = tier
        self._limits = {**self.DEFAULT_LIMITS}
        if custom_limits:
            self._limits.update(custom_limits)
        
        self._endpoint_counters: Dict[str, SlidingWindowCounter] = {}
        self._endpoint_limits: Dict[str, EndpointLimits] = {}
        self._backoff = ExponentialBackoff()
        self._lock = threading.RLock()
        
        # Adaptive parameters
        self._safety_buffer = 0.1  # Keep 10% of rate limit in reserve
        self._rate_limit_encountered = False
        self._last_rate_limit_time: Optional[datetime] = None
    
    def _get_endpoint_pattern(self, endpoint: str) -> str:
        """Extract the pattern from an endpoint path."""
        # Extract base path for rate limit lookup
        parts = endpoint.split('/')
        if len(parts) >= 2:
            base = '/' + parts[1] if parts[1] else '/default'
            return base
        return "default"
    
    def _get_counter(self, endpoint: str) -> SlidingWindowCounter:
        """Get or create a counter for an endpoint."""
        pattern = self._get_endpoint_pattern(endpoint)
        with self._lock:
            if pattern not in self._endpoint_counters:
                config = self._limits.get(pattern, self._limits["default"])
                self._endpoint_counters[pattern] = SlidingWindowCounter(
                    window_seconds=config.window_seconds
                )
            return self._endpoint_counters[pattern]
    
    def _get_limit_config(self, endpoint: str) -> RateLimitConfig:
        """Get rate limit configuration for an endpoint."""
        pattern = self._get_endpoint_pattern(endpoint)
        return self._limits.get(pattern, self._limits["default"])
    
    def record_request(self, endpoint: str, count: int = 1):
        """Record that a request was made to an endpoint."""
        counter = self._get_counter(endpoint)
        counter.increment(count)
        self._backoff.record_success()
    
    def record_rate_limit_response(self, endpoint: str):
        """Record that a rate limit response was received."""
        with self._lock:
            self._rate_limit_encountered = True
            self._last_rate_limit_time = datetime.now()
            self._backoff.record_failure()
    
    def update_from_headers(self, headers: Dict[str, str], endpoint: str = "default"):
        """
        Update rate limit information from response headers.
        
        Args:
            headers: Response headers containing rate limit info
            endpoint: The endpoint that was called
        """
        with self._lock:
            limit = headers.get(self.LIMIT_HEADER)
            remaining = headers.get(self.REMAINING_HEADER)
            reset = headers.get(self.RESET_HEADER)
            
            if all([limit, remaining, reset]):
                try:
                    reset_time = datetime.fromtimestamp(int(reset))
                    self._endpoint_limits[endpoint] = EndpointLimits(
                        endpoint=endpoint,
                        limit=int(limit),
                        remaining=int(remaining),
                        reset_time=reset_time
                    )
                except (ValueError, TypeError):
                    pass
    
    def get_wait_time(self, endpoint: str) -> float:
        """
        Calculate how long to wait before making a request.
        
        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        with self._lock:
            # Check if we have explicit limit info for this endpoint
            if endpoint in self._endpoint_limits:
                limit_info = self._endpoint_limits[endpoint]
                if limit_info.is_exhausted():
                    return limit_info.time_until_reset()
            
            # Check sliding window counter
            counter = self._get_counter(endpoint)
            config = self._get_limit_config(endpoint)
            
            current_count = counter.get_count()
            effective_limit = int(config.requests_per_window * (1 - self._safety_buffer))
            
            if current_count >= effective_limit:
                # Calculate time until oldest request exits the window
                rate = counter.get_rate()
                if rate > 0:
                    requests_to_clear = current_count - effective_limit + 1
                    wait = requests_to_clear / rate
                    return min(wait, config.window_seconds)
                return config.window_seconds
            
            # Add backoff delay if we recently hit rate limits
            if self._rate_limit_encountered and self._last_rate_limit_time:
                time_since_limit = (datetime.now() - self._last_rate_limit_time).total_seconds()
                if time_since_limit < 60:  # Within last minute
                    return self._backoff.get_delay()
            
            return 0
    
    def can_make_request(self, endpoint: str) -> bool:
        """Check if a request can be made without waiting."""
        return self.get_wait_time(endpoint) == 0
    
    def get_remaining_quota(self, endpoint: str) -> Optional[int]:
        """Get the remaining request quota for an endpoint."""
        with self._lock:
            if endpoint in self._endpoint_limits:
                return self._endpoint_limits[endpoint].remaining
            
            counter = self._get_counter(endpoint)
            config = self._get_limit_config(endpoint)
            return config.requests_per_window - counter.get_count()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current rate limiter statistics."""
        with self._lock:
            stats = {
                "tier": self._tier.value,
                "rate_limit_encountered": self._rate_limit_encountered,
                "backoff_attempts": self._backoff.attempts,
                "endpoints": {}
            }
            
            for pattern, counter in self._endpoint_counters.items():
                config = self._limits.get(pattern, self._limits["default"])
                stats["endpoints"][pattern] = {
                    "requests_in_window": counter.get_count(),
                    "rate_per_second": round(counter.get_rate(), 3),
                    "limit": config.requests_per_window,
                    "window_seconds": config.window_seconds
                }
            
            return stats
    
    def reset(self):
        """Reset all rate limit tracking."""
        with self._lock:
            self._endpoint_counters.clear()
            self._endpoint_limits.clear()
            self._backoff.reset()
            self._rate_limit_encountered = False
            self._last_rate_limit_time = None
