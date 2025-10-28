"""
Delete Pattern Command - Remove a pattern from a portfolio with confirmation.

Provides confirmation dialog and handles portfolio update with integrity checks.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ..core.helpers import format_aligned_summary
from ..core.logger import get_logger
from ..core.models import Pattern, Portfolio
from ..services.portfolio_service import PortfolioService

if TYPE_CHECKING:
    import sublime  # pyright: ignore[reportMissingImports]


class DeletePatternCommand:
    """
    Command to delete a pattern from a portfolio.

    Shows confirmation dialog with pattern details before deletion.
    Updates portfolio.updated field with current date.
    """

    def __init__(self, portfolio_service: PortfolioService | None = None) -> None:
        """
        Initialize the command.

        Args:
            portfolio_service: Optional PortfolioService instance (for testing)
        """
        self.portfolio_service = portfolio_service or PortfolioService()

    def run(
        self,
        window: sublime.Window,
        pattern: Pattern,
        portfolio: Portfolio,
    ) -> None:
        """
        Execute the delete pattern command with confirmation.

        This is an async operation - the actual deletion happens in the callback
        after user confirmation. Success/failure is communicated via status messages.

        Args:
            window: Sublime Text window instance
            pattern: Pattern to delete
            portfolio: Portfolio containing the pattern
        """
        logger = get_logger()
        logger.debug(f"Delete pattern requested: '{pattern.name}' from portfolio '{portfolio.name}'")

        # Build confirmation summary
        type_label = "Dynamic" if pattern.is_dynamic() else "Static"

        summary_items = [
            ("Pattern Name", pattern.name),
            ("Type", type_label),
            ("Description", pattern.description or "(no description)"),
            ("Portfolio", portfolio.name),
        ]

        summary_lines = format_aligned_summary("⚠️ Confirm Pattern Deletion", summary_items)

        # Build Quick Panel items with summary + warning + actions
        items = [
            *summary_lines,
            "",
            "⚠️ This action cannot be undone.",
            "",
            "─" * 60,
            "🗑️ Delete this pattern",
            "❌ Cancel",
        ]

        def on_select(index: int) -> None:
            """Handle user confirmation response."""
            # User cancelled
            if index == -1:
                logger.debug(f"Delete cancelled by user for pattern '{pattern.name}'")
                window.status_message(f"Regex Lab: Delete cancelled for '{pattern.name}'")
                return

            # Calculate action indices
            delete_index = len(summary_lines) + 4  # "🗑️ Delete this pattern"
            cancel_index = len(summary_lines) + 5  # "❌ Cancel"

            if index == delete_index:
                logger.debug(f"Delete confirmed by user for pattern '{pattern.name}'")
                self._execute_delete(window, pattern, portfolio)
            elif index == cancel_index:
                logger.debug(f"Delete cancelled by user for pattern '{pattern.name}'")
                window.status_message(f"Regex Lab: Delete cancelled for '{pattern.name}'")
            else:
                # User clicked on summary/warning line (re-show panel)
                logger.debug("Summary line clicked, re-showing confirmation")
                self.run(window, pattern, portfolio)

        logger.debug("Showing delete confirmation panel")

        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
        except (ImportError, AttributeError):
            window.show_quick_panel(items, on_select)

        # Async operation - no return value (deletion happens in callback)

    def _execute_delete(
        self,
        window: sublime.Window,
        pattern: Pattern,
        portfolio: Portfolio,
    ) -> None:
        """
        Execute pattern deletion after confirmation.

        Args:
            window: Sublime Text window instance
            pattern: Pattern to delete
            portfolio: Portfolio containing the pattern
        """
        logger = get_logger()

        # Find pattern in portfolio
        try:
            pattern_index = portfolio.patterns.index(pattern)
            logger.debug(f"Pattern found at index {pattern_index} in portfolio '{portfolio.name}'")
        except ValueError:
            logger.error(f"Pattern '{pattern.name}' not found in portfolio '{portfolio.name}'")
            window.status_message(f"Regex Lab: Error - Pattern '{pattern.name}' not found")
            return

        # Remove pattern from portfolio
        removed_pattern = portfolio.patterns.pop(pattern_index)
        logger.debug(f"Pattern '{removed_pattern.name}' removed from portfolio (index {pattern_index})")

        # Update portfolio.updated field with today's date (ISO format)
        today = datetime.now().strftime("%Y-%m-%d")
        portfolio.updated = today
        logger.debug(f"Portfolio updated field set to: {today}")

        # Save portfolio
        try:
            portfolio_path = self.portfolio_service.portfolio_manager._portfolio_paths.get(portfolio.name)
            if not portfolio_path:
                raise ValueError(f"Portfolio path not found for '{portfolio.name}'")

            logger.debug(f"Saving portfolio '{portfolio.name}' to: {portfolio_path}")
            self.portfolio_service.save_portfolio(portfolio, str(portfolio_path))
            logger.debug(f"Portfolio '{portfolio.name}' saved successfully")

            # Show success message
            window.status_message(f"Regex Lab: Pattern '{pattern.name}' deleted successfully")
            logger.debug(f"Delete operation completed successfully for pattern '{pattern.name}'")

        except (ValueError, OSError) as e:
            logger.error(f"Error saving portfolio after delete: {e}")
            # Rollback: add pattern back to portfolio
            portfolio.patterns.insert(pattern_index, removed_pattern)
            logger.debug(f"Rollback: Pattern '{pattern.name}' restored to portfolio at index {pattern_index}")
            window.status_message(f"Regex Lab: Error deleting pattern - {e}")
