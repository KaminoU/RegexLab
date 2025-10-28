"""
Unit tests for PortfolioService.

Tests cover:
- Active portfolio management
- Pattern CRUD operations via service
- Portfolio loading/saving via service
- Export/import operations
- Edge cases and error handling
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from src.core.models import Pattern, PatternType, Portfolio
from src.core.portfolio_manager import PortfolioManager
from src.services.portfolio_service import PortfolioService


class TestPortfolioServiceInit:
    """Test PortfolioService initialization."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        PortfolioManager.reset_instance()

    def test_init_default_manager(self) -> None:
        """Test initialization with default portfolio manager."""
        service = PortfolioService()

        assert service.portfolio_manager is not None
        assert isinstance(service.portfolio_manager, PortfolioManager)

    def test_init_custom_manager(self) -> None:
        """Test initialization with custom portfolio manager."""
        custom_manager = PortfolioManager.get_instance()
        service = PortfolioService(portfolio_manager=custom_manager)

        assert service.portfolio_manager is custom_manager


class TestPortfolioServiceActivePortfolio:
    """Test active portfolio management."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        PortfolioManager.reset_instance()
        self.service = PortfolioService()

    def test_get_active_portfolio_none_by_default(self) -> None:
        """Test that no portfolio is active by default."""
        assert self.service.get_active_portfolio() is None
        assert not self.service.has_active_portfolio()

    def test_set_active_portfolio(self) -> None:
        """Test setting an active portfolio."""
        portfolio = Portfolio(name="Test Portfolio")
        self.service.set_active_portfolio(portfolio)

        assert self.service.get_active_portfolio() is portfolio
        assert self.service.has_active_portfolio()

    def test_get_active_patterns_no_portfolio(self) -> None:
        """Test getting patterns when no portfolio is active."""
        patterns = self.service.get_active_patterns()

        assert patterns == []

    def test_get_active_patterns(self) -> None:
        """Test getting patterns from active portfolio."""
        p1 = Pattern(name="P1", regex=r"\d+", type=PatternType.STATIC)
        p2 = Pattern(name="P2", regex=r"\w+", type=PatternType.STATIC)
        portfolio = Portfolio(name="Test", patterns=[p1, p2])

        self.service.set_active_portfolio(portfolio)
        patterns = self.service.get_active_patterns()

        assert len(patterns) == 2
        assert p1 in patterns
        assert p2 in patterns


class TestPortfolioServicePatternOperations:
    """Test pattern CRUD operations via service."""

    def setup_method(self) -> None:
        """Reset singleton and setup test portfolio."""
        PortfolioManager.reset_instance()
        self.service = PortfolioService()
        self.portfolio = Portfolio(name="Test Portfolio")
        self.service.set_active_portfolio(self.portfolio)

    def test_add_pattern(self) -> None:
        """Test adding a pattern to active portfolio."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)

        self.service.add_pattern(pattern)

        assert len(self.service.get_active_patterns()) == 1
        assert self.service.get_pattern_by_name("Test") is pattern

    def test_add_pattern_no_active_portfolio_raises(self) -> None:
        """Test that adding pattern without active portfolio raises."""
        PortfolioManager.reset_instance()
        service = PortfolioService()
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)

        with pytest.raises(ValueError, match="No active portfolio"):
            service.add_pattern(pattern)

    def test_remove_pattern(self) -> None:
        """Test removing a pattern from active portfolio."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)
        self.service.add_pattern(pattern)

        result = self.service.remove_pattern("Test")

        assert result is True
        assert len(self.service.get_active_patterns()) == 0

    def test_remove_pattern_not_found(self) -> None:
        """Test removing a non-existent pattern."""
        result = self.service.remove_pattern("NonExistent")

        assert result is False

    def test_remove_pattern_no_active_portfolio_raises(self) -> None:
        """Test that removing pattern without active portfolio raises."""
        PortfolioManager.reset_instance()
        service = PortfolioService()

        with pytest.raises(ValueError, match="No active portfolio"):
            service.remove_pattern("Test")

    def test_get_pattern_by_name(self) -> None:
        """Test getting a specific pattern by name."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)
        self.service.add_pattern(pattern)

        found = self.service.get_pattern_by_name("Test")

        assert found is pattern

    def test_get_pattern_by_name_not_found(self) -> None:
        """Test getting a non-existent pattern."""
        found = self.service.get_pattern_by_name("NonExistent")

        assert found is None

    def test_get_pattern_by_name_no_active_portfolio(self) -> None:
        """Test getting pattern when no portfolio is active."""
        PortfolioManager.reset_instance()
        service = PortfolioService()

        found = service.get_pattern_by_name("Test")

        assert found is None

    def test_get_patterns_by_type(self) -> None:
        """Test filtering patterns by type."""
        p1 = Pattern(name="Static", regex=r"\d+", type=PatternType.STATIC)
        p2 = Pattern(
            name="Dynamic",
            regex=r"LOG \[{{DATE}}\]",
            type=PatternType.DYNAMIC,
        )
        self.service.add_pattern(p1)
        self.service.add_pattern(p2)

        static_patterns = self.service.get_patterns_by_type(PatternType.STATIC)
        dynamic_patterns = self.service.get_patterns_by_type(PatternType.DYNAMIC)

        assert len(static_patterns) == 1
        assert static_patterns[0] is p1
        assert len(dynamic_patterns) == 1
        assert dynamic_patterns[0] is p2

    def test_get_patterns_by_type_no_active_portfolio(self) -> None:
        """Test filtering patterns when no portfolio is active."""
        PortfolioManager.reset_instance()
        service = PortfolioService()

        patterns = service.get_patterns_by_type(PatternType.STATIC)

        assert patterns == []


class TestPortfolioServiceLoadSave:
    """Test loading and saving portfolios via service."""

    def setup_method(self) -> None:
        """Reset singleton and create temp directory."""
        PortfolioManager.reset_instance()
        self.service = PortfolioService()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def test_load_portfolio(self) -> None:
        """Test loading a portfolio and setting it as active."""
        # Create and save a portfolio
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)
        portfolio = Portfolio(name="Test Portfolio", patterns=[pattern])
        portfolio_path = self.temp_path / "test.json"
        PortfolioManager.get_instance().save_portfolio(portfolio, portfolio_path)

        # Load it via service
        loaded = self.service.load_portfolio(portfolio_path)

        assert loaded.name == "Test Portfolio"
        assert len(loaded.patterns) == 1
        assert self.service.get_active_portfolio() is loaded

    def test_save_active_portfolio(self) -> None:
        """Test saving the active portfolio."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)
        portfolio = Portfolio(name="Test Portfolio", patterns=[pattern])
        self.service.set_active_portfolio(portfolio)

        portfolio_path = self.temp_path / "saved.json"
        self.service.save_active_portfolio(portfolio_path)

        assert portfolio_path.exists()

        # Verify by loading (reload=True since portfolio is already loaded)
        loaded = PortfolioManager.get_instance().load_portfolio(portfolio_path, reload=True)
        assert loaded.name == "Test Portfolio"
        assert len(loaded.patterns) == 1


class TestPortfolioServiceExportImport:
    """Test export/import operations."""

    def setup_method(self) -> None:
        """Reset singleton and create temp directory."""
        PortfolioManager.reset_instance()
        self.service = PortfolioService()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def test_export_portfolio(self) -> None:
        """Test exporting a portfolio."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)
        portfolio = Portfolio(name="Export Test", patterns=[pattern])

        export_path = self.temp_path / "exported.json"
        self.service.export_portfolio(portfolio, export_path)

        assert export_path.exists()

    def test_import_portfolio(self) -> None:
        """Test importing a portfolio."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)
        portfolio = Portfolio(name="Import Test", patterns=[pattern])

        # First export it
        export_path = self.temp_path / "to_import.json"
        self.service.export_portfolio(portfolio, export_path)

        # Then import it
        imported = self.service.import_portfolio(export_path)

        assert imported.name == "Import Test"
        assert len(imported.patterns) == 1
        assert imported.patterns[0].name == "Test"

    def test_export_portfolio_to_path_success(self) -> None:
        """Test exporting a portfolio with validation (success case)."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)
        portfolio = Portfolio(name="Export Test", patterns=[pattern])

        dest_path = str(self.temp_path / "exported_new.json")
        success, message = self.service.export_portfolio_to_path(portfolio, dest_path)

        assert success is True
        assert "exported successfully" in message
        assert Path(dest_path).exists()


class TestPortfolioServiceQuickWins:
    """Additional tests to cover uncovered service branches."""

    def setup_method(self) -> None:
        """Reset singleton and prepare temp directory."""
        PortfolioManager.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.service = PortfolioService()

    def test_add_pattern_to_portfolio_success_logs_and_saves(self) -> None:
        """Adding a pattern to a named portfolio should persist and log success."""
        portfolio_data = {
            "name": "QuickWin",
            "description": "",
            "version": "1.0.0",
            "patterns": [],
        }
        portfolio_path = self.temp_path / "quick.json"
        portfolio_path.write_text(json.dumps(portfolio_data), encoding="utf-8")

        manager = PortfolioManager.get_instance()
        manager.load_portfolio(portfolio_path)

        new_pattern = Pattern(name="New", regex=r"\d+", type=PatternType.STATIC)

        with patch.object(PortfolioManager, "save_portfolio", return_value=None) as save_mock, patch(
            "src.services.portfolio_service.logger"
        ) as mock_logger:
            result = self.service.add_pattern_to_portfolio("QuickWin", new_pattern)

        assert result is True
        save_mock.assert_called_once()
        mock_logger.info.assert_called_once_with("Pattern '%s' added to portfolio '%s'", "New", "QuickWin")

    def test_portfolio_exists_true_when_disabled_portfolio_matches(self) -> None:
        """portfolio_exists should return True when a disabled portfolio matches the name."""
        with patch.object(
            PortfolioService,
            "get_disabled_portfolios",
            return_value=[("disabled.json", {"name": "Archived"})],
        ):
            result = self.service.portfolio_exists("Archived", packages_path=str(self.temp_path))

        assert result is True

    def test_export_portfolio_to_path_write_failure_returns_error(self) -> None:
        """export_portfolio_to_path should surface file write errors."""
        pattern = Pattern(name="Err", regex=r"\w+", type=PatternType.STATIC)
        portfolio = Portfolio(name="ErrPortfolio", patterns=[pattern])
        dest_path = str(self.temp_path / "fail.json")

        with patch("builtins.open", side_effect=OSError("disk full")):
            success, message = self.service.export_portfolio_to_path(portfolio, dest_path)

        assert success is False
        assert "disk full" in message.lower()

    def test_export_portfolio_to_path_invalid_extension(self) -> None:
        """Test exporting with invalid extension."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)
        portfolio = Portfolio(name="Export Test", patterns=[pattern])

        dest_path = str(self.temp_path / "exported.txt")
        success, message = self.service.export_portfolio_to_path(portfolio, dest_path)

        assert success is False
        assert ".json extension" in message

    def test_export_portfolio_to_path_file_exists(self) -> None:
        """Test exporting to existing file."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)
        portfolio = Portfolio(name="Export Test", patterns=[pattern])

        # Create existing file
        existing_path = self.temp_path / "existing.json"
        existing_path.write_text("{}", encoding="utf-8")

        dest_path = str(existing_path)
        success, message = self.service.export_portfolio_to_path(portfolio, dest_path)

        assert success is False
        assert "already exists" in message

    def test_export_portfolio_to_path_builtin_portfolio(self) -> None:
        """Test exporting builtin portfolio works (no restriction)."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)
        portfolio = Portfolio(name="Builtin Test", patterns=[pattern], readonly=True)

        dest_path = str(self.temp_path / "builtin_export.json")
        success, message = self.service.export_portfolio_to_path(portfolio, dest_path)

        assert success is True
        assert "exported successfully" in message
        assert Path(dest_path).exists()
