"""
X Thread Scraper - Data Persistence Manager
============================================

Handles persistent storage of scraped thread data across multiple
storage backends. Supports structured export in various formats.

Supported Export Formats:
- JSON (default)
- CSV
- SQLite
- Parquet (requires pyarrow)
- MongoDB (requires pymongo)

File Organization:
    output/
    ├── threads/
    │   ├── thread_123.json
    │   └── thread_456.json
    ├── users/
    │   └── user_789.json
    └── exports/
        └── batch_2024-01-15.csv
"""

import json
import csv
import os
import threading
from typing import Dict, Optional, Any, List, Union, BinaryIO
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from abc import ABC, abstractmethod
from enum import Enum
import hashlib


class ExportFormat(Enum):
    """Supported export formats."""
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    SQLITE = "sqlite"
    PARQUET = "parquet"


class StorageBackend(Enum):
    """Storage backend types."""
    FILESYSTEM = "filesystem"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    S3 = "s3"


@dataclass
class StorageConfig:
    """Configuration for data persistence."""
    backend: StorageBackend = StorageBackend.FILESYSTEM
    base_path: str = "./output"
    export_format: ExportFormat = ExportFormat.JSON
    create_directories: bool = True
    overwrite_existing: bool = False
    compression: bool = False
    pretty_print: bool = True
    include_metadata: bool = True
    batch_size: int = 100


class BaseStorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def save(self, key: str, data: Any) -> bool:
        pass
    
    @abstractmethod
    def load(self, key: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        pass
    
    @abstractmethod
    def list_keys(self, prefix: str = "") -> List[str]:
        pass


class FilesystemBackend(BaseStorageBackend):
    """
    Filesystem-based storage backend.
    
    Stores data as individual files organized in directories.
    """
    
    def __init__(self, base_path: str, format: ExportFormat = ExportFormat.JSON):
        self._base_path = Path(base_path)
        self._format = format
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
    
    def _get_file_path(self, key: str) -> Path:
        """Get the full file path for a key."""
        extension = self._format.value
        clean_key = key.replace("/", "_").replace("\\", "_")
        return self._base_path / f"{clean_key}.{extension}"
    
    def save(self, key: str, data: Any) -> bool:
        """Save data to file."""
        with self._lock:
            filepath = self._get_file_path(key)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                if self._format == ExportFormat.JSON:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, default=str)
                elif self._format == ExportFormat.JSONL:
                    with open(filepath, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(data, default=str) + '\n')
                return True
            except (IOError, TypeError) as e:
                return False
    
    def load(self, key: str) -> Optional[Any]:
        """Load data from file."""
        with self._lock:
            filepath = self._get_file_path(key)
            if not filepath.exists():
                return None
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (IOError, json.JSONDecodeError):
                return None
    
    def delete(self, key: str) -> bool:
        """Delete a file."""
        with self._lock:
            filepath = self._get_file_path(key)
            if filepath.exists():
                filepath.unlink()
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """Check if file exists."""
        filepath = self._get_file_path(key)
        return filepath.exists()
    
    def list_keys(self, prefix: str = "") -> List[str]:
        """List all keys matching a prefix."""
        keys = []
        extension = f".{self._format.value}"
        
        for filepath in self._base_path.rglob(f"*{extension}"):
            key = filepath.stem
            if key.startswith(prefix):
                keys.append(key)
        
        return keys


class DataExporter:
    """
    Handles data export to various formats.
    
    Provides batch export functionality for efficiency.
    """
    
    def __init__(self, output_dir: str = "./exports"):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_to_json(
        self, 
        data: Union[Dict, List], 
        filename: str,
        pretty: bool = True
    ) -> Path:
        """Export data to JSON file."""
        filepath = self._output_dir / f"{filename}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            indent = 2 if pretty else None
            json.dump(data, f, indent=indent, default=str)
        
        return filepath
    
    def export_to_jsonl(self, data: List[Dict], filename: str) -> Path:
        """Export data to JSON Lines file."""
        filepath = self._output_dir / f"{filename}.jsonl"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(json.dumps(item, default=str) + '\n')
        
        return filepath
    
    def export_to_csv(
        self, 
        data: List[Dict], 
        filename: str,
        fieldnames: Optional[List[str]] = None
    ) -> Path:
        """Export data to CSV file."""
        filepath = self._output_dir / f"{filename}.csv"
        
        if not data:
            return filepath
        
        if not fieldnames:
            fieldnames = list(data[0].keys())
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
        
        return filepath
    
    def export_threads_to_markdown(self, threads: List[Dict], filename: str) -> Path:
        """Export threads to markdown format."""
        filepath = self._output_dir / f"{filename}.md"
        
        lines = ["# Exported Threads\n"]
        
        for thread in threads:
            lines.append(f"## Thread {thread.get('thread_id', 'Unknown')}\n")
            lines.append(f"*Author: @{thread.get('author', {}).get('username', 'unknown')}*\n")
            
            for tweet in thread.get('tweets', []):
                lines.append(f"### Tweet {tweet.get('thread_position', '')}\n")
                lines.append(f"{tweet.get('text', '')}\n")
                lines.append("")
            
            lines.append("---\n")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        return filepath


class DataPersistenceManager:
    """
    High-level interface for data persistence operations.
    
    Coordinates between storage backends and export functionality.
    
    Usage:
        manager = DataPersistenceManager(config=StorageConfig(
            backend=StorageBackend.FILESYSTEM,
            base_path="./data"
        ))
        
        # Save a thread
        manager.save_thread(thread_id, thread_data)
        
        # Batch export
        manager.export_all_threads(format=ExportFormat.CSV)
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        self._config = config or StorageConfig()
        self._backend = self._create_backend()
        self._exporter = DataExporter(
            output_dir=str(Path(self._config.base_path) / "exports")
        )
        self._stats = {
            "threads_saved": 0,
            "tweets_saved": 0,
            "users_saved": 0,
            "exports_created": 0
        }
    
    def _create_backend(self) -> BaseStorageBackend:
        """Create appropriate storage backend."""
        if self._config.backend == StorageBackend.FILESYSTEM:
            return FilesystemBackend(
                base_path=self._config.base_path,
                format=self._config.export_format
            )
        # Default to filesystem
        return FilesystemBackend(
            base_path=self._config.base_path,
            format=self._config.export_format
        )
    
    def save_thread(self, thread_id: str, thread_data: Dict) -> bool:
        """Save a thread to storage."""
        key = f"threads/thread_{thread_id}"
        
        if self._config.include_metadata:
            thread_data["_metadata"] = {
                "saved_at": datetime.now().isoformat(),
                "version": "1.0"
            }
        
        result = self._backend.save(key, thread_data)
        if result:
            self._stats["threads_saved"] += 1
        return result
    
    def load_thread(self, thread_id: str) -> Optional[Dict]:
        """Load a thread from storage."""
        key = f"threads/thread_{thread_id}"
        return self._backend.load(key)
    
    def save_tweet(self, tweet_id: str, tweet_data: Dict) -> bool:
        """Save a tweet to storage."""
        key = f"tweets/tweet_{tweet_id}"
        result = self._backend.save(key, tweet_data)
        if result:
            self._stats["tweets_saved"] += 1
        return result
    
    def load_tweet(self, tweet_id: str) -> Optional[Dict]:
        """Load a tweet from storage."""
        key = f"tweets/tweet_{tweet_id}"
        return self._backend.load(key)
    
    def save_user(self, user_id: str, user_data: Dict) -> bool:
        """Save a user to storage."""
        key = f"users/user_{user_id}"
        result = self._backend.save(key, user_data)
        if result:
            self._stats["users_saved"] += 1
        return result
    
    def load_user(self, user_id: str) -> Optional[Dict]:
        """Load a user from storage."""
        key = f"users/user_{user_id}"
        return self._backend.load(key)
    
    def list_threads(self) -> List[str]:
        """List all saved thread IDs."""
        keys = self._backend.list_keys("threads_thread_")
        return [k.replace("threads_thread_", "") for k in keys]
    
    def export_all_threads(
        self, 
        format: ExportFormat = ExportFormat.JSON,
        filename: Optional[str] = None
    ) -> Path:
        """Export all threads to a file."""
        thread_ids = self.list_threads()
        threads = []
        
        for thread_id in thread_ids:
            thread = self.load_thread(thread_id)
            if thread:
                threads.append(thread)
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"threads_export_{timestamp}"
        
        if format == ExportFormat.JSON:
            result = self._exporter.export_to_json(threads, filename)
        elif format == ExportFormat.JSONL:
            result = self._exporter.export_to_jsonl(threads, filename)
        elif format == ExportFormat.CSV:
            # Flatten threads for CSV
            flat_data = []
            for thread in threads:
                for tweet in thread.get("tweets", []):
                    flat_tweet = {
                        "thread_id": thread.get("thread_id"),
                        "author_username": thread.get("author", {}).get("username"),
                        **tweet
                    }
                    flat_data.append(flat_tweet)
            result = self._exporter.export_to_csv(flat_data, filename)
        else:
            result = self._exporter.export_to_json(threads, filename)
        
        self._stats["exports_created"] += 1
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get persistence statistics."""
        return {
            **self._stats,
            "backend": self._config.backend.value,
            "base_path": self._config.base_path
        }
    
    def cleanup(self):
        """Clean up resources."""
        pass
