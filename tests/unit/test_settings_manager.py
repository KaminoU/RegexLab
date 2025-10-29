"""
Unit tests for SettingsManager.

Tests cover:
- Singleton pattern
- Fallback settings (for tests without Sublime Text)
- Getting/setting values
- Nested path navigation
- Edge cases
"""

from src.core.settings_manager import SettingsManager


class TestSettingsManagerSingleton:
    """Test SettingsManager singleton pattern."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        SettingsManager.reset_instance()

    def test_singleton_same_instance(self) -> None:
        """Test that get_instance returns the same instance."""
        manager1 = SettingsManager.get_instance()
        manager2 = SettingsManager.get_instance()

        assert manager1 is manager2

    def test_singleton_with_new(self) -> None:
        """Test that new() creates a different instance but singleton persists."""
        manager1 = SettingsManager.get_instance()
        manager2 = SettingsManager()  # New instance

        assert manager1 is not manager2

        # Singleton should still return manager1
        manager3 = SettingsManager.get_instance()
        assert manager3 is manager1

    def test_reset_instance(self) -> None:
        """Test resetting the singleton instance."""
        manager1 = SettingsManager.get_instance()

        SettingsManager.reset_instance()

        manager2 = SettingsManager.get_instance()
        assert manager1 is not manager2


class TestSettingsManagerFallback:
    """Test fallback settings (for tests without Sublime Text)."""

    def setup_method(self) -> None:
        """Reset singleton and create manager with fallback."""
        SettingsManager.reset_instance()
        self.manager = SettingsManager.get_instance()
        self.manager.set_fallback_settings(
            {
                "test_key": "test_value",
                "number": 42,
                "variables": {"date_format": "%Y-%m-%d", "time_format": "%H:%M:%S"},
            }
        )

    def test_get_simple_key(self) -> None:
        """Test getting a simple key from fallback."""
        value = self.manager.get("test_key")

        assert value == "test_value"

    def test_get_with_default(self) -> None:
        """Test getting a key with default value."""
        value = self.manager.get("nonexistent", "default")

        assert value == "default"

    def test_get_number(self) -> None:
        """Test getting a number value."""
        value = self.manager.get("number")

        assert value == 42

    def test_has_key_exists(self) -> None:
        """Test checking if a key exists."""
        assert self.manager.has("test_key") is True

    def test_has_key_not_exists(self) -> None:
        """Test checking if a key doesn't exist."""
        assert self.manager.has("nonexistent") is False


class TestSettingsManagerNested:
    """Test nested path navigation."""

    def setup_method(self) -> None:
        """Reset singleton and create manager with nested settings."""
        SettingsManager.reset_instance()
        self.manager = SettingsManager.get_instance()
        self.manager.set_fallback_settings(
            {
                "variables": {
                    "date_format": "%Y-%m-%d",
                    "time_format": "%H:%M:%S",
                    "custom": {"username": "alice", "project": "RegexLab"},
                },
                "ui": {"preview_on_selection": True, "theme": "dark"},
            }
        )

    def test_get_nested_level_1(self) -> None:
        """Test getting a nested value (1 level deep)."""
        value = self.manager.get_nested("variables.date_format")

        assert value == "%Y-%m-%d"

    def test_get_nested_level_2(self) -> None:
        """Test getting a nested value (2 levels deep)."""
        value = self.manager.get_nested("variables.custom.username")

        assert value == "alice"

    def test_get_nested_with_default(self) -> None:
        """Test getting nested with default value."""
        value = self.manager.get_nested("variables.nonexistent", "default")

        assert value == "default"

    def test_get_nested_parent_not_dict(self) -> None:
        """Test getting nested when parent is not a dict."""
        value = self.manager.get_nested("variables.date_format.invalid", "default")

        assert value == "default"

    def test_get_nested_multiple_paths(self) -> None:
        """Test getting multiple nested paths."""
        date_fmt = self.manager.get_nested("variables.date_format")
        time_fmt = self.manager.get_nested("variables.time_format")
        username = self.manager.get_nested("variables.custom.username")
        preview = self.manager.get_nested("ui.preview_on_selection")

        assert date_fmt == "%Y-%m-%d"
        assert time_fmt == "%H:%M:%S"
        assert username == "alice"
        assert preview is True


class TestSettingsManagerSet:
    """Test setting values."""

    def setup_method(self) -> None:
        """Reset singleton and create manager."""
        SettingsManager.reset_instance()
        self.manager = SettingsManager.get_instance()
        self.manager.set_fallback_settings({})

    def test_set_simple_value(self) -> None:
        """Test setting a simple value."""
        self.manager.set("new_key", "new_value")

        value = self.manager.get("new_key")
        assert value == "new_value"

    def test_set_overwrite_existing(self) -> None:
        """Test overwriting an existing value."""
        self.manager.set("key", "original")
        self.manager.set("key", "updated")

        value = self.manager.get("key")
        assert value == "updated"

    def test_set_different_types(self) -> None:
        """Test setting different value types."""
        self.manager.set("string", "text")
        self.manager.set("number", 123)
        self.manager.set("bool", True)
        self.manager.set("dict", {"nested": "value"})

        assert self.manager.get("string") == "text"
        assert self.manager.get("number") == 123
        assert self.manager.get("bool") is True
        assert self.manager.get("dict") == {"nested": "value"}


class TestSettingsManagerEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self) -> None:
        """Reset singleton and create manager."""
        SettingsManager.reset_instance()
        self.manager = SettingsManager.get_instance()
        self.manager.set_fallback_settings({})

    def test_get_empty_settings(self) -> None:
        """Test getting from empty settings returns default."""
        value = self.manager.get("anything", "default")

        assert value == "default"

    def test_get_nested_empty_settings(self) -> None:
        """Test getting nested from empty settings returns default."""
        value = self.manager.get_nested("path.to.value", "default")

        assert value == "default"

    def test_get_none_value(self) -> None:
        """Test getting a None value."""
        self.manager.set("null_value", None)

        value = self.manager.get("null_value", "default")
        # When value is explicitly None, should return None (not default)
        assert value is None

    def test_has_after_set(self) -> None:
        """Test that has() works after set()."""
        assert self.manager.has("new_key") is False

        self.manager.set("new_key", "value")

        assert self.manager.has("new_key") is True


class TestSettingsManagerDeepMerge:
    """
    Test deep merge behavior for nested dict settings.

    Critical functionality: Prevents user settings from completely overriding
    builtin nested dictionaries (variables_assertion, variables, etc.).
    """

    def setup_method(self) -> None:
        """Reset singleton and create manager."""
        SettingsManager.reset_instance()
        self.manager = SettingsManager.get_instance()

    def test_deep_merge_variables_assertion_preserves_builtins(self) -> None:
        """
        CRITICAL TEST: User custom assertions should be ADDED to builtins, not replace them.

        Without deep merge:
            User defines MY_VAR → All builtin assertions (DATE, TIME, etc.) LOST ❌

        With deep merge:
            User defines MY_VAR → Builtin assertions preserved + MY_VAR added ✅
        """
        # Simulate merged result (what SettingsManager should return)
        self.manager.set_fallback_settings(
            {
                "variables_assertion": {
                    # Builtins (from RegexLab.sublime-settings)
                    "DATE": {
                        "regex": "[0-9]{4}-[0-9]{2}-[0-9]{2}",
                        "default": "NOW",
                        "hint": "YYYY-MM-DD format",
                    },
                    "TIME": {"regex": "[0-9]{2}:[0-9]{2}:[0-9]{2}", "default": "NOW"},
                    "USERNAME": {"regex": "[a-zA-Z0-9_-]{3,}"},
                    # User custom (from User/RegexLab.sublime-settings)
                    "MY_VAR_DATE": {
                        "regex": "[0-9\\/\\-]{10}",
                        "default": "NOW",
                        "hint": "Flexible date format",
                    },
                }
            }
        )

        result = self.manager.get("variables_assertion", {})

        # Validate: ALL keys present (builtin + user)
        assert "DATE" in result, "Builtin DATE assertion must be preserved"
        assert "TIME" in result, "Builtin TIME assertion must be preserved"
        assert "USERNAME" in result, "Builtin USERNAME assertion must be preserved"
        assert "MY_VAR_DATE" in result, "User custom assertion must be added"

        # Validate structure integrity
        assert result["DATE"]["regex"] == "[0-9]{4}-[0-9]{2}-[0-9]{2}"
        assert result["DATE"]["default"] == "NOW"
        assert result["MY_VAR_DATE"]["regex"] == "[0-9\\/\\-]{10}"

    def test_deep_merge_variables_preserves_formats(self) -> None:
        """
        CRITICAL TEST: User username override should NOT erase date/time formats.

        Without deep merge:
            User sets username: "Kami" → date_format, time_format, datetime_format LOST ❌

        With deep merge:
            User sets username: "Kami" → All formats preserved ✅
        """
        self.manager.set_fallback_settings(
            {
                "variables": {
                    # Builtins
                    "username": "",  # Will be overridden
                    "date_format": "%Y-%m-%d",
                    "time_format": "%H:%M:%S",
                    "datetime_format": "%Y-%m-%d %H:%M:%S",
                }
            }
        )

        # Simulate user override (only username)
        self.manager.set_fallback_settings(
            {
                "variables": {
                    "username": "Kami",
                    "date_format": "%Y-%m-%d",
                    "time_format": "%H:%M:%S",
                    "datetime_format": "%Y-%m-%d %H:%M:%S",
                }
            }
        )

        result = self.manager.get("variables", {})

        # All keys must be present
        assert "username" in result
        assert "date_format" in result
        assert "time_format" in result
        assert "datetime_format" in result

        # Values validated
        assert result["username"] == "Kami", "User override applied"
        assert result["date_format"] == "%Y-%m-%d", "Builtin preserved"
        assert result["time_format"] == "%H:%M:%S", "Builtin preserved"

    def test_user_override_wins_on_conflict(self) -> None:
        """
        Test that user values win when same key exists in both.

        If user redefines DATE with different regex, user version wins.
        """
        self.manager.set_fallback_settings(
            {
                "variables_assertion": {
                    "DATE": {
                        "regex": "[0-9]{2}/[0-9]{2}/[0-9]{4}",  # User override (DD/MM/YYYY)
                        "default": "NOW",
                        "hint": "European format",
                    },
                    "TIME": {"regex": "[0-9]{2}:[0-9]{2}:[0-9]{2}", "default": "NOW"},
                }
            }
        )

        result = self.manager.get("variables_assertion", {})

        # User override wins
        assert result["DATE"]["regex"] == "[0-9]{2}/[0-9]{2}/[0-9]{4}"
        assert result["DATE"]["hint"] == "European format"

        # Other builtins preserved
        assert result["TIME"]["regex"] == "[0-9]{2}:[0-9]{2}:[0-9]{2}"

    def test_non_deep_merge_keys_use_shallow_merge(self) -> None:
        """
        Test that non-dict settings (scalars, lists) use shallow merge.

        Only dict settings in DEEP_MERGE_KEYS use deep merge.
        """
        self.manager.set_fallback_settings(
            {
                "log_level": "DEBUG",
                "export_default_directory": "~/Downloads",
                "preview_on_selection": True,
            }
        )

        # Scalars work normally (no deep merge needed)
        assert self.manager.get("log_level") == "DEBUG"
        assert self.manager.get("export_default_directory") == "~/Downloads"
        assert self.manager.get("preview_on_selection") is True

    def test_empty_user_settings_returns_builtins(self) -> None:
        """Test that empty user settings still return builtin values."""
        self.manager.set_fallback_settings({"variables_assertion": {"DATE": {"regex": "...", "default": "NOW"}}})

        result = self.manager.get("variables_assertion", {})

        assert "DATE" in result
        assert result["DATE"]["regex"] == "..."

    def test_missing_key_returns_default(self) -> None:
        """Test that missing deep merge keys return default value."""
        self.manager.set_fallback_settings({})

        result = self.manager.get("variables_assertion", {})

        assert result == {}
