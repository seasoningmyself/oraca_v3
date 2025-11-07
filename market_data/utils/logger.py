"""
Centralized logging configuration for the Market Data module.
"""
import logging
import sys
from typing import Optional


def setup_logger(
    name: str,
    level: str = "INFO",
    log_format: Optional[str] = None
) -> logging.Logger:
    """
    Set up a logger with consistent formatting.

    Args:
        name: Logger name (usually __name__)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom log format string

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)

    # Set level
    logger.setLevel(getattr(logging, level.upper()))

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    # Set format
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    formatter = logging.Formatter(log_format)
    handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with default configuration.

    Args:
        name: Logger name (usually __name__)

    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(name)
