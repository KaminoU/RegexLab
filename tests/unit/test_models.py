"""
Unit tests for core models (Pattern, PatternType, Portfolio).

Tests cover:
- Pattern creation, validation, resolution
- Portfolio CRUD operations
- JSON serialization/deserialization
- Edge cases and error handling
"""

import pytest
from src.core.models import Pattern, PatternType, Portfolio


class TestPatternType:
    """Test PatternType enum."""

    def test_pattern_type_values(self) -> None:
        """Test PatternType enum values."""
        assert PatternType.STATIC.value == "static"
        assert PatternType.DYNAMIC.value == "dynamic"

    def test_pattern_type_str(self) -> None:
        """Test PatternType string conversion."""
        assert str(PatternType.STATIC) == "static"
        assert str(PatternType.DYNAMIC) == "dynamic"


class TestPattern:
    """Test Pattern dataclass."""

    def test_create_static_pattern(self) -> None:
        """Test creating a static pattern."""
        pattern = Pattern(
            name="TODO Comments",
            regex=r"\bTODO\b.*",
            type=PatternType.STATIC,
            description="Find TODO comments",
        )

        assert pattern.name == "TODO Comments"
        assert pattern.regex == r"\bTODO\b.*"
        assert pattern.type == PatternType.STATIC
        assert pattern.description == "Find TODO comments"
        assert pattern.variables == []
        assert not pattern.is_dynamic()

    def test_create_dynamic_pattern(self) -> None:
        """Test creating a dynamic pattern."""
        pattern = Pattern(
            name="User TODO",
            regex=r"TODO \({{{USERNAME}}}\).*",
            type=PatternType.DYNAMIC,
            description="Find TODO by user",
        )

        assert pattern.name == "User TODO"
        assert pattern.type == PatternType.DYNAMIC
        assert pattern.variables == ["USERNAME"]
        assert pattern.is_dynamic()

    def test_create_pattern_with_string_type(self) -> None:
        """Test creating pattern with string type (auto-conversion)."""
        pattern = Pattern(
            name="Test",
            regex=r"\btest\b",
            type="static",  # type: ignore
        )

        assert pattern.type == PatternType.STATIC

    def test_auto_detect_variables(self) -> None:
        """Test automatic variable detection in dynamic patterns."""
        pattern = Pattern(
            name="Multi Var",
            regex=r"TODO \({{USERNAME}}\) \[{{DATE}}\] - {{PRIORITY}}",
            type=PatternType.DYNAMIC,
        )

        assert set(pattern.variables) == {"USERNAME", "DATE", "PRIORITY"}

    def test_auto_detect_variables_with_duplicates(self) -> None:
        """Test variable detection removes duplicates."""
        pattern = Pattern(
            name="Duplicate Vars",
            regex=r"{{FOO}} and {{BAR}} and {{FOO}}",
            type=PatternType.DYNAMIC,
        )

        assert pattern.variables == ["FOO", "BAR"]

    def test_pattern_empty_name_raises(self) -> None:
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Pattern name cannot be empty"):
            Pattern(name="", regex=r"\btest\b", type=PatternType.STATIC)

    def test_pattern_empty_regex_raises(self) -> None:
        """Test that empty regex raises ValueError."""
        with pytest.raises(ValueError, match="Pattern regex cannot be empty"):
            Pattern(name="Test", regex="", type=PatternType.STATIC)

    def test_pattern_invalid_regex_raises(self) -> None:
        """Test that invalid regex syntax raises ValueError."""
        with pytest.raises(ValueError, match="Invalid regex syntax"):
            Pattern(name="Bad Regex", regex=r"[unclosed", type=PatternType.STATIC)

    def test_resolve_static_pattern(self) -> None:
        """Test resolving a static pattern returns regex as-is."""
        pattern = Pattern(name="Static", regex=r"\bTODO\b", type=PatternType.STATIC)

        resolved = pattern.resolve()
        assert resolved == r"\bTODO\b"

    def test_resolve_dynamic_pattern(self) -> None:
        """Test resolving a dynamic pattern with variables."""
        pattern = Pattern(
            name="Dynamic",
            regex=r"TODO \({{USERNAME}}\)",
            type=PatternType.DYNAMIC,
        )

        resolved = pattern.resolve({"USERNAME": "Alice"})
        assert resolved == r"TODO \(Alice\)"

    def test_resolve_dynamic_with_special_chars(self) -> None:
        """Test resolving does NOT escape special chars (user can use regex in values)."""
        pattern = Pattern(
            name="Special",
            regex=r"{{TEXT}}",
            type=PatternType.DYNAMIC,
        )

        # No more escaping! User value passed as-is
        resolved = pattern.resolve({"TEXT": "foo.*bar"})
        assert resolved == r"foo.*bar"  # NOT escaped - user can use regex

    def test_resolve_dynamic_keeps_placeholder_when_value_is_none(self) -> None:
        """Test that placeholders remain untouched when provided value is None."""
        pattern = Pattern(
            name="Optional",
            regex=r"Hello {{NAME}}",
            type=PatternType.DYNAMIC,
        )

        resolved = pattern.resolve({"NAME": None})  # type: ignore[arg-type]

        assert resolved == "Hello {{NAME}}"

    def test_resolve_dynamic_missing_variables_raises(self) -> None:
        """Test that resolving without variables raises ValueError."""
        pattern = Pattern(
            name="Dynamic",
            regex=r"{{USERNAME}}",
            type=PatternType.DYNAMIC,
        )

        with pytest.raises(ValueError, match="requires variables"):
            pattern.resolve()

    def test_resolve_dynamic_incomplete_variables_raises(self) -> None:
        """Test that resolving with missing variables raises ValueError."""
        pattern = Pattern(
            name="Multi",
            regex=r"{{USERNAME}} {{DATE}}",
            type=PatternType.DYNAMIC,
        )

        with pytest.raises(ValueError, match="Missing variables"):
            pattern.resolve({"USERNAME": "Alice"})  # Missing 'DATE'

    def test_resolve_dynamic_case_insensitive(self) -> None:
        """Test that variables are case-insensitive."""
        # Mix of cases in regex
        pattern = Pattern(
            name="MixedCase",
            regex=r"{{Date}} - {{TIME}} - {{username}}",
            type=PatternType.DYNAMIC,
        )

        # Variables should be normalized to uppercase
        assert pattern.variables == ["DATE", "TIME", "USERNAME"]

        # Resolve with mixed case keys - should work
        resolved = pattern.resolve(
            {
                "date": "2025-10-20",  # lowercase
                "TIME": "14:30",  # uppercase
                "UsErNaMe": "Michel",  # mixed case
            }
        )
        assert resolved == r"2025-10-20 - 14:30 - Michel"

    def test_pattern_to_dict(self) -> None:
        """Test converting pattern to dictionary."""
        pattern = Pattern(
            name="Test",
            regex=r"\btest\b",
            type=PatternType.STATIC,
            description="Test pattern",
        )

        data = pattern.to_dict()
        assert data == {
            "name": "Test",
            "regex": r"\btest\b",
            "type": "static",
            "description": "Test pattern",
        }

    def test_pattern_from_dict(self) -> None:
        """Test creating pattern from dictionary (with legacy 'variables' key ignored)."""
        data = {
            "name": "Test",
            "regex": r"\btest\b",
            "type": "static",
            "description": "Test pattern",
            "variables": [],  # Legacy key - should be ignored
        }

        pattern = Pattern.from_dict(data)
        assert pattern.name == "Test"
        assert pattern.regex == r"\btest\b"
        assert pattern.type == PatternType.STATIC
        assert pattern.description == "Test pattern"

    def test_pattern_from_dict_minimal(self) -> None:
        """Test creating pattern from minimal dictionary."""
        data = {
            "name": "Minimal",
            "regex": r"\btest\b",
            "type": "static",
        }

        pattern = Pattern.from_dict(data)
        assert pattern.name == "Minimal"
        assert pattern.description == ""
        assert pattern.variables == []

    def test_pattern_with_valid_default_panel_find(self) -> None:
        """Test creating pattern with valid default_panel='find'."""
        pattern = Pattern(
            name="Email",
            regex=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            type=PatternType.STATIC,
            default_panel="find",
        )
        assert pattern.default_panel == "find"

    def test_pattern_with_valid_default_panel_replace(self) -> None:
        """Test creating pattern with valid default_panel='replace'."""
        pattern = Pattern(
            name="Refactor",
            regex=r"old_function_name",
            type=PatternType.STATIC,
            default_panel="replace",
        )
        assert pattern.default_panel == "replace"

    def test_pattern_with_valid_default_panel_find_in_files(self) -> None:
        """Test creating pattern with valid default_panel='find_in_files'."""
        pattern = Pattern(
            name="TODO Comments",
            regex=r"TODO:\s*(.+)",
            type=PatternType.STATIC,
            default_panel="find_in_files",
        )
        assert pattern.default_panel == "find_in_files"

    def test_pattern_with_invalid_default_panel_raises(self) -> None:
        """Test creating pattern with invalid default_panel raises ValueError."""
        with pytest.raises(ValueError, match="Invalid default_panel 'invalid_panel'"):
            Pattern(
                name="Invalid",
                regex=r"\btest\b",
                type=PatternType.STATIC,
                default_panel="invalid_panel",
            )

    def test_pattern_with_none_default_panel(self) -> None:
        """Test creating pattern with default_panel=None (default behavior)."""
        pattern = Pattern(
            name="Flexible",
            regex=r"\btest\b",
            type=PatternType.STATIC,
            default_panel=None,
        )
        assert pattern.default_panel is None

    def test_pattern_to_dict_with_default_panel(self) -> None:
        """Test pattern to_dict includes default_panel when set."""
        pattern = Pattern(
            name="Logs",
            regex=r"ERROR:.*",
            type=PatternType.STATIC,
            default_panel="find_in_files",
        )
        data = pattern.to_dict()
        assert data["default_panel"] == "find_in_files"

    def test_pattern_to_dict_without_default_panel(self) -> None:
        """Test pattern to_dict excludes default_panel when None."""
        pattern = Pattern(
            name="Simple",
            regex=r"\btest\b",
            type=PatternType.STATIC,
        )
        data = pattern.to_dict()
        assert "default_panel" not in data

    def test_pattern_from_dict_with_default_panel(self) -> None:
        """Test creating pattern from dict with default_panel."""
        data = {
            "name": "Application Logs",
            "regex": r"\[ERROR\].*",
            "type": "static",
            "description": "Error logs",
            "default_panel": "find_in_files",
        }
        pattern = Pattern.from_dict(data)
        assert pattern.default_panel == "find_in_files"

    def test_pattern_from_dict_without_default_panel(self) -> None:
        """Test creating pattern from dict without default_panel (backward compat)."""
        data = {
            "name": "Old Pattern",
            "regex": r"\btest\b",
            "type": "static",
        }
        pattern = Pattern.from_dict(data)
        assert pattern.default_panel is None


class TestPortfolio:
    """Test Portfolio dataclass."""

    def test_create_empty_portfolio(self) -> None:
        """Test creating an empty portfolio."""
        portfolio = Portfolio(name="My Portfolio", description="Test portfolio")

        assert portfolio.name == "My Portfolio"
        assert portfolio.description == "Test portfolio"
        assert portfolio.version == "1.0.0"
        assert portfolio.patterns == []

    def test_create_portfolio_with_patterns(self) -> None:
        """Test creating portfolio with initial patterns."""
        pattern1 = Pattern(name="P1", regex=r"\bfoo\b", type=PatternType.STATIC)
        pattern2 = Pattern(name="P2", regex=r"\bbar\b", type=PatternType.STATIC)

        portfolio = Portfolio(name="Test", patterns=[pattern1, pattern2])

        assert len(portfolio.patterns) == 2
        assert portfolio.patterns[0].name == "P1"
        assert portfolio.patterns[1].name == "P2"

    def test_portfolio_empty_name_raises(self) -> None:
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Portfolio name cannot be empty"):
            Portfolio(name="")

    def test_portfolio_duplicate_names_raises(self) -> None:
        """Test that duplicate pattern names raise ValueError."""
        pattern1 = Pattern(name="Duplicate", regex=r"\bfoo\b", type=PatternType.STATIC)
        pattern2 = Pattern(name="Duplicate", regex=r"\bbar\b", type=PatternType.STATIC)

        with pytest.raises(ValueError, match="Duplicate pattern names"):
            Portfolio(name="Test", patterns=[pattern1, pattern2])

    def test_add_pattern(self) -> None:
        """Test adding a pattern to portfolio."""
        portfolio = Portfolio(name="Test")
        pattern = Pattern(name="New", regex=r"\btest\b", type=PatternType.STATIC)

        portfolio.add_pattern(pattern)

        assert len(portfolio.patterns) == 1
        assert portfolio.patterns[0].name == "New"

    def test_add_pattern_duplicate_raises(self) -> None:
        """Test that adding duplicate pattern raises ValueError."""
        portfolio = Portfolio(name="Test")
        pattern1 = Pattern(name="Dup", regex=r"\bfoo\b", type=PatternType.STATIC)
        pattern2 = Pattern(name="Dup", regex=r"\bbar\b", type=PatternType.STATIC)

        portfolio.add_pattern(pattern1)

        with pytest.raises(ValueError, match="already exists"):
            portfolio.add_pattern(pattern2)

    def test_remove_pattern(self) -> None:
        """Test removing a pattern from portfolio."""
        pattern = Pattern(name="ToRemove", regex=r"\btest\b", type=PatternType.STATIC)
        portfolio = Portfolio(name="Test", patterns=[pattern])

        result = portfolio.remove_pattern("ToRemove")

        assert result is True
        assert len(portfolio.patterns) == 0

    def test_remove_pattern_not_found(self) -> None:
        """Test removing non-existent pattern returns False."""
        portfolio = Portfolio(name="Test")

        result = portfolio.remove_pattern("NonExistent")

        assert result is False

    def test_get_pattern(self) -> None:
        """Test getting a pattern by name."""
        pattern = Pattern(name="Find", regex=r"\btest\b", type=PatternType.STATIC)
        portfolio = Portfolio(name="Test", patterns=[pattern])

        found = portfolio.get_pattern("Find")

        assert found is not None
        assert found.name == "Find"

    def test_get_pattern_not_found(self) -> None:
        """Test getting non-existent pattern returns None."""
        portfolio = Portfolio(name="Test")

        found = portfolio.get_pattern("NonExistent")

        assert found is None

    def test_list_patterns_all(self) -> None:
        """Test listing all patterns."""
        pattern1 = Pattern(name="P1", regex=r"\bfoo\b", type=PatternType.STATIC)
        pattern2 = Pattern(name="P2", regex=r"\bbar\b", type=PatternType.STATIC)
        portfolio = Portfolio(name="Test", patterns=[pattern1, pattern2])

        patterns = portfolio.list_patterns()

        assert len(patterns) == 2
        assert patterns[0].name == "P1"
        assert patterns[1].name == "P2"

    def test_list_patterns_by_type(self) -> None:
        """Test listing patterns filtered by type."""
        static = Pattern(name="Static", regex=r"\bfoo\b", type=PatternType.STATIC)
        dynamic = Pattern(name="Dynamic", regex=r"{{BAR}}", type=PatternType.DYNAMIC)
        portfolio = Portfolio(name="Test", patterns=[static, dynamic])

        static_patterns = portfolio.list_patterns(PatternType.STATIC)
        dynamic_patterns = portfolio.list_patterns(PatternType.DYNAMIC)

        assert len(static_patterns) == 1
        assert static_patterns[0].name == "Static"
        assert len(dynamic_patterns) == 1
        assert dynamic_patterns[0].name == "Dynamic"

    def test_portfolio_to_dict(self) -> None:
        """Test converting portfolio to dictionary."""
        pattern = Pattern(name="P1", regex=r"\btest\b", type=PatternType.STATIC)
        portfolio = Portfolio(
            name="Test Portfolio",
            description="Test desc",
            version="1.0.0",
            patterns=[pattern],
        )

        data = portfolio.to_dict()

        assert data["name"] == "Test Portfolio"
        assert data["description"] == "Test desc"
        assert data["version"] == "1.0.0"
        assert len(data["patterns"]) == 1
        assert data["patterns"][0]["name"] == "P1"

    def test_portfolio_from_dict(self) -> None:
        """Test creating portfolio from dictionary."""
        data = {
            "name": "Test Portfolio",
            "description": "Test desc",
            "version": "1.0.0",
            "patterns": [
                {
                    "name": "P1",
                    "regex": r"\btest\b",
                    "type": "static",
                    "description": "",
                    "variables": [],
                }
            ],
        }

        portfolio = Portfolio.from_dict(data)

        assert portfolio.name == "Test Portfolio"
        assert portfolio.description == "Test desc"
        assert portfolio.version == "1.0.0"
        assert len(portfolio.patterns) == 1
        assert portfolio.patterns[0].name == "P1"

    def test_portfolio_from_dict_minimal(self) -> None:
        """Test creating portfolio from minimal dictionary."""
        data = {
            "name": "Minimal",
        }

        portfolio = Portfolio.from_dict(data)

        assert portfolio.name == "Minimal"
        assert portfolio.description == ""
        assert portfolio.version == "1.0.0"
        assert portfolio.patterns == []


class TestPortfolioEdgeCases:
    """Test Portfolio edge cases and error handling."""

    def test_add_pattern_duplicate_name(self) -> None:
        """Test adding pattern with duplicate name raises ValueError."""
        pattern1 = Pattern(name="Same", regex=r"\btest\b", type=PatternType.STATIC)
        pattern2 = Pattern(name="Same", regex=r"\bdifferent\b", type=PatternType.STATIC)
        portfolio = Portfolio(name="Test", patterns=[pattern1])

        with pytest.raises(ValueError, match="Pattern 'Same' already exists in portfolio"):
            portfolio.add_pattern(pattern2)

    def test_remove_pattern_readonly_raises(self) -> None:
        """Test removing pattern from readonly portfolio raises ValueError."""
        pattern = Pattern(name="P1", regex=r"\btest\b", type=PatternType.STATIC)
        portfolio = Portfolio(name="Test", patterns=[pattern], readonly=True)

        with pytest.raises(ValueError, match="Cannot remove pattern from readonly portfolio"):
            portfolio.remove_pattern("P1")

    def test_to_dict_with_all_metadata(self) -> None:
        """Test to_dict includes all optional metadata fields."""
        pattern = Pattern(name="P1", regex=r"\btest\b", type=PatternType.STATIC)
        portfolio = Portfolio(
            name="Full Portfolio",
            description="Full description",
            version="2.0.0",
            patterns=[pattern],
            author="Alice",
            created="2024-01-01",
            updated="2024-01-15",
            tags=["tag1", "tag2"],
            readonly=True,
        )

        data = portfolio.to_dict()

        assert data["name"] == "Full Portfolio"
        assert data["description"] == "Full description"
        assert data["version"] == "2.0.0"
        assert data["author"] == "Alice"
        assert data["created"] == "2024-01-01"
        assert data["updated"] == "2024-01-15"
        assert data["tags"] == ["tag1", "tag2"]
        assert data["readonly"] is True


class TestPatternEdgeCases:
    """Test Pattern edge cases and error handling."""

    def test_add_pattern_to_readonly_portfolio_raises(self) -> None:
        """Test that adding a pattern to a readonly portfolio raises ValueError (line 246)."""
        portfolio = Portfolio(
            name="Readonly Portfolio",
            readonly=True,
            patterns=[],
        )

        new_pattern = Pattern(name="NewPattern", regex=r"\btest\b", type=PatternType.STATIC)

        with pytest.raises(ValueError, match="Cannot add pattern to readonly portfolio"):
            portfolio.add_pattern(new_pattern)
