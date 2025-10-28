"""
Portfolio Manager for Regex Lab.

Handles multiple portfolio loading, saving, and management.
Implements singleton pattern for portfolio state.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .helpers import is_builtin_portfolio_path
from .logger import get_logger
from .models import Portfolio

logger = get_logger()


class PortfolioManager:
    """
    Manages multiple regex pattern portfolios.

    Singleton pattern ensures consistent portfolio state across the application.
    Handles:
    - Multiple portfolios loaded simultaneously
    - Built-in "RegexLab" portfolio (special, always loaded first)
    - JSON file I/O with proper error handling
    - Soft immutability (readonly flag protection)

    Implementation:
        Uses @classmethod singleton pattern for explicit, readable initialization.
        Call get_instance() to obtain the singleton instance.
    """

    _instance: PortfolioManager | None = None

    def __init__(self) -> None:
        """
        Initialize the portfolio manager.

        Note:
            This should not be called directly. Use get_instance() instead.
        """
        self._loaded_portfolios: dict[str, Portfolio] = {}
        self._builtin_portfolio: Portfolio | None = None
        self._portfolio_paths: dict[str, Path] = {}

    @classmethod
    def get_instance(cls) -> PortfolioManager:
        """
        Get the singleton instance.

        Returns:
            The PortfolioManager singleton instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ========== Portfolio Loading ==========

    def load_portfolio_from_file(self, path: Path) -> Portfolio:
        """
        Load a portfolio from a JSON file.

        Args:
            path: Path to the JSON portfolio file

        Returns:
            Loaded Portfolio object

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the JSON is invalid or missing required fields
            PermissionError: If the file can't be read
        """
        if not path.exists():
            raise FileNotFoundError(f"Portfolio file not found: {path}")

        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in portfolio file: {e}") from e
        except PermissionError as e:
            raise PermissionError(f"Cannot read portfolio file: {e}") from e

        try:
            portfolio = Portfolio.from_dict(data)
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid portfolio data: {e}") from e

        return portfolio

    def load_portfolio(self, path: Path, set_as_builtin: bool = False, reload: bool = False) -> Portfolio:
        """
        Load a portfolio from file and add it to loaded portfolios.

        Args:
            path: Path to the portfolio file
            set_as_builtin: If True, set this portfolio as the built-in portfolio
            reload: If True, allow reloading an already loaded portfolio

        Returns:
            Loaded Portfolio object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If portfolio is invalid or name collision (unless reload=True)
        """
        portfolio = self.load_portfolio_from_file(path)

        # Check for name collision (unless reloading)
        if portfolio.name in self._loaded_portfolios and not set_as_builtin and not reload:
            raise ValueError(f"Portfolio '{portfolio.name}' is already loaded")

        # Add to loaded portfolios (overwrite if reload)
        self._loaded_portfolios[portfolio.name] = portfolio
        self._portfolio_paths[portfolio.name] = path

        # Set as built-in if requested
        if set_as_builtin:
            self._builtin_portfolio = portfolio
            logger.info(f"Built-in portfolio '{portfolio.name}' loaded from {path}")
        else:
            action = "reloaded" if reload else "loaded"
            logger.info(f"Portfolio '{portfolio.name}' {action} from {path}")

        return portfolio

    def unload_portfolio(self, name: str) -> bool:
        """
        Unload a portfolio by name.

        Built-in portfolio cannot be unloaded.

        Args:
            name: Name of the portfolio to unload

        Returns:
            True if unloaded, False if not found or protected

        Raises:
            ValueError: If trying to unload built-in portfolio
        """
        if name not in self._loaded_portfolios:
            logger.warning(f"Portfolio '{name}' not found")
            return False

        # Protect built-in portfolio
        if self._builtin_portfolio and self._builtin_portfolio.name == name:
            raise ValueError("Cannot unload built-in portfolio")

        # Remove from loaded portfolios
        del self._loaded_portfolios[name]
        if name in self._portfolio_paths:
            del self._portfolio_paths[name]

        logger.info(f"Portfolio '{name}' unloaded")
        return True

    # ========== Portfolio Saving ==========

    def save_portfolio(self, portfolio: Portfolio, path: Path | None = None, *, allow_readonly: bool = False) -> None:
        """
        Save a portfolio to a JSON file.

        Respects readonly flag (soft immutability).

        Args:
            portfolio: Portfolio object to save
            path: Path where to save the JSON file (if None, use tracked path)
            allow_readonly: Set True to bypass readonly guard (used by maintenance flows)

        Raises:
            ValueError: If portfolio is readonly or invalid
            PermissionError: If the file can't be written
            OSError: If directory creation fails
        """
        # Soft immutability check
        if portfolio.readonly and not allow_readonly:
            logger.warning(f"Portfolio '{portfolio.name}' is readonly, cannot save")
            raise ValueError(f"Portfolio '{portfolio.name}' is readonly")

        # Determine save path
        if path is None:
            # Use tracked path if available
            if portfolio.name in self._portfolio_paths:
                path = self._portfolio_paths[portfolio.name]
            else:
                raise ValueError(f"No path tracked for portfolio '{portfolio.name}'")

        # Update 'updated' timestamp
        portfolio.updated = datetime.now().strftime("%Y-%m-%d")

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        data = portfolio.to_dict()

        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Portfolio '{portfolio.name}' saved to {path}")
        except PermissionError as e:
            raise PermissionError(f"Cannot write portfolio file: {e}") from e
        except OSError as e:
            raise OSError(f"Failed to save portfolio: {e}") from e

    # ========== Multi-Portfolio Queries ==========

    def get_portfolio(self, name: str) -> Portfolio | None:
        """
        Get a loaded portfolio by name.

        Args:
            name: Portfolio name

        Returns:
            Portfolio object or None if not found
        """
        return self._loaded_portfolios.get(name)

    def get_all_portfolios(self) -> list[Portfolio]:
        """
        Get all loaded portfolios.

        Returns ordered list: ALL built-in portfolios first (alphabetically),
        then custom portfolios (alphabetically).

        Returns:
            List of loaded Portfolio objects
        """
        builtin: list[Portfolio] = []
        custom: list[Portfolio] = []

        # Separate all portfolios into builtin and custom groups
        for portfolio_name, portfolio in self._loaded_portfolios.items():
            portfolio_path = self._portfolio_paths.get(portfolio_name)
            is_builtin = is_builtin_portfolio_path(portfolio_path)

            if is_builtin:
                builtin.append(portfolio)
            else:
                custom.append(portfolio)

        # Sort each group alphabetically (case-insensitive)
        builtin.sort(key=lambda p: p.name.lower())
        custom.sort(key=lambda p: p.name.lower())

        # Return builtin first, then custom
        return builtin + custom

    def get_portfolio_names(self) -> list[str]:
        """
        Get names of all loaded portfolios.

        Returns ordered list: built-in first, then others alphabetically.

        Returns:
            List of portfolio names
        """
        return [p.name for p in self.get_all_portfolios()]

    def is_loaded(self, name: str) -> bool:
        """
        Check if a portfolio is currently loaded.

        Args:
            name: Portfolio name

        Returns:
            True if loaded, False otherwise
        """
        return name in self._loaded_portfolios

    def get_builtin_portfolio(self) -> Portfolio | None:
        """
        Get the built-in portfolio.

        Returns:
            Built-in Portfolio or None if not loaded
        """
        return self._builtin_portfolio

    # ========== Import/Export (User-Friendly Aliases) ==========

    def export_portfolio(self, portfolio: Portfolio, path: Path) -> None:
        """
        Export a portfolio to user-chosen location.

        User-friendly alias for save_portfolio().
        Allows users to save/share portfolios to any location.

        Args:
            portfolio: Portfolio to export
            path: User-chosen destination path

        Raises:
            ValueError: If portfolio is readonly
            PermissionError: If destination can't be written
            OSError: If export fails
        """
        self.save_portfolio(portfolio, path)

    def import_portfolio(self, path: Path) -> Portfolio:
        """
        Import a portfolio from user-chosen location.

        Loads portfolio into memory and adds to loaded portfolios.

        Args:
            path: User-chosen source file path

        Returns:
            Imported Portfolio object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If portfolio is invalid or name collision
            PermissionError: If file can't be read
        """
        return self.load_portfolio(path)

    # ========== Legacy Compatibility (V1 API) ==========

    def get_active_portfolio(self) -> Portfolio | None:
        """
        Get the active portfolio (legacy V1 API compatibility).

        In V2, the concept of "active portfolio" is replaced by "loaded portfolios".
        This method returns the first loaded portfolio for backward compatibility.

        Returns:
            First loaded Portfolio or None if no portfolio loaded
        """
        if self._builtin_portfolio:
            return self._builtin_portfolio
        # Fallback to first loaded portfolio
        if self._loaded_portfolios:
            return next(iter(self._loaded_portfolios.values()))
        return None

    def set_active_portfolio(self, portfolio: Portfolio) -> None:
        """
        Set a portfolio as active (legacy V1 API compatibility).

        In V2, portfolios are managed via load_portfolio()/unload_portfolio().
        This method adds the portfolio to loaded portfolios and sets as builtin.

        Args:
            portfolio: Portfolio to set as active
        """
        self._loaded_portfolios[portfolio.name] = portfolio
        self._builtin_portfolio = portfolio

    def load_and_set_active(self, path: Path) -> Portfolio:
        """
        Load a portfolio from file and set as active (legacy V1 API compatibility).

        Args:
            path: Path to the portfolio file

        Returns:
            Loaded Portfolio

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If portfolio is invalid
        """
        portfolio = self.load_portfolio(path, reload=True)
        self._builtin_portfolio = portfolio
        return portfolio

    def save_active_portfolio(self, path: Path) -> None:
        """
        Save the active portfolio to file (legacy V1 API compatibility).

        Args:
            path: Path where to save the portfolio

        Raises:
            ValueError: If no active portfolio or readonly
            PermissionError: If file can't be written
        """
        if self._builtin_portfolio is None:
            raise ValueError("No active portfolio to save")

        self.save_portfolio(self._builtin_portfolio, path)

    def clear_active_portfolio(self) -> None:
        """
        Clear all loaded portfolios (legacy V1 API compatibility).
        """
        self._loaded_portfolios.clear()
        self._portfolio_paths.clear()
        self._builtin_portfolio = None

    # ========== Utilities ==========

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton instance.

        Useful for testing to ensure clean state between tests.
        """
        cls._instance = None
