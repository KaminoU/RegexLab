"""
Pattern Engine for Regex Lab.

Handles dynamic variable resolution for patterns.
Provides built-in variables (date, time, username, clipboard) and custom variables.
"""

from __future__ import annotations

import getpass
import os
from datetime import datetime

from .constants import LOG_TRUNCATE_LONG, LOG_TRUNCATE_SHORT
from .helpers import truncate_for_log
from .logger import get_logger
from .models import Pattern
from .settings_manager import SettingsManager

logger = get_logger()


class PatternEngine:
    """
    Engine for resolving dynamic pattern variables.

    Provides built-in variables:
    - {date}: Current date (format configurable, default: %Y-%m-%d)
    - {time}: Current time (format configurable, default: %H:%M:%S)
    - {username}: System username or custom from settings
    - {clipboard}: Clipboard content (requires sublime module, fallback to empty)

    Also supports custom variables from settings.
    """

    settings: SettingsManager
    custom_variables: dict[str, str]
    date_format: str
    time_format: str
    _username: str | None

    def __init__(
        self,
        custom_variables: dict[str, str] | None = None,
        settings_manager: SettingsManager | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        username: str | None = None,
    ) -> None:
        """
        Initialize the PatternEngine.

        Args:
            custom_variables: Custom variable mappings {name: value} (keys normalized to UPPERCASE)
            settings_manager: Optional settings manager (defaults to singleton)
            date_format: strftime format for {date} variable (overrides settings)
            time_format: strftime format for {time} variable (overrides settings)
            username: Custom username (overrides settings, defaults to system username)
        """
        self.settings = settings_manager or SettingsManager.get_instance()
        # Normalize custom variable keys to UPPERCASE for case-insensitive matching
        self.custom_variables = {k.upper(): v for k, v in (custom_variables or {}).items()}

        # Get formats from settings or use provided overrides
        self.date_format = (
            date_format if date_format is not None else self.settings.get_nested("variables.date_format", "%Y-%m-%d")
        )
        self.time_format = (
            time_format if time_format is not None else self.settings.get_nested("variables.time_format", "%H:%M:%S")
        )
        self._username = username if username is not None else self.settings.get_nested("variables.username", None)

    def _get_builtin_variable(self, var_name: str) -> str | None:
        """
        Get value for a built-in variable.

        Args:
            var_name: Variable name (case-insensitive, e.g., "DATE", "date", "Date")

        Returns:
            Variable value or None if not a built-in variable
        """
        logger.debug("Resolving builtin variable: %s", var_name)
        # Normalize to lowercase for comparison
        var_lower = var_name.lower()
        now = datetime.now()

        if var_lower == "date":
            value = now.strftime(self.date_format)
            logger.debug("Variable {%s} resolved to: %s", var_name, value)
            return value

        if var_lower == "time":
            value = now.strftime(self.time_format)
            logger.debug("Variable {%s} resolved to: %s", var_name, value)
            return value

        if var_lower == "username":
            if self._username:
                logger.debug("Variable {%s} resolved to custom: %s", var_name, self._username)
                return self._username
            # Fallback to system username
            try:
                # Note: getpass.getuser() returns str but mypy sees it as Any
                system_user = str(getpass.getuser())
                logger.debug("Variable {%s} resolved to system: %s", var_name, system_user)
                return system_user
            except (KeyError, OSError, ImportError) as e:
                # Fallback to environment variable
                # KeyError: user not found in pwd database
                # OSError: system-level errors accessing user info
                # ImportError: pwd module not available (Windows)
                fallback: str | None = os.getenv("USER", os.getenv("USERNAME", "unknown"))
                result = fallback if fallback is not None else "unknown"
                logger.debug("Variable {%s} fallback to env: %s (error: %s)", var_name, result, e)
                return result

        if var_lower == "clipboard":
            # Try to get clipboard content from sublime if available
            try:
                import sublime  # pyright: ignore[reportMissingImports]

                clipboard_content: str = sublime.get_clipboard()
                logger.debug("Variable {%s} resolved from clipboard: %s", var_name, truncate_for_log(clipboard_content))
                return clipboard_content
            except (ImportError, Exception) as e:
                # Fallback: try system clipboard (not reliable cross-platform)
                logger.debug("Variable {%s} clipboard unavailable: %s", var_name, e)
                return ""

        logger.debug("Variable {%s} is not a builtin variable", var_name)
        return None

    def resolve_variables(self, pattern: Pattern) -> dict[str, str]:
        """
        Resolve all variables in a pattern to their values.

        Args:
            pattern: Pattern with variables to resolve

        Returns:
            Dictionary mapping variable names to their resolved values

        Raises:
            ValueError: If a variable cannot be resolved
        """
        if not pattern.is_dynamic():
            logger.debug("Pattern '%s' is static, no variables to resolve", pattern.name)
            return {}

        logger.debug("Resolving variables for pattern '%s': %s", pattern.name, pattern.variables)
        resolved: dict[str, str] = {}

        for var_name in pattern.variables:
            # Try built-in variables first
            value = self._get_builtin_variable(var_name)

            # Try custom variables if not built-in
            if value is None:
                value = self.custom_variables.get(var_name)
                if value is not None:
                    logger.debug("Variable {%s} resolved from custom variables", var_name)

            # If still None, variable is unknown
            if value is None:
                logger.debug("Variable {%s} not found - raising error", var_name)
                raise ValueError(f"Unknown variable: {var_name}")

            resolved[var_name] = value

        truncated = {k: truncate_for_log(v, LOG_TRUNCATE_SHORT) for k, v in resolved.items()}
        logger.debug("All variables resolved: %s", truncated)
        return resolved

    def resolve_pattern(self, pattern: Pattern, variables: dict[str, str] | None = None) -> str:
        """
        Resolve a pattern with its variables.

        Args:
            pattern: Pattern to resolve
            variables: Optional custom variable values (overrides auto-resolution)

        Returns:
            Resolved regex string

        Raises:
            ValueError: If variables cannot be resolved
        """
        logger.debug("Resolving pattern '%s' (dynamic=%s)", pattern.name, pattern.is_dynamic())

        if not pattern.is_dynamic():
            logger.debug("Pattern '%s' is static, returning regex as-is", pattern.name)
            return pattern.regex

        # Use provided variables or auto-resolve
        if variables is None:
            logger.debug("No variables provided, auto-resolving for pattern '%s'", pattern.name)
            variables = self.resolve_variables(pattern)
        else:
            logger.debug("Using provided variables for pattern '%s'", pattern.name)

        resolved = pattern.resolve(variables)
        logger.debug("Pattern '%s' resolved to: %s", pattern.name, truncate_for_log(resolved, LOG_TRUNCATE_LONG))
        return resolved

    def add_custom_variable(self, name: str, value: str) -> None:
        """
        Add or update a custom variable.

        Args:
            name: Variable name (without braces, normalized to UPPERCASE)
            value: Variable value
        """
        # Normalize key to UPPERCASE for consistency
        normalized_name = name.upper()
        logger.debug("Adding custom variable: %s = %s", normalized_name, truncate_for_log(value))
        self.custom_variables[normalized_name] = value

    def remove_custom_variable(self, name: str) -> bool:
        """
        Remove a custom variable.

        Args:
            name: Variable name to remove (normalized to UPPERCASE)

        Returns:
            True if removed, False if not found
        """
        # Normalize key to UPPERCASE for lookup
        key = name.upper()
        logger.debug("Removing custom variable: %s", key)
        if key in self.custom_variables:
            del self.custom_variables[key]
            logger.debug("Variable %s removed successfully", key)
            return True
        logger.debug("Variable %s not found in custom variables", key)
        return False
