#!/usr/bin/env python3
"""
Advanced Example - Batch Thread Extraction with Proxy Support
=============================================================

This example demonstrates advanced features including:
- Batch extraction of multiple threads
- Proxy rotation for distributed scraping
- Custom caching configuration
- Export to multiple formats

Before running, ensure you have:
1. Read through integration_config.py completely
2. Set up your API credentials
3. Configured your proxy list (if using proxies)
"""

import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from xscraper import ThreadScraper
from xscraper.core.scraper import ScraperConfig
from xscraper.integration_config import (
    IntegrationConfig,
    APICredentials,
    RateLimitSettings,
    ProxySettings,
    ExtractionSettings,
    OutputSettings,
    AccessTier,
    OutputFormat,
    create_production_config
)
from xscraper.handlers.cache_handler import CacheHandler, CacheConfig, CacheBackend
from xscraper.handlers.proxy_handler import ProxyManager, ProxyType
from xscraper.handlers.persistence_handler import DataPersistenceManager, StorageConfig


def main():
    # =============================================
    # Production Configuration
    # =============================================
    
    config = IntegrationConfig(
        credentials=APICredentials(),  # Uses env vars
        rate_limits=RateLimitSettings(
            tier=AccessTier.ELEVATED,
            tweets_per_window=810,  # 900 with 10% buffer
            safety_buffer_percent=10,
            max_concurrent_requests=4
        ),
        proxy=ProxySettings(
            enabled=False,  # Set to True if using proxies
            proxy_list=[
                # Add your proxies here
                # "http://user:pass@proxy1.example.com:8080",
                # "socks5://user:pass@proxy2.example.com:1080",
            ],
            rotation_strategy="round_robin",
            max_failures=5
        ),
        extraction=ExtractionSettings(
            include_metrics=True,
            include_media=True,
            include_quoted_tweets=True,
            include_replies=False,
            max_thread_depth=150,
            download_media=False
        ),
        output=OutputSettings(
            format=OutputFormat.JSONL,
            output_directory="./output/batch",
            include_metadata=True,
            compress_output=True
        )
    )
    
    # =============================================
    # Initialize Components
    # =============================================
    
    # Cache handler for performance
    cache = CacheHandler(CacheConfig(
        backend=CacheBackend.MEMORY,
        max_size=1000,
        default_ttl=3600
    ))
    
    # Proxy manager (if enabled)
    proxy_manager = None
    if config.proxy.enabled:
        proxy_manager = ProxyManager()
        for proxy_url in config.proxy.proxy_list:
            # Parse and add proxies
            pass
    
    # Persistence manager for storage
    persistence = DataPersistenceManager(StorageConfig(
        base_path=config.output.output_directory
    ))
    
    # =============================================
    # Initialize Scraper
    # =============================================
    
    scraper_config = ScraperConfig(
        max_threads=config.rate_limits.max_concurrent_requests,
        cache_enabled=True,
        request_timeout=30,
        retry_attempts=config.error_handling.max_retries
    )
    
    scraper = ThreadScraper(config=scraper_config)
    
    # Authenticate
    creds = config.credentials
    if not scraper.authenticate(
        api_key=creds.api_key,
        api_secret=creds.api_secret,
        access_token=creds.access_token,
        access_secret=creds.access_secret,
        bearer_token=creds.bearer_token
    ):
        print("Authentication failed!")
        return
    
    print("✓ Authenticated successfully")
    
    # =============================================
    # Batch Extraction
    # =============================================
    
    # List of thread IDs to extract
    thread_ids = [
        "1234567890123456789",
        "9876543210987654321",
        "1111111111111111111",
        # Add more thread IDs...
    ]
    
    print(f"\nExtracting {len(thread_ids)} threads...")
    
    # Extract in batch
    threads = scraper.extract_threads_batch(
        thread_ids=thread_ids,
        parallel=True
    )
    
    print(f"✓ Extracted {len(threads)} threads successfully")
    
    # =============================================
    # Save Results
    # =============================================
    
    for thread in threads:
        # Save to persistence layer
        persistence.save_thread(thread.thread_id, thread.to_dict())
        
        # Also cache for quick access
        cache.set_thread(thread.thread_id, thread.to_dict())
    
    # Export all to combined file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = persistence.export_all_threads(
        format=OutputFormat.JSONL,
        filename=f"threads_batch_{timestamp}"
    )
    
    print(f"✓ Exported to: {export_path}")
    
    # =============================================
    # Statistics
    # =============================================
    
    print("\n" + "="*50)
    print("EXTRACTION SUMMARY")
    print("="*50)
    
    scraper_metrics = scraper.get_metrics()
    cache_stats = cache.get_stats()
    persistence_stats = persistence.get_stats()
    
    print(f"\nScraper Metrics:")
    for key, value in scraper_metrics.items():
        print(f"  {key}: {value}")
    
    print(f"\nCache Statistics:")
    for key, value in cache_stats.items():
        print(f"  {key}: {value}")
    
    print(f"\nPersistence Statistics:")
    for key, value in persistence_stats.items():
        print(f"  {key}: {value}")
    
    # Cleanup
    scraper.shutdown()
    print("\n✓ Complete!")


if __name__ == "__main__":
    main()
