# X Thread Scraper

<div align="center">

![Version](https://img.shields.io/badge/version-2.4.1-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

**A professional-grade toolkit for extracting threaded conversations from X (formerly Twitter)**

[Installation](#installation) • [Quick Start](#quick-start) • [Configuration](#configuration) • [Examples](#examples) • [API Reference](#api-reference)

</div>

---

## ⚠️ IMPORTANT: Before You Begin

> **📌 CRITICAL STEP: You MUST read through [`src/xscraper/integration_config.py`](src/xscraper/integration_config.py) before attempting to use this toolkit.**
>
> This file contains essential configuration parameters, credential setup instructions, rate limit guidelines, and integration requirements. **Every comment in this file is important** for successful integration.
>
> Failure to properly configure these settings will result in authentication failures, rate limit violations, and potential account suspension.

---

## Features

- 🔐 **Multiple Authentication Methods** - OAuth 1.0a, OAuth 2.0, Bearer Token
- ⚡ **Intelligent Rate Limiting** - Adaptive rate limiting with exponential backoff
- 🔄 **Proxy Support** - Built-in proxy rotation with multiple strategies
- 💾 **Smart Caching** - Memory, file, and Redis caching backends
- 📊 **Rich Data Extraction** - Metrics, media, quotes, replies, and more
- 🎯 **Batch Processing** - Parallel extraction for multiple threads
- 📁 **Multiple Export Formats** - JSON, JSONL, CSV, Parquet, Markdown

## Installation

### Using pip

```bash
pip install x-thread-scraper
```

### From source

```bash
git clone https://github.com/xscraper/x-thread-scraper.git
cd x-thread-scraper
pip install -e .
```

### With optional dependencies

```bash
# For data export features
pip install x-thread-scraper[export]

# For caching features
pip install x-thread-scraper[cache]

# For development
pip install x-thread-scraper[dev]
```

## Quick Start

### 1. Read the Configuration Guide

**This is not optional.** Before writing any code, thoroughly read:

```
src/xscraper/integration_config.py
```

This file contains:
- API credential setup instructions
- Rate limit configurations per tier
- Proxy configuration options
- Data extraction settings
- Error handling options
- Output format configurations

### 2. Set Up Credentials

Set your credentials as environment variables:

```bash
# OAuth 1.0a (recommended for full access)
export X_API_KEY="your_api_key"
export X_API_SECRET="your_api_secret"
export X_ACCESS_TOKEN="your_access_token"
export X_ACCESS_SECRET="your_access_secret"

# OR use Bearer Token (for public data only)
export X_BEARER_TOKEN="your_bearer_token"
```

### 3. Extract Your First Thread

```python
from xscraper import ThreadScraper
from xscraper.integration_config import IntegrationConfig, APICredentials

# Create configuration (reads from environment variables)
config = IntegrationConfig(credentials=APICredentials())

# Validate configuration
is_valid, errors = config.validate()
if not is_valid:
    print("Configuration errors:", errors)
    exit(1)

# Initialize scraper
scraper = ThreadScraper()

# Authenticate
scraper.authenticate(
    api_key=config.credentials.api_key,
    api_secret=config.credentials.api_secret,
    access_token=config.credentials.access_token,
    access_secret=config.credentials.access_secret
)

# Extract a thread
thread = scraper.extract_thread(thread_url="https://x.com/user/status/1234567890")

# Output
print(thread.to_json())

# Cleanup
scraper.shutdown()
```

## Configuration

### Configuration Checklist

Before using the scraper, ensure you have:

- [ ] Read `src/xscraper/integration_config.py` completely
- [ ] Set up API credentials (environment variables recommended)
- [ ] Configured rate limits appropriate for your API tier
- [ ] Set up proxy rotation (if needed)
- [ ] Configured data extraction settings
- [ ] Set up output format and directory

### Configuration Templates

The toolkit provides pre-configured templates for common use cases:

```python
from xscraper.integration_config import (
    create_minimal_config,
    create_production_config,
    create_research_config
)

# For testing and learning
config = create_minimal_config()

# For production use
config = create_production_config()

# For academic research
config = create_research_config()
```

## API Reference

### ThreadScraper

The main scraper class for thread extraction.

```python
from xscraper import ThreadScraper

scraper = ThreadScraper(config=ScraperConfig(...))
```

#### Methods

| Method | Description |
|--------|-------------|
| `authenticate()` | Set up API authentication |
| `extract_thread()` | Extract a single thread |
| `extract_threads_batch()` | Extract multiple threads in parallel |
| `get_metrics()` | Get scraping statistics |
| `shutdown()` | Clean up resources |

### Data Models

```python
from xscraper.models import Thread, Tweet, Author

# Thread contains
thread.thread_id      # Unique identifier
thread.tweets         # List of Tweet objects
thread.author         # Author object
thread.total_tweets   # Number of tweets
thread.total_likes    # Aggregate likes
```

## Examples

See the `examples/` directory for complete examples:

- `basic_extraction.py` - Simple single thread extraction
- `advanced_batch.py` - Batch extraction with caching and export

## Project Structure

```
x-thread-scraper/
├── src/
│   └── xscraper/
│       ├── __init__.py
│       ├── integration_config.py    ⬅️ READ THIS FIRST!
│       ├── main.py
│       ├── core/
│       │   ├── scraper.py          # Main scraping engine
│       │   ├── authenticator.py    # OAuth handling
│       │   └── rate_limiter.py     # Rate limit management
│       ├── handlers/
│       │   ├── cache_handler.py    # Caching
│       │   ├── proxy_handler.py    # Proxy rotation
│       │   └── persistence_handler.py  # Data storage
│       ├── models/
│       │   └── thread.py           # Data models
│       └── utils/
│           ├── helpers.py          # Utility functions
│           └── logger.py           # Logging setup
├── examples/
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Rate Limits

The scraper respects X API rate limits. Current limits (as of API v2):

| Endpoint | Essential | Elevated | Academic |
|----------|-----------|----------|----------|
| Tweet lookup | 300/15min | 900/15min | 900/15min |
| User lookup | 300/15min | 900/15min | 900/15min |
| Search | 180/15min | 450/15min | 450/15min |

Configure your tier in `integration_config.py`.

## Troubleshooting

### Authentication Errors

1. Verify credentials are set correctly
2. Check that credentials are for the correct environment (sandbox vs production)
3. Ensure your app has the required permissions

### Rate Limit Errors

1. Reduce `requests_per_window` in configuration
2. Increase `safety_buffer_percent`
3. Enable caching to reduce redundant requests

### Thread Not Found

1. Verify the thread URL/ID is correct
2. Check if the account is protected
3. Ensure the thread hasn't been deleted

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## License

MIT License - see LICENSE file for details.

## Support

- Documentation: https://xscraper-docs.internal
- Issues: https://github.com/xscraper/x-thread-scraper/issues
- Email: support@xscraper.internal

---

<div align="center">

**Remember: Always read [`src/xscraper/integration_config.py`](src/xscraper/integration_config.py) before starting!**

</div>
