"""
Tests for Portfolio Service Extensions (Portfolio Manager UI).

Tests for new methods added to PortfolioService for V2.2.0:
- get_available_portfolios
- validate_portfolio_file
- is_portfolio_loaded
- get_portfolio_by_name
- portfolio_exists
- save_portfolio
- toggle_readonly
"""

import json
import os
import tempfile
import unittest

from src.core.models import Portfolio
from src.core.portfolio_manager import PortfolioManager
from src.services.portfolio_service import PortfolioService


class TestPortfolioServiceValidation(unittest.TestCase):
    """Test portfolio file validation."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        PortfolioManager.reset_instance()
        self.service = PortfolioService()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        # Clean up temp files
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_validate_portfolio_file_valid(self) -> None:
        """Test validating a valid portfolio file."""
        # Create valid portfolio file
        portfolio_data = {
            "name": "Test Portfolio",
            "description": "A test portfolio",
            "version": "1.0.0",
            "patterns": [],
            "readonly": False,
            "author": "Test Author",
            "tags": ["test"],
        }

        filepath = os.path.join(self.temp_dir, "test.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f)

        # Validate
        valid, result = self.service.validate_portfolio_file(filepath)

        self.assertTrue(valid)
        self.assertIsInstance(result, dict)
        # Type narrowing: result is Dict[str, Any] when valid is True
        assert isinstance(result, dict)
        metadata = result
        self.assertEqual(metadata["name"], "Test Portfolio")
        self.assertEqual(metadata["description"], "A test portfolio")
        self.assertEqual(metadata["pattern_count"], 0)
        self.assertEqual(metadata["readonly"], False)
        self.assertEqual(metadata["author"], "Test Author")

    def test_validate_portfolio_file_missing_fields(self) -> None:
        """Test validating portfolio with missing required fields."""
        # Create invalid portfolio (missing 'version')
        portfolio_data = {
            "name": "Test Portfolio",
            "description": "A test portfolio",
            "patterns": [],
        }

        filepath = os.path.join(self.temp_dir, "invalid.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f)

        # Validate
        valid, result = self.service.validate_portfolio_file(filepath)

        self.assertFalse(valid)
        self.assertIsInstance(result, str)
        self.assertIn("Missing required fields", result)  # type: ignore[arg-type]
        self.assertIn("version", result)  # type: ignore[arg-type]

    def test_validate_portfolio_file_invalid_json(self) -> None:
        """Test validating a file with invalid JSON."""
        filepath = os.path.join(self.temp_dir, "invalid.json")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("{invalid json")

        # Validate
        valid, result = self.service.validate_portfolio_file(filepath)

        self.assertFalse(valid)
        self.assertIsInstance(result, str)
        self.assertIn("Invalid JSON", result)  # type: ignore[arg-type]

    def test_validate_portfolio_file_not_found(self) -> None:
        """Test validating a non-existent file."""
        filepath = os.path.join(self.temp_dir, "nonexistent.json")

        # Validate
        valid, result = self.service.validate_portfolio_file(filepath)

        self.assertFalse(valid)
        self.assertIsInstance(result, str)
        self.assertIn("Error reading file", result)  # type: ignore[arg-type]


class TestPortfolioServiceDiscovery(unittest.TestCase):
    """Test portfolio discovery (available portfolios)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.packages_path = self.temp_dir
        self.portfolio_dir = os.path.join(self.packages_path, "User", "RegexLab", "portfolios")
        os.makedirs(self.portfolio_dir, exist_ok=True)

        PortfolioManager.reset_instance()
        self.service = PortfolioService()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        # Clean up temp files
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_get_available_portfolios_empty(self) -> None:
        """Test getting disabled portfolios when directory is empty."""
        disabled = self.service.get_disabled_portfolios(self.packages_path)

        self.assertEqual(disabled, [])

    def test_get_available_portfolios_with_valid_files(self) -> None:
        """Test discovering valid disabled portfolio files."""
        # Create disabled_portfolios directory
        disabled_dir = os.path.join(self.temp_dir, "User", "RegexLab", "disabled_portfolios")
        os.makedirs(disabled_dir, exist_ok=True)

        # Create two valid portfolios
        portfolio1 = {
            "name": "Portfolio 1",
            "description": "First portfolio",
            "version": "1.0.0",
            "patterns": [{"name": "Test", "regex": "test"}],
        }
        portfolio2 = {
            "name": "Portfolio 2",
            "description": "Second portfolio",
            "version": "1.0.0",
            "patterns": [],
        }

        filepath1 = os.path.join(disabled_dir, "portfolio1.json")
        filepath2 = os.path.join(disabled_dir, "portfolio2.json")

        with open(filepath1, "w", encoding="utf-8") as f:
            json.dump(portfolio1, f)
        with open(filepath2, "w", encoding="utf-8") as f:
            json.dump(portfolio2, f)

        # Discover
        disabled = self.service.get_disabled_portfolios(self.packages_path)

        self.assertEqual(len(disabled), 2)
        paths, metadatas = zip(*disabled)
        self.assertIn(filepath1, paths)
        self.assertIn(filepath2, paths)

        # Check metadata
        names = [m["name"] for m in metadatas]
        self.assertIn("Portfolio 1", names)
        self.assertIn("Portfolio 2", names)

    def test_get_available_portfolios_skips_loaded(self) -> None:
        """Test that disabled portfolios are correctly discovered (V2.2.1+ no 'loaded' filter)."""
        # Create disabled_portfolios directory
        disabled_dir = os.path.join(self.temp_dir, "User", "RegexLab", "disabled_portfolios")
        os.makedirs(disabled_dir, exist_ok=True)

        # Create portfolio file in disabled_portfolios/
        portfolio_data = {
            "name": "Disabled Portfolio",
            "description": "This is disabled",
            "version": "1.0.0",
            "patterns": [],
        }
        filepath = os.path.join(disabled_dir, "disabled.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f)

        # Discover (V2.2.1+: disabled portfolios are NOT filtered by loaded status)
        disabled = self.service.get_disabled_portfolios(self.packages_path)

        # Should find the disabled portfolio
        self.assertEqual(len(disabled), 1)
        found_path, found_meta = disabled[0]
        self.assertEqual(found_path, filepath)
        self.assertEqual(found_meta["name"], "Disabled Portfolio")

    def test_get_available_portfolios_skips_invalid(self) -> None:
        """Test that invalid portfolio files are skipped in disabled_portfolios/."""
        # Create disabled_portfolios directory
        disabled_dir = os.path.join(self.temp_dir, "User", "RegexLab", "disabled_portfolios")
        os.makedirs(disabled_dir, exist_ok=True)

        # Create one valid, one invalid
        valid_portfolio = {
            "name": "Valid",
            "description": "Valid portfolio",
            "version": "1.0.0",
            "patterns": [],
        }
        invalid_portfolio = {
            "name": "Invalid",
            # Missing required fields
        }

        valid_path = os.path.join(disabled_dir, "valid.json")
        invalid_path = os.path.join(disabled_dir, "invalid.json")

        with open(valid_path, "w", encoding="utf-8") as f:
            json.dump(valid_portfolio, f)
        with open(invalid_path, "w", encoding="utf-8") as f:
            json.dump(invalid_portfolio, f)

        # Discover
        disabled = self.service.get_disabled_portfolios(self.packages_path)

        # Should only find valid one
        self.assertEqual(len(disabled), 1)
        filepath, metadata = disabled[0]
        self.assertEqual(filepath, valid_path)
        self.assertEqual(metadata["name"], "Valid")


class TestPortfolioServiceLoaded(unittest.TestCase):
    """Test loaded portfolio checks."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        PortfolioManager.reset_instance()
        self.service = PortfolioService()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_is_portfolio_loaded_false(self) -> None:
        """Test checking unloaded portfolio."""
        self.assertFalse(self.service.is_portfolio_loaded("Nonexistent"))

    def test_is_portfolio_loaded_true(self) -> None:
        """Test checking loaded portfolio."""
        # Create and load portfolio file
        portfolio_data = {
            "name": "Test Portfolio",
            "description": "Test",
            "version": "1.0.0",
            "patterns": [],
        }
        filepath = os.path.join(self.temp_dir, "test.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f)

        from pathlib import Path

        self.service.portfolio_manager.load_portfolio(Path(filepath))

        # Check
        self.assertTrue(self.service.is_portfolio_loaded("Test Portfolio"))

    def test_get_portfolio_by_name_found(self) -> None:
        """Test getting portfolio by name."""
        # Create and load portfolio file
        portfolio_data = {
            "name": "My Portfolio",
            "description": "Test",
            "version": "1.0.0",
            "patterns": [],
        }
        filepath = os.path.join(self.temp_dir, "myportfolio.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f)

        from pathlib import Path

        self.service.portfolio_manager.load_portfolio(Path(filepath))

        # Get by name
        result = self.service.get_portfolio_by_name("My Portfolio")

        self.assertIsNotNone(result)
        # Type narrowing: result is Portfolio when not None
        assert result is not None
        self.assertEqual(result.name, "My Portfolio")

    def test_get_portfolio_by_name_not_found(self) -> None:
        """Test getting nonexistent portfolio."""
        result = self.service.get_portfolio_by_name("Nonexistent")

        self.assertIsNone(result)


class TestPortfolioServiceExists(unittest.TestCase):
    """Test portfolio existence checks."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.packages_path = self.temp_dir
        self.portfolio_dir = os.path.join(self.packages_path, "User", "RegexLab", "portfolios")
        os.makedirs(self.portfolio_dir, exist_ok=True)

        PortfolioManager.reset_instance()
        self.service = PortfolioService()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_portfolio_exists_loaded(self) -> None:
        """Test portfolio_exists returns True for loaded portfolio."""
        # Create and load portfolio file
        portfolio_data = {
            "name": "Loaded",
            "description": "Test",
            "version": "1.0.0",
            "patterns": [],
        }
        filepath = os.path.join(self.portfolio_dir, "loaded.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f)

        from pathlib import Path

        self.service.portfolio_manager.load_portfolio(Path(filepath))

        # Check
        self.assertTrue(self.service.portfolio_exists("Loaded", self.packages_path))

    def test_portfolio_exists_available(self) -> None:
        """Test portfolio_exists returns True for available (unloaded) portfolio."""
        # Create portfolio file
        portfolio_data = {
            "name": "Available",
            "description": "Test",
            "version": "1.0.0",
            "patterns": [],
        }
        filepath = os.path.join(self.portfolio_dir, "available.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f)

        # Check
        self.assertTrue(self.service.portfolio_exists("Available", self.packages_path))

    def test_portfolio_exists_not_found(self) -> None:
        """Test portfolio_exists returns False for nonexistent portfolio."""
        self.assertFalse(self.service.portfolio_exists("Nonexistent", self.packages_path))


class TestPortfolioServiceSave(unittest.TestCase):
    """Test portfolio save operations."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        PortfolioManager.reset_instance()
        self.service = PortfolioService()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_save_portfolio_updates_timestamp(self) -> None:
        """Test that save_portfolio updates the 'updated' timestamp."""
        portfolio = Portfolio(name="Test", description="Test", version="1.0.0")
        portfolio.updated = "2000-01-01T00:00:00"

        filepath = os.path.join(self.temp_dir, "test.json")

        # Save
        self.service.save_portfolio(portfolio, filepath)

        # Check timestamp was updated
        self.assertNotEqual(portfolio.updated, "2000-01-01T00:00:00")
        self.assertIn("2025", portfolio.updated)  # Current year

    def test_save_portfolio_creates_file(self) -> None:
        """Test that save_portfolio creates the file."""
        portfolio = Portfolio(name="Test", description="Test", version="1.0.0")
        filepath = os.path.join(self.temp_dir, "test.json")

        # Save
        self.service.save_portfolio(portfolio, filepath)

        # Check file exists
        self.assertTrue(os.path.exists(filepath))

        # Check content
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["name"], "Test")
        self.assertEqual(data["description"], "Test")


class TestPortfolioServiceToggleReadonly(unittest.TestCase):
    """Test readonly toggle operations."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        PortfolioManager.reset_instance()
        self.service = PortfolioService()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_toggle_readonly_false_to_true(self) -> None:
        """Test toggling readonly from False to True."""
        portfolio = Portfolio(name="Test", description="Test", version="1.0.0", readonly=False)
        filepath = os.path.join(self.temp_dir, "test.json")

        # Toggle
        self.service.toggle_readonly(portfolio, filepath)

        # Check
        self.assertTrue(portfolio.readonly)

    def test_toggle_readonly_true_to_false(self) -> None:
        """Test toggling readonly from True to False."""
        portfolio = Portfolio(name="Test", description="Test", version="1.0.0", readonly=True)
        filepath = os.path.join(self.temp_dir, "test.json")

        # Toggle
        self.service.toggle_readonly(portfolio, filepath)

        # Check
        self.assertFalse(portfolio.readonly)

    def test_toggle_readonly_saves_file(self) -> None:
        """Test that toggle_readonly saves the portfolio."""
        portfolio = Portfolio(name="Test", description="Test", version="1.0.0", readonly=False)
        filepath = os.path.join(self.temp_dir, "test.json")

        # Toggle
        self.service.toggle_readonly(portfolio, filepath)

        # Check file exists and readonly is True
        self.assertTrue(os.path.exists(filepath))

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        self.assertTrue(data["readonly"])


if __name__ == "__main__":
    unittest.main()
