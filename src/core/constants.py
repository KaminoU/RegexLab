"""
Constants for Regex Lab.

Centralized constants for magic numbers, default values, and configuration.
This module provides a single source of truth for commonly used values
to improve maintainability and avoid magic numbers scattered throughout the codebase.
"""

from __future__ import annotations

# =============================================================================
# UI Display Constants
# =============================================================================

# Default width for Quick Panel items (in characters)
# Used for formatting pattern/portfolio names in lists
DEFAULT_QUICK_PANEL_WIDTH: int = 80

# Duration for status messages (in milliseconds)
# Default: 13 seconds (13000ms) to ensure users see important notifications
DEFAULT_STATUS_MESSAGE_DURATION: int = 13000

# Interval for repeating status messages (in milliseconds)
# Messages repeat every 2 seconds to maintain visibility
DEFAULT_STATUS_REPEAT_INTERVAL: int = 2000

# Duration for popup displays (in milliseconds)
# Default: 20 seconds (20000ms) for popups showing pattern details/help
DEFAULT_POPUP_DISPLAY_DURATION: int = 20000

# Show phantom preview when text is selected (default: False)
DEFAULT_PREVIEW_ON_SELECTION: bool = False

# Show icons for static/dynamic patterns (default: True)
DEFAULT_SHOW_PATTERN_TYPE_ICONS: bool = True

# Show descriptions in Quick Panel (default: True)
DEFAULT_QUICK_PANEL_SHOW_DESCRIPTIONS: bool = True

# Show helpful popup when entering variable values (default: False)
DEFAULT_SHOW_INPUT_HELP_POPUP: bool = False

# =============================================================================
# Variables & Format Constants
# =============================================================================

# Default date format for {date} patterns and {{DATE}} variable
DEFAULT_DATE_FORMAT: str = "%Y-%m-%d"

# Default time format for {time} patterns and {{TIME}} variable
DEFAULT_TIME_FORMAT: str = "%H:%M:%S"

# Default datetime format for {{DATETIME}} variable
DEFAULT_DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# Default variables configuration
DEFAULT_VARIABLES: dict[str, str] = {
    "username": "",  # Empty = use system username
    "date_format": DEFAULT_DATE_FORMAT,
    "time_format": DEFAULT_TIME_FORMAT,
    "datetime_format": DEFAULT_DATETIME_FORMAT,
}

# Default variables assertion configuration
# These are the builtin variable validations that should ALWAYS be available
DEFAULT_VARIABLES_ASSERTION: dict[str, dict[str, str] | str] = {
    # Date/Time formats (with hints and examples)
    "DATE": {
        "regex": "[0-9]{4}-[0-9]{2}-[0-9]{2}",
        "default": "NOW",
        "hint": "YYYY-MM-DD format",
        "example": "2025-10-23",
    },
    "DATETIME": {
        "regex": "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}",
        "default": "NOW",
        "hint": "YYYY-MM-DD HH:MM:SS format",
        "example": "2025-10-23 15:30:45",
    },
    "TIME": {
        "regex": "[0-9]{2}:[0-9]{2}:[0-9]{2}",
        "default": "NOW",
        "hint": "HH:MM:SS format",
        "example": "15:30:45",
    },
    # Log levels
    "LEVEL": {
        "regex": "DEBUG|INFO|WARN(ING)?|ERROR|CRITICAL|FATAL",
        "default": "INFO",
        "hint": "Log severity level",
        "example": "DEBUG, INFO, WARN/WARNING, ERROR, CRITICAL, FATAL",
    },
    # Common technical patterns
    "USERNAME": {
        "regex": "[a-zA-Z0-9_-]{3,}",
        "hint": "Alphanumeric username (min 3 chars)",
        "example": "john_doe, user123",
    },
    "EMAIL": {
        "regex": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "hint": "Email address",
        "example": "user@example.com",
    },
    "IP": {
        "regex": r"([0-9]{1,3}\.){3}[0-9]{1,3}",
        "hint": "IPv4 address",
        "example": "192.168.1.1",
    },
    "PORT": {
        "regex": "[0-9]{1,5}",
        "default": "8080",
        "hint": "Port number (0-99999)",
        "example": "80, 443, 8080",
    },
    "UUID": {
        "regex": "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "hint": "UUID format",
        "example": "550e8400-e29b-41d4-a716-446655440000",
    },
}

# =============================================================================
# Search Configuration Constants
# =============================================================================

# Inject patterns to native Sublime Find panel (default: True)
DEFAULT_INJECT_TO_NATIVE_FIND_PANEL: bool = True

# Preserve case-sensitive flag when injecting (default: False)
DEFAULT_PRESERVE_CASE_SENSITIVE: bool = False

# Preserve regex mode when injecting (default: True)
DEFAULT_PRESERVE_REGEX_MODE: bool = True

# =============================================================================
# Logging Constants
# =============================================================================

# Default log level for RegexLab logger
# Options: "DEBUG", "INFO", "WARNING", "ERROR"
DEFAULT_LOG_LEVEL: str = "INFO"

# Default path display mode for logs and UI
# Options: "relative", "ellipsis", "full"
# - "relative": ./Packages/User/RegexLab/... (relative to Sublime Text root)
# - "ellipsis": C:\Users\...\RegexLab\portfolios\file.json (start...end)
# - "full": Full absolute path (no shortening)
DEFAULT_PATH_DISPLAY_MODE: str = "relative"

# Number of directory levels to keep at start/end for "ellipsis" mode
# Example with ellipsis_parts=2: C:\Users\miche\...\RegexLab\portfolios\file.json
DEFAULT_PATH_ELLIPSIS_PARTS: int = 2

# =============================================================================
# File System Constants
# =============================================================================

# Default encoding for JSON portfolio files
DEFAULT_ENCODING: str = "utf-8"

# JSON indentation level for pretty-printing
DEFAULT_JSON_INDENT: int = 2

# Default export directory for portfolios (relative to home directory)
# User can override with "export_default_directory" setting
DEFAULT_EXPORT_DIRECTORY: str = "~/RegexLab"

# =============================================================================
# Portfolio Constants
# =============================================================================

# Name of the built-in portfolio (special, always loaded first)
BUILTIN_PORTFOLIO_NAME: str = "RegexLab"

# Maximum pattern name length (for validation)
MAX_PATTERN_NAME_LENGTH: int = 100

# Maximum portfolio name length (for validation)
MAX_PORTFOLIO_NAME_LENGTH: int = 100

# =============================================================================
# Settings Constants
# =============================================================================

# Default settings file name
DEFAULT_SETTINGS_FILE: str = "RegexLab.sublime-settings"

# Default data directory name (relative to Packages)
DEFAULT_DATA_DIR: str = "User/RegexLab"

# =============================================================================
# Integrity/Security Constants
# =============================================================================

# Salt file name for cryptographic operations
INTEGRITY_SALT_FILENAME: str = "salt.key"

# Keystore file name for encrypted portfolio data
INTEGRITY_KEYSTORE_FILENAME: str = "keystore.bin"

# KDF iteration count (for password-based key derivation)
# Higher = more secure but slower
KDF_ITERATIONS: int = 100_000

# =============================================================================
# Pattern Engine Constants
# =============================================================================

# Maximum recursion depth for pattern variable resolution
MAX_PATTERN_RECURSION_DEPTH: int = 10

# Default regex flags (case-insensitive, multiline, dotall)
DEFAULT_REGEX_FLAGS: str = "ims"

# Logging truncation lengths
LOG_TRUNCATE_LENGTH: int = 30  # Standard truncation for log messages
LOG_TRUNCATE_SHORT: int = 20  # Short truncation for dict values
LOG_TRUNCATE_LONG: int = 50  # Longer truncation for resolved patterns

# =============================================================================
# UI Icons Constants
# =============================================================================

# Pattern Type Icons
ICON_STATIC_PATTERN: str = "📄"  # Static pattern (fixed document)
ICON_DYNAMIC_PATTERN: str = "🧪"  # Dynamic pattern (lab flask for variables)

# Panel Type Icons
ICON_FIND_PANEL: str = "🔍"  # Find panel (Ctrl+F)
ICON_REPLACE_PANEL: str = "🔄"  # Replace panel (Ctrl+H)
ICON_FIND_IN_FILES_PANEL: str = "📁"  # Find in Files panel (Ctrl+Shift+F)

# Action Icons
ICON_EDIT: str = "✏️"  # Edit action
ICON_DELETE: str = "🗑️"  # Delete action
ICON_ADD: str = "➕"  # Add/Create action  # noqa: RUF001
ICON_DISABLED: str = "🚫"  # Disabled/forbidden action

# Status Icons
ICON_SUCCESS: str = "✅"  # Success/enabled status
ICON_ERROR: str = "❌"  # Error/disabled status
ICON_WARNING: str = "⚠️"  # Warning status
ICON_INFO: str = "ℹ️"  # Information status  # noqa: RUF001

# Navigation Icons
ICON_BACK: str = "❌"  # Back/Cancel action
ICON_BROWSE: str = "🔍"  # Browse/Search action

# Portfolio Status Icons
ICON_BUILTIN: str = "📦"  # Built-in portfolio
ICON_BUILTIN_BOOK: str = "📚"  # Built-in portfolio (alternative book icon)
ICON_USER: str = "👤"  # User portfolio
ICON_READONLY: str = "🔒"  # Read-only portfolio
ICON_EDITABLE: str = "📝"  # Editable portfolio (1 Unicode char for alignment)
ICON_AVAILABLE: str = "💾"  # Available/saved portfolio

# Action Icons (extended)
ICON_IMPORT: str = "📥"  # Import action
ICON_EXPORT: str = "📤"  # Export action
ICON_RELOAD: str = "🔄"  # Reload action
ICON_SETTINGS: str = "⚙️"  # Settings action
ICON_DEFAULT: str = "🔧"  # Default/fallback action icon
ICON_FOLDER: str = "📂"  # Folder/directory icon

# Section Icons
ICON_SECTION_LOADED: str = "📁"  # Loaded portfolios section
ICON_SECTION_DISABLED: str = "🚫"  # Disabled portfolios section
ICON_SECTION_ACTIONS: str = "⚙️"  # Actions section

# ─────────────────────────────────────────────────────────────────────────────
# Status Messages
# ─────────────────────────────────────────────────────────────────────────────

MSG_PATTERN_LOADED_FIND: str = "Regex Lab: Loaded pattern '{name}'"
MSG_PATTERN_LOADED_REPLACE: str = "Regex Lab: Loaded pattern '{name}' into Replace panel"
MSG_PATTERN_LOADED_FIND_IN_FILES: str = "Regex Lab: Loaded pattern '{name}' into Find in Files"
MSG_PATTERN_CLIPBOARD_NO_VIEW: str = "Regex Lab: Pattern copied to clipboard (no active view)"

# ─────────────────────────────────────────────────────────────────────────────
# Portfolio Validation
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_PORTFOLIO_FIELDS: list[str] = ["name", "description", "version", "patterns"]
