"""
Unit tests for PatternEngine.

Tests cover:
- Built-in variable resolution (date, time, username, clipboard)
- Custom variable support
- Pattern resolution
- Edge cases (unknown variables, invalid formats, etc.)
- Error handling
"""

import re
from datetime import datetime

import pytest
from src.core.models import Pattern, PatternType
from src.core.pattern_engine import PatternEngine
from src.core.settings_manager import SettingsManager


class TestPatternEngineInit:
    """Test PatternEngine initialization."""

    def setup_method(self) -> None:
        """Setup mock settings for each test."""
        SettingsManager.reset_instance()
        settings = SettingsManager.get_instance()
        settings.set_fallback_settings(
            {"VARIABLES": {"date_format": "%Y-%m-%d", "time_format": "%H:%M:%S", "username": None}}
        )

    def test_init_default(self) -> None:
        """Test default initialization."""
        engine = PatternEngine()

        assert engine.custom_variables == {}
        assert engine.date_format == "%Y-%m-%d"
        assert engine.time_format == "%H:%M:%S"
        assert engine._username is None

    def test_init_custom_variables(self) -> None:
        """Test initialization with custom variables."""
        custom_vars = {"PROJECT": "MyProject", "priority": "HIGH"}
        engine = PatternEngine(custom_variables=custom_vars)

        # All keys are normalized to UPPERCASE
        assert engine.custom_variables == {"PROJECT": "MyProject", "PRIORITY": "HIGH"}

    def test_init_custom_formats(self) -> None:
        """Test initialization with custom date/time formats."""
        engine = PatternEngine(date_format="%d/%m/%Y", time_format="%I:%M %p")

        assert engine.date_format == "%d/%m/%Y"
        assert engine.time_format == "%I:%M %p"

    def test_init_custom_username(self) -> None:
        """Test initialization with custom username."""
        engine = PatternEngine(username="alice")

        assert engine._username == "alice"


class TestPatternEngineBuiltinVariables:
    """Test built-in variable resolution."""

    def test_resolve_date_default_format(self) -> None:
        """Test date variable with default format."""
        engine = PatternEngine()
        date_value = engine._get_builtin_variable("date")

        # Check it's today's date
        expected = datetime.now().strftime("%Y-%m-%d")
        assert date_value == expected

    def test_resolve_date_custom_format(self) -> None:
        """Test date variable with custom format."""
        engine = PatternEngine(date_format="%d/%m/%Y")
        date_value = engine._get_builtin_variable("date")

        # Check format is applied
        expected = datetime.now().strftime("%d/%m/%Y")
        assert date_value is not None
        assert date_value == expected
        assert re.match(r"\d{2}/\d{2}/\d{4}", date_value)

    def test_resolve_time_default_format(self) -> None:
        """Test time variable with default format."""
        engine = PatternEngine()
        time_value = engine._get_builtin_variable("time")

        # Check format HH:MM:SS
        assert time_value is not None
        assert re.match(r"\d{2}:\d{2}:\d{2}", time_value)

    def test_resolve_time_custom_format(self) -> None:
        """Test time variable with custom format."""
        engine = PatternEngine(time_format="%I:%M %p")
        time_value = engine._get_builtin_variable("time")

        # Check 12-hour format with AM/PM
        assert time_value is not None
        assert re.match(r"\d{2}:\d{2} (AM|PM)", time_value)

    def test_resolve_username_custom(self) -> None:
        """Test username variable with custom value."""
        engine = PatternEngine(username="bob")
        username_value = engine._get_builtin_variable("username")

        assert username_value == "bob"

    def test_resolve_username_system_fallback(self) -> None:
        """Test username falls back to system username."""
        engine = PatternEngine()
        username_value = engine._get_builtin_variable("username")

        # Should get some username (system dependent)
        assert username_value is not None
        assert len(username_value) > 0
        assert username_value != "unknown"

    def test_resolve_clipboard_no_sublime(self) -> None:
        """Test clipboard variable when sublime is not available."""
        engine = PatternEngine()
        clipboard_value = engine._get_builtin_variable("clipboard")

        # Should return empty string when sublime not available
        assert clipboard_value == ""

    def test_resolve_clipboard_with_sublime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test clipboard variable with sublime module available (covers lines 124-125)."""
        import sys
        from unittest.mock import MagicMock

        # Create a mock sublime module that successfully returns clipboard content
        mock_sublime = MagicMock()
        mock_sublime.get_clipboard.return_value = "Mocked clipboard content"

        # Inject mock into sys.modules
        monkeypatch.setitem(sys.modules, "sublime", mock_sublime)

        engine = PatternEngine()
        pattern = Pattern(name="Test", regex=r"Clip: {{CLIPBOARD}}", type=PatternType.DYNAMIC)
        result = engine.resolve_pattern(pattern)

        # Should use clipboard content from sublime
        assert result == "Clip: Mocked clipboard content"
        # Verify sublime.get_clipboard() was called
        mock_sublime.get_clipboard.assert_called_once()

    def test_resolve_unknown_builtin(self) -> None:
        """Test that unknown built-in variables return None."""
        engine = PatternEngine()
        value = engine._get_builtin_variable("unknown_var")

        assert value is None


class TestPatternEngineCustomVariables:
    """Test custom variable handling."""

    def test_add_custom_variable(self) -> None:
        """Test adding a custom variable."""
        engine = PatternEngine()
        engine.add_custom_variable("project", "RegexLab")

        assert engine.custom_variables["PROJECT"] == "RegexLab"

    def test_update_custom_variable(self) -> None:
        """Test updating an existing custom variable."""
        engine = PatternEngine(custom_variables={"VERSION": "1.0"})
        engine.add_custom_variable("version", "2.0")

        assert engine.custom_variables["VERSION"] == "2.0"

    def test_remove_custom_variable(self) -> None:
        """Test removing a custom variable."""
        engine = PatternEngine(custom_variables={"TEMP": "value"})

        result = engine.remove_custom_variable("temp")

        assert result is True
        assert "temp" not in engine.custom_variables

    def test_remove_nonexistent_variable(self) -> None:
        """Test removing a non-existent variable returns False."""
        engine = PatternEngine()

        result = engine.remove_custom_variable("nonexistent")

        assert result is False


class TestPatternEngineResolveVariables:
    """Test pattern variable resolution."""

    def test_resolve_static_pattern(self) -> None:
        """Test resolving static pattern returns empty dict."""
        pattern = Pattern(name="Static", regex=r"\bTODO\b", type=PatternType.STATIC)
        engine = PatternEngine()

        resolved = engine.resolve_variables(pattern)

        assert resolved == {}

    def test_resolve_dynamic_pattern_builtin(self) -> None:
        """Test resolving dynamic pattern with built-in variables."""
        pattern = Pattern(name="Dynamic", regex=r"TODO {{USERNAME}}", type=PatternType.DYNAMIC)
        engine = PatternEngine(username="alice")

        resolved = engine.resolve_variables(pattern)

        assert "USERNAME" in resolved
        assert resolved["USERNAME"] == "alice"

    def test_resolve_dynamic_pattern_custom(self) -> None:
        """Test resolving dynamic pattern with custom variables."""
        pattern = Pattern(name="Custom", regex=r"{{PROJECT}} v{{VERSION}}", type=PatternType.DYNAMIC)
        engine = PatternEngine(custom_variables={"PROJECT": "RegexLab", "version": "1.0"})

        resolved = engine.resolve_variables(pattern)

        # All keys normalized to UPPERCASE
        assert resolved == {"PROJECT": "RegexLab", "VERSION": "1.0"}

    def test_resolve_dynamic_pattern_mixed(self) -> None:
        """Test resolving pattern with both built-in and custom variables."""
        pattern = Pattern(name="Mixed", regex=r"{{PROJECT}} - {{DATE}} - {{USERNAME}}", type=PatternType.DYNAMIC)
        engine = PatternEngine(username="bob", custom_variables={"PROJECT": "Test"})

        resolved = engine.resolve_variables(pattern)

        assert "PROJECT" in resolved
        assert resolved["PROJECT"] == "Test"
        assert "DATE" in resolved
        assert "USERNAME" in resolved
        assert resolved["USERNAME"] == "bob"

    def test_resolve_unknown_variable_raises(self) -> None:
        """Test that unknown variable raises ValueError."""
        pattern = Pattern(name="Unknown", regex=r"{{UNKNOWN_VAR}}", type=PatternType.DYNAMIC)
        engine = PatternEngine()

        with pytest.raises(ValueError, match="Unknown variable: UNKNOWN_VAR"):
            engine.resolve_variables(pattern)


class TestPatternEngineResolvePattern:
    """Test full pattern resolution."""

    def test_resolve_pattern_static(self) -> None:
        """Test resolving static pattern returns regex as-is."""
        pattern = Pattern(name="Static", regex=r"\bTODO\b", type=PatternType.STATIC)
        engine = PatternEngine()

        resolved = engine.resolve_pattern(pattern)

        assert resolved == r"\bTODO\b"

    def test_resolve_pattern_dynamic_auto(self) -> None:
        """Test auto-resolving dynamic pattern."""
        pattern = Pattern(name="Dynamic", regex=r"TODO {{USERNAME}}", type=PatternType.DYNAMIC)
        engine = PatternEngine(username="alice")

        resolved = engine.resolve_pattern(pattern)

        assert resolved == r"TODO alice"

    def test_resolve_pattern_dynamic_manual_variables(self) -> None:
        """Test resolving with manually provided variables."""
        pattern = Pattern(name="Manual", regex=r"{{FOO}} and {{BAR}}", type=PatternType.DYNAMIC)
        engine = PatternEngine()

        resolved = engine.resolve_pattern(pattern, variables={"FOO": "hello", "bar": "world"})

        assert resolved == r"hello and world"

    def test_resolve_pattern_with_date(self) -> None:
        """Test pattern resolution with date variable."""
        pattern = Pattern(name="Dated", regex=r"LOG \[{{DATE}}\]", type=PatternType.DYNAMIC)
        engine = PatternEngine(date_format="%Y-%m-%d")

        resolved = engine.resolve_pattern(pattern)
        expected_date = datetime.now().strftime("%Y-%m-%d")

        # No escaping - simple replacement
        assert resolved == f"LOG \\[{expected_date}\\]"

    def test_resolve_pattern_escapes_special_chars(self) -> None:
        """Test that pattern resolution escapes special regex chars."""
        pattern = Pattern(name="Special", regex=r"{{TEXT}}", type=PatternType.DYNAMIC)
        engine = PatternEngine()

        # Variable value contains regex special chars
        resolved = engine.resolve_pattern(pattern, variables={"TEXT": "foo.*bar"})

        assert resolved == r"foo.*bar"


class TestPatternEngineEdgeCases:
    """Test edge cases and error handling."""

    def test_resolve_multiple_same_variable(self) -> None:
        """Test pattern with same variable multiple times."""
        pattern = Pattern(name="Duplicate", regex=r"{{FOO}} and {{FOO}} again", type=PatternType.DYNAMIC)
        engine = PatternEngine()

        resolved = engine.resolve_pattern(pattern, variables={"FOO": "bar"})

        assert resolved == r"bar and bar again"

    def test_empty_custom_variables(self) -> None:
        """Test pattern with empty custom variable value."""
        pattern = Pattern(name="Empty", regex=r"prefix{{EMPTY}}suffix", type=PatternType.DYNAMIC)
        engine = PatternEngine(custom_variables={"EMPTY": ""})

        resolved = engine.resolve_pattern(pattern)

        assert resolved == r"prefixsuffix"

    def test_variable_with_unicode(self) -> None:
        """Test custom variable with unicode characters."""
        pattern = Pattern(name="Unicode", regex=r"Name: {{NAME}}", type=PatternType.DYNAMIC)
        engine = PatternEngine(custom_variables={"NAME": "Björk"})

        resolved = engine.resolve_pattern(pattern)

        assert resolved == r"Name: Björk"


class TestPatternEngineExceptionHandling:
    """Test exception handling in builtin variable resolution."""

    def test_username_exception_keyerror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test {username} fallback when getpass.getuser() raises KeyError."""
        import getpass

        def raise_keyerror() -> str:
            raise KeyError("user not found")

        monkeypatch.setattr(getpass, "getuser", raise_keyerror)
        monkeypatch.setenv("USER", "fallback_user")

        engine = PatternEngine()
        pattern = Pattern(name="Test", regex=r"User: {{USERNAME}}", type=PatternType.DYNAMIC)
        result = engine.resolve_pattern(pattern)

        assert result == "User: fallback_user"

    def test_username_exception_oserror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test {username} fallback when getpass.getuser() raises OSError."""
        import getpass

        def raise_oserror() -> str:
            raise OSError("system error")

        monkeypatch.setattr(getpass, "getuser", raise_oserror)
        monkeypatch.delenv("USER", raising=False)  # CI Linux uses USER=runner
        monkeypatch.setenv("USERNAME", "fallback_username")

        engine = PatternEngine()
        pattern = Pattern(name="Test", regex=r"User: {{USERNAME}}", type=PatternType.DYNAMIC)
        result = engine.resolve_pattern(pattern)

        assert result == "User: fallback_username"

    def test_username_exception_importerror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test {username} fallback when getpass.getuser() raises ImportError."""
        import getpass

        def raise_importerror() -> str:
            raise ImportError("pwd not available")

        monkeypatch.setattr(getpass, "getuser", raise_importerror)
        monkeypatch.delenv("USER", raising=False)
        monkeypatch.delenv("USERNAME", raising=False)

        engine = PatternEngine()
        pattern = Pattern(name="Test", regex=r"User: {{USERNAME}}", type=PatternType.DYNAMIC)
        result = engine.resolve_pattern(pattern)

        assert result == "User: unknown"

    def test_clipboard_exception_importerror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test {clipboard} returns empty string when sublime unavailable."""
        # No need to mock - sublime already unavailable in test environment
        engine = PatternEngine()
        pattern = Pattern(name="Test", regex=r"Clip: {{CLIPBOARD}}", type=PatternType.DYNAMIC)
        result = engine.resolve_pattern(pattern)

        # ImportError -> empty string fallback
        assert result == "Clip: "

    def test_clipboard_exception_generic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test {clipboard} returns empty string on generic exception (lines 123-125)."""
        # Mock sublime module to raise a generic Exception when get_clipboard() is called
        import sys
        from unittest.mock import MagicMock

        # Create a mock sublime module
        mock_sublime = MagicMock()
        mock_sublime.get_clipboard.side_effect = RuntimeError("Clipboard access failed")

        # Inject mock into sys.modules
        monkeypatch.setitem(sys.modules, "sublime", mock_sublime)

        engine = PatternEngine()
        pattern = Pattern(name="Test", regex=r"Clip: {{CLIPBOARD}}", type=PatternType.DYNAMIC)
        result = engine.resolve_pattern(pattern)

        # Should fallback to empty string when Exception is raised
        assert result == "Clip: "
        # Verify sublime.get_clipboard() was called
        mock_sublime.get_clipboard.assert_called_once()
