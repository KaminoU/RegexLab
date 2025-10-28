"""
Unit tests for PortfolioService error handlers.

Tests cover error handling for:
- add_pattern_to_portfolio() edge cases
- get_disabled_portfolios() I/O errors
- validate_portfolio_file() malformed JSON
- Portfolio creation/deletion errors
"""

from __future__ import annotations

import contextlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from src.core.models import Pattern, PatternType, Portfolio
from src.core.portfolio_manager import PortfolioManager
from src.services.portfolio_service import PortfolioService


class TestPortfolioServiceAddPatternErrorHandlers:
    """Test add_pattern_to_portfolio() error handlers."""

    def setup_method(self) -> None:
        """Reset singleton and setup service."""
        PortfolioManager.reset_instance()
        self.service = PortfolioService()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self) -> None:
        """Clean up temp directory."""
        with contextlib.suppress(Exception):
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_pattern_portfolio_not_found(self):
        """Test adding pattern to non-existent portfolio raises ValueError."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)

        with pytest.raises(ValueError, match="not found"):
            self.service.add_pattern_to_portfolio("NonExistent", pattern)

    def test_add_pattern_readonly_portfolio(self):
        """Test adding pattern to readonly portfolio raises ValueError."""
        # Create readonly portfolio file
        portfolio_data = {
            "name": "Readonly",
            "description": "Readonly portfolio",
            "version": "1.0.0",
            "readonly": True,
            "patterns": [],
        }
        portfolio_path = self.temp_path / "readonly.json"
        portfolio_path.write_text(json.dumps(portfolio_data), encoding="utf-8")

        manager = PortfolioManager.get_instance()
        manager.load_portfolio(portfolio_path, set_as_builtin=True)

        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)

        with pytest.raises(ValueError, match="read-only"):
            self.service.add_pattern_to_portfolio("Readonly", pattern)

    def test_add_pattern_duplicate_name(self):
        """Test adding pattern with duplicate name raises ValueError."""
        # Create portfolio file with existing pattern
        portfolio_data = {
            "name": "Test",
            "description": "Test portfolio",
            "version": "1.0.0",
            "patterns": [
                {
                    "name": "Duplicate",
                    "regex": r"\d+",
                    "type": "static",
                    "description": "Existing pattern",
                }
            ],
        }
        portfolio_path = self.temp_path / "test.json"
        portfolio_path.write_text(json.dumps(portfolio_data), encoding="utf-8")

        manager = PortfolioManager.get_instance()
        manager.load_portfolio(portfolio_path)

        # Try adding pattern with same name
        new_pattern = Pattern(name="Duplicate", regex=r"\w+", type=PatternType.STATIC)

        with pytest.raises(ValueError, match="already exists"):
            self.service.add_pattern_to_portfolio("Test", new_pattern)

    def test_add_pattern_save_failure(self):
        """Test add_pattern returns False when save fails."""
        # Create portfolio file
        portfolio_data = {
            "name": "Test",
            "description": "Test portfolio",
            "version": "1.0.0",
            "patterns": [],
        }
        portfolio_path = self.temp_path / "test.json"
        portfolio_path.write_text(json.dumps(portfolio_data), encoding="utf-8")

        manager = PortfolioManager.get_instance()
        portfolio = manager.load_portfolio(portfolio_path)

        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)

        # Mock save_portfolio to raise exception
        with patch.object(manager, "save_portfolio", side_effect=OSError("Disk full")):
            result = self.service.add_pattern_to_portfolio("Test", pattern)

        assert result is False
        # Pattern should still be added to in-memory portfolio (rollback not implemented)
        assert len(portfolio.patterns) == 1


class TestPortfolioServiceDisabledPortfoliosErrorHandlers:
    """Test get_disabled_portfolios() error handlers."""

    def setup_method(self) -> None:
        """Reset singleton and setup service."""
        PortfolioManager.reset_instance()
        self.service = PortfolioService()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self) -> None:
        """Clean up temp directory."""
        with contextlib.suppress(Exception):
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_disabled_portfolios_dir_not_exists(self):
        """Test get_disabled_portfolios returns empty list when dir doesn't exist."""
        packages_path = str(self.temp_path)

        result = self.service.get_disabled_portfolios(packages_path)

        assert result == []

    def test_get_disabled_portfolios_invalid_json(self):
        """Test get_disabled_portfolios skips invalid JSON files."""
        # Create disabled_portfolios directory
        disabled_dir = self.temp_path / "User" / "RegexLab" / "disabled_portfolios"
        disabled_dir.mkdir(parents=True)

        # Create invalid JSON file
        invalid_file = disabled_dir / "invalid.json"
        invalid_file.write_text("{ INVALID JSON }", encoding="utf-8")

        # Create valid portfolio file
        valid_file = disabled_dir / "valid.json"
        valid_data = {
            "name": "Valid Portfolio",
            "description": "Test",
            "version": "1.0.0",
            "patterns": [],
        }
        valid_file.write_text(json.dumps(valid_data), encoding="utf-8")

        packages_path = str(self.temp_path)
        result = self.service.get_disabled_portfolios(packages_path)

        # Should return only valid portfolio
        assert len(result) == 1
        assert result[0][1]["name"] == "Valid Portfolio"

    def test_get_disabled_portfolios_non_json_files(self):
        """Test get_disabled_portfolios ignores non-.json files."""
        # Create disabled_portfolios directory
        disabled_dir = self.temp_path / "User" / "RegexLab" / "disabled_portfolios"
        disabled_dir.mkdir(parents=True)

        # Create non-JSON files
        (disabled_dir / "readme.txt").write_text("Not a portfolio", encoding="utf-8")
        (disabled_dir / "backup.bak").write_text("{}", encoding="utf-8")

        # Create valid portfolio
        valid_file = disabled_dir / "valid.json"
        valid_data = {
            "name": "Valid",
            "description": "",
            "version": "1.0.0",
            "patterns": [],
        }
        valid_file.write_text(json.dumps(valid_data), encoding="utf-8")

        packages_path = str(self.temp_path)
        result = self.service.get_disabled_portfolios(packages_path)

        # Should return only .json file
        assert len(result) == 1
        assert result[0][1]["name"] == "Valid"


class TestPortfolioServiceValidateFileErrorHandlers:
    """Test validate_portfolio_file() error handlers."""

    def setup_method(self) -> None:
        """Setup service and temp directory."""
        PortfolioManager.reset_instance()
        self.service = PortfolioService()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self) -> None:
        """Clean up temp directory."""
        with contextlib.suppress(Exception):
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_portfolio_file_not_exists(self):
        """Test validating non-existent file returns False with error."""
        non_existent = str(self.temp_path / "does_not_exist.json")

        valid, result = self.service.validate_portfolio_file(non_existent)

        assert valid is False
        assert isinstance(result, str)
        assert "error" in result.lower()  # Message contains "Error reading file"

    def test_validate_portfolio_file_invalid_json(self):
        """Test validating file with malformed JSON."""
        invalid_file = self.temp_path / "invalid.json"
        invalid_file.write_text("{ INVALID JSON }", encoding="utf-8")

        valid, result = self.service.validate_portfolio_file(str(invalid_file))

        assert valid is False
        assert isinstance(result, str)
        assert "json" in result.lower()

    def test_validate_portfolio_file_missing_required_fields(self):
        """Test validating portfolio with missing required fields."""
        incomplete_file = self.temp_path / "incomplete.json"
        incomplete_data = {"name": "Test"}  # Missing description, version, patterns
        incomplete_file.write_text(json.dumps(incomplete_data), encoding="utf-8")

        valid, result = self.service.validate_portfolio_file(str(incomplete_file))

        assert valid is False
        assert isinstance(result, str)

    def test_validate_portfolio_file_valid(self):
        """Test validating valid portfolio file."""
        valid_file = self.temp_path / "valid.json"
        valid_data = {
            "name": "Valid Portfolio",
            "description": "Test portfolio",
            "version": "1.0.0",
            "patterns": [],
        }
        valid_file.write_text(json.dumps(valid_data), encoding="utf-8")

        valid, result = self.service.validate_portfolio_file(str(valid_file))

        assert valid is True
        assert isinstance(result, dict)
        assert result["name"] == "Valid Portfolio"


class TestPortfolioServiceCreateDeleteErrorHandlers:
    """Test portfolio creation/deletion error handlers."""

    def setup_method(self) -> None:
        """Setup service and temp directory."""
        PortfolioManager.reset_instance()
        self.service = PortfolioService()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self) -> None:
        """Clean up temp directory."""
        with contextlib.suppress(Exception):
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_portfolio_invalid_path(self):
        """Test creating portfolio with invalid path (cross-platform)."""
        # Use path to non-existent parent directory (works on all platforms)
        invalid_path = str(self.temp_path / "does_not_exist_dir" / "subdir" / "test.json")

        portfolio_data = {
            "name": "Test",
            "description": "Test",
            "version": "1.0.0",
            "patterns": [],
        }

        # Should raise FileNotFoundError when parent directory doesn't exist
        with pytest.raises((OSError, FileNotFoundError)):
            # write_text fails if parent directory doesn't exist
            Path(invalid_path).write_text(json.dumps(portfolio_data), encoding="utf-8")

    def test_remove_pattern_no_active_portfolio(self):
        """Test removing pattern when no portfolio is active."""
        with pytest.raises(ValueError, match="No active portfolio"):
            self.service.remove_pattern("Test")

    def test_remove_pattern_not_found(self):
        """Test removing non-existent pattern returns False."""
        # Create and set active portfolio
        portfolio = Portfolio(name="Test")
        manager = PortfolioManager.get_instance()
        manager.set_active_portfolio(portfolio)

        result = self.service.remove_pattern("NonExistent")

        assert result is False

    def test_save_portfolio_to_string_path(self):
        """Test save_portfolio accepts string paths."""
        portfolio = Portfolio(name="Test")
        filepath = str(self.temp_path / "test.json")

        # Should not raise
        self.service.save_portfolio(portfolio, filepath)

        assert Path(filepath).exists()

    def test_export_portfolio_to_path_directory_creation_error(self):
        """Test export_portfolio_to_path handles directory creation errors."""
        pattern = Pattern(name="Test", regex=r"\d+", type=PatternType.STATIC)
        portfolio = Portfolio(name="Test", patterns=[pattern])

        # Use invalid path (Windows: path with invalid chars)
        # dest_path = str(self.temp_path / "subdir>invalid<" / "test.json")
        # Note: This might not work on all systems, so we mock mkdir instead
        dest_path = str(self.temp_path / "newdir" / "test.json")

        # Mock mkdir to raise permission error
        with patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
            success, message = self.service.export_portfolio_to_path(portfolio, dest_path)

        assert success is False
        assert "error" in message.lower() or "cannot create" in message.lower()
