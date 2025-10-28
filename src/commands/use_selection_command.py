"""
Use Selection Command - Create pattern from selected text.

Provides quick pattern creation workflow from selected text in editor:
1. Quick Panel: Choose action (Create Pattern / Use as Find/Replace/Find in Files)
2. If Create Pattern: Simplified wizard (name + portfolio selection)
3. If Use as Pattern: Direct injection into corresponding panel

Context-aware: Only available when text is selected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.logger import get_logger
from ..core.models import Pattern, PatternType, Portfolio
from ..services.pattern_service import PatternService
from ..services.portfolio_service import PortfolioService
from ..utils.panel_injection import (
    inject_into_find_in_files_panel,
    inject_into_find_panel,
    inject_into_replace_panel,
)

if TYPE_CHECKING:
    import sublime


class RegexLabUseSelectionCommand:
    """
    Command to create a pattern from selected text or inject into panels.

    Workflow:
    1. Get selected text from active view
    2. Show Quick Panel with 4 actions:
       - Create New Pattern (save to portfolio)
       - Use as Find Pattern (Ctrl+F panel)
       - Use as Replace Pattern (Ctrl+H panel)
       - Use as Find in Files Pattern (Ctrl+Shift+F panel)
    3. Execute selected action

    Context: Only enabled when text is selected (handled by keymap context)
    """

    def __init__(
        self,
        pattern_service: PatternService | None = None,
        portfolio_service: PortfolioService | None = None,
    ) -> None:
        """
        Initialize Use Selection command.

        Args:
            pattern_service: Optional PatternService instance (for testing)
            portfolio_service: Optional PortfolioService instance (for testing)
        """
        self.pattern_service = pattern_service or PatternService()
        self.portfolio_service = portfolio_service or PortfolioService()
        self.logger = get_logger()

    def run(self, window: sublime.Window) -> None:
        """
        Execute Use Selection command.

        Gets selected text and shows action Quick Panel.

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Use Selection: Command started")

        # Get active view
        view = window.active_view()
        if not view:
            window.status_message("Regex Lab: No active view")
            self.logger.warning("Use Selection: No active view found")
            return

        # Get selected text (first selection only)
        selections = view.sel()
        if not selections or selections[0].empty():
            window.status_message("Regex Lab: No text selected")
            self.logger.warning("Use Selection: No text selected")
            return

        selected_text = view.substr(selections[0])
        self.logger.debug("Use Selection: Selected text (%s chars): %s", len(selected_text), selected_text[:50])

        # Show action Quick Panel
        self._show_action_menu(window, selected_text)

    def _show_action_menu(self, window: sublime.Window, selected_text: str) -> None:
        """
        Show Quick Panel with available actions.

        Actions:
        1. Create New Pattern (save to portfolio)
        2. Use as Find Pattern (inject directly into Find panel)
        3. Use as Replace Pattern (inject directly into Replace panel)
        4. Use as Find in Files Pattern (inject directly into Find in Files panel)

        Args:
            window: Sublime Text window instance
            selected_text: Text selected by user
        """
        self.logger.debug("Use Selection: Showing action menu")

        items = [
            ["✨ Create New Pattern", "Save selected text as a new pattern in a portfolio"],
            ["🔍 Use as Find Pattern", "Inject selected text directly into Find panel (Ctrl+F)"],
            ["🔄 Use as Replace Pattern", "Inject selected text directly into Replace panel (Ctrl+H)"],
            [
                "📁 Use as Find in Files Pattern",
                "Inject selected text directly into Find in Files panel (Ctrl+Shift+F)",
            ],
        ]

        def on_select(index: int) -> None:
            if index == -1:
                self.logger.debug("Use Selection: Action menu cancelled")
                return

            if index == 0:
                # Create New Pattern
                self.logger.debug("Use Selection: User chose 'Create New Pattern'")
                self._start_pattern_wizard(window, selected_text)
            elif index == 1:
                # Use as Find Pattern
                self.logger.debug("Use Selection: User chose 'Use as Find Pattern'")
                inject_into_find_panel(window, selected_text, "Selected Text")
            elif index == 2:
                # Use as Replace Pattern
                self.logger.debug("Use Selection: User chose 'Use as Replace Pattern'")
                inject_into_replace_panel(window, selected_text, "Selected Text")
            elif index == 3:
                # Use as Find in Files Pattern
                self.logger.debug("Use Selection: User chose 'Use as Find in Files Pattern'")
                inject_into_find_in_files_panel(window, selected_text, "Selected Text")

        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
            self.logger.debug("Use Selection: Action menu displayed with MONOSPACE_FONT")
        except (ImportError, AttributeError):
            window.show_quick_panel(items, on_select)
            self.logger.debug("Use Selection: Action menu displayed (fallback mode)")

    def _start_pattern_wizard(self, window: sublime.Window, selected_text: str) -> None:
        """
        Start simplified pattern creation wizard.

        Workflow:
        1. Input panel: Pattern name
        2. Quick Panel: Portfolio selection
        3. Save pattern to portfolio

        Args:
            window: Sublime Text window instance
            selected_text: Text to use as pattern regex
        """
        self.logger.debug("Use Selection: Starting pattern creation wizard")

        # Step 1: Ask for pattern name
        def on_name_done(pattern_name: str) -> None:
            if not pattern_name.strip():
                self.logger.debug("Use Selection: Empty pattern name, wizard cancelled")
                return

            pattern_name = pattern_name.strip()
            self.logger.debug("Use Selection: Pattern name entered: '%s'", pattern_name)

            # Step 2: Show portfolio selection
            self._show_portfolio_selection(window, pattern_name, selected_text)

        window.show_input_panel(
            "Pattern Name:",
            "",
            on_name_done,
            None,  # on_change
            None,  # on_cancel
        )
        self.logger.debug("Use Selection: Pattern name input panel displayed")

    def _show_portfolio_selection(self, window: sublime.Window, pattern_name: str, selected_text: str) -> None:
        """
        Show Quick Panel to select target portfolio.

        Only shows custom (non-builtin, non-readonly) portfolios.

        Args:
            window: Sublime Text window instance
            pattern_name: Name for the new pattern
            selected_text: Text to use as pattern regex
        """
        self.logger.debug("Use Selection: Showing portfolio selection")

        # Get all loaded portfolios
        portfolios = self.portfolio_service.get_all_portfolios()
        self.logger.debug("Use Selection: Found %s loaded portfolios", len(portfolios))

        # Filter: Only custom, non-readonly portfolios
        editable_portfolios = [p for p in portfolios if not p.readonly]
        self.logger.debug("Use Selection: Found %s editable portfolios", len(editable_portfolios))

        if not editable_portfolios:
            window.status_message("Regex Lab: No editable portfolios available. Create one first.")
            self.logger.warning("Use Selection: No editable portfolios found")
            return

        # Build Quick Panel items
        from ..core.helpers import pluralize

        items = []
        for portfolio in editable_portfolios:
            pattern_count = len(portfolio.patterns)
            description = f"{pattern_count} {pluralize(pattern_count, 'pattern')}"
            items.append([f"📂 {portfolio.name}", description])

        self.logger.debug("Use Selection: Displaying %s portfolio options", len(items))

        def on_select(index: int) -> None:
            if index == -1:
                self.logger.debug("Use Selection: Portfolio selection cancelled")
                return

            selected_portfolio = editable_portfolios[index]
            self.logger.debug("Use Selection: Portfolio selected: '%s'", selected_portfolio.name)

            # Create and save pattern
            self._create_pattern(window, pattern_name, selected_text, selected_portfolio)

        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
            self.logger.debug("Use Selection: Portfolio selection displayed with MONOSPACE_FONT")
        except (ImportError, AttributeError):
            window.show_quick_panel(items, on_select)
            self.logger.debug("Use Selection: Portfolio selection displayed (fallback mode)")

    def _create_pattern(
        self, window: sublime.Window, pattern_name: str, selected_text: str, portfolio: Portfolio
    ) -> None:
        """
        Create and save new pattern to portfolio.

        Creates a static pattern with selected text as regex.

        Args:
            window: Sublime Text window instance
            pattern_name: Name for the new pattern
            selected_text: Text to use as pattern regex
            portfolio: Target portfolio to save pattern
        """
        self.logger.debug("Use Selection: Creating pattern '%s' in portfolio '%s'", pattern_name, portfolio.name)

        try:
            # Create new static pattern
            new_pattern = Pattern(
                name=pattern_name,
                regex=selected_text,
                type=PatternType.STATIC,
                description=f"Created from selection ({len(selected_text)} chars)",
                default_panel=None,
            )

            self.logger.debug(
                "Use Selection: Pattern object created (type: STATIC, regex length: %s)",
                len(selected_text),
            )

            # Add pattern to portfolio
            portfolio.patterns.append(new_pattern)
            self.logger.debug("Use Selection: Pattern added to portfolio (total patterns: %s)", len(portfolio.patterns))

            # Save portfolio to disk
            portfolio_path = self.portfolio_service.portfolio_manager._portfolio_paths.get(portfolio.name)
            if not portfolio_path:
                raise ValueError(f"Portfolio path not found for '{portfolio.name}'")

            self.portfolio_service.save_portfolio(portfolio, str(portfolio_path))
            self.logger.info(
                "Use Selection: Pattern '%s' saved to portfolio '%s' successfully",
                pattern_name,
                portfolio.name,
            )

            window.status_message(f"Regex Lab: Pattern '{pattern_name}' created in portfolio '{portfolio.name}'")

        except (ValueError, OSError) as e:
            # ValueError: Invalid pattern data
            # OSError: File I/O error during save
            window.status_message(f"Regex Lab: Error creating pattern - {e}")
            self.logger.error(
                "Use Selection: Error creating pattern '%s' - %s: %s",
                pattern_name,
                type(e).__name__,
                e,
            )
