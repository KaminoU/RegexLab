"""
Unit tests for Logger module.

Tests cover:
- Logger initialization
- Log level configuration
- Log level filtering
- Message formatting
- Global logger instance management
"""

from io import StringIO
from unittest.mock import MagicMock, patch

from src.core.logger import Logger, LogLevel, get_logger, set_logger
from src.core.settings_manager import SettingsManager


class TestLogLevel:
    """Test LogLevel enum."""

    def test_log_level_values(self) -> None:
        """Test LogLevel enum values are correctly ordered."""
        assert LogLevel.DEBUG == 10
        assert LogLevel.INFO == 20
        assert LogLevel.WARNING == 30
        assert LogLevel.ERROR == 40

    def test_log_level_ordering(self) -> None:
        """Test LogLevel comparison operators work correctly."""
        assert LogLevel.DEBUG < LogLevel.INFO
        assert LogLevel.INFO < LogLevel.WARNING
        assert LogLevel.WARNING < LogLevel.ERROR
        assert LogLevel.ERROR >= LogLevel.WARNING


class TestLoggerInit:
    """Test Logger initialization."""

    def test_init_default_settings_manager(self) -> None:
        """Test initialization with default settings manager."""
        logger = Logger()
        assert logger.settings is not None
        assert isinstance(logger.settings, SettingsManager)

    def test_init_custom_settings_manager(self) -> None:
        """Test initialization with custom settings manager."""
        settings = SettingsManager()
        logger = Logger(settings_manager=settings)
        assert logger.settings is settings


class TestLoggerGetLogLevel:
    """Test Logger.get_log_level() method."""

    def test_get_log_level_debug(self) -> None:
        """Test getting DEBUG log level from settings."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "DEBUG"
        logger = Logger(settings_manager=settings)

        assert logger.get_log_level() == LogLevel.DEBUG

    def test_get_log_level_info(self) -> None:
        """Test getting INFO log level from settings."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "INFO"
        logger = Logger(settings_manager=settings)

        assert logger.get_log_level() == LogLevel.INFO

    def test_get_log_level_warning(self) -> None:
        """Test getting WARNING log level from settings."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "WARNING"
        logger = Logger(settings_manager=settings)

        assert logger.get_log_level() == LogLevel.WARNING

    def test_get_log_level_error(self) -> None:
        """Test getting ERROR log level from settings."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "ERROR"
        logger = Logger(settings_manager=settings)

        assert logger.get_log_level() == LogLevel.ERROR

    def test_get_log_level_case_insensitive(self) -> None:
        """Test log level is case-insensitive."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "debug"
        logger = Logger(settings_manager=settings)

        assert logger.get_log_level() == LogLevel.DEBUG

    def test_get_log_level_invalid_defaults_to_info(self) -> None:
        """Test invalid log level defaults to INFO."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "INVALID"
        logger = Logger(settings_manager=settings)

        assert logger.get_log_level() == LogLevel.INFO

    def test_get_log_level_missing_defaults_to_info(self) -> None:
        """Test missing log level defaults to INFO."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "INFO"  # Default from get()
        logger = Logger(settings_manager=settings)

        assert logger.get_log_level() == LogLevel.INFO


class TestLoggerShouldLog:
    """Test Logger._should_log() filtering logic."""

    def test_should_log_debug_when_level_debug(self) -> None:
        """Test DEBUG messages logged when level is DEBUG."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "DEBUG"
        logger = Logger(settings_manager=settings)

        assert logger._should_log(LogLevel.DEBUG) is True
        assert logger._should_log(LogLevel.INFO) is True
        assert logger._should_log(LogLevel.WARNING) is True
        assert logger._should_log(LogLevel.ERROR) is True

    def test_should_log_info_when_level_info(self) -> None:
        """Test INFO messages logged when level is INFO."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "INFO"
        logger = Logger(settings_manager=settings)

        assert logger._should_log(LogLevel.DEBUG) is False
        assert logger._should_log(LogLevel.INFO) is True
        assert logger._should_log(LogLevel.WARNING) is True
        assert logger._should_log(LogLevel.ERROR) is True

    def test_should_log_warning_when_level_warning(self) -> None:
        """Test WARNING messages logged when level is WARNING."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "WARNING"
        logger = Logger(settings_manager=settings)

        assert logger._should_log(LogLevel.DEBUG) is False
        assert logger._should_log(LogLevel.INFO) is False
        assert logger._should_log(LogLevel.WARNING) is True
        assert logger._should_log(LogLevel.ERROR) is True

    def test_should_log_error_when_level_error(self) -> None:
        """Test ERROR messages logged when level is ERROR."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "ERROR"
        logger = Logger(settings_manager=settings)

        assert logger._should_log(LogLevel.DEBUG) is False
        assert logger._should_log(LogLevel.INFO) is False
        assert logger._should_log(LogLevel.WARNING) is False
        assert logger._should_log(LogLevel.ERROR) is True


class TestLoggerDebug:
    """Test Logger.debug() method."""

    def test_debug_logs_when_level_debug(self) -> None:
        """Test debug() logs messages when log level is DEBUG."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "DEBUG"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.debug("Test debug message")
            output = mock_stdout.getvalue()

        assert "[RegexLab:DEBUG] Test debug message" in output

    def test_debug_not_logged_when_level_info(self) -> None:
        """Test debug() does not log when log level is INFO."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "INFO"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.debug("Test debug message")
            output = mock_stdout.getvalue()

        assert output == ""

    def test_debug_with_format_args(self) -> None:
        """Test debug() with format arguments."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "DEBUG"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.debug("Value is %s", 42)
            output = mock_stdout.getvalue()

        assert "[RegexLab:DEBUG] Value is 42" in output

    def test_debug_with_multiple_format_args(self) -> None:
        """Test debug() with multiple format arguments."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "DEBUG"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.debug("Values: %s and %s", "foo", "bar")
            output = mock_stdout.getvalue()

        assert "[RegexLab:DEBUG] Values: foo and bar" in output


class TestLoggerInfo:
    """Test Logger.info() method."""

    def test_info_logs_when_level_info(self) -> None:
        """Test info() logs messages when log level is INFO."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "INFO"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.info("Test info message")
            output = mock_stdout.getvalue()

        assert "[RegexLab] Test info message" in output

    def test_info_not_logged_when_level_warning(self) -> None:
        """Test info() does not log when log level is WARNING."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "WARNING"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.info("Test info message")
            output = mock_stdout.getvalue()

        assert output == ""

    def test_info_with_format_args(self) -> None:
        """Test info() with format arguments."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "INFO"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.info("Pattern: %s", "email")
            output = mock_stdout.getvalue()

        assert "[RegexLab] Pattern: email" in output


class TestLoggerWarning:
    """Test Logger.warning() method."""

    def test_warning_logs_when_level_warning(self) -> None:
        """Test warning() logs messages when log level is WARNING."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "WARNING"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.warning("Test warning message")
            output = mock_stdout.getvalue()

        assert "[RegexLab:WARNING] Test warning message" in output

    def test_warning_not_logged_when_level_error(self) -> None:
        """Test warning() does not log when log level is ERROR."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "ERROR"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.warning("Test warning message")
            output = mock_stdout.getvalue()

        assert output == ""

    def test_warning_with_format_args(self) -> None:
        """Test warning() with format arguments."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "WARNING"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.warning("Variable %s not found", "DATE")
            output = mock_stdout.getvalue()

        assert "[RegexLab:WARNING] Variable DATE not found" in output


class TestLoggerError:
    """Test Logger.error() method."""

    def test_error_always_logs(self) -> None:
        """Test error() always logs regardless of log level."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "ERROR"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.error("Test error message")
            output = mock_stdout.getvalue()

        assert "[RegexLab:ERROR] Test error message" in output

    def test_error_with_format_args(self) -> None:
        """Test error() with format arguments."""
        settings = MagicMock(spec=SettingsManager)
        settings.get.return_value = "ERROR"
        logger = Logger(settings_manager=settings)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            logger.error("Failed to load: %s", "pattern.json")
            output = mock_stdout.getvalue()

        assert "[RegexLab:ERROR] Failed to load: pattern.json" in output


class TestGlobalLogger:
    """Test global logger instance management."""

    def test_get_logger_returns_singleton(self) -> None:
        """Test get_logger() returns the same instance."""
        logger1 = get_logger()
        logger2 = get_logger()

        assert logger1 is logger2

    def test_set_logger_changes_global_instance(self) -> None:
        """Test set_logger() changes the global logger instance."""
        # Create custom logger
        settings = MagicMock(spec=SettingsManager)
        custom_logger = Logger(settings_manager=settings)

        # Set it as global
        set_logger(custom_logger)

        # Get logger should return the custom one
        retrieved = get_logger()
        assert retrieved is custom_logger

    def test_get_logger_creates_instance_if_none(self) -> None:
        """Test get_logger() creates a new instance if none exists."""
        # Reset global logger
        from src.core import logger as logger_module

        logger_module._logger_instance = None

        # Get logger should create new instance
        logger = get_logger()
        assert logger is not None
        assert isinstance(logger, Logger)
