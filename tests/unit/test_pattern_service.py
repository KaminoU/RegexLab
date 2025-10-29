"""
Unit tests for PatternService.

Tests cover:
- Pattern resolution (static and dynamic)
- Variable resolution
- Regex validation
- Pattern creation from text
- Custom variable management
- Formatting for Find panel
"""

from datetime import datetime

import pytest
from src.core.models import Pattern, PatternType
from src.core.pattern_engine import PatternEngine
from src.services.pattern_service import PatternService


class TestPatternServiceInit:
    """Test PatternService initialization."""

    def test_init_default_engine(self) -> None:
        """Test initialization with default pattern engine."""
        service = PatternService()

        assert service.pattern_engine is not None
        assert isinstance(service.pattern_engine, PatternEngine)

    def test_init_custom_engine(self) -> None:
        """Test initialization with custom pattern engine."""
        custom_engine = PatternEngine(date_format="%d/%m/%Y")
        service = PatternService(pattern_engine=custom_engine)

        assert service.pattern_engine is custom_engine

    def test_init_custom_formats_via_engine(self) -> None:
        """Test initialization with custom date/time formats via PatternEngine."""
        # Create custom PatternEngine with custom formats
        custom_engine = PatternEngine(date_format="%d/%m/%Y", time_format="%I:%M %p")
        service = PatternService(pattern_engine=custom_engine)

        # Test that the formats are applied
        today = datetime.now()
        expected_date = today.strftime("%d/%m/%Y")

        pattern = Pattern(
            name="Test",
            regex=r"{{DATE}}",
            type=PatternType.DYNAMIC,
        )
        resolved = service.resolve_pattern(pattern)

        assert expected_date in resolved


class TestPatternServiceResolvePattern:
    """Test pattern resolution."""

    def setup_method(self) -> None:
        """Create service instance."""
        self.service = PatternService()

    def test_resolve_static_pattern(self) -> None:
        """Test resolving a static pattern returns regex as-is."""
        pattern = Pattern(name="Static", regex=r"\d{{3}}-\d{{4}}", type=PatternType.STATIC)

        resolved = self.service.resolve_pattern(pattern)

        assert resolved == r"\d{{3}}-\d{{4}}"

    def test_resolve_dynamic_pattern_with_date(self) -> None:
        """Test resolving a dynamic pattern with date variable."""
        pattern = Pattern(
            name="DateLog",
            regex=r"LOG \[{{DATE}}\]",
            type=PatternType.DYNAMIC,
        )

        resolved = self.service.resolve_pattern(pattern)

        # Should contain today's date - no escaping, simple replacement
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in resolved

    def test_resolve_dynamic_pattern_with_custom_variables(self) -> None:
        """Test resolving with custom variables."""
        pattern = Pattern(
            name="Custom",
            regex=r"User: {{USERNAME}}",
            type=PatternType.DYNAMIC,
        )

        resolved = self.service.resolve_pattern(pattern, custom_variables={"USERNAME": "alice"})

        assert "alice" in resolved

    def test_resolve_pattern_unknown_variable_raises(self) -> None:
        """Test that unknown variables raise ValueError."""
        pattern = Pattern(
            name="Unknown",
            regex=r"{{UNKNOWN_VAR}}",
            type=PatternType.DYNAMIC,
        )

        with pytest.raises(ValueError, match="Unknown variable"):
            self.service.resolve_pattern(pattern)


class TestPatternServiceVariables:
    """Test variable operations."""

    def setup_method(self) -> None:
        """Create service instance."""
        self.service = PatternService()

    def test_get_pattern_variables(self) -> None:
        """Test getting variables from a pattern."""
        pattern = Pattern(
            name="Multi",
            regex=r"{{DATE}} - {{TIME}} - {{USERNAME}}",
            type=PatternType.DYNAMIC,
        )

        variables = self.service.get_pattern_variables(pattern)

        # Variables are returned in UPPERCASE
        assert variables == ["DATE", "TIME", "USERNAME"]

    def test_resolve_variables(self) -> None:
        """Test resolving all variables to their values."""
        pattern = Pattern(
            name="Test",
            regex=r"{{DATE}} {{TIME}}",
            type=PatternType.DYNAMIC,
        )

        resolved = self.service.resolve_variables(pattern)

        assert "DATE" in resolved
        assert "TIME" in resolved
        # Values should be actual date/time strings
        assert len(resolved["DATE"]) > 0
        assert len(resolved["TIME"]) > 0

    def test_resolve_variables_with_custom(self) -> None:
        """Test resolving variables with custom overrides."""
        pattern = Pattern(
            name="Test",
            regex=r"{{CUSTOM}}",
            type=PatternType.DYNAMIC,
        )

        resolved = self.service.resolve_variables(pattern, custom_variables={"CUSTOM": "my_value"})

        assert resolved["CUSTOM"] == "my_value"

    def test_add_custom_variable(self) -> None:
        """Test adding a custom variable."""
        self.service.add_custom_variable("project", "RegexLab")

        variables = self.service.get_custom_variables()

        assert "PROJECT" in variables
        assert variables["PROJECT"] == "RegexLab"

    def test_remove_custom_variable(self) -> None:
        """Test removing a custom variable."""
        self.service.add_custom_variable("temp", "value")

        result = self.service.remove_custom_variable("temp")

        assert result is True
        assert "temp" not in self.service.get_custom_variables()

    def test_remove_nonexistent_variable(self) -> None:
        """Test removing a non-existent variable."""
        result = self.service.remove_custom_variable("nonexistent")

        assert result is False


class TestPatternServiceValidation:
    """Test regex validation."""

    def setup_method(self) -> None:
        """Create service instance."""
        self.service = PatternService()

    def test_validate_regex_valid(self) -> None:
        """Test validating a correct regex."""
        valid_patterns = [
            r"\d+",
            r"\w{3,10}",
            r"[a-z]+",
            r"(?:foo|bar)",
            r"\bword\b",
        ]

        for regex in valid_patterns:
            assert self.service.validate_regex(regex) is True

    def test_validate_regex_invalid(self) -> None:
        """Test validating an incorrect regex."""
        invalid_patterns = [
            r"[",  # Unclosed bracket
            r"(?P<",  # Incomplete named group
            r"*",  # Invalid quantifier
            r"(?P<name>.*(?P<name>.*)",  # Duplicate group name
        ]

        for regex in invalid_patterns:
            assert self.service.validate_regex(regex) is False


class TestPatternServiceCreateFromText:
    """Test creating patterns from text."""

    def setup_method(self) -> None:
        """Create service instance."""
        self.service = PatternService()

    def test_create_pattern_basic(self) -> None:
        """Test creating a basic pattern from text."""
        pattern = self.service.create_pattern_from_text(text="hello", name="HelloPattern")

        assert pattern.name == "HelloPattern"
        assert pattern.type == PatternType.STATIC
        assert "hello" in pattern.regex

    def test_create_pattern_escapes_special_chars(self) -> None:
        """Test that special regex characters are escaped."""
        pattern = self.service.create_pattern_from_text(text="$100.00", name="PricePattern")

        # $ and . should be escaped
        assert r"\$" in pattern.regex
        assert r"\." in pattern.regex

    def test_create_pattern_with_word_boundary(self) -> None:
        """Test creating pattern with word boundaries."""
        pattern = self.service.create_pattern_from_text(text="word", name="WordPattern", word_boundary=True)

        assert r"\b" in pattern.regex

    def test_create_pattern_empty_text_raises(self) -> None:
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Cannot create pattern from empty text"):
            self.service.create_pattern_from_text(text="", name="Empty")

    def test_create_pattern_with_description(self) -> None:
        """Test creating pattern with custom description."""
        pattern = self.service.create_pattern_from_text(text="test", name="Test", description="Custom description")

        assert pattern.description == "Custom description"

    def test_create_pattern_default_description(self) -> None:
        """Test that default description is generated."""
        pattern = self.service.create_pattern_from_text(text="test", name="Test")

        assert "Pattern created from selection" in pattern.description


class TestPatternServiceUtilities:
    """Test utility methods."""

    def setup_method(self) -> None:
        """Create service instance."""
        self.service = PatternService()

    def test_is_dynamic_pattern_static(self) -> None:
        """Test checking if static pattern is dynamic."""
        pattern = Pattern(name="Static", regex=r"\d+", type=PatternType.STATIC)

        assert self.service.is_dynamic_pattern(pattern) is False

    def test_is_dynamic_pattern_dynamic(self) -> None:
        """Test checking if dynamic pattern is dynamic."""
        pattern = Pattern(
            name="Dynamic",
            regex=r"{{DATE}}",
            type=PatternType.DYNAMIC,
        )

        assert self.service.is_dynamic_pattern(pattern) is True

    def test_format_for_find_panel_static(self) -> None:
        """Test formatting static pattern for Find panel."""
        pattern = Pattern(name="Static", regex=r"\d{{3}}", type=PatternType.STATIC)

        formatted = self.service.format_for_find_panel(pattern)

        assert formatted == r"\d{{3}}"

    def test_format_for_find_panel_dynamic(self) -> None:
        """Test formatting dynamic pattern for Find panel."""
        pattern = Pattern(
            name="Dynamic",
            regex=r"LOG {{DATE}}",
            type=PatternType.DYNAMIC,
        )

        formatted = self.service.format_for_find_panel(pattern)

        # Should contain resolved date - no escaping, simple replacement
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in formatted

    def test_format_for_find_panel_with_custom_variables(self) -> None:
        """Test formatting with custom variables."""
        pattern = Pattern(
            name="Custom",
            regex=r"User: {{USER}}",
            type=PatternType.DYNAMIC,
        )

        formatted = self.service.format_for_find_panel(pattern, custom_variables={"USER": "bob"})

        assert "bob" in formatted
