"""
Settings Manager - Centralized settings management for Regex Lab.

This module provides a singleton for accessing Sublime Text settings
with fallback to defaults when running outside Sublime Text (e.g., tests).
"""

from __future__ import annotations

from typing import Any

from .constants import DEFAULT_SETTINGS_FILE, DEFAULT_VARIABLES, DEFAULT_VARIABLES_ASSERTION
from .helpers import deep_merge_dicts

# Settings keys that require deep merge (nested dicts that users extend, not replace)
DEEP_MERGE_KEYS = frozenset(["variables", "variables_assertion", "variables_assertion_defaults"])

# Builtin defaults for deep merge keys (fallback when Sublime settings unavailable)
BUILTIN_DEFAULTS: dict[str, dict[str, Any]] = {
    "variables": DEFAULT_VARIABLES,
    "variables_assertion": DEFAULT_VARIABLES_ASSERTION,
    "variables_assertion_defaults": {},  # Deprecated, but keep for backward compat
}


class SettingsManager:
    """
    Singleton for managing Sublime Text settings.

    This class provides a centralized way to access settings from
    RegexLab.sublime-settings with proper fallbacks for testing.
    """

    _instance: SettingsManager | None = None

    def __init__(self, settings_file: str = DEFAULT_SETTINGS_FILE) -> None:
        """
        Initialize the settings manager.

        Args:
            settings_file: Name of the Sublime Text settings file.
        """
        self.settings_file = settings_file
        self._settings: Any | None = None
        self._fallback_settings: dict[str, Any] = {}

        # Try to load Sublime Text settings
        try:
            import sublime  # pyright: ignore[reportMissingImports]

            self._settings = sublime.load_settings(settings_file)
        except (ImportError, NameError):
            # Running outside Sublime Text (e.g., in tests)
            # Use fallback settings dictionary
            self._settings = None

    @classmethod
    def get_instance(cls) -> SettingsManager:
        """
        Get the singleton instance.

        Returns:
            The SettingsManager singleton instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton instance.

        Useful for testing to ensure clean state between tests.
        """
        cls._instance = None

    def set_fallback_settings(self, settings: dict[str, Any]) -> None:
        """
        Set fallback settings for use when Sublime Text is not available.

        This is primarily used in tests to mock settings.

        Args:
            settings: Dictionary of settings to use as fallback.
        """
        self._fallback_settings = settings

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value with deep merge for nested dict settings.

        For keys in DEEP_MERGE_KEYS (variables, variables_assertion, etc.),
        this method performs a DEEP MERGE between builtin defaults and user overrides
        to prevent user settings from completely replacing builtin nested dicts.

        Why deep merge?
        ---------------
        Sublime Text's load_settings() does SHALLOW merge, causing critical issues:

        Example WITHOUT deep merge (Sublime's default behavior):
            builtin.sublime-settings:
                "variables_assertion": {
                    "DATE": {"regex": "...", "default": "NOW"},
                    "TIME": {"regex": "...", "default": "NOW"},
                    "USERNAME": {"regex": "..."}
                }

            User.sublime-settings:
                "variables_assertion": {
                    "MY_VAR": {"regex": "..."}
                }

            Result:
                "variables_assertion": {"MY_VAR": {...}}  # DATE/TIME/USERNAME LOST! ❌

        Example WITH deep merge (this implementation):
            Result:
                "variables_assertion": {
                    "DATE": {...},      # ✅ Preserved from builtin
                    "TIME": {...},      # ✅ Preserved from builtin
                    "USERNAME": {...},  # ✅ Preserved from builtin
                    "MY_VAR": {...}     # ✅ Added from user
                }

        Args:
            key: The setting key to retrieve.
            default: Default value if the setting is not found.

        Returns:
            The setting value (deep-merged if dict), or default if not found.
        """
        if self._settings is not None:
            # Sublime Text mode: check if key requires deep merge
            # NOTE: This branch is NOT covered by unit tests (requires Sublime Text runtime)
            # Coverage: Tested manually in Sublime Text
            if key in DEEP_MERGE_KEYS:
                # Get builtin defaults from constants (guaranteed to exist)
                builtin_value = BUILTIN_DEFAULTS.get(key, {})

                # Get user value from Sublime settings (merged builtin + user)
                # Note: Sublime's load_settings() returns shallow merge, so user dict
                # completely replaces builtin dict. We need to restore builtin keys.
                user_value = self._settings.get(key, {})

                # Deep merge: builtin + user (user wins on conflicts)
                if isinstance(builtin_value, dict) and isinstance(user_value, dict):
                    return deep_merge_dicts(builtin_value, user_value)

                # If only one is dict, or both None, return user value (or builtin if user None)
                return user_value if user_value is not None else builtin_value

            # Non-deep-merge keys: use Sublime's shallow merge
            return self._settings.get(key, default)
        else:
            # Test mode: use fallback settings dictionary
            return self._fallback_settings.get(key, default)

    def get_nested(self, path: str, default: Any = None) -> Any:
        """
        Get a nested setting value using dot notation.

        Examples:
            get_nested("variables.date_format", "%Y-%m-%d")
            get_nested("ui.preview_on_selection", False)

        Args:
            path: Dot-separated path to the nested setting.
            default: Default value if the setting is not found.

        Returns:
            The nested setting value, or default if not found.
        """
        keys = path.split(".")

        # Get root value from settings or fallback
        value: Any = self._settings.get(keys[0]) if self._settings is not None else self._fallback_settings.get(keys[0])

        # Navigate nested dictionaries
        for key in keys[1:]:
            if value is None:
                return default
            if isinstance(value, dict):
                value = value.get(key)
            else:
                # Can't navigate further
                return default

        return value if value is not None else default

    def set(self, key: str, value: Any) -> None:
        """
        Set a setting value.

        Args:
            key: The setting key to set.
            value: The value to set.

        Note:
            Changes are only persisted if Sublime Text settings are available.
            In test mode, only fallback settings are modified.
        """
        if self._settings is not None:
            self._settings.set(key, value)
        else:
            self._fallback_settings[key] = value

    def has(self, key: str) -> bool:
        """
        Check if a setting key exists.

        Args:
            key: The setting key to check.

        Returns:
            True if the setting exists, False otherwise.
        """
        if self._settings is not None:
            result: bool = self._settings.has(key)
            return result
        else:
            return key in self._fallback_settings

    def add_to_loaded_portfolios(self, filepath: str) -> None:
        """
        Add portfolio path to loaded_portfolios setting.

        Args:
            filepath: Path to portfolio file to add

        Note:
            Does nothing if filepath already in loaded_portfolios.
        """
        loaded = self.get("loaded_portfolios", [])
        if filepath not in loaded:
            loaded.append(filepath)
            self.set("loaded_portfolios", loaded)
            self._save_settings()

    def remove_from_loaded_portfolios(self, filepath: str) -> None:
        """
        Remove portfolio path from loaded_portfolios setting.

        Args:
            filepath: Path to portfolio file to remove

        Note:
            Does nothing if filepath not in loaded_portfolios.
        """
        loaded = self.get("loaded_portfolios", [])
        if filepath in loaded:
            loaded.remove(filepath)
            self.set("loaded_portfolios", loaded)
            self._save_settings()

    def _save_settings(self) -> None:
        """
        Save settings to disk (Sublime Text only).

        In test mode, this is a no-op.
        """
        if self._settings is not None:
            try:
                import sublime  # pyright: ignore[reportMissingImports]

                sublime.save_settings(self.settings_file)
            except (ImportError, NameError, AttributeError):
                pass
