"""
Portfolio Service - Business logic for portfolio management.

This service orchestrates Portfolio and PortfolioManager to provide
high-level operations for the UI layer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..core.constants import REQUIRED_PORTFOLIO_FIELDS
from ..core.helpers import get_current_timestamp
from ..core.logger import get_logger
from ..core.models import Pattern, PatternType, Portfolio
from ..core.portfolio_manager import PortfolioManager

logger = get_logger()


class PortfolioService:
    """
    Service for managing portfolios and patterns.

    This service provides business logic operations for:
    - Managing the active portfolio
    - CRUD operations on patterns within portfolios
    - Loading/saving portfolios
    - Exporting/importing portfolios
    """

    def __init__(self, portfolio_manager: PortfolioManager | None = None) -> None:
        """
        Initialize the portfolio service.

        Args:
            portfolio_manager: Optional portfolio manager instance.
            If None, uses the singleton instance.
        """
        self.portfolio_manager = portfolio_manager or PortfolioManager.get_instance()

    def get_active_portfolio(self) -> Portfolio | None:
        """
        Get the currently active portfolio.

        Returns:
            The active portfolio, or None if no portfolio is active.
        """
        return self.portfolio_manager.get_active_portfolio()

    def set_active_portfolio(self, portfolio: Portfolio) -> None:
        """
        Set the active portfolio.

        Args:
            portfolio: The portfolio to set as active.
        """
        self.portfolio_manager.set_active_portfolio(portfolio)

    def load_portfolio(self, path: Path) -> Portfolio:
        """
        Load a portfolio from disk and set it as active.

        Args:
            path: Path to the portfolio JSON file.

        Returns:
            The loaded portfolio.

        Raises:
            FileNotFoundError: If the portfolio file doesn't exist.
            ValueError: If the portfolio file is invalid.
        """
        portfolio = self.portfolio_manager.load_and_set_active(path)
        return portfolio

    def save_active_portfolio(self, path: Path) -> None:
        """
        Save the active portfolio to disk.

        Args:
            path: Path where to save the portfolio.

        Raises:
            ValueError: If no portfolio is active.
        """
        self.portfolio_manager.save_active_portfolio(path)

    def export_portfolio(self, portfolio: Portfolio, path: Path) -> None:
        """
        Export a portfolio to a user-chosen location.

        Args:
            portfolio: The portfolio to export.
            path: Destination path for the export.
        """
        self.portfolio_manager.export_portfolio(portfolio, path)

    def import_portfolio(self, path: Path) -> Portfolio:
        """
        Import a portfolio from a user-chosen file.

        Args:
            path: Path to the portfolio file to import.

        Returns:
            The imported portfolio.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file is invalid.
        """
        return self.portfolio_manager.import_portfolio(path)

    def get_active_patterns(self) -> list[Pattern]:
        """
        Get all patterns from the active portfolio.

        Returns:
            List of patterns, or empty list if no portfolio is active.
        """
        portfolio = self.get_active_portfolio()
        if portfolio is None:
            return []
        return portfolio.list_patterns()

    def get_patterns_by_type(self, pattern_type: PatternType) -> list[Pattern]:
        """
        Get patterns of a specific type from the active portfolio.

        Args:
            pattern_type: The type of patterns to retrieve.

        Returns:
            List of patterns matching the type, or empty list if no portfolio is active.
        """
        portfolio = self.get_active_portfolio()
        if portfolio is None:
            return []
        return portfolio.list_patterns(pattern_type=pattern_type)

    def get_pattern_by_name(self, name: str) -> Pattern | None:
        """
        Get a specific pattern by name from the active portfolio.

        Args:
            name: Name of the pattern to retrieve.

        Returns:
            The pattern if found, None otherwise.
        """
        portfolio = self.get_active_portfolio()
        if portfolio is None:
            return None
        return portfolio.get_pattern(name)

    def add_pattern(self, pattern: Pattern) -> None:
        """
        Add a pattern to the active portfolio.

        Args:
            pattern: The pattern to add.

        Raises:
            ValueError: If no portfolio is active or pattern name already exists.
        """
        portfolio = self.get_active_portfolio()
        if portfolio is None:
            raise ValueError("No active portfolio")
        portfolio.add_pattern(pattern)

    def add_pattern_to_portfolio(self, portfolio_name: str, pattern: Pattern) -> bool:
        """
        Add a pattern to a specific portfolio by name.

        This method:
        1. Finds portfolio by name
        2. Validates portfolio is editable (not readonly)
        3. Adds pattern to portfolio in memory
        4. Saves portfolio to disk (updates 'updated' timestamp)
        5. Reloads portfolio to sync changes

        Args:
            portfolio_name: Name of portfolio to add pattern to
            pattern: Pattern object to add

        Returns:
            True if pattern was added successfully, False otherwise

        Raises:
            ValueError: If portfolio not found or readonly
        """
        portfolio = self.get_portfolio_by_name(portfolio_name)
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_name}' not found")

        if portfolio.readonly:
            raise ValueError(f"Portfolio '{portfolio_name}' is read-only")

        # Check if pattern name already exists
        if any(p.name == pattern.name for p in portfolio.patterns):
            raise ValueError(f"Pattern '{pattern.name}' already exists in portfolio")

        # Add pattern to portfolio
        portfolio.add_pattern(pattern)

        # Update 'updated' timestamp
        portfolio.updated = get_current_timestamp()

        # Save portfolio to disk
        try:
            manager = PortfolioManager.get_instance()
            manager.save_portfolio(portfolio)  # Raises exception on failure

            logger.info("Pattern '%s' added to portfolio '%s'", pattern.name, portfolio_name)
            return True

        except Exception as e:
            logger.error("Failed to save portfolio after adding pattern: %s", e)
            return False

    def remove_pattern(self, name: str) -> bool:
        """
        Remove a pattern from the active portfolio.

        Args:
            name: Name of the pattern to remove.

        Returns:
            True if the pattern was removed, False if not found.

        Raises:
            ValueError: If no portfolio is active.
        """
        portfolio = self.get_active_portfolio()
        if portfolio is None:
            raise ValueError("No active portfolio")
        return portfolio.remove_pattern(name)

    def has_active_portfolio(self) -> bool:
        """
        Check if there is an active portfolio.

        Returns:
            True if a portfolio is active, False otherwise.
        """
        return self.get_active_portfolio() is not None

    def get_all_portfolios(self) -> list[Portfolio]:
        """
        Get all loaded portfolios (V2 multi-portfolio support).

        Returns portfolios in display order:
        - Built-in portfolio first (if loaded)
        - Other portfolios alphabetically

        Returns:
            List of all loaded portfolios.
        """
        return self.portfolio_manager.get_all_portfolios()

    def get_disabled_portfolios(self, packages_path: str) -> list[tuple[str, dict[str, Any]]]:
        """
        Scan User/RegexLab/disabled_portfolios/ for .json files.

        Returns portfolios that have been disabled by the user (moved to disabled_portfolios/).
        These portfolios are NOT loaded automatically but can be re-enabled via Portfolio Manager.

        Args:
            packages_path: Path to Sublime Text packages directory

        Returns:
            List of (filepath, metadata_dict) tuples for disabled portfolios
        """
        logger.debug("Scanning for disabled portfolios in: %s", packages_path)
        disabled_dir = os.path.join(packages_path, "User", "RegexLab", "disabled_portfolios")
        if not os.path.exists(disabled_dir):
            logger.debug("Disabled portfolios directory does not exist: %s", disabled_dir)
            return []

        disabled = []

        for filename in os.listdir(disabled_dir):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(disabled_dir, filename)

            # Validate portfolio file
            valid, result = self.validate_portfolio_file(filepath)
            if not valid:
                # Log as WARNING so user sees the problem
                logger.warning("Skipping invalid portfolio file '%s': %s", filename, result)
                logger.warning("  → Location: %s", filepath)
                logger.warning("  → Fix the JSON errors and reload RegexLab (Ctrl+Shift+P → Reload)")
                continue

            # result is a Dict when valid is True
            metadata = result
            assert isinstance(metadata, dict)

            logger.debug("Found disabled portfolio: %s (%s)", metadata["name"], filename)
            disabled.append((filepath, metadata))

        logger.debug("Total disabled portfolios: %s", len(disabled))
        return disabled

    def validate_portfolio_file(self, filepath: str) -> tuple[bool, dict[str, Any] | str]:
        """
        Validate that .json file is a valid portfolio.

        Args:
            filepath: Path to .json file to validate

        Returns:
            Tuple of (is_valid, metadata_or_error):
            - If valid: (True, metadata_dict)
            - If invalid: (False, error_message)
        """
        logger.debug("Validating portfolio file: %s", filepath)
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            # Check required fields
            missing = [field for field in REQUIRED_PORTFOLIO_FIELDS if field not in data]
            if missing:
                error = f"Missing required fields: {', '.join(missing)}"
                logger.debug("Validation failed for %s: %s", filepath, error)
                return (False, error)

            # Return metadata
            metadata: dict[str, Any] = {
                "name": data["name"],
                "description": data.get("description", ""),
                "pattern_count": len(data.get("patterns", [])),
                "readonly": data.get("readonly", False),
                "version": data.get("version", "1.0.0"),
                "author": data.get("author", "Unknown"),
                "tags": data.get("tags", []),
            }
            logger.debug("Validation successful: %s (%s patterns)", metadata["name"], metadata["pattern_count"])
            return (True, metadata)

        except json.JSONDecodeError as e:
            error = f"Invalid JSON: {e!s}"
            logger.debug("Validation failed for %s: %s", filepath, error)
            return (False, error)
        except (OSError, ValueError) as e:
            # OSError: File I/O errors (permissions, disk issues, missing file)
            # ValueError: Invalid path or data format
            error = f"Error reading file: {e!s}"
            logger.error("Validation failed for %s - %s: %s", filepath, type(e).__name__, error)
            return (False, error)

    def is_portfolio_loaded(self, portfolio_name: str) -> bool:
        """
        Check if portfolio with given name is currently loaded.

        Args:
            portfolio_name: Name of portfolio to check

        Returns:
            True if portfolio is loaded, False otherwise
        """
        loaded_portfolios = self.get_all_portfolios()
        is_loaded = any(p.name == portfolio_name for p in loaded_portfolios)
        logger.debug("Portfolio '%s' loaded: %s", portfolio_name, is_loaded)
        return is_loaded

    def get_portfolio_by_name(self, name: str) -> Portfolio | None:
        """
        Get loaded portfolio by name.

        Args:
            name: Name of portfolio to retrieve

        Returns:
            Portfolio if found, None otherwise
        """
        logger.debug("Looking for loaded portfolio: %s", name)
        for portfolio in self.get_all_portfolios():
            if portfolio.name == name:
                logger.debug("Found portfolio: %s", name)
                return portfolio
        logger.debug("Portfolio not found: %s", name)
        return None

    def portfolio_exists(self, name: str, packages_path: str) -> bool:
        """
        Check if portfolio with given name exists (loaded or available).

        Optimized: Single-pass check minimizing file I/O operations.

        Args:
            name: Name of portfolio to check
            packages_path: Path to Sublime Text packages directory

        Returns:
            True if portfolio exists, False otherwise
        """
        logger.debug("Checking if portfolio exists: %s", name)

        # Check 1: Loaded portfolios (O(n) memory check, fast)
        if self.is_portfolio_loaded(name):
            logger.debug("Portfolio exists (loaded): %s", name)
            return True

        # Check 2: Disabled portfolios (typically smaller list, check first)
        disabled = self.get_disabled_portfolios(packages_path)
        if any(metadata["name"] == name for _, metadata in disabled):
            logger.debug("Portfolio exists (disabled): %s", name)
            return True

        # Check 3: Active portfolios (only if not found in disabled)
        portfolios_dir = os.path.join(packages_path, "User", "RegexLab", "portfolios")
        if os.path.exists(portfolios_dir):
            for filename in os.listdir(portfolios_dir):
                if filename.endswith(".json"):
                    filepath = os.path.join(portfolios_dir, filename)
                    valid, result = self.validate_portfolio_file(filepath)
                    if valid and isinstance(result, dict) and result["name"] == name:
                        logger.debug("Portfolio exists (active): %s", name)
                        return True

        logger.debug("Portfolio does not exist: %s", name)
        return False

    def save_portfolio(self, portfolio: Portfolio, filepath: str) -> None:
        """
        Save portfolio to specified file path.

        Updates 'updated' timestamp before saving.

        Args:
            portfolio: Portfolio to save
            filepath: Path where to save the portfolio

        Raises:
            IOError: If save fails
        """
        logger.debug("Saving portfolio '%s' to: %s", portfolio.name, filepath)
        # Update timestamp
        portfolio.updated = get_current_timestamp()

        # Save using portfolio manager
        self.portfolio_manager.save_portfolio(portfolio, Path(filepath))
        logger.debug("Portfolio saved successfully: %s", portfolio.name)

    def toggle_readonly(self, portfolio: Portfolio, filepath: str) -> None:
        """
        Toggle readonly flag and save portfolio.

        Special handling: Saves directly to file to bypass readonly protection.

        Args:
            portfolio: Portfolio to toggle
            filepath: Path to portfolio file

        Raises:
            IOError: If save fails
        """
        old_value = portfolio.readonly
        portfolio.readonly = not portfolio.readonly
        portfolio.updated = get_current_timestamp()
        logger.debug("Toggling readonly for '%s': %s -> %s", portfolio.name, old_value, portfolio.readonly)

        save_path = Path(filepath)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        manager = PortfolioManager.get_instance()
        manager.save_portfolio(portfolio, save_path, allow_readonly=True)

        logger.debug("Portfolio readonly toggled and saved: %s", portfolio.name)

    def export_portfolio_to_path(self, portfolio: Portfolio, destination_path: str) -> tuple[bool, str]:
        """
        Export a portfolio to an external location with validation.

        Enhanced version of export_portfolio() with user-friendly error handling.
        Copies the portfolio JSON file to the specified destination.
        Works for both builtin and custom portfolios.

        Args:
            portfolio: Portfolio to export
            destination_path: Full path to destination file (must end with .json)

        Returns:
            Tuple of (success, message):
            - If successful: (True, success_message)
            - If failed: (False, error_message)
        """
        logger.debug(
            "Export portfolio '%s' (readonly: %s, %s patterns) to: {}",
            portfolio.name,
            portfolio.readonly,
            len(portfolio.patterns),
            destination_path,
        )

        # Validate destination path
        if not destination_path.endswith(".json"):
            error = "Destination file must have .json extension"
            logger.warning("Export validation failed: %s", error)
            return (False, error)

        dest = Path(destination_path)
        logger.debug("Export destination resolved: %s", dest.absolute())

        # Check if destination already exists
        if dest.exists():
            error = f"File already exists: {dest.name}"
            logger.warning("Export blocked: file already exists at %s", dest.absolute())
            return (False, error)

        # Create parent directory if needed
        try:
            if not dest.parent.exists():
                logger.debug("Creating destination directory: %s", dest.parent)
                dest.parent.mkdir(parents=True, exist_ok=True)
                logger.debug("Destination directory created successfully")
        except (OSError, ValueError) as e:
            # OSError: File system errors (permissions, disk full, invalid path)
            # ValueError: Invalid path or directory name
            error = f"Cannot create destination directory: {e!s}"
            logger.error("Export failed during directory creation - %s: %s", type(e).__name__, error)
            return (False, error)

        # Export portfolio data
        try:
            logger.debug("Serializing portfolio data to JSON")
            data = portfolio.to_dict()
            logger.debug("Portfolio data serialized: %s keys", len(data.keys()))

            logger.debug("Writing portfolio to file: %s", dest)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

            file_size = dest.stat().st_size
            success_msg = f"Portfolio '{portfolio.name}' exported successfully"
            logger.info(
                "Export successful: '%s' -> %s (%s bytes, %s patterns)",
                portfolio.name,
                dest.name,
                file_size,
                len(portfolio.patterns),
            )
            return (True, success_msg)

        except (OSError, ValueError, TypeError) as e:
            # OSError: File I/O errors (write permissions, disk full)
            # ValueError: Invalid data format for JSON serialization
            # TypeError: Non-serializable objects in portfolio data
            error = f"Export failed: {e!s}"
            logger.error("Export error during file write - %s: %s", type(e).__name__, error)
            return (False, error)
