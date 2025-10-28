import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core.settings_manager import SettingsManager


class TestSettingsManagerImportError:
    """Test settings_manager when sublime is unavailable (line 40)."""

    def test_init_without_sublime_uses_fallback(self, monkeypatch):
        """When sublime import fails, should use fallback settings dict."""

        # Force ImportError by making sublime unavailable
        def mock_import(name, *args, **kwargs):
            if name == "sublime":
                raise ImportError("No module named 'sublime'")
            return __builtins__.__import__(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", mock_import)

        SettingsManager.reset_instance()
        manager = SettingsManager()

        # Should use fallback (None for _settings)
        assert manager._settings is None
        assert isinstance(manager._fallback_settings, dict)


class TestSettingsManagerFallbackBranches:
    """Test settings_manager fallback branches (lines 91, 141)."""

    def test_get_uses_fallback_when_settings_none(self):
        """Line 91: get() should use fallback when _settings is None."""
        SettingsManager.reset_instance()
        manager = SettingsManager()
        manager._settings = None
        manager.set_fallback_settings({"test_key": "fallback_value"})

        result = manager.get("test_key")
        assert result == "fallback_value"

    def test_get_nested_uses_fallback_when_settings_none(self):
        """Line 141: get_nested() should use fallback when _settings is None."""
        SettingsManager.reset_instance()
        manager = SettingsManager()
        manager._settings = None
        manager.set_fallback_settings({"nested": {"key": "nested_value"}})

        result = manager.get_nested("nested.key")
        assert result == "nested_value"

    def test_get_nested_returns_default_when_branch_not_dict(self):
        """Should return default if traversal encounters non-dict value."""
        SettingsManager.reset_instance()
        manager = SettingsManager()
        manager._settings = None
        manager.set_fallback_settings({"flat": "value"})

        result = manager.get_nested("flat.inner", default="missing")
        assert result == "missing"


class TestSettingsManagerSetBranches:
    """Test settings_manager set() branches (lines 156-157)."""

    def test_set_uses_sublime_settings_when_available(self):
        """Lines 156-157: set() should call _settings.set() when available."""
        SettingsManager.reset_instance()
        manager = SettingsManager()

        mock_settings = MagicMock()
        manager._settings = mock_settings

        manager.set("test_key", "test_value")

        mock_settings.set.assert_called_once_with("test_key", "test_value")

    def test_set_updates_fallback_when_settings_unavailable(self):
        """Should store values in fallback settings when Sublime settings absent."""
        SettingsManager.reset_instance()
        manager = SettingsManager()
        manager._settings = None

        manager.set("test_key", "fallback")

        assert manager._fallback_settings["test_key"] == "fallback"


class TestSettingsManagerAddRemovePortfolios:
    """Test add/remove portfolio methods (lines 171-175, 187-191)."""

    def test_add_to_loaded_portfolios_when_not_present(self):
        """Lines 171-175: Should add filepath and save when not already loaded."""
        SettingsManager.reset_instance()
        manager = SettingsManager()
        manager._settings = None
        manager.set_fallback_settings({"loaded_portfolios": []})

        manager.add_to_loaded_portfolios("/path/to/portfolio.json")

        loaded = manager.get("loaded_portfolios")
        assert "/path/to/portfolio.json" in loaded

    def test_add_to_loaded_portfolios_with_settings_calls_save(self):
        """When Sublime settings exist, should trigger save."""
        SettingsManager.reset_instance()
        manager = SettingsManager()

        class FakeSettings:
            def __init__(self) -> None:
                self.store = {"loaded_portfolios": []}

            def get(self, key, default=None):
                return self.store.get(key, default)

            def set(self, key, value):
                self.store[key] = value

            def has(self, key):
                return key in self.store

        manager._settings = FakeSettings()

        with patch.object(manager, "_save_settings") as save_mock:
            manager.add_to_loaded_portfolios("/tmp/file.json")

        save_mock.assert_called_once()

    def test_add_to_loaded_portfolios_skips_duplicates(self):
        """Adding an existing path should leave list unchanged."""
        SettingsManager.reset_instance()
        manager = SettingsManager()
        manager._settings = None
        manager.set_fallback_settings({"loaded_portfolios": ["/dup.json"]})

        manager.add_to_loaded_portfolios("/dup.json")

        assert manager.get("loaded_portfolios") == ["/dup.json"]

    def test_remove_from_loaded_portfolios_when_present(self):
        """Lines 187-191: Should remove filepath and save when present."""
        SettingsManager.reset_instance()
        manager = SettingsManager()
        manager._settings = None
        manager.set_fallback_settings({"loaded_portfolios": ["/path/to/portfolio.json"]})

        manager.remove_from_loaded_portfolios("/path/to/portfolio.json")

        loaded = manager.get("loaded_portfolios", [])
        assert "/path/to/portfolio.json" not in loaded

    def test_remove_from_loaded_portfolios_with_settings_calls_save(self):
        """Removing with Sublime settings should trigger save."""
        SettingsManager.reset_instance()
        manager = SettingsManager()

        class FakeSettings:
            def __init__(self) -> None:
                self.store = {"loaded_portfolios": ["/tmp/file.json", "/tmp/other.json"]}

            def get(self, key, default=None):
                return self.store.get(key, default)

            def set(self, key, value):
                self.store[key] = value

            def has(self, key):
                return key in self.store

        manager._settings = FakeSettings()

        with patch.object(manager, "_save_settings") as save_mock:
            manager.remove_from_loaded_portfolios("/tmp/file.json")

        save_mock.assert_called_once()

    def test_remove_from_loaded_portfolios_missing_path_noop(self):
        """Removing absent path should not alter list."""
        SettingsManager.reset_instance()
        manager = SettingsManager()
        manager._settings = None
        manager.set_fallback_settings({"loaded_portfolios": ["/keep.json"]})

        manager.remove_from_loaded_portfolios("/missing.json")

        assert manager.get("loaded_portfolios") == ["/keep.json"]


class TestSettingsManagerSaveSettings:
    """Test _save_settings() method (lines 199-205)."""

    def test_save_settings_handles_import_error(self):
        """Lines 199-205: Should handle ImportError gracefully."""
        SettingsManager.reset_instance()
        manager = SettingsManager()

        mock_settings = MagicMock()
        manager._settings = mock_settings

        # This should not raise even if sublime.save_settings fails
        # (tested by having mock settings but no actual sublime module)
        manager._save_settings()

        # In real code, this would call sublime.save_settings
        # We just verify it doesn't crash

    def test_save_settings_does_nothing_when_settings_none(self):
        """Lines 199-205: Should do nothing when _settings is None."""
        SettingsManager.reset_instance()
        manager = SettingsManager()
        manager._settings = None

        # Should not raise
        manager._save_settings()

    def test_save_settings_calls_sublime_save_when_available(self):
        """Should invoke sublime.save_settings when module present."""
        SettingsManager.reset_instance()
        manager = SettingsManager()

        class FakeSettings:
            def __init__(self) -> None:
                self.store = {}

            def get(self, key, default=None):
                return self.store.get(key, default)

            def set(self, key, value):
                self.store[key] = value

            def has(self, key):
                return key in self.store

        manager._settings = FakeSettings()
        fake_sublime = SimpleNamespace(save_settings=MagicMock())

        with patch.dict(sys.modules, {"sublime": fake_sublime}):
            manager._save_settings()

        fake_sublime.save_settings.assert_called_once_with(manager.settings_file)


class TestSettingsManagerSublimeBranches:
    """Additional coverage for Sublime-enabled branches (deep merge, has, get)."""

    class FakeSettings:
        def __init__(self) -> None:
            self.store: dict[str, object] = {}

        def get(self, key, default=None):
            return self.store.get(key, default)

        def set(self, key, value):
            self.store[key] = value

        def has(self, key):
            return key in self.store

    def setup_method(self) -> None:
        SettingsManager.reset_instance()
        self.manager = SettingsManager()
        self.fake_settings = self.FakeSettings()
        self.manager._settings = self.fake_settings

    def test_get_deep_merge_preserves_builtin_values(self):
        """Deep merge should retain builtin keys while adding user overrides."""
        self.fake_settings.store["variables_assertion"] = {"CUSTOM": {"regex": "custom"}}

        merged = self.manager.get("variables_assertion")

        assert "CUSTOM" in merged
        # DATE comes from builtin defaults and should still exist
        assert "DATE" in merged
        assert merged["CUSTOM"]["regex"] == "custom"

    def test_get_non_deep_key_returns_sublime_value(self):
        """Non-deep-merge keys should return Sublime-provided value."""
        self.fake_settings.store["ui_mode"] = "panel"

        assert self.manager.get("ui_mode", default="fallback") == "panel"

    def test_get_nested_reads_from_sublime_settings(self):
        """get_nested should traverse nested dictionaries from Sublime settings."""
        self.fake_settings.store["nested"] = {"inner": {"value": 42}}

        assert self.manager.get_nested("nested.inner.value") == 42

    def test_has_delegates_to_sublime_settings(self):
        """has() should delegate when Sublime settings are available."""
        self.fake_settings.store["feature_flag"] = True

        assert self.manager.has("feature_flag") is True

    def test_has_uses_fallback_when_settings_absent(self):
        """has() should fall back to internal dict when Sublime settings missing."""
        SettingsManager.reset_instance()
        manager = SettingsManager()
        manager._settings = None
        manager.set_fallback_settings({"flag": True})

        assert manager.has("flag") is True
        assert manager.has("missing") is False
