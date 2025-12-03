"""
Edit Pattern Command - Edit pattern fields with submenu workflow.

Provides Quick Panel submenu to edit Name/Description/Regex/Default Panel.
Auto-detects type from regex content (dynamic if contains {{VAR}}).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from ..core.constants import (
    ICON_DYNAMIC_PATTERN,
    ICON_EDIT,
    ICON_FIND_IN_FILES_PANEL,
    ICON_FIND_PANEL,
    ICON_REPLACE_PANEL,
    ICON_STATIC_PATTERN,
)
from ..core.helpers import show_persistent_status
from ..core.logger import get_logger
from ..core.models import Pattern, PatternType, Portfolio
from ..services.portfolio_service import PortfolioService

if TYPE_CHECKING:
    import sublime  # pyright: ignore[reportMissingImports]


class EditPatternCommand:
    """
    Command to edit a pattern's fields with submenu workflow.

    Shows submenu with edit options for each field.
    Auto-detects pattern type from regex content.
    Updates portfolio.updated field on save.
    """

    # Regex pattern to detect dynamic variables
    DYNAMIC_VAR_PATTERN = re.compile(r"{{[^}]+}}")

    def __init__(self, portfolio_service: PortfolioService | None = None) -> None:
        """
        Initialize the command.

        Args:
            portfolio_service: Optional PortfolioService instance (for testing)
        """
        self.portfolio_service = portfolio_service or PortfolioService()
        self.window: sublime.Window | None = None
        self.pattern: Pattern | None = None
        self.portfolio: Portfolio | None = None
        self.modified = False  # Track if any changes made

    def run(
        self,
        window: sublime.Window,
        pattern: Pattern,
        portfolio: Portfolio,
    ) -> None:
        """
        Execute the edit pattern command.

        Args:
            window: Sublime Text window instance
            pattern: Pattern to edit
            portfolio: Portfolio containing the pattern
        """
        logger = get_logger()
        logger.debug(f"Edit pattern started: '{pattern.name}' from portfolio '{portfolio.name}'")

        self.window = window
        self.pattern = pattern
        self.portfolio = portfolio
        self.modified = False

        # Show main context in status bar
        self._show_main_status()

        # Show edit submenu
        self._show_edit_submenu()

    def _show_main_status(self) -> None:
        """Display main editing context in status bar with persistent display."""
        if self.window and self.pattern and self.portfolio:
            status = f"Regex Lab: Editing '{self.pattern.name}' - {self.pattern.description} [{self.portfolio.name}]"
            show_persistent_status(self.window, status)

    def _show_edit_submenu(self) -> None:
        """Show Quick Panel submenu with edit options."""
        if not self.window or not self.pattern:
            return

        logger = get_logger()
        logger.debug("Showing edit submenu")

        # Get current type icon
        type_icon = ICON_DYNAMIC_PATTERN if self.pattern.is_dynamic() else ICON_STATIC_PATTERN
        type_label = "Dynamic" if self.pattern.is_dynamic() else "Static"

        # Get current default_panel display
        panel_display = "None"
        if self.pattern.default_panel:
            panel_icons = {
                "find": ICON_FIND_PANEL,
                "replace": ICON_REPLACE_PANEL,
                "find_in_files": ICON_FIND_IN_FILES_PANEL,
            }
            panel_icon = panel_icons.get(self.pattern.default_panel, "")
            panel_display = f"{panel_icon} {self.pattern.default_panel}"

        items = [
            [
                f"{ICON_EDIT} Edit Name",
                f"Current: {self.pattern.name}",
            ],
            [
                f"{ICON_EDIT} Edit Description",
                f"Current: {self.pattern.description}",
            ],
            [
                f"{ICON_EDIT} Edit Regex",
                f"Current: {self.pattern.regex} ({type_icon} {type_label})",
            ],
            [
                f"{ICON_EDIT} Edit Default Panel",
                f"Current: {panel_display}",
            ],
            [
                "✅ Done",
                "Save changes and exit" if self.modified else "Exit without changes",
            ],
        ]

        self.window.show_quick_panel(
            items,
            lambda index: self._handle_submenu_selection(index),
            placeholder=f"Edit Pattern: {self.pattern.name}",
        )

    def _handle_submenu_selection(self, index: int) -> None:
        """
        Handle user selection from edit submenu.

        Args:
            index: Selected index (-1 = cancelled, 0-3 = edit fields, 4 = done)
        """
        logger = get_logger()

        if index == -1:
            # User cancelled
            logger.debug("Edit submenu cancelled")
            if self.modified and self.window:
                self.window.status_message("Regex Lab: Edit cancelled (changes not saved)")
            return

        if index == 0:
            self._edit_name()
        elif index == 1:
            self._edit_description()
        elif index == 2:
            self._edit_regex()
        elif index == 3:
            self._edit_default_panel()
        elif index == 4:
            self._done()

    def _edit_name(self) -> None:
        """Edit pattern name."""
        if not self.window or not self.pattern or not self.portfolio:
            return

        logger = get_logger()
        logger.debug(f"Editing name for pattern '{self.pattern.name}'")

        # Update status bar with persistent display
        status = f"Regex Lab: Editing Name for '{self.pattern.name}' [{self.portfolio.name}]"
        show_persistent_status(self.window, status)

        def on_done(new_name: str) -> None:
            """Handle name input completion."""
            new_name = new_name.strip()
            if not new_name:
                logger.debug("Empty name provided, no change")
                self._show_main_status()
                self._show_edit_submenu()
                return

            if new_name != self.pattern.name:  # type: ignore
                old_name = self.pattern.name  # type: ignore
                self.pattern.name = new_name  # type: ignore
                self.modified = True
                logger.debug(f"Pattern name changed: '{old_name}' → '{new_name}'")

            self._show_main_status()
            self._show_edit_submenu()

        def on_cancel() -> None:
            """Handle name input cancellation."""
            logger.debug("Name edit cancelled")
            self._show_main_status()
            self._show_edit_submenu()

        self.window.show_input_panel(
            "Edit Pattern Name:",
            self.pattern.name,
            on_done,
            None,
            on_cancel,
        )

    def _edit_description(self) -> None:
        """Edit pattern description."""
        if not self.window or not self.pattern or not self.portfolio:
            return

        logger = get_logger()
        logger.debug(f"Editing description for pattern '{self.pattern.name}'")

        # Update status bar with persistent display
        status = f"Regex Lab: Editing Description for '{self.pattern.name}' [{self.portfolio.name}]"
        show_persistent_status(self.window, status)

        def on_done(new_desc: str) -> None:
            """Handle description input completion."""
            new_desc = new_desc.strip()
            if not new_desc:
                logger.debug("Empty description provided, no change")
                self._show_main_status()
                self._show_edit_submenu()
                return

            if new_desc != self.pattern.description:  # type: ignore
                old_desc = self.pattern.description  # type: ignore
                self.pattern.description = new_desc  # type: ignore
                self.modified = True
                logger.debug(f"Pattern description changed: '{old_desc}' → '{new_desc}'")

            self._show_main_status()
            self._show_edit_submenu()

        def on_cancel() -> None:
            """Handle description input cancellation."""
            logger.debug("Description edit cancelled")
            self._show_main_status()
            self._show_edit_submenu()

        self.window.show_input_panel(
            "Edit Pattern Description:",
            self.pattern.description,
            on_done,
            None,
            on_cancel,
        )

    def _edit_regex(self) -> None:
        """Edit pattern regex with auto-detect type."""
        if not self.window or not self.pattern or not self.portfolio:
            return

        logger = get_logger()
        logger.debug(f"Editing regex for pattern '{self.pattern.name}'")

        # Update status bar with persistent display
        status = f"Regex Lab: Editing Regex for '{self.pattern.name}' [{self.portfolio.name}]"
        show_persistent_status(self.window, status)

        def on_done(new_regex: str) -> None:
            """Handle regex input completion with type auto-detection."""
            # Do not strip regex! Trailing spaces might be intentional.
            # new_regex = new_regex.strip()
            if not new_regex:
                logger.debug("Empty regex provided, no change")
                self._show_main_status()
                self._show_edit_submenu()
                return

            if new_regex != self.pattern.regex:  # type: ignore
                old_regex = self.pattern.regex  # type: ignore
                old_type = self.pattern.type  # type: ignore
                self.pattern.regex = new_regex  # type: ignore

                # Auto-detect type from regex content
                if self.DYNAMIC_VAR_PATTERN.search(new_regex):
                    self.pattern.type = PatternType.DYNAMIC  # type: ignore
                    logger.debug("Auto-detected type: dynamic (found {{VAR}} pattern)")
                else:
                    self.pattern.type = PatternType.STATIC  # type: ignore
                    logger.debug("Auto-detected type: static (no {{VAR}} pattern)")

                self.modified = True
                logger.debug(f"Pattern regex changed: '{old_regex}' → '{new_regex}'")
                if old_type != self.pattern.type:  # type: ignore
                    logger.debug(f"Pattern type changed: {old_type} → {self.pattern.type}")  # type: ignore

            self._show_main_status()
            self._show_edit_submenu()

        def on_cancel() -> None:
            """Handle regex input cancellation."""
            logger.debug("Regex edit cancelled")
            self._show_main_status()
            self._show_edit_submenu()

        self.window.show_input_panel(
            "Edit Pattern Regex:",
            self.pattern.regex,
            on_done,
            None,
            on_cancel,
        )

    def _edit_default_panel(self) -> None:
        """Edit pattern default_panel with Quick Panel selection."""
        if not self.window or not self.pattern or not self.portfolio:
            return

        logger = get_logger()
        logger.debug(f"Editing default_panel for pattern '{self.pattern.name}'")

        # Update status bar with persistent display
        status = f"Regex Lab: Editing Default Panel for '{self.pattern.name}' [{self.portfolio.name}]"
        show_persistent_status(self.window, status)

        items = [
            [f"{ICON_FIND_PANEL} find", "Inject into Find panel"],
            [f"{ICON_REPLACE_PANEL} replace", "Inject into Replace panel"],
            [f"{ICON_FIND_IN_FILES_PANEL} find_in_files", "Inject into Find In Files panel"],
            ["❌ None", "No default panel (show Actions menu)"],
        ]

        def on_select(index: int) -> None:
            """Handle panel selection."""
            if index == -1:
                logger.debug("Default panel edit cancelled")
                self._show_main_status()
                self._show_edit_submenu()
                return

            old_panel = self.pattern.default_panel  # type: ignore

            if index == 0:
                new_panel = "find"
            elif index == 1:
                new_panel = "replace"
            elif index == 2:
                new_panel = "find_in_files"
            else:  # index == 3
                new_panel = None

            if new_panel != old_panel:
                self.pattern.default_panel = new_panel  # type: ignore
                self.modified = True
                logger.debug(f"Pattern default_panel changed: {old_panel} → {new_panel}")

            self._show_main_status()
            self._show_edit_submenu()

        self.window.show_quick_panel(items, on_select, placeholder="Select Default Panel")

    def _done(self) -> None:
        """Save changes and exit edit workflow."""
        if not self.window or not self.pattern or not self.portfolio:
            return

        logger = get_logger()

        if not self.modified:
            logger.debug("No changes made, exiting without save")
            self.window.status_message("Regex Lab: No changes made")
            return

        logger.debug(f"Saving changes for pattern '{self.pattern.name}'")

        # Update portfolio.updated field with today's date (ISO format)
        today = datetime.now().strftime("%Y-%m-%d")
        self.portfolio.updated = today
        logger.debug(f"Portfolio updated field set to: {today}")

        # Save portfolio
        try:
            portfolio_path = self.portfolio_service.portfolio_manager._portfolio_paths.get(self.portfolio.name)
            if not portfolio_path:
                raise ValueError(f"Portfolio path not found for '{self.portfolio.name}'")

            logger.debug(f"Saving portfolio '{self.portfolio.name}' to: {portfolio_path}")
            self.portfolio_service.save_portfolio(self.portfolio, str(portfolio_path))
            logger.debug(f"Portfolio '{self.portfolio.name}' saved successfully")

            # Show success message
            self.window.status_message(f"Regex Lab: Pattern '{self.pattern.name}' updated [{self.portfolio.name}]")
            logger.debug(f"Edit operation completed successfully for pattern '{self.pattern.name}'")

        except (ValueError, OSError) as e:
            logger.error(f"Error saving portfolio after edit: {e}")
            self.window.status_message(f"Regex Lab: Error saving changes - {e}")
