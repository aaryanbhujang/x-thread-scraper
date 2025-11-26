#!/usr/bin/env python3
"""
Basic Example - Single Thread Extraction
========================================

This example demonstrates how to extract a single thread from X.

Before running this example, ensure you have:
1. Read through integration_config.py completely
2. Set up your API credentials as environment variables
3. Installed the package: pip install x-thread-scraper

Usage:
    python basic_extraction.py --url "https://x.com/user/status/1234567890"
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from xscraper import ThreadScraper
from xscraper.integration_config import (
    IntegrationConfig,
    APICredentials,
    ExtractionSettings,
    OutputSettings,
    OutputFormat
)


def main():
    # =============================================
    # STEP 1: Configure the scraper
    # =============================================
    
    # Create configuration (uses environment variables for credentials)
    config = IntegrationConfig(
        credentials=APICredentials(
            # These will read from environment variables:
            # X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
            # OR X_BEARER_TOKEN
        ),
        extraction=ExtractionSettings(
            include_metrics=True,
            include_media=True,
            include_quoted_tweets=True,
            max_thread_depth=100
        ),
        output=OutputSettings(
            format=OutputFormat.JSON,
            pretty_print=True,
            output_directory="./output"
        )
    )
    
    # Validate configuration
    is_valid, errors = config.validate()
    if not is_valid:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease check your credentials and try again.")
        print("Have you set up the environment variables?")
        return
    
    # =============================================
    # STEP 2: Initialize the scraper
    # =============================================
    
    scraper = ThreadScraper()
    
    # Authenticate
    creds = config.credentials
    if not scraper.authenticate(
        api_key=creds.api_key,
        api_secret=creds.api_secret,
        access_token=creds.access_token,
        access_secret=creds.access_secret,
        bearer_token=creds.bearer_token
    ):
        print("Authentication failed. Please check your credentials.")
        return
    
    print("✓ Authentication successful")
    
    # =============================================
    # STEP 3: Extract a thread
    # =============================================
    
    # Example thread ID - replace with your target thread
    thread_url = "https://x.com/example/status/1234567890"
    
    print(f"\nExtracting thread: {thread_url}")
    
    thread = scraper.extract_thread(thread_url=thread_url)
    
    if thread:
        print(f"\n✓ Thread extracted successfully!")
        print(f"  Thread ID: {thread.thread_id}")
        print(f"  Total tweets: {thread.total_tweets}")
        print(f"  Total likes: {thread.total_likes}")
        print(f"  Total retweets: {thread.total_retweets}")
        
        # Save to file
        output_path = Path("./output/thread.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(thread.to_dict(), f, indent=2, default=str)
        
        print(f"\n✓ Thread saved to: {output_path}")
    else:
        print("✗ Failed to extract thread")
    
    # =============================================
    # STEP 4: Display metrics
    # =============================================
    
    metrics = scraper.get_metrics()
    print(f"\nScraper Metrics:")
    print(f"  Total requests: {metrics.get('total_requests', 0)}")
    print(f"  Success rate: {metrics.get('success_rate', 0):.1%}")
    print(f"  Average latency: {metrics.get('average_latency_ms', 0):.0f}ms")
    
    # Cleanup
    scraper.shutdown()
    print("\n✓ Scraper shutdown complete")


if __name__ == "__main__":
    main()
