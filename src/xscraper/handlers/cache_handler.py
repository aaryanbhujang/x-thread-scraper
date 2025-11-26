"""
X Thread Scraper - Cache Handler
================================

This module provides intelligent caching functionality for thread data
to minimize API calls and improve performance. Supports multiple
caching backends including in-memory, file-based, and Redis.

Cache Strategies:
- LRU (Least Recently Used): Default for memory cache
- TTL (Time To Live): Automatic expiration
- Write-through: Immediate persistence
- Write-back: Batched persistence

Cache Key Format:
    thread:{thread_id}:{version}
    tweet:{tweet_id}:{version}
    user:{user_id}:{version}
"""

import json
import hashlib
import time
import threading
import pickle
from typing import Dict, Optional, Any, List, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from collections import OrderedDict
from abc import ABC, abstractmethod
from enum import Enum


class CacheBackend(Enum):
    """Supported cache backend types."""
    MEMORY = "memory"
    FILE = "file"
    REDIS = "redis"
    SQLITE = "sqlite"


class EvictionPolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"


@dataclass
class CacheConfig:
    """Configuration for cache behavior."""
    backend: CacheBackend = CacheBackend.MEMORY
    max_size: int = 1000
    default_ttl: int = 3600  # 1 hour
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    compression_enabled: bool = False
    encryption_enabled: bool = False
    persistence_path: Optional[str] = None
    redis_url: Optional[str] = None
    redis_prefix: str = "xscraper:"


@dataclass
class CacheEntry:
    """Individual cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    size_bytes: int = 0
    
    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def touch(self):
        """Update access metadata."""
        self.last_accessed = datetime.now()
        self.access_count += 1


class CacheStats:
    """Tracks cache performance metrics."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._writes = 0
        self._bytes_written = 0
        self._bytes_read = 0
    
    def record_hit(self, size: int = 0):
        with self._lock:
            self._hits += 1
            self._bytes_read += size
    
    def record_miss(self):
        with self._lock:
            self._misses += 1
    
    def record_write(self, size: int = 0):
        with self._lock:
            self._writes += 1
            self._bytes_written += size
    
    def record_eviction(self):
        with self._lock:
            self._evictions += 1
    
    @property
    def hit_rate(self) -> float:
        with self._lock:
            total = self._hits + self._misses
            return self._hits / total if total > 0 else 0.0
    
    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self.hit_rate * 100, 2),
                "evictions": self._evictions,
                "writes": self._writes,
                "bytes_written": self._bytes_written,
                "bytes_read": self._bytes_read
            }


class BaseCacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store a value in cache."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Remove a value from cache."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        pass
    
    @abstractmethod
    def clear(self) -> int:
        """Clear all cached values."""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get the number of items in cache."""
        pass


class MemoryCacheBackend(BaseCacheBackend):
    """
    In-memory cache with LRU eviction.
    
    Uses OrderedDict for O(1) access and LRU tracking.
    Thread-safe through RLock.
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            if entry.is_expired():
                del self._cache[key]
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            
            ttl = ttl or self._default_ttl
            expires_at = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None
            
            entry = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at,
                size_bytes=len(str(value))
            )
            
            self._cache[key] = entry
            return True
    
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def exists(self, key: str) -> bool:
        with self._lock:
            if key not in self._cache:
                return False
            if self._cache[key].is_expired():
                del self._cache[key]
                return False
            return True
    
    def clear(self) -> int:
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count
    
    def size(self) -> int:
        with self._lock:
            return len(self._cache)
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        with self._lock:
            expired_keys = [
                k for k, v in self._cache.items() 
                if v.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)


class FileCacheBackend(BaseCacheBackend):
    """
    File-based cache backend with JSON serialization.
    
    Stores each cache entry as a separate file for simplicity.
    Suitable for persistent caching across restarts.
    """
    
    def __init__(self, cache_dir: str, default_ttl: int = 3600):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._index: Dict[str, str] = {}  # key -> filename mapping
        self._load_index()
    
    def _get_filename(self, key: str) -> str:
        """Generate a safe filename from cache key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return f"cache_{key_hash}.json"
    
    def _load_index(self):
        """Load cache index from disk."""
        index_path = self._cache_dir / "index.json"
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._index = {}
    
    def _save_index(self):
        """Save cache index to disk."""
        index_path = self._cache_dir / "index.json"
        with open(index_path, 'w') as f:
            json.dump(self._index, f)
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._index:
                return None
            
            filepath = self._cache_dir / self._index[key]
            if not filepath.exists():
                del self._index[key]
                return None
            
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                # Check expiration
                expires_at = data.get("expires_at")
                if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
                    filepath.unlink()
                    del self._index[key]
                    return None
                
                return data.get("value")
            except (json.JSONDecodeError, IOError):
                return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        with self._lock:
            filename = self._get_filename(key)
            filepath = self._cache_dir / filename
            
            ttl = ttl or self._default_ttl
            expires_at = (datetime.now() + timedelta(seconds=ttl)).isoformat() if ttl > 0 else None
            
            data = {
                "key": key,
                "value": value,
                "created_at": datetime.now().isoformat(),
                "expires_at": expires_at
            }
            
            try:
                with open(filepath, 'w') as f:
                    json.dump(data, f)
                
                self._index[key] = filename
                self._save_index()
                return True
            except IOError:
                return False
    
    def delete(self, key: str) -> bool:
        with self._lock:
            if key not in self._index:
                return False
            
            filepath = self._cache_dir / self._index[key]
            try:
                if filepath.exists():
                    filepath.unlink()
                del self._index[key]
                self._save_index()
                return True
            except IOError:
                return False
    
    def exists(self, key: str) -> bool:
        with self._lock:
            return key in self._index and (self._cache_dir / self._index[key]).exists()
    
    def clear(self) -> int:
        with self._lock:
            count = 0
            for filename in self._index.values():
                filepath = self._cache_dir / filename
                if filepath.exists():
                    filepath.unlink()
                    count += 1
            
            self._index.clear()
            self._save_index()
            return count
    
    def size(self) -> int:
        return len(self._index)


class CacheHandler:
    """
    High-level cache interface with multiple backend support.
    
    This is the main entry point for caching operations in the scraper.
    It handles backend selection, statistics tracking, and provides
    convenience methods for common caching patterns.
    
    Usage:
        cache = CacheHandler(config=CacheConfig(backend=CacheBackend.MEMORY))
        
        # Store a thread
        cache.set_thread("thread_123", thread_data)
        
        # Retrieve if exists
        if cached_thread := cache.get_thread("thread_123"):
            return cached_thread
        
        # Check statistics
        print(cache.get_stats())
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self._config = config or CacheConfig()
        self._stats = CacheStats()
        self._backend = self._create_backend()
    
    def _create_backend(self) -> BaseCacheBackend:
        """Create appropriate backend based on config."""
        if self._config.backend == CacheBackend.MEMORY:
            return MemoryCacheBackend(
                max_size=self._config.max_size,
                default_ttl=self._config.default_ttl
            )
        elif self._config.backend == CacheBackend.FILE:
            path = self._config.persistence_path or "/tmp/xscraper_cache"
            return FileCacheBackend(
                cache_dir=path,
                default_ttl=self._config.default_ttl
            )
        else:
            # Default to memory
            return MemoryCacheBackend(
                max_size=self._config.max_size,
                default_ttl=self._config.default_ttl
            )
    
    def _generate_key(self, prefix: str, identifier: str, version: str = "v1") -> str:
        """Generate a standardized cache key."""
        return f"{prefix}:{identifier}:{version}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        value = self._backend.get(key)
        if value is not None:
            self._stats.record_hit()
        else:
            self._stats.record_miss()
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store a value in cache."""
        result = self._backend.set(key, value, ttl)
        if result:
            self._stats.record_write()
        return result
    
    def delete(self, key: str) -> bool:
        """Remove a value from cache."""
        return self._backend.delete(key)
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        return self._backend.exists(key)
    
    # Convenience methods for common types
    
    def get_thread(self, thread_id: str) -> Optional[Any]:
        """Get a cached thread."""
        key = self._generate_key("thread", thread_id)
        return self.get(key)
    
    def set_thread(self, thread_id: str, thread_data: Any, ttl: int = 3600) -> bool:
        """Cache a thread."""
        key = self._generate_key("thread", thread_id)
        return self.set(key, thread_data, ttl)
    
    def get_tweet(self, tweet_id: str) -> Optional[Any]:
        """Get a cached tweet."""
        key = self._generate_key("tweet", tweet_id)
        return self.get(key)
    
    def set_tweet(self, tweet_id: str, tweet_data: Any, ttl: int = 1800) -> bool:
        """Cache a tweet."""
        key = self._generate_key("tweet", tweet_id)
        return self.set(key, tweet_data, ttl)
    
    def get_user(self, user_id: str) -> Optional[Any]:
        """Get a cached user."""
        key = self._generate_key("user", user_id)
        return self.get(key)
    
    def set_user(self, user_id: str, user_data: Any, ttl: int = 7200) -> bool:
        """Cache a user."""
        key = self._generate_key("user", user_id)
        return self.set(key, user_data, ttl)
    
    def clear(self) -> int:
        """Clear all cached data."""
        return self._backend.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "backend": self._config.backend.value,
            "size": self._backend.size(),
            "max_size": self._config.max_size,
            **self._stats.get_summary()
        }
    
    def get_or_set(
        self, 
        key: str, 
        factory: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get from cache or compute and store if missing.
        
        This implements the "cache-aside" pattern.
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        
        value = factory()
        self.set(key, value, ttl)
        return value
