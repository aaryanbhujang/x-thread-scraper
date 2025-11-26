"""
================================================================================
                    X THREAD SCRAPER - INTEGRATION CONFIGURATION
================================================================================

                              ⚠️  IMPORTANT  ⚠️
                              
    This file contains CRITICAL configuration parameters required for the 
    X Thread Scraper to function correctly. READ EVERY COMMENT CAREFULLY
    before attempting to use this toolkit.
    
    Failure to properly configure these settings will result in:
    - Authentication failures
    - Rate limit violations  
    - Data extraction errors
    - Account suspension risk
    
    Last Updated: 2024-01-15
    Configuration Version: 3.2.1
    
================================================================================

QUICK START CHECKLIST:
    □ Read Section 1: API Credentials Setup
    □ Read Section 2: Rate Limit Configuration
    □ Read Section 3: Proxy Configuration (if applicable)
    □ Read Section 4: Data Extraction Settings
    □ Read Section 5: Error Handling Options
    □ Read Section 6: Output Configuration
    □ Verify all required fields are populated
    □ Test with a single thread before batch operations

================================================================================
"""

# ==============================================================================
# SECTION 1: API CREDENTIALS CONFIGURATION
# ==============================================================================
#
# X (formerly Twitter) requires authenticated API access for thread extraction.
# You must obtain credentials from the X Developer Portal:
# https://developer.x.com/en/portal/dashboard
#
# CREDENTIAL TYPES:
#
#   1. OAuth 1.0a (User Context) - Required for accessing user-specific data
#      - Provides: api_key, api_secret, access_token, access_secret
#      - Use when: Scraping threads with user permission
#      - Rate limits: Higher (900 requests/15min)
#
#   2. OAuth 2.0 App-Only - For public data only
#      - Provides: bearer_token
#      - Use when: Scraping public threads only
#      - Rate limits: Lower (300 requests/15min)
#
#   3. OAuth 2.0 with PKCE - For user-authorized applications
#      - Provides: client_id, client_secret, refresh_token
#      - Use when: Building user-facing applications
#
# ⚠️  SECURITY WARNING:
#     NEVER commit credentials to version control!
#     Use environment variables or a secure secrets manager.
#
# To set credentials via environment variables:
#     export X_API_KEY="your_api_key_here"
#     export X_API_SECRET="your_api_secret_here"
#     export X_ACCESS_TOKEN="your_access_token_here"
#     export X_ACCESS_SECRET="your_access_secret_here"
#     export X_BEARER_TOKEN="your_bearer_token_here"
#

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from pathlib import Path


class AuthMethod(Enum):
    """
    Authentication method to use with X API.
    
    Choose based on your access tier and use case:
    - OAUTH1: Full user context, highest rate limits
    - BEARER: App-only, lower rate limits but simpler
    - OAUTH2_PKCE: For user-authorized apps with token refresh
    """
    OAUTH1 = "oauth1"
    BEARER = "bearer"
    OAUTH2_PKCE = "oauth2_pkce"


@dataclass
class APICredentials:
    """
    Container for X API credentials.
    
    ⚠️  IMPORTANT: Do not hardcode credentials!
    
    Recommended approaches:
    1. Environment variables (shown below)
    2. AWS Secrets Manager
    3. HashiCorp Vault
    4. Encrypted configuration file
    
    Example with environment variables:
        credentials = APICredentials(
            api_key=os.getenv("X_API_KEY"),
            api_secret=os.getenv("X_API_SECRET"),
            access_token=os.getenv("X_ACCESS_TOKEN"),
            access_secret=os.getenv("X_ACCESS_SECRET")
        )
    """
    # OAuth 1.0a credentials (User Context)
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("X_API_KEY"))
    api_secret: Optional[str] = field(default_factory=lambda: os.getenv("X_API_SECRET"))
    access_token: Optional[str] = field(default_factory=lambda: os.getenv("X_ACCESS_TOKEN"))
    access_secret: Optional[str] = field(default_factory=lambda: os.getenv("X_ACCESS_SECRET"))
    
    # App-Only Bearer Token
    bearer_token: Optional[str] = field(default_factory=lambda: os.getenv("X_BEARER_TOKEN"))
    
    # OAuth 2.0 PKCE credentials
    client_id: Optional[str] = field(default_factory=lambda: os.getenv("X_CLIENT_ID"))
    client_secret: Optional[str] = field(default_factory=lambda: os.getenv("X_CLIENT_SECRET"))
    
    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate that required credentials are present.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        has_oauth1 = all([self.api_key, self.api_secret, 
                         self.access_token, self.access_secret])
        has_bearer = bool(self.bearer_token)
        has_oauth2 = all([self.client_id, self.client_secret])
        
        if not (has_oauth1 or has_bearer or has_oauth2):
            errors.append(
                "No valid credentials found. Provide either OAuth 1.0a credentials "
                "(api_key, api_secret, access_token, access_secret), a bearer_token, "
                "or OAuth 2.0 credentials (client_id, client_secret)."
            )
        
        return len(errors) == 0, errors


# ==============================================================================
# SECTION 2: RATE LIMIT CONFIGURATION
# ==============================================================================
#
# X API enforces strict rate limits. Exceeding these limits will result in
# temporary blocks (15 minutes to 24 hours) or permanent suspension.
#
# CURRENT RATE LIMITS (as of API v2):
#
# ┌─────────────────────────┬─────────────┬─────────────┬─────────────┐
# │ Endpoint                │ Essential   │ Elevated    │ Academic    │
# ├─────────────────────────┼─────────────┼─────────────┼─────────────┤
# │ Tweet lookup            │ 300/15min   │ 900/15min   │ 900/15min   │
# │ User lookup             │ 300/15min   │ 900/15min   │ 900/15min   │
# │ Search (recent)         │ 180/15min   │ 450/15min   │ 450/15min   │
# │ Search (full archive)   │ N/A         │ N/A         │ 300/15min   │
# │ User timeline           │ 1500/15min  │ 1500/15min  │ 1500/15min  │
# └─────────────────────────┴─────────────┴─────────────┴─────────────┘
#
# RECOMMENDATIONS:
# - Start with conservative limits and increase gradually
# - Implement exponential backoff on rate limit errors
# - Monitor rate limit headers in responses
# - Use caching to avoid redundant requests
#

class AccessTier(Enum):
    """
    X API access tier determines rate limits.
    
    Apply for higher tiers at: https://developer.x.com/en/products/twitter-api
    """
    ESSENTIAL = "essential"      # Free tier, limited access
    ELEVATED = "elevated"        # Requires application, higher limits
    ACADEMIC = "academic"        # Research access, full archive
    ENTERPRISE = "enterprise"    # Highest limits, dedicated support


@dataclass
class RateLimitSettings:
    """
    Rate limiting configuration.
    
    ⚠️  CRITICAL: Set these values according to your API access tier!
    
    Using limits higher than your tier allows WILL result in account suspension.
    
    Safety Buffer:
        The safety_buffer_percent reserves a portion of your rate limit
        to handle unexpected spikes. Recommended: 10-20%
    
    Example for Essential tier:
        settings = RateLimitSettings(
            tier=AccessTier.ESSENTIAL,
            tweets_per_window=270,      # 300 limit - 10% buffer
            users_per_window=270,
            searches_per_window=160,    # 180 limit - 10% buffer
            safety_buffer_percent=10
        )
    """
    tier: AccessTier = AccessTier.ESSENTIAL
    
    # Requests per 15-minute window
    tweets_per_window: int = 270          # Default: Essential tier with buffer
    users_per_window: int = 270
    searches_per_window: int = 160
    timeline_per_window: int = 1350
    
    # Safety settings
    safety_buffer_percent: int = 10       # Reserve 10% of limit
    
    # Backoff settings (seconds)
    initial_backoff: float = 1.0          # Start with 1 second
    max_backoff: float = 300.0            # Cap at 5 minutes
    backoff_multiplier: float = 2.0       # Double each time
    
    # Concurrency
    max_concurrent_requests: int = 5      # Parallel request limit
    
    # Window settings
    window_duration_seconds: int = 900    # 15 minutes


# ==============================================================================
# SECTION 3: PROXY CONFIGURATION
# ==============================================================================
#
# Proxy usage is OPTIONAL but recommended for:
# - Distributed scraping across multiple IPs
# - Bypassing geographic restrictions
# - Reducing risk of IP-based rate limiting
#
# ⚠️  WARNING:
#     Using proxies may violate X's Terms of Service.
#     Use at your own risk.
#     
#     Residential proxies are less likely to be detected.
#     Datacenter proxies may be blocked quickly.
#
# PROXY FORMAT:
#     http://username:password@host:port
#     socks5://username:password@host:port
#

@dataclass 
class ProxySettings:
    """
    Proxy configuration for distributed requests.
    
    ⚠️  NOTE: Proxy usage may violate X Terms of Service.
    
    Recommended proxy providers (not endorsements):
    - Bright Data (residential)
    - Oxylabs (datacenter/residential)
    - SmartProxy (rotating residential)
    
    Example configuration:
        proxy_settings = ProxySettings(
            enabled=True,
            proxy_list=[
                "http://user:pass@proxy1.example.com:8080",
                "http://user:pass@proxy2.example.com:8080",
            ],
            rotation_strategy="round_robin",
            test_before_use=True
        )
    """
    enabled: bool = False
    
    # List of proxy URLs
    proxy_list: List[str] = field(default_factory=list)
    
    # Rotation strategy: round_robin, random, least_used, performance
    rotation_strategy: str = "round_robin"
    
    # Test proxy connectivity before use
    test_before_use: bool = True
    
    # Maximum failures before removing proxy
    max_failures: int = 5
    
    # Timeout for proxy connections (seconds)
    connection_timeout: int = 30
    
    # Geographic targeting (ISO country codes)
    preferred_countries: List[str] = field(default_factory=list)


# ==============================================================================
# SECTION 4: DATA EXTRACTION SETTINGS
# ==============================================================================
#
# Configure what data to extract from threads.
#
# AVAILABLE FIELDS:
# - Tweet text and metadata
# - Author information
# - Engagement metrics (likes, retweets, replies)
# - Media attachments (images, videos, GIFs)
# - Quoted tweets and references
# - Hashtags and mentions
# - URLs and cards
#
# ⚠️  NOTE: Some fields require elevated access or specific permissions.
#

@dataclass
class ExtractionSettings:
    """
    Data extraction configuration.
    
    Customize what data is extracted from threads.
    
    Example for full extraction:
        settings = ExtractionSettings(
            include_metrics=True,
            include_media=True,
            include_quoted_tweets=True,
            include_replies=False,        # Requires more API calls
            max_thread_depth=100,
            extract_user_details=True
        )
    
    Example for minimal extraction (faster):
        settings = ExtractionSettings(
            include_metrics=False,
            include_media=False,
            include_quoted_tweets=False,
            include_replies=False,
            max_thread_depth=50,
            extract_user_details=False
        )
    """
    # Content extraction
    include_metrics: bool = True          # Likes, retweets, etc.
    include_media: bool = True            # Images, videos, GIFs
    include_quoted_tweets: bool = True    # Embedded quotes
    include_replies: bool = False         # Reply chain (expensive!)
    include_cards: bool = True            # URL previews
    
    # Thread depth
    max_thread_depth: int = 100           # Max tweets per thread
    
    # User data
    extract_user_details: bool = True     # Full user profiles
    
    # Text processing
    clean_text: bool = True               # Remove extra whitespace
    expand_urls: bool = True              # Resolve t.co links
    
    # Media download
    download_media: bool = False          # Download media files locally
    media_download_path: str = "./media"  # Where to save media


# ==============================================================================
# SECTION 5: ERROR HANDLING SETTINGS
# ==============================================================================
#
# Configure how the scraper handles errors and failures.
#
# ERROR TYPES:
# - Rate limit errors (429): Automatic backoff and retry
# - Authentication errors (401/403): Check credentials
# - Not found (404): Skip and continue
# - Server errors (5xx): Retry with backoff
# - Network errors: Retry with backoff
#

@dataclass
class ErrorHandlingSettings:
    """
    Error handling and retry configuration.
    
    Recommended settings for production:
        settings = ErrorHandlingSettings(
            max_retries=5,
            retry_on_rate_limit=True,
            retry_on_server_error=True,
            skip_on_not_found=True,
            log_errors=True,
            raise_on_auth_error=True
        )
    """
    # Retry settings
    max_retries: int = 3                  # Max retry attempts
    retry_on_rate_limit: bool = True      # Auto-retry on 429
    retry_on_server_error: bool = True    # Auto-retry on 5xx
    retry_on_network_error: bool = True   # Auto-retry on connection errors
    
    # Skip/continue settings
    skip_on_not_found: bool = True        # Continue if tweet deleted
    skip_on_protected: bool = True        # Skip protected accounts
    
    # Error reporting
    log_errors: bool = True               # Log all errors
    log_level: str = "WARNING"            # ERROR, WARNING, INFO, DEBUG
    
    # Fatal errors
    raise_on_auth_error: bool = True      # Stop on auth failure
    raise_on_permanent_error: bool = False # Stop on unrecoverable errors


# ==============================================================================
# SECTION 6: OUTPUT CONFIGURATION
# ==============================================================================
#
# Configure how extracted data is stored and exported.
#
# SUPPORTED FORMATS:
# - JSON: Full fidelity, nested structure
# - JSONL: One object per line, streaming-friendly
# - CSV: Tabular format, flattened structure
# - SQLite: Local database storage
# - Parquet: Columnar format for analytics
#

class OutputFormat(Enum):
    """Output format for extracted data."""
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    SQLITE = "sqlite"
    PARQUET = "parquet"


@dataclass
class OutputSettings:
    """
    Output and storage configuration.
    
    Example for JSON output:
        settings = OutputSettings(
            format=OutputFormat.JSON,
            output_directory="./output",
            pretty_print=True,
            include_metadata=True
        )
    
    Example for database storage:
        settings = OutputSettings(
            format=OutputFormat.SQLITE,
            output_directory="./data",
            database_name="threads.db"
        )
    """
    # Output format
    format: OutputFormat = OutputFormat.JSON
    
    # Directory settings
    output_directory: str = "./output"
    create_directories: bool = True
    
    # File naming
    filename_template: str = "thread_{thread_id}_{timestamp}"
    
    # JSON settings
    pretty_print: bool = True
    indent: int = 2
    
    # Metadata
    include_metadata: bool = True         # Add scrape timestamp, version, etc.
    include_raw_response: bool = False    # Include raw API response
    
    # Database settings (for SQLite/Parquet)
    database_name: str = "threads.db"
    table_name: str = "threads"
    
    # Compression
    compress_output: bool = False
    compression_format: str = "gzip"      # gzip, bz2, lz4


# ==============================================================================
# SECTION 7: MASTER CONFIGURATION
# ==============================================================================
#
# This is the main configuration class that combines all settings.
# Use this class to instantiate the scraper with your desired configuration.
#

@dataclass
class IntegrationConfig:
    """
    Master configuration for X Thread Scraper.
    
    ⚠️  COMPLETE CONFIGURATION CHECKLIST:
    
    1. API Credentials
       □ Set API key and secret (OAuth 1.0a) OR
       □ Set bearer token (App-Only)
       □ Verify credentials are not hardcoded
    
    2. Rate Limits
       □ Set appropriate tier
       □ Configure safety buffer
       □ Enable backoff settings
    
    3. Proxy (Optional)
       □ Add proxy URLs if needed
       □ Configure rotation strategy
    
    4. Extraction
       □ Select required fields
       □ Set appropriate depth limit
    
    5. Error Handling
       □ Configure retry behavior
       □ Set logging level
    
    6. Output
       □ Choose output format
       □ Set output directory
    
    EXAMPLE USAGE:
    
        from xscraper import ThreadScraper
        from xscraper.integration_config import IntegrationConfig
        
        # Create configuration
        config = IntegrationConfig(
            credentials=APICredentials(),  # Uses env vars
            rate_limits=RateLimitSettings(tier=AccessTier.ESSENTIAL),
            extraction=ExtractionSettings(include_media=True),
            output=OutputSettings(format=OutputFormat.JSON)
        )
        
        # Validate configuration
        is_valid, errors = config.validate()
        if not is_valid:
            for error in errors:
                print(f"Config error: {error}")
            exit(1)
        
        # Initialize scraper
        scraper = ThreadScraper(integration_config=config)
        
        # Extract a thread
        thread = scraper.extract_thread("1234567890")
    """
    # Sub-configurations
    credentials: APICredentials = field(default_factory=APICredentials)
    rate_limits: RateLimitSettings = field(default_factory=RateLimitSettings)
    proxy: ProxySettings = field(default_factory=ProxySettings)
    extraction: ExtractionSettings = field(default_factory=ExtractionSettings)
    error_handling: ErrorHandlingSettings = field(default_factory=ErrorHandlingSettings)
    output: OutputSettings = field(default_factory=OutputSettings)
    
    # Global settings
    debug_mode: bool = False
    verbose_logging: bool = False
    dry_run: bool = False                 # Validate without making requests
    
    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate the complete configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        all_errors = []
        
        # Validate credentials
        is_valid, errors = self.credentials.validate()
        all_errors.extend(errors)
        
        # Validate rate limits
        if self.rate_limits.tweets_per_window <= 0:
            all_errors.append("tweets_per_window must be positive")
        
        # Validate proxy if enabled
        if self.proxy.enabled and not self.proxy.proxy_list:
            all_errors.append("Proxy enabled but no proxies configured")
        
        # Validate output directory
        output_path = Path(self.output.output_directory)
        if not output_path.exists() and not self.output.create_directories:
            all_errors.append(f"Output directory does not exist: {output_path}")
        
        return len(all_errors) == 0, all_errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding sensitive data)."""
        return {
            "rate_limits": {
                "tier": self.rate_limits.tier.value,
                "tweets_per_window": self.rate_limits.tweets_per_window,
                "safety_buffer_percent": self.rate_limits.safety_buffer_percent
            },
            "proxy": {
                "enabled": self.proxy.enabled,
                "proxy_count": len(self.proxy.proxy_list),
                "rotation_strategy": self.proxy.rotation_strategy
            },
            "extraction": {
                "include_metrics": self.extraction.include_metrics,
                "include_media": self.extraction.include_media,
                "max_thread_depth": self.extraction.max_thread_depth
            },
            "output": {
                "format": self.output.format.value,
                "directory": self.output.output_directory
            },
            "debug_mode": self.debug_mode,
            "verbose_logging": self.verbose_logging
        }


# ==============================================================================
# QUICK START TEMPLATES
# ==============================================================================
#
# Pre-configured templates for common use cases.
#


def create_minimal_config() -> IntegrationConfig:
    """
    Create minimal configuration for simple use cases.
    
    Use this when:
    - Testing the scraper
    - Extracting a few threads
    - Learning the API
    """
    return IntegrationConfig(
        extraction=ExtractionSettings(
            include_metrics=False,
            include_media=False,
            include_quoted_tweets=False,
            max_thread_depth=50
        ),
        output=OutputSettings(
            format=OutputFormat.JSON,
            pretty_print=True
        )
    )


def create_production_config() -> IntegrationConfig:
    """
    Create configuration for production use.
    
    Use this when:
    - Running in production environment
    - Processing many threads
    - Reliability is important
    """
    return IntegrationConfig(
        rate_limits=RateLimitSettings(
            safety_buffer_percent=20,
            max_concurrent_requests=3
        ),
        extraction=ExtractionSettings(
            include_metrics=True,
            include_media=True,
            include_quoted_tweets=True,
            max_thread_depth=100
        ),
        error_handling=ErrorHandlingSettings(
            max_retries=5,
            log_errors=True,
            log_level="INFO"
        ),
        output=OutputSettings(
            format=OutputFormat.JSONL,
            include_metadata=True,
            compress_output=True
        )
    )


def create_research_config() -> IntegrationConfig:
    """
    Create configuration for research/academic use.
    
    Use this when:
    - Conducting academic research
    - Need full data extraction
    - Have elevated/academic API access
    """
    return IntegrationConfig(
        rate_limits=RateLimitSettings(
            tier=AccessTier.ACADEMIC,
            tweets_per_window=810,  # 900 with 10% buffer
            searches_per_window=405
        ),
        extraction=ExtractionSettings(
            include_metrics=True,
            include_media=True,
            include_quoted_tweets=True,
            include_replies=True,
            extract_user_details=True,
            max_thread_depth=200
        ),
        output=OutputSettings(
            format=OutputFormat.PARQUET,
            include_metadata=True,
            include_raw_response=True
        )
    )


# ==============================================================================
# END OF CONFIGURATION
# ==============================================================================
#
# For support and documentation:
# - GitHub Issues: https://github.com/xscraper/x-thread-scraper/issues
# - Documentation: https://xscraper-docs.internal
# - Email: support@xscraper.internal
#
# Remember: Always respect X's Terms of Service and rate limits.
#
# ================================================================================
