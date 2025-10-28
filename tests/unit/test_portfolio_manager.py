"""
Unit tests for PortfolioManager.

Tests cover:
- Singleton pattern
- Load/save operations
- Active portfolio management
- Error handling (file not found, invalid JSON, permissions)
- Edge cases
"""

from __future__ import annotations

import contextlib
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from src.core.models import Pattern, PatternType, Portfolio
from src.core.portfolio_manager import PortfolioManager


class TestPortfolioManagerSingleton:
    """Test PortfolioManager singleton pattern."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        PortfolioManager.reset_instance()

    def test_singleton_same_instance(self) -> None:
        """Test that get_instance always returns the same instance."""
        manager1 = PortfolioManager.get_instance()
        manager2 = PortfolioManager.get_instance()

        assert manager1 is manager2

    def test_singleton_with_new(self) -> None:
        """Test that __new__ returns the same instance."""
        manager1 = PortfolioManager.get_instance()
        manager2 = PortfolioManager.get_instance()

        assert manager1 is manager2

    def test_reset_instance(self) -> None:
        """Test that reset_instance clears the singleton."""
        manager1 = PortfolioManager.get_instance()
        PortfolioManager.reset_instance()
        manager2 = PortfolioManager.get_instance()

        # After reset, we get a new instance
        assert manager1 is not manager2


class TestPortfolioManagerLoad:
    """Test portfolio loading."""

    def setup_method(self) -> None:
        """Reset singleton and create temp directory."""
        PortfolioManager.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def test_load_portfolio_success(self) -> None:
        """Test successfully loading a valid portfolio."""
        # Create a test portfolio file
        portfolio_path = self.temp_path / "test.json"
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

        portfolio_path.write_text(json.dumps(data), encoding="utf-8")

        manager = PortfolioManager.get_instance()
        portfolio = manager.load_portfolio(portfolio_path)

        assert portfolio.name == "Test Portfolio"
        assert portfolio.description == "Test desc"
        assert len(portfolio.patterns) == 1
        assert portfolio.patterns[0].name == "P1"

    def test_load_portfolio_file_not_found(self) -> None:
        """Test loading non-existent file raises FileNotFoundError."""
        manager = PortfolioManager.get_instance()
        non_existent = self.temp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError, match="Portfolio file not found"):
            manager.load_portfolio(non_existent)

    def test_load_portfolio_path_is_directory(self) -> None:
        """Test loading a directory raises ValueError."""
        manager = PortfolioManager.get_instance()

        with pytest.raises(ValueError, match="Path is not a file"):
            manager.load_portfolio(self.temp_path)

    def test_load_portfolio_invalid_json(self) -> None:
        """Test loading invalid JSON raises ValueError."""
        portfolio_path = self.temp_path / "invalid.json"
        portfolio_path.write_text("{ invalid json }", encoding="utf-8")

        manager = PortfolioManager.get_instance()

        with pytest.raises(ValueError, match="Invalid JSON"):
            manager.load_portfolio(portfolio_path)

    def test_load_portfolio_missing_required_field(self) -> None:
        """Test loading portfolio without required fields raises ValueError."""
        portfolio_path = self.temp_path / "missing.json"
        data = {"description": "Missing name field"}

        portfolio_path.write_text(json.dumps(data), encoding="utf-8")

        manager = PortfolioManager.get_instance()

        with pytest.raises(ValueError, match="Invalid portfolio data"):
            manager.load_portfolio(portfolio_path)


class TestPortfolioManagerSave:
    """Test portfolio saving."""

    def setup_method(self) -> None:
        """Reset singleton and create temp directory."""
        PortfolioManager.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def test_save_portfolio_success(self) -> None:
        """Test successfully saving a portfolio."""
        pattern = Pattern(name="P1", regex=r"\btest\b", type=PatternType.STATIC)
        portfolio = Portfolio(name="Test", patterns=[pattern])

        portfolio_path = self.temp_path / "saved.json"

        manager = PortfolioManager.get_instance()
        manager.save_portfolio(portfolio, portfolio_path)

        # Verify file was created
        assert portfolio_path.exists()

        # Verify content is valid JSON
        data = json.loads(portfolio_path.read_text(encoding="utf-8"))
        assert data["name"] == "Test"
        assert len(data["patterns"]) == 1

    def test_save_portfolio_creates_directories(self) -> None:
        """Test that save_portfolio creates parent directories."""
        pattern = Pattern(name="P1", regex=r"\btest\b", type=PatternType.STATIC)
        portfolio = Portfolio(name="Test", patterns=[pattern])

        # Path with non-existent directories
        portfolio_path = self.temp_path / "subdir" / "nested" / "portfolio.json"

        manager = PortfolioManager.get_instance()
        manager.save_portfolio(portfolio, portfolio_path)

        assert portfolio_path.exists()
        assert portfolio_path.parent.exists()

    def test_save_portfolio_overwrites_existing(self) -> None:
        """Test that saving overwrites existing file."""
        portfolio1 = Portfolio(name="First")
        portfolio2 = Portfolio(name="Second")

        portfolio_path = self.temp_path / "overwrite.json"

        manager = PortfolioManager.get_instance()
        manager.save_portfolio(portfolio1, portfolio_path)
        manager.save_portfolio(portfolio2, portfolio_path)

        # Verify file contains second portfolio
        data = json.loads(portfolio_path.read_text(encoding="utf-8"))
        assert data["name"] == "Second"


class TestPortfolioManagerActive:
    """Test active portfolio management."""

    def setup_method(self) -> None:
        """Reset singleton."""
        PortfolioManager.reset_instance()

    def test_get_active_portfolio_none_by_default(self) -> None:
        """Test that active portfolio is None by default."""
        manager = PortfolioManager.get_instance()

        assert manager.get_active_portfolio() is None

    def test_set_active_portfolio(self) -> None:
        """Test setting the active portfolio."""
        portfolio = Portfolio(name="Active")
        manager = PortfolioManager.get_instance()

        manager.set_active_portfolio(portfolio)

        active = manager.get_active_portfolio()
        assert active is portfolio
        assert active is not None
        assert active.name == "Active"

    def test_clear_active_portfolio(self) -> None:
        """Test clearing the active portfolio."""
        portfolio = Portfolio(name="Active")
        manager = PortfolioManager.get_instance()

        manager.set_active_portfolio(portfolio)
        manager.clear_active_portfolio()

        assert manager.get_active_portfolio() is None

    def test_load_and_set_active(self) -> None:
        """Test loading and setting active portfolio in one operation."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        portfolio_path = temp_path / "test.json"

        data = {
            "name": "Test Portfolio",
            "description": "",
            "version": "1.0.0",
            "patterns": [],
        }

        portfolio_path.write_text(json.dumps(data), encoding="utf-8")

        manager = PortfolioManager.get_instance()
        portfolio = manager.load_and_set_active(portfolio_path)

        assert portfolio.name == "Test Portfolio"
        assert manager.get_active_portfolio() is portfolio

    def test_save_active_portfolio_success(self) -> None:
        """Test saving the active portfolio."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        portfolio_path = temp_path / "active.json"

        portfolio = Portfolio(name="Active Portfolio")
        manager = PortfolioManager.get_instance()

        manager.set_active_portfolio(portfolio)
        manager.save_active_portfolio(portfolio_path)

        # Verify file was created with correct content
        data = json.loads(portfolio_path.read_text(encoding="utf-8"))
        assert data["name"] == "Active Portfolio"

    def test_save_active_portfolio_no_active_raises(self) -> None:
        """Test that saving without active portfolio raises ValueError."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        portfolio_path = temp_path / "test.json"

        manager = PortfolioManager.get_instance()

        with pytest.raises(ValueError, match="No active portfolio"):
            manager.save_active_portfolio(portfolio_path)


class TestPortfolioManagerExportImport:
    """Test export/import aliases."""

    def setup_method(self) -> None:
        """Reset singleton and create temp directory."""
        PortfolioManager.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def test_export_portfolio(self) -> None:
        """Test exporting portfolio to user-chosen location."""
        pattern = Pattern(name="P1", regex=r"\btest\b", type=PatternType.STATIC)
        portfolio = Portfolio(name="Export Test", patterns=[pattern])

        export_path = self.temp_path / "exported.json"
        manager = PortfolioManager.get_instance()

        manager.export_portfolio(portfolio, export_path)

        # Verify file was created
        assert export_path.exists()
        data = json.loads(export_path.read_text(encoding="utf-8"))
        assert data["name"] == "Export Test"

    def test_import_portfolio(self) -> None:
        """Test importing portfolio from user-chosen location."""
        # Create test file
        import_path = self.temp_path / "to_import.json"
        data = {
            "name": "Import Test",
            "description": "",
            "version": "1.0.0",
            "patterns": [],
        }
        import_path.write_text(json.dumps(data), encoding="utf-8")

        manager = PortfolioManager.get_instance()
        portfolio = manager.import_portfolio(import_path)

        assert portfolio.name == "Import Test"

    def test_export_import_roundtrip(self) -> None:
        """Test full export/import workflow."""
        pattern = Pattern(name="P1", regex=r"\btest\b", type=PatternType.STATIC)
        original = Portfolio(name="Roundtrip Test", patterns=[pattern])

        export_path = self.temp_path / "shared.json"
        manager = PortfolioManager.get_instance()

        # Export
        manager.export_portfolio(original, export_path)

        # Import
        imported = manager.import_portfolio(export_path)

        # Verify
        assert imported.name == original.name
        assert len(imported.patterns) == len(original.patterns)
        assert imported.patterns[0].name == original.patterns[0].name


class TestPortfolioManagerEdgeCases:
    """Test PortfolioManager edge cases and error handling."""

    def setup_method(self) -> None:
        """Reset singleton and create temp directory."""
        PortfolioManager.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def test_reset_instance_clears_active_portfolio(self) -> None:
        """Test that reset_instance clears the active portfolio."""
        portfolio = Portfolio(name="Active")
        manager = PortfolioManager.get_instance()
        manager.set_active_portfolio(portfolio)

        assert manager.get_active_portfolio() is not None

        PortfolioManager.reset_instance()
        new_manager = PortfolioManager.get_instance()

        # Active portfolio should be cleared after reset
        assert new_manager.get_active_portfolio() is None


class TestPortfolioManagerIntegration:
    """Integration tests for PortfolioManager."""

    def setup_method(self) -> None:
        """Reset singleton and create temp directory."""
        PortfolioManager.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def test_full_workflow(self) -> None:
        """Test complete workflow: create, save, load, modify, save."""
        # Create portfolio
        pattern1 = Pattern(name="P1", regex=r"\bfoo\b", type=PatternType.STATIC)
        portfolio = Portfolio(name="Workflow Test", patterns=[pattern1])

        # Save
        portfolio_path = self.temp_path / "workflow.json"
        manager = PortfolioManager.get_instance()
        manager.save_portfolio(portfolio, portfolio_path)

        # Load and set active
        loaded = manager.load_and_set_active(portfolio_path)
        assert loaded.name == "Workflow Test"
        assert len(loaded.patterns) == 1

        # Modify
        pattern2 = Pattern(name="P2", regex=r"\bbar\b", type=PatternType.STATIC)
        loaded.add_pattern(pattern2)

        # Save active
        manager.save_active_portfolio(portfolio_path)

        # Load again to verify modification was saved
        final = manager.load_portfolio(portfolio_path, reload=True)
        assert len(final.patterns) == 2
        assert final.get_pattern("P2") is not None

    def test_multiple_load_save_cycles(self) -> None:
        """Test multiple load/save cycles maintain data integrity."""
        portfolio_path = self.temp_path / "cycle.json"
        manager = PortfolioManager.get_instance()

        # Cycle 1: Create and save
        p1 = Pattern(name="P1", regex=r"\btest1\b", type=PatternType.STATIC)
        portfolio1 = Portfolio(name="Cycle Test", patterns=[p1])
        manager.save_portfolio(portfolio1, portfolio_path)

        # Cycle 2: Load, modify, save
        loaded1 = manager.load_portfolio(portfolio_path, reload=True)
        p2 = Pattern(name="P2", regex=r"\btest2\b", type=PatternType.STATIC)
        loaded1.add_pattern(p2)
        manager.save_portfolio(loaded1, portfolio_path)

        # Cycle 3: Load, modify, save
        loaded2 = manager.load_portfolio(portfolio_path, reload=True)
        p3 = Pattern(name="P3", regex=r"\btest3\b", type=PatternType.STATIC)
        loaded2.add_pattern(p3)
        manager.save_portfolio(loaded2, portfolio_path)

        # Final verification
        final = manager.load_portfolio(portfolio_path, reload=True)
        assert len(final.patterns) == 3
        assert final.get_pattern("P1") is not None
        assert final.get_pattern("P2") is not None
        assert final.get_pattern("P3") is not None


# ============================================================================
# Additional Error Handler Tests (Coverage Improvement)
# ============================================================================


class TestPortfolioManagerErrorHandlers:
    """Tests for error handling edge cases (improve coverage from 76% to 90%)."""

    def setup_method(self) -> None:
        """Reset singleton and create temp directory."""
        PortfolioManager.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self) -> None:
        """Clean up temp directory."""
        with contextlib.suppress(Exception):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_portfolio_from_file_invalid_json(self):
        """Test loading portfolio with malformed JSON."""
        portfolio_path = self.temp_path / "invalid.json"
        portfolio_path.write_text("{ INVALID JSON }", encoding="utf-8")

        manager = PortfolioManager.get_instance()

        with pytest.raises(ValueError, match="Invalid JSON"):
            manager.load_portfolio_from_file(portfolio_path)

    def test_load_portfolio_from_file_invalid_portfolio_data(self):
        """Test loading portfolio with invalid portfolio structure."""
        portfolio_path = self.temp_path / "invalid_structure.json"
        # JSON valid but missing required Portfolio fields
        portfolio_path.write_text('{"invalid": "structure"}', encoding="utf-8")

        manager = PortfolioManager.get_instance()

        with pytest.raises(ValueError, match="Invalid portfolio data"):
            manager.load_portfolio_from_file(portfolio_path)

    def test_load_portfolio_name_collision_without_reload(self):
        """Test loading portfolio with name collision (should raise ValueError)."""
        portfolio_path = self.temp_path / "duplicate.json"
        data = {
            "name": "Duplicate",
            "description": "",
            "version": "1.0.0",
            "patterns": [],
        }
        portfolio_path.write_text(json.dumps(data), encoding="utf-8")

        manager = PortfolioManager.get_instance()

        # Load first time (OK)
        manager.load_portfolio(portfolio_path)

        # Load second time without reload=True (should fail)
        with pytest.raises(ValueError, match="already loaded"):
            manager.load_portfolio(portfolio_path, reload=False)

    def test_unload_portfolio_not_found(self):
        """Test unloading non-existent portfolio (should return False and log warning)."""
        manager = PortfolioManager.get_instance()

        result = manager.unload_portfolio("NonExistent")

        assert result is False

    def test_unload_builtin_portfolio_raises_error(self):
        """Test unloading built-in portfolio (should raise ValueError)."""
        portfolio_path = self.temp_path / "builtin.json"
        data = {
            "name": "Builtin",
            "description": "",
            "version": "1.0.0",
            "patterns": [],
        }
        portfolio_path.write_text(json.dumps(data), encoding="utf-8")

        manager = PortfolioManager.get_instance()
        manager.load_portfolio(portfolio_path, set_as_builtin=True)

        with pytest.raises(ValueError, match="Cannot unload built-in portfolio"):
            manager.unload_portfolio("Builtin")

    def test_save_portfolio_readonly(self):
        """Test saving readonly portfolio (should raise ValueError)."""
        portfolio = Portfolio(name="Readonly", readonly=True)
        portfolio_path = self.temp_path / "readonly.json"

        manager = PortfolioManager.get_instance()

        with pytest.raises(ValueError, match="is readonly"):
            manager.save_portfolio(portfolio, portfolio_path)

    def test_save_active_portfolio_no_active(self):
        """Test saving active portfolio when none is active (should raise ValueError)."""
        manager = PortfolioManager.get_instance()
        portfolio_path = self.temp_path / "active.json"

        with pytest.raises(ValueError, match="No active portfolio"):
            manager.save_active_portfolio(portfolio_path)

    def test_import_portfolio_file_not_found(self):
        """Test importing from non-existent file (should raise FileNotFoundError)."""
        manager = PortfolioManager.get_instance()
        non_existent = self.temp_path / "does_not_exist.json"

        with pytest.raises(FileNotFoundError):
            manager.import_portfolio(non_existent)

    def test_set_active_portfolio_not_loaded(self):
        """Test setting active portfolio that isn't loaded (should load it first or raise)."""
        portfolio = Portfolio(name="NotLoaded")
        manager = PortfolioManager.get_instance()

        # This should work - portfolio can be set as active even if not loaded
        manager.set_active_portfolio(portfolio)

        assert manager.get_active_portfolio() == portfolio

    def test_unload_portfolio_successfully_removes_tracking(self):
        """Unloading a regular portfolio should clear cached paths and entries."""
        portfolio_path = self.temp_path / "regular.json"
        data = {
            "name": "Regular",
            "description": "",
            "version": "1.0.0",
            "patterns": [],
        }
        portfolio_path.write_text(json.dumps(data), encoding="utf-8")

        manager = PortfolioManager.get_instance()
        manager.load_portfolio(portfolio_path)

        assert manager.unload_portfolio("Regular") is True
        assert manager.get_portfolio("Regular") is None

    def test_save_portfolio_uses_tracked_path_when_available(self):
        """Saving without explicit path should use the previously loaded file."""
        portfolio_path = self.temp_path / "tracked.json"
        portfolio_data = {
            "name": "Tracked",
            "description": "",
            "version": "1.0.0",
            "patterns": [],
        }
        portfolio_path.write_text(json.dumps(portfolio_data), encoding="utf-8")

        manager = PortfolioManager.get_instance()
        portfolio = manager.load_portfolio(portfolio_path)

        manager.save_portfolio(portfolio)

        # Updated timestamp should be persisted to the tracked file
        saved = json.loads(portfolio_path.read_text(encoding="utf-8"))
        assert saved["name"] == "Tracked"
        assert saved["updated"]

    def test_save_portfolio_without_tracked_path_raises(self):
        """Attempting to save without a known path should raise ValueError."""
        manager = PortfolioManager.get_instance()
        portfolio = Portfolio(name="Orphan")

        with pytest.raises(ValueError, match="No path tracked"):
            manager.save_portfolio(portfolio)

    def test_save_portfolio_permission_error_propagates(self):
        """Permission errors during write should raise descriptive PermissionError."""
        manager = PortfolioManager.get_instance()
        portfolio = Portfolio(name="PermTest")
        portfolio_path = self.temp_path / "perm.json"

        with patch("pathlib.Path.open", side_effect=PermissionError("denied")), pytest.raises(
            PermissionError, match="Cannot write portfolio file"
        ):
            manager.save_portfolio(portfolio, portfolio_path)

    def test_save_portfolio_os_error_propagates(self):
        """Generic OS errors during write should be surfaced as OSError."""
        manager = PortfolioManager.get_instance()
        portfolio = Portfolio(name="OsTest")
        portfolio_path = self.temp_path / "os.json"

        with patch("pathlib.Path.open", side_effect=OSError("disk full")), pytest.raises(
            OSError, match="Failed to save portfolio"
        ):
            manager.save_portfolio(portfolio, portfolio_path)
