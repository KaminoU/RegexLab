"""
Logger module for RegexLab.

Provides configurable logging with settings-based log levels.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from .constants import DEFAULT_LOG_LEVEL
from .settings_manager import SettingsManager


class LogLevel(IntEnum):
    """Log levels for filtering messages."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40


class Logger:
    """
    Centralized logger for RegexLab plugin.

    Reads log level from settings and provides formatted logging.
    All logs are prefixed with [RegexLab] for easy filtering.

    Log levels (from most to least verbose):
    - DEBUG: Detailed diagnostic information
    - INFO: General informational messages
    - WARNING: Warning messages
    - ERROR: Error messages
    """

    def __init__(self, settings_manager: SettingsManager | None = None) -> None:
        """
        Initialize logger.

        Args:
            settings_manager: Optional settings manager instance.
        """
        self.settings = settings_manager or SettingsManager.get_instance()

    def get_log_level(self) -> LogLevel:
        """
        Get the current log level from settings.

        Returns:
            The configured log level (defaults to INFO).
        """
        level_str = self.settings.get("log_level", DEFAULT_LOG_LEVEL).upper()

        # Map string to LogLevel
        level_map = {
            "DEBUG": LogLevel.DEBUG,
            "INFO": LogLevel.INFO,
            "WARNING": LogLevel.WARNING,
            "ERROR": LogLevel.ERROR,
        }

        return level_map.get(level_str, LogLevel.INFO)

    def _should_log(self, level: LogLevel) -> bool:
        """
        Check if a message at the given level should be logged.

        Args:
            level: The log level of the message.

        Returns:
            True if the message should be logged, False otherwise.
        """
        return level >= self.get_log_level()

    def debug(self, message: str, *args: Any) -> None:
        """
        Log a debug message (only if log level <= DEBUG).

        Args:
            message: Message to log (supports % format placeholders like %s, %d).
            *args: Arguments for string formatting.
        """
        if self._should_log(LogLevel.DEBUG):
            formatted = message % args if args else message
            print(f"[RegexLab:DEBUG] {formatted}")

    def info(self, message: str, *args: Any) -> None:
        """
        Log an info message (only if log level <= INFO).

        Args:
            message: Message to log (supports % format placeholders like %s, %d).
            *args: Arguments for string formatting.
        """
        if self._should_log(LogLevel.INFO):
            formatted = message % args if args else message
            print(f"[RegexLab] {formatted}")

    def warning(self, message: str, *args: Any) -> None:
        """
        Log a warning message (only if log level <= WARNING).

        Args:
            message: Message to log (supports % format placeholders like %s, %d).
            *args: Arguments for string formatting.
        """
        if self._should_log(LogLevel.WARNING):
            formatted = message % args if args else message
            print(f"[RegexLab:WARNING] {formatted}")

    def error(self, message: str, *args: Any) -> None:
        """
        Log an error message (always shown).

        Args:
            message: Message to log (supports % format placeholders like %s, %d).
            *args: Arguments for string formatting.
        """
        if self._should_log(LogLevel.ERROR):
            formatted = message % args if args else message
            print(f"[RegexLab:ERROR] {formatted}")


# Global logger instance
_logger_instance: Logger | None = None


def get_logger() -> Logger:
    """
    Get the global logger instance.

    Returns:
        The global Logger instance.
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = Logger()
    return _logger_instance


def set_logger(logger: Logger) -> None:
    """
    Set the global logger instance (for testing).

    Args:
        logger: Logger instance to use globally.
    """
    global _logger_instance
    _logger_instance = logger
