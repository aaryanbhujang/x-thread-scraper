"""
X Thread Scraper - Logging Module
=================================

Provides consistent logging across all scraper components.
Supports multiple output formats and log levels.

Features:
- Structured logging with JSON support
- Log rotation and archival
- Sensitive data filtering
- Performance metrics logging
"""

import logging
import sys
import json
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import threading


# Default log format
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
JSON_FORMAT = True

# Sensitive fields to redact
SENSITIVE_FIELDS = [
    "password",
    "secret",
    "token",
    "api_key",
    "access_token",
    "bearer",
    "authorization"
]


class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive information from log records."""
    
    def __init__(self, sensitive_fields: Optional[list] = None):
        super().__init__()
        self._sensitive_fields = sensitive_fields or SENSITIVE_FIELDS
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter the log record, redacting sensitive data."""
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for field in self._sensitive_fields:
                # Simple pattern matching for key=value pairs
                import re
                pattern = rf"({field}['\"]?\s*[:=]\s*['\"]?)([^'\"}\s]+)"
                record.msg = re.sub(
                    pattern, 
                    r"\1[REDACTED]", 
                    record.msg, 
                    flags=re.IGNORECASE
                )
        return True


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in [
                'name', 'msg', 'args', 'created', 'levelname', 'levelno',
                'pathname', 'filename', 'module', 'exc_info', 'exc_text',
                'stack_info', 'lineno', 'funcName', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'message'
            ]:
                log_obj[key] = value
        
        return json.dumps(log_obj, default=str)


class LoggerConfig:
    """Configuration for logger setup."""
    
    def __init__(
        self,
        name: str = "xscraper",
        level: int = logging.INFO,
        format_string: str = DEFAULT_FORMAT,
        use_json: bool = False,
        log_to_file: bool = False,
        log_file_path: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        filter_sensitive: bool = True
    ):
        self.name = name
        self.level = level
        self.format_string = format_string
        self.use_json = use_json
        self.log_to_file = log_to_file
        self.log_file_path = log_file_path or f"{name}.log"
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.filter_sensitive = filter_sensitive


class LoggerManager:
    """
    Manages logger instances and configuration.
    
    Thread-safe singleton pattern ensures consistent logging
    across all components.
    """
    
    _instance: Optional['LoggerManager'] = None
    _lock = threading.Lock()
    _loggers: Dict[str, logging.Logger] = {}
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._config: Optional[LoggerConfig] = None
        self._initialized = True
    
    def configure(self, config: LoggerConfig):
        """Apply logging configuration."""
        self._config = config
        
        # Configure root logger
        root_logger = logging.getLogger(config.name)
        root_logger.setLevel(config.level)
        
        # Remove existing handlers
        root_logger.handlers.clear()
        
        # Create formatter
        if config.use_json:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(config.format_string)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # File handler (if enabled)
        if config.log_to_file:
            file_handler = RotatingFileHandler(
                config.log_file_path,
                maxBytes=config.max_file_size,
                backupCount=config.backup_count
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        
        # Add sensitive data filter
        if config.filter_sensitive:
            sensitive_filter = SensitiveDataFilter()
            for handler in root_logger.handlers:
                handler.addFilter(sensitive_filter)
        
        self._loggers[config.name] = root_logger
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger with the given name."""
        if name not in self._loggers:
            base_name = self._config.name if self._config else "xscraper"
            full_name = f"{base_name}.{name}" if name != base_name else name
            
            logger = logging.getLogger(full_name)
            if self._config:
                logger.setLevel(self._config.level)
            
            self._loggers[name] = logger
        
        return self._loggers[name]


# Module-level functions for convenient access

_manager = LoggerManager()


def setup_logger(
    name: str = "xscraper",
    level: int = logging.INFO,
    use_json: bool = False,
    log_to_file: bool = False,
    log_file_path: Optional[str] = None
) -> logging.Logger:
    """
    Set up and configure the logging system.
    
    Args:
        name: Base logger name
        level: Logging level
        use_json: Use JSON formatted output
        log_to_file: Enable file logging
        log_file_path: Path for log file
    
    Returns:
        Configured logger instance
    """
    config = LoggerConfig(
        name=name,
        level=level,
        use_json=use_json,
        log_to_file=log_to_file,
        log_file_path=log_file_path
    )
    _manager.configure(config)
    return _manager.get_logger(name)


def get_logger(name: str = "xscraper") -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (will be prefixed with base name)
    
    Returns:
        Logger instance
    """
    return _manager.get_logger(name)


class LogContext:
    """
    Context manager for adding extra fields to log records.
    
    Usage:
        with LogContext(request_id="abc123", user="john"):
            logger.info("Processing request")
    """
    
    def __init__(self, **kwargs):
        self._extra = kwargs
        self._old_factory = None
    
    def __enter__(self):
        self._old_factory = logging.getLogRecordFactory()
        extra = self._extra
        
        def record_factory(*args, **kwargs):
            record = self._old_factory(*args, **kwargs)
            for key, value in extra.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self._old_factory)
        return False
