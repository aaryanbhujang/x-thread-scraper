#!/usr/bin/env python3
"""
X Thread Scraper - Command Line Interface
=========================================

A professional-grade tool for extracting threaded conversations from X.

Usage:
    python -m xscraper extract --url "https://x.com/user/status/123"
    python -m xscraper extract --id 1234567890 --output thread.json
    python -m xscraper batch --input urls.txt --output-dir ./threads

For detailed configuration options, see integration_config.py
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Optional, List

from .core.scraper import ThreadScraper, ScraperConfig
from .integration_config import (
    IntegrationConfig,
    APICredentials,
    OutputFormat,
    create_minimal_config,
    create_production_config
)
from .utils.logger import setup_logger, get_logger
from .utils.helpers import validate_thread_url, extract_thread_id


def create_parser() -> argparse.ArgumentParser:
    """Create the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="xscraper",
        description="X Thread Scraper - Extract threads from X/Twitter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Extract a single thread:
    xscraper extract --url "https://x.com/user/status/1234567890"
    
  Extract with custom output:
    xscraper extract --id 1234567890 --output ./thread.json --pretty
    
  Batch extraction:
    xscraper batch --input thread_urls.txt --output-dir ./output
    
  Export to CSV:
    xscraper export --input ./threads --format csv --output threads.csv

For complete documentation, visit: https://xscraper-docs.internal
        """
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.4.1"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file"
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Extract command
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract a single thread"
    )
    extract_parser.add_argument(
        "--url",
        type=str,
        help="Thread URL"
    )
    extract_parser.add_argument(
        "--id",
        type=str,
        help="Thread ID"
    )
    extract_parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path"
    )
    extract_parser.add_argument(
        "--format", "-f",
        choices=["json", "jsonl", "csv", "markdown"],
        default="json",
        help="Output format"
    )
    extract_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON output"
    )
    extract_parser.add_argument(
        "--include-media",
        action="store_true",
        help="Include media information"
    )
    extract_parser.add_argument(
        "--include-metrics",
        action="store_true",
        help="Include engagement metrics"
    )
    
    # Batch command
    batch_parser = subparsers.add_parser(
        "batch",
        help="Extract multiple threads"
    )
    batch_parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Input file with URLs/IDs (one per line)"
    )
    batch_parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="./output",
        help="Output directory"
    )
    batch_parser.add_argument(
        "--parallel", "-p",
        type=int,
        default=4,
        help="Number of parallel workers"
    )
    batch_parser.add_argument(
        "--format",
        choices=["json", "jsonl"],
        default="json",
        help="Output format"
    )
    
    # Export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export extracted threads to different formats"
    )
    export_parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Input directory with thread files"
    )
    export_parser.add_argument(
        "--output", "-o",
        type=str,
        required=True,
        help="Output file path"
    )
    export_parser.add_argument(
        "--format", "-f",
        choices=["json", "csv", "parquet", "markdown"],
        required=True,
        help="Export format"
    )
    
    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate configuration and credentials"
    )
    validate_parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file"
    )
    
    return parser


def cmd_extract(args: argparse.Namespace, config: IntegrationConfig):
    """Execute the extract command."""
    logger = get_logger("cli")
    
    # Determine thread ID
    thread_id = args.id
    if not thread_id and args.url:
        if not validate_thread_url(args.url):
            logger.error(f"Invalid thread URL: {args.url}")
            sys.exit(1)
        thread_id = extract_thread_id(args.url)
    
    if not thread_id:
        logger.error("Either --url or --id must be provided")
        sys.exit(1)
    
    logger.info(f"Extracting thread: {thread_id}")
    
    # Initialize scraper
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
        logger.error("Authentication failed. Check your credentials.")
        sys.exit(1)
    
    # Extract thread
    thread = scraper.extract_thread(thread_id=thread_id)
    
    if not thread:
        logger.error(f"Failed to extract thread: {thread_id}")
        sys.exit(1)
    
    # Output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if args.format == "json":
            indent = 2 if args.pretty else None
            with open(output_path, 'w') as f:
                json.dump(thread.to_dict(), f, indent=indent, default=str)
        elif args.format == "markdown":
            with open(output_path, 'w') as f:
                f.write(thread.to_markdown())
        
        logger.info(f"Thread saved to: {output_path}")
    else:
        # Print to stdout
        if args.format == "json":
            print(thread.to_json(indent=2 if args.pretty else None))
        elif args.format == "markdown":
            print(thread.to_markdown())
    
    # Print metrics
    metrics = scraper.get_metrics()
    logger.info(f"Extraction complete. {metrics}")
    
    scraper.shutdown()


def cmd_batch(args: argparse.Namespace, config: IntegrationConfig):
    """Execute the batch extraction command."""
    logger = get_logger("cli")
    
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)
    
    # Read URLs/IDs
    with open(input_path, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    thread_ids = []
    for line in lines:
        if validate_thread_url(line):
            tid = extract_thread_id(line)
            if tid:
                thread_ids.append(tid)
        else:
            thread_ids.append(line)
    
    logger.info(f"Found {len(thread_ids)} threads to extract")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize scraper
    scraper_config = ScraperConfig(max_threads=args.parallel)
    scraper = ThreadScraper(config=scraper_config)
    
    # Authenticate
    creds = config.credentials
    scraper.authenticate(
        api_key=creds.api_key,
        api_secret=creds.api_secret,
        access_token=creds.access_token,
        access_secret=creds.access_secret,
        bearer_token=creds.bearer_token
    )
    
    # Extract threads
    threads = scraper.extract_threads_batch(thread_ids, parallel=True)
    
    # Save threads
    for thread in threads:
        output_path = output_dir / f"thread_{thread.thread_id}.json"
        with open(output_path, 'w') as f:
            json.dump(thread.to_dict(), f, indent=2, default=str)
    
    logger.info(f"Extracted {len(threads)} threads to {output_dir}")
    
    scraper.shutdown()


def cmd_validate(args: argparse.Namespace, config: IntegrationConfig):
    """Execute the validate command."""
    logger = get_logger("cli")
    
    logger.info("Validating configuration...")
    
    is_valid, errors = config.validate()
    
    if is_valid:
        logger.info("✓ Configuration is valid")
        print("\nConfiguration Summary:")
        print(json.dumps(config.to_dict(), indent=2))
    else:
        logger.error("✗ Configuration has errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.debug else ("INFO" if args.verbose else "WARNING")
    setup_logger(level=log_level)
    logger = get_logger("cli")
    
    # Load configuration
    if args.config:
        # Load from file (would need implementation)
        config = create_minimal_config()
    else:
        config = create_minimal_config()
    
    config.debug_mode = args.debug
    config.verbose_logging = args.verbose
    
    # Execute command
    if args.command == "extract":
        cmd_extract(args, config)
    elif args.command == "batch":
        cmd_batch(args, config)
    elif args.command == "validate":
        cmd_validate(args, config)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
