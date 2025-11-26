"""
X Thread Scraper - Proxy Handler
================================

This module provides intelligent proxy management for distributed
scraping operations. Features include:
- Proxy rotation with multiple strategies
- Health checking and automatic failover
- Geographic distribution for regional content
- Performance-based proxy selection

Proxy Types Supported:
- HTTP/HTTPS proxies
- SOCKS4/SOCKS5 proxies
- Rotating residential proxies
- Datacenter proxies

Security Note:
    Proxy credentials are handled securely and never logged.
    All proxy connections support authentication.
"""

import random
import time
import threading
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum
from urllib.parse import urlparse
import hashlib


class ProxyType(Enum):
    """Supported proxy types."""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class RotationStrategy(Enum):
    """Proxy rotation strategies."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_USED = "least_used"
    BEST_PERFORMANCE = "best_performance"
    GEOGRAPHIC = "geographic"


class ProxyStatus(Enum):
    """Proxy health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    BANNED = "banned"
    UNKNOWN = "unknown"


@dataclass
class ProxyConfig:
    """Configuration for proxy management."""
    rotation_strategy: RotationStrategy = RotationStrategy.ROUND_ROBIN
    health_check_interval: int = 300  # 5 minutes
    max_failures_before_removal: int = 5
    request_timeout: int = 30
    enable_authentication: bool = True
    enable_geographic_routing: bool = False
    fallback_to_direct: bool = False
    retry_banned_after: int = 3600  # 1 hour


@dataclass
class ProxyEntry:
    """Individual proxy configuration and metadata."""
    host: str
    port: int
    proxy_type: ProxyType = ProxyType.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    isp: Optional[str] = None
    status: ProxyStatus = ProxyStatus.UNKNOWN
    last_used: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_response_time: float = 0.0
    consecutive_failures: int = 0
    banned_until: Optional[datetime] = None
    
    @property
    def url(self) -> str:
        """Generate the proxy URL."""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.request_count == 0:
            return 0.0
        return self.success_count / self.request_count
    
    def is_available(self) -> bool:
        """Check if proxy is available for use."""
        if self.status == ProxyStatus.BANNED:
            if self.banned_until and datetime.now() < self.banned_until:
                return False
            # Ban period expired, mark as unknown
            self.status = ProxyStatus.UNKNOWN
        return self.status not in (ProxyStatus.UNHEALTHY, ProxyStatus.BANNED)
    
    def record_success(self, response_time: float):
        """Record a successful request."""
        self.request_count += 1
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_used = datetime.now()
        self.last_success = datetime.now()
        
        # Update average response time (exponential moving average)
        alpha = 0.3
        if self.avg_response_time == 0:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = alpha * response_time + (1 - alpha) * self.avg_response_time
        
        self.status = ProxyStatus.HEALTHY
    
    def record_failure(self, is_ban: bool = False):
        """Record a failed request."""
        self.request_count += 1
        self.failure_count += 1
        self.consecutive_failures += 1
        self.last_used = datetime.now()
        self.last_failure = datetime.now()
        
        if is_ban:
            self.status = ProxyStatus.BANNED
            self.banned_until = datetime.now() + timedelta(hours=1)
        elif self.consecutive_failures >= 3:
            self.status = ProxyStatus.UNHEALTHY
        elif self.consecutive_failures >= 1:
            self.status = ProxyStatus.DEGRADED


class ProxyPool:
    """
    Thread-safe pool of proxies with rotation support.
    
    Manages a collection of proxies and provides intelligent
    selection based on configured strategy.
    """
    
    def __init__(self, config: Optional[ProxyConfig] = None):
        self._config = config or ProxyConfig()
        self._proxies: Dict[str, ProxyEntry] = {}
        self._rotation_index = 0
        self._lock = threading.RLock()
        self._by_country: Dict[str, List[str]] = defaultdict(list)
    
    def _generate_proxy_id(self, host: str, port: int) -> str:
        """Generate unique ID for a proxy."""
        return hashlib.md5(f"{host}:{port}".encode()).hexdigest()[:12]
    
    def add_proxy(
        self,
        host: str,
        port: int,
        proxy_type: ProxyType = ProxyType.HTTP,
        username: Optional[str] = None,
        password: Optional[str] = None,
        country: Optional[str] = None,
        city: Optional[str] = None
    ) -> str:
        """Add a proxy to the pool."""
        with self._lock:
            proxy_id = self._generate_proxy_id(host, port)
            
            self._proxies[proxy_id] = ProxyEntry(
                host=host,
                port=port,
                proxy_type=proxy_type,
                username=username,
                password=password,
                country=country,
                city=city
            )
            
            if country:
                self._by_country[country.upper()].append(proxy_id)
            
            return proxy_id
    
    def remove_proxy(self, proxy_id: str) -> bool:
        """Remove a proxy from the pool."""
        with self._lock:
            if proxy_id not in self._proxies:
                return False
            
            proxy = self._proxies[proxy_id]
            if proxy.country:
                country_list = self._by_country.get(proxy.country.upper(), [])
                if proxy_id in country_list:
                    country_list.remove(proxy_id)
            
            del self._proxies[proxy_id]
            return True
    
    def get_proxy(self, country: Optional[str] = None) -> Optional[ProxyEntry]:
        """Get the next proxy based on rotation strategy."""
        with self._lock:
            available = self._get_available_proxies(country)
            if not available:
                return None
            
            strategy = self._config.rotation_strategy
            
            if strategy == RotationStrategy.ROUND_ROBIN:
                return self._select_round_robin(available)
            elif strategy == RotationStrategy.RANDOM:
                return self._select_random(available)
            elif strategy == RotationStrategy.LEAST_USED:
                return self._select_least_used(available)
            elif strategy == RotationStrategy.BEST_PERFORMANCE:
                return self._select_best_performance(available)
            else:
                return self._select_round_robin(available)
    
    def _get_available_proxies(self, country: Optional[str] = None) -> List[ProxyEntry]:
        """Get all available proxies, optionally filtered by country."""
        if country:
            proxy_ids = self._by_country.get(country.upper(), [])
            proxies = [self._proxies[pid] for pid in proxy_ids if pid in self._proxies]
        else:
            proxies = list(self._proxies.values())
        
        return [p for p in proxies if p.is_available()]
    
    def _select_round_robin(self, available: List[ProxyEntry]) -> ProxyEntry:
        """Select next proxy in round-robin order."""
        if not available:
            return None
        self._rotation_index = (self._rotation_index + 1) % len(available)
        return available[self._rotation_index]
    
    def _select_random(self, available: List[ProxyEntry]) -> ProxyEntry:
        """Select a random proxy."""
        return random.choice(available) if available else None
    
    def _select_least_used(self, available: List[ProxyEntry]) -> ProxyEntry:
        """Select the least used proxy."""
        if not available:
            return None
        return min(available, key=lambda p: p.request_count)
    
    def _select_best_performance(self, available: List[ProxyEntry]) -> ProxyEntry:
        """Select the best performing proxy."""
        if not available:
            return None
        # Score based on success rate and response time
        def score(proxy: ProxyEntry) -> float:
            success_score = proxy.success_rate * 100
            # Lower response time is better, cap at 10 seconds
            time_score = max(0, 100 - (proxy.avg_response_time * 10))
            return success_score * 0.7 + time_score * 0.3
        
        return max(available, key=score)
    
    def record_result(self, proxy_id: str, success: bool, response_time: float = 0, is_ban: bool = False):
        """Record the result of using a proxy."""
        with self._lock:
            if proxy_id not in self._proxies:
                return
            
            proxy = self._proxies[proxy_id]
            if success:
                proxy.record_success(response_time)
            else:
                proxy.record_failure(is_ban)
                
                # Auto-remove if too many failures
                if proxy.consecutive_failures >= self._config.max_failures_before_removal:
                    self.remove_proxy(proxy_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            total = len(self._proxies)
            healthy = sum(1 for p in self._proxies.values() if p.status == ProxyStatus.HEALTHY)
            degraded = sum(1 for p in self._proxies.values() if p.status == ProxyStatus.DEGRADED)
            unhealthy = sum(1 for p in self._proxies.values() if p.status == ProxyStatus.UNHEALTHY)
            banned = sum(1 for p in self._proxies.values() if p.status == ProxyStatus.BANNED)
            
            return {
                "total_proxies": total,
                "healthy": healthy,
                "degraded": degraded,
                "unhealthy": unhealthy,
                "banned": banned,
                "countries": len(self._by_country),
                "rotation_strategy": self._config.rotation_strategy.value
            }
    
    @property
    def size(self) -> int:
        """Get the number of proxies in the pool."""
        return len(self._proxies)


class ProxyManager:
    """
    High-level proxy management interface.
    
    Provides a simple API for proxy operations and integrates
    with the scraper's request handling.
    
    Usage:
        manager = ProxyManager()
        
        # Add proxies
        manager.add_proxy("proxy1.example.com", 8080)
        manager.add_proxy("proxy2.example.com", 8080, proxy_type=ProxyType.SOCKS5)
        
        # Get proxy for request
        proxy = manager.get_proxy_for_request()
        if proxy:
            # Make request through proxy
            response = make_request(url, proxy=proxy.url)
            
            # Report result
            manager.report_success(proxy, response_time=0.5)
    """
    
    def __init__(self, config: Optional[ProxyConfig] = None):
        self._config = config or ProxyConfig()
        self._pool = ProxyPool(self._config)
        self._current_proxy_id: Optional[str] = None
        self._enabled = True
    
    def add_proxy(
        self,
        host: str,
        port: int,
        proxy_type: ProxyType = ProxyType.HTTP,
        username: Optional[str] = None,
        password: Optional[str] = None,
        country: Optional[str] = None
    ) -> str:
        """Add a proxy to the manager."""
        return self._pool.add_proxy(
            host=host,
            port=port,
            proxy_type=proxy_type,
            username=username,
            password=password,
            country=country
        )
    
    def add_proxies_from_list(self, proxy_list: List[Dict[str, Any]]):
        """Add multiple proxies from a list of configurations."""
        for proxy_config in proxy_list:
            self.add_proxy(**proxy_config)
    
    def remove_proxy(self, proxy_id: str) -> bool:
        """Remove a proxy."""
        return self._pool.remove_proxy(proxy_id)
    
    def get_proxy_for_request(self, country: Optional[str] = None) -> Optional[ProxyEntry]:
        """Get a proxy for making a request."""
        if not self._enabled:
            return None
        
        proxy = self._pool.get_proxy(country)
        if proxy:
            self._current_proxy_id = self._pool._generate_proxy_id(proxy.host, proxy.port)
        return proxy
    
    def report_success(self, proxy: ProxyEntry, response_time: float = 0):
        """Report a successful request through a proxy."""
        proxy_id = self._pool._generate_proxy_id(proxy.host, proxy.port)
        self._pool.record_result(proxy_id, True, response_time)
    
    def report_failure(self, proxy: ProxyEntry, is_ban: bool = False):
        """Report a failed request through a proxy."""
        proxy_id = self._pool._generate_proxy_id(proxy.host, proxy.port)
        self._pool.record_result(proxy_id, False, is_ban=is_ban)
    
    def enable(self):
        """Enable proxy usage."""
        self._enabled = True
    
    def disable(self):
        """Disable proxy usage."""
        self._enabled = False
    
    @property
    def is_enabled(self) -> bool:
        """Check if proxy usage is enabled."""
        return self._enabled
    
    def get_stats(self) -> Dict[str, Any]:
        """Get proxy manager statistics."""
        stats = self._pool.get_stats()
        stats["enabled"] = self._enabled
        return stats
    
    def clear(self):
        """Remove all proxies."""
        with self._pool._lock:
            self._pool._proxies.clear()
            self._pool._by_country.clear()
            self._pool._rotation_index = 0
