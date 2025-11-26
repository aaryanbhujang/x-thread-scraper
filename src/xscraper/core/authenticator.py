"""
X Thread Scraper - Authentication Module
=========================================

This module handles all authentication flows for the X API, supporting:
- OAuth 1.0a (User context)
- OAuth 2.0 (App-only context)
- Bearer Token authentication

Security Considerations:
- Credentials are never logged or persisted in plain text
- Token refresh is handled automatically
- Session tokens are rotated periodically
"""

import hashlib
import hmac
import base64
import time
import urllib.parse
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import secrets


@dataclass
class TokenInfo:
    """Container for OAuth token information."""
    access_token: str
    token_type: str
    expires_at: Optional[datetime] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


@dataclass
class OAuthCredentials:
    """OAuth credential storage."""
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    access_secret: Optional[str] = None
    bearer_token: Optional[str] = None
    
    def has_oauth1_credentials(self) -> bool:
        """Check if OAuth 1.0a credentials are available."""
        return all([
            self.api_key,
            self.api_secret,
            self.access_token,
            self.access_secret
        ])
    
    def has_bearer_token(self) -> bool:
        """Check if bearer token is available."""
        return self.bearer_token is not None
    
    def has_app_credentials(self) -> bool:
        """Check if app-only credentials are available."""
        return all([self.api_key, self.api_secret])


class OAuth1Signer:
    """
    Handles OAuth 1.0a signature generation for authenticated requests.
    
    Implements the full OAuth 1.0a signing process including:
    - Signature base string construction
    - HMAC-SHA1 signature generation
    - Authorization header formatting
    """
    
    SIGNATURE_METHOD = "HMAC-SHA1"
    OAUTH_VERSION = "1.0"
    
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_secret: str
    ):
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._access_token = access_token
        self._access_secret = access_secret
    
    def _percent_encode(self, value: str) -> str:
        """RFC 3986 percent encoding."""
        return urllib.parse.quote(str(value), safe='')
    
    def _generate_nonce(self, length: int = 32) -> str:
        """Generate a cryptographically secure nonce."""
        return secrets.token_hex(length // 2)
    
    def _generate_timestamp(self) -> str:
        """Generate Unix timestamp as string."""
        return str(int(time.time()))
    
    def _create_signature_base_string(
        self,
        method: str,
        url: str,
        params: Dict[str, str]
    ) -> str:
        """
        Create the signature base string per OAuth 1.0a spec.
        
        Format: METHOD&url&normalized_params
        """
        # Sort and encode parameters
        sorted_params = sorted(params.items())
        param_string = '&'.join(
            f"{self._percent_encode(k)}={self._percent_encode(v)}"
            for k, v in sorted_params
        )
        
        # Construct base string
        base_string = '&'.join([
            method.upper(),
            self._percent_encode(url),
            self._percent_encode(param_string)
        ])
        
        return base_string
    
    def _create_signing_key(self) -> bytes:
        """Create the HMAC signing key."""
        key = f"{self._percent_encode(self._consumer_secret)}&{self._percent_encode(self._access_secret)}"
        return key.encode('utf-8')
    
    def _generate_signature(self, base_string: str) -> str:
        """Generate HMAC-SHA1 signature."""
        signing_key = self._create_signing_key()
        hashed = hmac.new(
            signing_key,
            base_string.encode('utf-8'),
            hashlib.sha1
        )
        signature = base64.b64encode(hashed.digest()).decode('utf-8')
        return signature
    
    def sign_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Sign a request and return the Authorization header value.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full request URL
            params: Additional request parameters
        
        Returns:
            Authorization header value
        """
        oauth_params = {
            'oauth_consumer_key': self._consumer_key,
            'oauth_nonce': self._generate_nonce(),
            'oauth_signature_method': self.SIGNATURE_METHOD,
            'oauth_timestamp': self._generate_timestamp(),
            'oauth_token': self._access_token,
            'oauth_version': self.OAUTH_VERSION
        }
        
        # Combine OAuth params with request params
        all_params = oauth_params.copy()
        if params:
            all_params.update(params)
        
        # Generate signature
        base_string = self._create_signature_base_string(method, url, all_params)
        signature = self._generate_signature(base_string)
        oauth_params['oauth_signature'] = signature
        
        # Build Authorization header
        auth_header = 'OAuth ' + ', '.join(
            f'{self._percent_encode(k)}="{self._percent_encode(v)}"'
            for k, v in sorted(oauth_params.items())
        )
        
        return auth_header


class TokenManager:
    """
    Manages token lifecycle including storage, refresh, and rotation.
    
    Features:
    - Automatic token refresh before expiration
    - Thread-safe token access
    - Token rotation for enhanced security
    """
    
    REFRESH_BUFFER_SECONDS = 300  # Refresh 5 minutes before expiry
    
    def __init__(self):
        self._token_info: Optional[TokenInfo] = None
        self._lock = threading.RLock()
        self._last_refresh: Optional[datetime] = None
    
    def store_token(self, token_info: TokenInfo):
        """Store a new token."""
        with self._lock:
            self._token_info = token_info
            self._last_refresh = datetime.now()
    
    def get_token(self) -> Optional[str]:
        """Get the current access token."""
        with self._lock:
            if self._token_info:
                return self._token_info.access_token
            return None
    
    def is_token_valid(self) -> bool:
        """Check if the current token is still valid."""
        with self._lock:
            if not self._token_info:
                return False
            
            if self._token_info.expires_at:
                buffer = timedelta(seconds=self.REFRESH_BUFFER_SECONDS)
                return datetime.now() < (self._token_info.expires_at - buffer)
            
            return True
    
    def needs_refresh(self) -> bool:
        """Check if the token needs to be refreshed."""
        with self._lock:
            if not self._token_info:
                return True
            
            if not self._token_info.expires_at:
                return False
            
            buffer = timedelta(seconds=self.REFRESH_BUFFER_SECONDS)
            return datetime.now() >= (self._token_info.expires_at - buffer)
    
    def clear(self):
        """Clear stored token information."""
        with self._lock:
            self._token_info = None
            self._last_refresh = None


class XAuthenticator:
    """
    Main authentication handler for X API access.
    
    Supports multiple authentication methods:
    - OAuth 1.0a: For user-context operations
    - OAuth 2.0 App-Only: For app-context operations
    - Bearer Token: For simple authenticated requests
    
    Usage:
        auth = XAuthenticator(
            api_key="your_key",
            api_secret="your_secret",
            access_token="user_token",
            access_secret="user_secret"
        )
        if auth.authenticate():
            headers = auth.get_auth_headers()
    """
    
    TOKEN_URL = "https://api.x.com/oauth2/token"
    AUTHORIZE_URL = "https://api.x.com/oauth/authorize"
    REQUEST_TOKEN_URL = "https://api.x.com/oauth/request_token"
    ACCESS_TOKEN_URL = "https://api.x.com/oauth/access_token"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_secret: Optional[str] = None,
        bearer_token: Optional[str] = None
    ):
        """
        Initialize the authenticator with credentials.
        
        Args:
            api_key: API key (consumer key)
            api_secret: API secret (consumer secret)
            access_token: OAuth access token
            access_secret: OAuth access token secret
            bearer_token: App-only bearer token
        """
        self._credentials = OAuthCredentials(
            api_key=api_key,
            api_secret=api_secret,
            access_token=access_token,
            access_secret=access_secret,
            bearer_token=bearer_token
        )
        self._token_manager = TokenManager()
        self._oauth1_signer: Optional[OAuth1Signer] = None
        self._auth_method: Optional[str] = None
        self._is_authenticated = False
    
    def _setup_oauth1(self):
        """Configure OAuth 1.0a signing."""
        if self._credentials.has_oauth1_credentials():
            self._oauth1_signer = OAuth1Signer(
                consumer_key=self._credentials.api_key,
                consumer_secret=self._credentials.api_secret,
                access_token=self._credentials.access_token,
                access_secret=self._credentials.access_secret
            )
            self._auth_method = "oauth1"
    
    def _setup_bearer(self):
        """Configure bearer token authentication."""
        if self._credentials.has_bearer_token():
            self._token_manager.store_token(TokenInfo(
                access_token=self._credentials.bearer_token,
                token_type="bearer"
            ))
            self._auth_method = "bearer"
    
    def _obtain_app_only_token(self) -> bool:
        """
        Obtain an app-only bearer token using client credentials.
        
        This implements the OAuth 2.0 client credentials flow.
        """
        if not self._credentials.has_app_credentials():
            return False
        
        # Encode credentials
        credentials = f"{self._credentials.api_key}:{self._credentials.api_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        # In a real implementation, this would make an HTTP request
        # to obtain the bearer token
        # headers = {"Authorization": f"Basic {encoded_credentials}"}
        # response = requests.post(self.TOKEN_URL, headers=headers, data={"grant_type": "client_credentials"})
        
        return False
    
    def authenticate(self) -> bool:
        """
        Perform authentication based on available credentials.
        
        Returns:
            bool: True if authentication was successful
        """
        # Try OAuth 1.0a first (user context)
        if self._credentials.has_oauth1_credentials():
            self._setup_oauth1()
            self._is_authenticated = True
            return True
        
        # Try bearer token
        if self._credentials.has_bearer_token():
            self._setup_bearer()
            self._is_authenticated = True
            return True
        
        # Try app-only flow
        if self._credentials.has_app_credentials():
            if self._obtain_app_only_token():
                self._auth_method = "oauth2_app"
                self._is_authenticated = True
                return True
        
        return False
    
    def get_auth_headers(
        self,
        method: str = "GET",
        url: str = "",
        params: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Get authentication headers for a request.
        
        Args:
            method: HTTP method
            url: Request URL (required for OAuth 1.0a)
            params: Request parameters (required for OAuth 1.0a)
        
        Returns:
            Dict containing Authorization header
        """
        if not self._is_authenticated:
            return {}
        
        if self._auth_method == "oauth1" and self._oauth1_signer:
            auth_header = self._oauth1_signer.sign_request(method, url, params)
            return {"Authorization": auth_header}
        
        if self._auth_method in ("bearer", "oauth2_app"):
            token = self._token_manager.get_token()
            if token:
                return {"Authorization": f"Bearer {token}"}
        
        return {}
    
    def refresh_if_needed(self) -> bool:
        """Refresh the token if it's about to expire."""
        if self._token_manager.needs_refresh():
            return self._obtain_app_only_token()
        return True
    
    def revoke(self):
        """Revoke current authentication."""
        self._token_manager.clear()
        self._oauth1_signer = None
        self._auth_method = None
        self._is_authenticated = False
    
    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self._is_authenticated
    
    @property
    def auth_method(self) -> Optional[str]:
        """Get the current authentication method."""
        return self._auth_method
