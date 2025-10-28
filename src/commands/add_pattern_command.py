"""
Add Pattern Command

This module provides a wizard interface for adding new patterns to existing portfolios.
The wizard guides users through pattern creation:
    1. Pattern Name (required, validated)
    2. Regex Pattern (required, validated for syntax)
    3. Description (optional)
    4. Auto-detection of Static vs Dynamic (based on regex analysis)
    5. Confirmation (displays summary, adds pattern to portfolio)

After creation, the pattern is saved to the portfolio file and the portfolio
is automatically reloaded to reflect the changes.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ..core.helpers import format_aligned_summary
from ..core.logger import get_logger
from ..core.models import Pattern, PatternType
from ..services.portfolio_service import PortfolioService

if TYPE_CHECKING:
    import sublime  # pyright: ignore[reportMissingImports]


class AddPatternCommand:
    """
    Command for adding new patterns to portfolios.

    Provides multi-step wizard interface:
    - Pattern name input
    - Regex pattern input with syntax validation
    - Optional description
    - Auto-detect static vs dynamic
    - Summary confirmation
    - Save and reload portfolio
    """

    def __init__(self) -> None:
        """Initialize Add Pattern command."""
        self.logger = get_logger()
        self.portfolio_service = PortfolioService()
        self.portfolio_name: str | None = None
        self.wizard_data: dict[str, Any] = {}

    def run(self, window: sublime.Window, portfolio_name: str) -> None:
        """
        Start Add Pattern wizard.

        Args:
            window: Sublime Text window instance
            portfolio_name: Name of portfolio to add pattern to
        """
        self.logger.debug("Add Pattern: Starting wizard for portfolio '%s'", portfolio_name)

        # Validate portfolio exists and is editable
        portfolio = self.portfolio_service.get_portfolio_by_name(portfolio_name)
        if not portfolio:
            self.logger.error("Add Pattern: Portfolio '%s' not found", portfolio_name)
            window.status_message(f"Regex Lab: Portfolio '{portfolio_name}' not found")
            return

        if portfolio.readonly:
            self.logger.error("Add Pattern: Portfolio '%s' is read-only", portfolio_name)
            window.status_message(f"Regex Lab: Portfolio '{portfolio_name}' is read-only")
            return

        self.portfolio_name = portfolio_name
        self.wizard_data = {}

        # Step 1: Ask for pattern name
        self._show_name_input(window)

    def _show_name_input(self, window: sublime.Window) -> None:
        """
        Show input panel for pattern name.

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Add Pattern: Showing name input panel")

        def on_done(name: str) -> None:
            name = name.strip()
            if not name:
                self.logger.debug("Add Pattern: Empty name, wizard cancelled")
                return

            # Validate name doesn't already exist in portfolio
            portfolio = self.portfolio_service.get_portfolio_by_name(self.portfolio_name)  # type: ignore
            if portfolio and any(p.name == name for p in portfolio.patterns):
                self.logger.warning("Add Pattern: Pattern name '%s' already exists", name)
                window.status_message(f"Regex Lab: Pattern '{name}' already exists in portfolio")
                # Re-show input panel
                self._show_name_input(window)
                return

            self.wizard_data["name"] = name
            self.logger.debug("Add Pattern: Name set to '%s'", name)

            # Step 2: Ask for regex pattern
            self._show_regex_input(window)

        def on_change(text: str) -> None:
            pass

        def on_cancel() -> None:
            self.logger.debug("Add Pattern: Name input cancelled")

        window.show_input_panel(
            "Pattern Name:",
            "",
            on_done,
            on_change,
            on_cancel,
        )

    def _show_regex_input(self, window: sublime.Window) -> None:
        """
        Show input panel for regex pattern.

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Add Pattern: Showing regex input panel")

        def on_done(regex: str) -> None:
            regex = regex.strip()
            if not regex:
                self.logger.debug("Add Pattern: Empty regex, wizard cancelled")
                return

            # Validate regex syntax
            try:
                re.compile(regex)
                self.logger.debug("Add Pattern: Regex syntax valid")
            except re.error as e:
                self.logger.warning("Add Pattern: Invalid regex syntax - %s", e)
                window.status_message(f"Regex Lab: Invalid regex syntax - {e}")
                # Re-show input panel
                self._show_regex_input(window)
                return

            self.wizard_data["regex"] = regex
            self.logger.debug("Add Pattern: Regex set to '%s'", regex)

            # Auto-detect pattern type (static vs dynamic)
            pattern_type = self._detect_pattern_type(regex)
            self.wizard_data["type"] = pattern_type
            self.logger.debug("Add Pattern: Detected type: %s", pattern_type.value)

            # Step 3: Ask for description (optional)
            self._show_description_input(window)

        def on_change(text: str) -> None:
            pass

        def on_cancel() -> None:
            self.logger.debug("Add Pattern: Regex input cancelled")

        window.show_input_panel(
            f"Regex Pattern for '{self.wizard_data['name']}':",
            "",
            on_done,
            on_change,
            on_cancel,
        )

    def _show_description_input(self, window: sublime.Window) -> None:
        """
        Show input panel for description (optional).

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Add Pattern: Showing description input panel")

        def on_done(description: str) -> None:
            description = description.strip()
            if description:
                self.wizard_data["description"] = description
                self.logger.debug("Add Pattern: Description set")
            else:
                self.wizard_data["description"] = ""
                self.logger.debug("Add Pattern: No description provided")

            # Step 4: Show confirmation summary
            self._show_confirmation(window)

        def on_change(text: str) -> None:
            pass

        def on_cancel() -> None:
            self.logger.debug("Add Pattern: Description input cancelled")
            # Still show confirmation even if description is cancelled
            self.wizard_data["description"] = ""
            self._show_confirmation(window)

        window.show_input_panel(
            "Description (optional):",
            "",
            on_done,
            on_change,
            on_cancel,
        )

    def _show_confirmation(self, window: sublime.Window) -> None:
        """
        Show confirmation panel with pattern summary.

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Add Pattern: Showing confirmation panel")

        # Build summary
        summary_items = [
            ("Portfolio", self.portfolio_name),
            ("Pattern Name", self.wizard_data["name"]),
            ("Regex", self.wizard_data["regex"]),
            ("Type", self.wizard_data["type"].value),
        ]

        if self.wizard_data.get("description"):
            summary_items.append(("Description", self.wizard_data["description"]))

        summary_lines = format_aligned_summary("New Pattern Summary", summary_items)

        # Build Quick Panel items with summary + actions
        # Format: [*summary_lines, "", separator, "✅ Create", "❌ Cancel"]
        items = [*summary_lines, "", "─" * 60, "✅ Create this pattern", "❌ Cancel"]

        def on_select(index: int) -> None:
            # User cancelled
            if index == -1:
                self.logger.debug("Add Pattern: Confirmation cancelled")
                window.status_message("Regex Lab: Pattern creation cancelled")
                return

            # Calculate action indices (summary + blank + separator + 2 actions)
            create_index = len(summary_lines) + 2  # "✅ Create this pattern"
            cancel_index = len(summary_lines) + 3  # "❌ Cancel"

            if index == create_index:
                self.logger.debug("Add Pattern: User confirmed pattern creation")
                self._create_pattern(window)
            elif index == cancel_index:
                self.logger.debug("Add Pattern: User cancelled pattern creation")
                window.status_message("Regex Lab: Pattern creation cancelled")
            else:
                # User clicked on summary line (ignore, re-show panel)
                self.logger.debug("Add Pattern: Summary line clicked, re-showing confirmation")
                self._show_confirmation(window)

        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
            self.logger.debug("Add Pattern: Confirmation panel displayed")
        except (ImportError, AttributeError):
            window.show_quick_panel(items, on_select)
            self.logger.debug("Add Pattern: Confirmation panel displayed (fallback)")

    def _create_pattern(self, window: sublime.Window) -> None:
        """
        Create pattern and add to portfolio.

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Add Pattern: Creating pattern and adding to portfolio")

        try:
            # Create Pattern object
            pattern = Pattern(
                name=self.wizard_data["name"],
                regex=self.wizard_data["regex"],
                type=self.wizard_data["type"],
                description=self.wizard_data.get("description", ""),
            )

            # Add pattern to portfolio
            success = self.portfolio_service.add_pattern_to_portfolio(
                self.portfolio_name,  # type: ignore
                pattern,
            )

            if success:
                self.logger.info(
                    "Add Pattern: Pattern '%s' added to portfolio '%s'",
                    pattern.name,
                    self.portfolio_name,
                )
                window.status_message(f"Regex Lab: Pattern '{pattern.name}' added to portfolio '{self.portfolio_name}'")
            else:
                self.logger.error(
                    "Add Pattern: Failed to add pattern '%s' to portfolio '%s'",
                    pattern.name,
                    self.portfolio_name,
                )
                window.status_message(f"Regex Lab: Failed to add pattern '{pattern.name}'")

        except Exception as e:
            self.logger.error("Add Pattern: Error creating pattern - %s: %s", type(e).__name__, e)
            window.status_message(f"Regex Lab: Error creating pattern - {e}")

    def _detect_pattern_type(self, regex: str) -> PatternType:
        """
        Auto-detect if pattern is static or dynamic based on regex analysis.

        Rules:
        - Dynamic: Contains variables ($VAR, ${VAR}, {{VAR}})
        - Static: No variables detected

        Args:
            regex: Regex pattern to analyze

        Returns:
            PatternType.STATIC or PatternType.DYNAMIC
        """
        # Check for variable patterns:
        # $VAR, ${VAR}, {{VAR}}, {VAR}
        variable_patterns = [
            r"\$[A-Z_][A-Z0-9_]*",  # $VAR
            r"\$\{[A-Z_][A-Z0-9_]*\}",  # ${VAR}
            r"\{\{[A-Z_][A-Z0-9_]*\}\}",  # {{VAR}}
            r"\{[A-Z_][A-Z0-9_]*\}",  # {VAR}
        ]

        for pattern in variable_patterns:
            if re.search(pattern, regex):
                self.logger.debug("Add Pattern: Detected variable pattern, type = DYNAMIC")
                return PatternType.DYNAMIC

        self.logger.debug("Add Pattern: No variables detected, type = STATIC")
        return PatternType.STATIC
