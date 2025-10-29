"""
Load Pattern Command - Load a pattern from active portfolio into Find panel.

Provides Quick Panel selection and injection into Sublime Text Find panel.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Callable

from ..core.constants import (
    DEFAULT_DATE_FORMAT,
    DEFAULT_QUICK_PANEL_SHOW_DESCRIPTIONS,
    DEFAULT_QUICK_PANEL_WIDTH,
    DEFAULT_SHOW_INPUT_HELP_POPUP,
    DEFAULT_TIME_FORMAT,
    ICON_DELETE,
    ICON_DISABLED,
    ICON_DYNAMIC_PATTERN,
    ICON_EDIT,
    ICON_FIND_IN_FILES_PANEL,
    ICON_FIND_PANEL,
    ICON_REPLACE_PANEL,
    ICON_STATIC_PATTERN,
)
from ..core.helpers import (
    format_centered_separator,
    format_quick_panel_line,
    is_builtin_portfolio_path,
    pluralize,
)
from ..core.logger import get_logger
from ..core.models import Pattern, Portfolio
from ..core.settings_manager import SettingsManager
from ..services.pattern_service import PatternService
from ..services.portfolio_service import PortfolioService
from ..utils.panel_injection import (
    inject_into_find_in_files_panel,
    inject_into_find_panel,
    inject_into_replace_panel,
)
from .delete_pattern_command import DeletePatternCommand
from .edit_pattern_command import EditPatternCommand
from .portfolio_manager_command_helper import collect_variables_for_pattern

if TYPE_CHECKING:
    import sublime  # pyright: ignore[reportMissingImports]


class LoadPatternCommand:
    """
    Command to load a pattern from the active portfolio.

    Shows Quick Panel with available patterns and injects selected pattern
    into the Find panel (for static patterns) or prompts for variables (dynamic).

    Version 2: Static and dynamic patterns supported
    """

    def __init__(
        self,
        pattern_service: PatternService | None = None,
        portfolio_service: PortfolioService | None = None,
        settings_manager: SettingsManager | None = None,
    ) -> None:
        """
        Initialize the command.

        Args:
            pattern_service: Optional PatternService instance (for testing)
            portfolio_service: Optional PortfolioService instance (for testing)
            settings_manager: Optional SettingsManager instance (for testing)
        """
        self.pattern_service = pattern_service or PatternService()
        self.portfolio_service = portfolio_service or PortfolioService()
        self.settings_manager = settings_manager or SettingsManager.get_instance()

    def run(self, window: sublime.Window) -> None:
        """
        Execute the command.

        Supports both V1 (single portfolio) and V2 (multi-portfolio) modes:
        - V2: Multiple portfolios with separators and [Portfolio] tags
        - V1 (fallback): Single portfolio, classic display

        Args:
            window: Sublime Text window instance
        """
        # Try V2 multi-portfolio mode first
        all_portfolios = self.portfolio_service.get_all_portfolios()

        if all_portfolios:
            # V2 Multi-Portfolio Mode
            self._run_multi_portfolio(window, all_portfolios)
        else:
            # V1 Single-Portfolio Mode (fallback for backward compatibility)
            self._run_single_portfolio(window)

    def _run_multi_portfolio(self, window: sublime.Window, all_portfolios: list[Portfolio]) -> None:
        """
        Run command in V2 multi-portfolio mode with grouped display.

        Portfolios are already sorted by get_all_portfolios() (builtin first, alphabetical).
        Patterns within each portfolio are sorted alphabetically for consistency.

        Args:
            window: Sublime Text window instance
            all_portfolios: List of loaded portfolios (already sorted by get_all_portfolios())
        """
        # Get Quick Panel width from settings
        panel_width = self.settings_manager.get("quick_panel_width", DEFAULT_QUICK_PANEL_WIDTH)

        # Portfolios already sorted by get_all_portfolios() - no need to re-sort

        # Build grouped display with separators
        items: list[list[str]] = []
        # Map: (Portfolio or None for separator, Pattern or None for separator)
        pattern_map: list[tuple[Portfolio | None, Pattern | None]] = []

        for portfolio in all_portfolios:
            patterns = portfolio.patterns
            if not patterns:
                continue

            # Sort patterns alphabetically by name (case-insensitive)
            patterns = sorted(patterns, key=lambda p: p.name.lower())

            # Determine if portfolio is truly builtin (based on file location)
            portfolio_path = self.portfolio_service.portfolio_manager._portfolio_paths.get(portfolio.name)
            is_builtin = is_builtin_portfolio_path(portfolio_path)

            # Add separator for this portfolio (centered with readonly indicator)
            separator_line = self._format_separator(portfolio.name, is_builtin, portfolio.readonly, panel_width)
            pattern_count = len(patterns)
            items.append([separator_line, f"{pattern_count} {pluralize(pattern_count, 'pattern')}"])
            pattern_map.append((None, None))  # Placeholder for separator (not selectable)

            # Add patterns from this portfolio with aligned formatting
            for pattern in patterns:
                formatted_line = self._format_pattern_line(pattern, portfolio.name, panel_width)

                # Check if descriptions should be shown
                show_descriptions = self.settings_manager.get(
                    "quick_panel_show_descriptions", DEFAULT_QUICK_PANEL_SHOW_DESCRIPTIONS
                )

                if show_descriptions:
                    description_line = self._format_description_line(pattern)
                    items.append([formatted_line, description_line])
                else:
                    # Single-line mode: no description
                    items.append([formatted_line])

                pattern_map.append((portfolio, pattern))

        if not pattern_map:
            window.status_message("Regex Lab: No patterns available")
            return

        # Show Quick Panel with pattern selector callback
        on_select = self._create_pattern_selector(window, pattern_map)

        # Show Quick Panel with monospace font for proper alignment
        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
        except (ImportError, AttributeError):
            # Fallback for tests (sublime module not available)
            window.show_quick_panel(items, on_select)

    def _run_single_portfolio(self, window: sublime.Window) -> None:
        """
        Run command in V1 single-portfolio mode (legacy/fallback).

        Classic display without separators or portfolio tags.

        Args:
            window: Sublime Text window instance
        """
        # Get active portfolio (V1 API)
        active_portfolio = self.portfolio_service.get_active_portfolio()

        if not active_portfolio:
            window.status_message("Regex Lab: No active portfolio")
            return

        # Get patterns from active portfolio
        patterns = active_portfolio.patterns

        if not patterns:
            window.status_message("Regex Lab: No patterns in active portfolio")
            return

        # Prepare Quick Panel items (classic format)
        items: list[list[str]] = []

        # Check if descriptions should be shown
        show_descriptions = self.settings_manager.get(
            "quick_panel_show_descriptions", DEFAULT_QUICK_PANEL_SHOW_DESCRIPTIONS
        )

        # Build pattern map for selector
        pattern_map: list[tuple[Portfolio | None, Pattern | None]] = []

        for pattern in patterns:
            # Line 1: Pattern name
            # Line 2 (optional): Smart description with panel icon or type info
            if show_descriptions:
                description_line = self._format_description_line(pattern)
                items.append([pattern.name, description_line])
            else:
                # Single-line mode: no description
                items.append([pattern.name])

            pattern_map.append((active_portfolio, pattern))

        # Show Quick Panel with pattern selector callback
        on_select = self._create_pattern_selector(window, pattern_map)

        # Show Quick Panel with monospace font for proper alignment
        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
        except (ImportError, AttributeError):
            # Fallback for tests (sublime module not available)
            window.show_quick_panel(items, on_select)

    def _format_separator(self, portfolio_name: str, is_builtin: bool, is_readonly: bool, panel_width: int) -> str:
        """
        Format a centered separator line for portfolio with readonly indicator.

        Delegates to helpers.format_centered_separator() for consistency.
        Adds 🔒 icon after name for builtin or readonly portfolios.

        Args:
            portfolio_name: Name of the portfolio
            is_builtin: Whether this is the builtin portfolio
            is_readonly: Whether the portfolio is readonly
            panel_width: Total width for Quick Panel (from settings)

        Returns:
            Centered separator string with optional readonly indicator

        Examples:
            Builtin portfolio:     "─────── Built-in 🔒 ───────"
            User readonly:         "─────── My Portfolio 🔒 ───────"
            User editable:         "─────── Custom Portfolio ───────"
        """
        # Build label with readonly indicator
        if is_builtin:
            label = f"{portfolio_name} (Built-in) 🔒"
        elif is_readonly:
            label = f"{portfolio_name} 🔒"
        else:
            label = portfolio_name

        return format_centered_separator(label, panel_width)

    def _format_pattern_line(self, pattern: Pattern, portfolio_name: str, panel_width: int) -> str:
        """
        Format a pattern line with aligned columns.

        Format (right-aligned suffix):
        Pattern Name                [Portfolio] 📄 Static

        Args:
            pattern: Pattern to format
            portfolio_name: Name of the portfolio
            panel_width: Total width for Quick Panel (from settings)

        Returns:
            Formatted line string
        """
        # Determine icon and type label
        icon = ICON_DYNAMIC_PATTERN if pattern.is_dynamic() else ICON_STATIC_PATTERN
        type_label = "Dynamic" if pattern.is_dynamic() else "Static "  # Add space after Static for alignment

        # Build right suffix: [Portfolio] Icon Type
        right_text = f"[{portfolio_name}] {icon} {type_label}"

        # Delegate to unified formatter
        return format_quick_panel_line(pattern.name, right_text, panel_width)

    def _format_description_line(self, pattern: Pattern) -> str:
        """
        Format description line for Quick Panel with smart panel icon.

        Shows ONLY the description, optionally prefixed with panel icon if
        pattern has default_panel configured. This avoids redundancy since
        type info (Static/Dynamic) is already shown in the main line (right side).

        Args:
            pattern: Pattern to format description for

        Returns:
            Formatted description string

        Examples:
            With default_panel:
                "🔍 Find FIXME comments in project files"
                "📁 Search across all project files"

            Without default_panel:
                "Find FIXME comments in project files"
                "Match email addresses in text"
        """
        # Panel icons mapping
        panel_icons = {
            "find": ICON_FIND_PANEL,
            "replace": ICON_REPLACE_PANEL,
            "find_in_files": ICON_FIND_IN_FILES_PANEL,
        }

        # If pattern has default_panel, show panel icon + description
        if pattern.default_panel and pattern.default_panel in panel_icons:
            panel_icon = panel_icons[pattern.default_panel]
            return f"{panel_icon} {pattern.description}"

        # Otherwise, show ONLY description (type info already in main line)
        return pattern.description

    def _show_pattern_actions_menu(
        self,
        window: sublime.Window,
        pattern: Pattern,
        portfolio: Portfolio,
        on_action_callback: Callable[[str, str | None], None],
    ) -> None:
        """
        Show Actions Quick Panel after pattern selection.

        Displays available actions for the selected pattern:
        - Use in Find / Replace / Find In Files (always available)
        - Edit Pattern (only if portfolio is editable)
        - Delete Pattern (only if portfolio is editable)

        Actions are context-aware:
        - Builtin portfolios: Edit/Delete not shown
        - User portfolios (readonly=true): Edit/Delete shown but disabled
        - User portfolios (readonly=false): Edit/Delete enabled

        Args:
            window: Sublime Text window instance
            pattern: Selected pattern
            portfolio: Portfolio containing the pattern
            on_action_callback: Callback function receiving (action_type, panel_type)
                - action_type: "use" | "edit" | "delete"
                - panel_type: "find" | "replace" | "find_in_files" (only for "use" actions)
        """
        logger = get_logger()
        logger.debug(f"Showing Actions menu for pattern '{pattern.name}' in portfolio '{portfolio.name}'")

        # Determine if portfolio is builtin (based on file path)
        portfolio_path = self.portfolio_service.portfolio_manager._portfolio_paths.get(portfolio.name)
        logger.debug(f"Portfolio path: {portfolio_path}")

        # Check if portfolio path indicates builtin
        is_builtin = is_builtin_portfolio_path(portfolio_path)

        logger.debug(f"Builtin detection: path={portfolio_path}, is_builtin={is_builtin}")

        # Check if portfolio is editable (not builtin + not readonly)
        is_editable = not is_builtin and not portfolio.readonly

        logger.debug(
            f"Portfolio '{portfolio.name}': builtin={is_builtin}, readonly={portfolio.readonly}, editable={is_editable}"
        )

        # Build items list with context-aware actions
        items = [
            [f"{ICON_FIND_PANEL} Use in Find", "Inject into Find panel (Ctrl+F)"],
            [f"{ICON_REPLACE_PANEL} Use in Replace", "Inject into Replace panel (Ctrl+H)"],
            [f"{ICON_FIND_IN_FILES_PANEL} Use in Find In Files", "Inject into Find In Files panel (Ctrl+Shift+F)"],
        ]

        # Only show Edit/Delete if portfolio is NOT builtin
        if not is_builtin:
            if is_editable:
                # Enabled actions for editable portfolios
                items.append([f"{ICON_EDIT} Edit Pattern", "Modify this pattern (Phase 2)"])
                items.append([f"{ICON_DELETE} Delete Pattern", "Remove this pattern (Phase 2)"])
            else:
                # Disabled actions for readonly portfolios (visual feedback with prohibition icon)
                items.append([f"{ICON_DISABLED} Edit Pattern", "Portfolio is in read-only mode"])
                items.append([f"{ICON_DISABLED} Delete Pattern", "Portfolio is in read-only mode"])

        def on_select(index: int) -> None:
            if index == -1:
                logger.debug("Actions menu cancelled by user")
                return

            # Map index to action type and panel type
            if index in [0, 1, 2]:
                # Use actions (always at indices 0-2)
                panel_types = ["find", "replace", "find_in_files"]
                selected_panel = panel_types[index]
                logger.debug(f"User selected 'use' action with panel={selected_panel}")
                on_action_callback("use", selected_panel)
            elif not is_builtin and index == 3:
                # Edit action (index 3 if not builtin)
                if is_editable:
                    logger.debug("User selected 'edit' action")
                    on_action_callback("edit", None)
                else:
                    logger.debug("Edit action blocked: portfolio is readonly")
                    window.status_message("Regex Lab: Cannot edit pattern - portfolio is read-only")
            elif not is_builtin and index == 4:
                # Delete action (index 4 if not builtin)
                if is_editable:
                    logger.debug("User selected 'delete' action")
                    on_action_callback("delete", None)
                else:
                    logger.debug("Delete action blocked: portfolio is readonly")
                    window.status_message("Regex Lab: Cannot delete pattern - portfolio is read-only")

        window.show_quick_panel(items, on_select)

    def _create_pattern_selector(
        self,
        window: sublime.Window,
        pattern_map: list[tuple[Portfolio | None, Pattern | None]],
    ) -> Callable[[int], None]:
        """
        Factory function to create pattern selection callback.

        Reduces nesting level from 2 to 1 by extracting the nested on_select callback.

        Args:
            window: Sublime Text window instance
            pattern_map: List mapping Quick Panel indices to (portfolio, pattern) tuples

        Returns:
            Callback function for Quick Panel on_select
        """

        def on_select(index: int) -> None:
            if index == -1:
                # User cancelled
                return

            selected_portfolio, selected_pattern = pattern_map[index]

            # Skip separators (both are None)
            if selected_pattern is None or selected_portfolio is None:
                return

            logger = get_logger()
            logger.debug(
                f"Pattern selected: '{selected_pattern.name}' "
                f"(type={selected_pattern.type}, dynamic={selected_pattern.is_dynamic()})"
            )

            # PRIORITY: If pattern has default_panel configured, skip Actions menu and inject directly
            if selected_pattern.default_panel:
                logger.debug(f"Pattern has default_panel='{selected_pattern.default_panel}', skipping Actions menu")
                self._handle_use_action(window, selected_pattern, selected_pattern.default_panel, None)
                return

            # Show Actions Quick Panel with unified callback
            on_action_callback = self._create_action_callback(window, selected_pattern, selected_portfolio)
            self._show_pattern_actions_menu(window, selected_pattern, selected_portfolio, on_action_callback)

        return on_select

    def _create_action_callback(
        self,
        window: sublime.Window,
        pattern: Pattern,
        portfolio: Portfolio,
    ) -> Callable[[str, str | None], None]:
        """
        Factory function to create action callback for pattern actions menu.

        Eliminates 85% code duplication between V1 and V2 modes by unifying
        the action handling logic.

        Args:
            window: Sublime Text window instance
            pattern: Selected pattern
            portfolio: Portfolio containing the pattern

        Returns:
            Callback function for action selection (action_type, panel_type)
        """

        def on_action_callback(action_type: str, panel_type: str | None) -> None:
            """Callback when user selects an action from Actions menu."""
            logger = get_logger()
            logger.debug(f"Action selected: type={action_type}, panel={panel_type}")

            if action_type == "use":
                # User chose "Use in X" - route to injection workflow
                self._handle_use_action(window, pattern, panel_type, None)  # type: ignore
            elif action_type == "edit":
                # Edit Pattern
                logger.debug(f"Edit Pattern action triggered for '{pattern.name}'")
                edit_cmd = EditPatternCommand(self.portfolio_service)
                edit_cmd.run(window, pattern, portfolio)
            elif action_type == "delete":
                # Delete Pattern
                logger.debug(f"Delete Pattern action triggered for '{pattern.name}'")
                delete_cmd = DeletePatternCommand(self.portfolio_service)
                delete_cmd.run(window, pattern, portfolio)

        return on_action_callback

    def _handle_use_action(
        self,
        window: sublime.Window,
        pattern: Pattern,
        panel_type: str,
        captured_panel: str | None = None,
    ) -> None:
        """
        Handle 'Use' action for a pattern.

        Routes to appropriate injection logic:
        - Static patterns: inject directly into specified panel
        - Dynamic patterns: collect variables, then inject

        Args:
            window: Sublime Text window instance
            pattern: Pattern to inject
            panel_type: Target panel ("find" | "replace" | "find_in_files")
            captured_panel: Previously captured panel (for dynamic patterns, unused in refactored flow)
        """
        logger = get_logger()
        logger.debug(
            f"Handling 'use' action: pattern='{pattern.name}', panel={panel_type}, is_dynamic={pattern.is_dynamic()}"
        )

        # Static patterns: format and inject directly
        if not pattern.is_dynamic():
            logger.debug("Static pattern detected, injecting directly")
            resolved_pattern = self.pattern_service.format_for_find_panel(pattern)
            self._inject_pattern_in_panel(window, panel_type, resolved_pattern, pattern.name)
            return

        # Dynamic patterns: collect variables first
        variables_to_collect = pattern.variables or []
        if not variables_to_collect:
            logger.debug("Dynamic pattern has no variables configured")
            window.status_message("Regex Lab: Dynamic pattern has no variables")
            return

        logger.debug(
            f"Collecting {len(variables_to_collect)} "
            f"{pluralize(len(variables_to_collect), 'variable')} for dynamic pattern"
        )

        def on_completion(collected_values: dict[str, str]) -> None:
            """Callback when all variables collected - resolve and inject pattern."""
            try:
                logger.debug(f"Variables collected successfully: {list(collected_values.keys())}")
                resolved_pattern = self.pattern_service.resolve_pattern(pattern, collected_values)
                logger.debug(f"Pattern resolved successfully, injecting into {panel_type} panel")
                self._inject_pattern_in_panel(window, panel_type, resolved_pattern, pattern.name)
            except ValueError as e:
                logger.error(f"Error resolving pattern '{pattern.name}': {e}")
                window.status_message(f"Regex Lab: Error resolving pattern - {e}")

        # Start variable collection workflow
        # captured_panel is None in refactored flow (panel already chosen via Actions menu)
        collect_variables_for_pattern(
            window, pattern, variables_to_collect, {}, captured_panel or "", self.pattern_service, on_completion
        )

    def _get_variable_hint(self, var_name: str) -> str:
        """
        Get smart hint for variable based on naming convention.

        Args:
            var_name: Name of the variable

        Returns:
            Pre-filled value for input panel (empty string if no hint)
        """
        settings = SettingsManager.get_instance()

        # Date variable - use date_format setting
        if var_name.lower() == "date":
            date_format = settings.get("date_format", DEFAULT_DATE_FORMAT)
            return datetime.now().strftime(date_format)

        # Time variable - use time_format setting
        if var_name.lower() == "time":
            time_format = settings.get("time_format", DEFAULT_TIME_FORMAT)
            return datetime.now().strftime(time_format)

        # No hint for other variables
        return ""

    def _get_variable_mask(self, var_name: str) -> str | None:
        """
        Get validation regex mask for variable based on naming convention.

        Args:
            var_name: Name of the variable

        Returns:
            Regex pattern for validation (None if no validation)
        """
        settings = SettingsManager.get_instance()

        # Date variable - convert date_format to regex
        if var_name.lower() == "date":
            date_format = settings.get("date_format", DEFAULT_DATE_FORMAT)
            return self._format_to_regex(date_format)

        # Time variable - convert time_format to regex
        if var_name.lower() == "time":
            time_format = settings.get("time_format", DEFAULT_TIME_FORMAT)
            return self._format_to_regex(time_format)

        # No validation for other variables
        return None

    def _format_to_regex(self, strftime_format: str) -> str:
        """
        Convert strftime format to strict ISO-compliant regex pattern.

        Uses strict patterns with zero-padding validation for date/time components:
        - Year: 1000-2999 (4 digits)
        - Month: 01-12 (zero-padded)
        - Day: 01-31 (zero-padded)
        - Hour: 00-23 (zero-padded, 24h format)
        - Minute/Second: 00-59 (zero-padded)

        Args:
            strftime_format: Python strftime format string (e.g., "%Y-%m-%d")

        Returns:
            Strict ISO regex pattern (e.g., r"[12][0-9]{3}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])")

        Note:
            V2 will support custom user-defined masks. This enforces ISO 8601 standard.
        """
        # Map strftime directives to strict ISO regex patterns
        # These patterns enforce zero-padding and valid ranges
        replacements = {
            "%Y": r"[12][0-9]{3}",  # Year: 1000-2999 (ISO 8601)
            "%y": r"[0-9]{2}",  # 2-digit year: 00-99
            "%m": r"(0[1-9]|1[0-2])",  # Month: 01-12 (zero-padded)
            "%d": r"(0[1-9]|[12][0-9]|3[01])",  # Day: 01-31 (zero-padded)
            "%H": r"([01][0-9]|2[0-3])",  # Hour 24h: 00-23 (zero-padded)
            "%I": r"(0[1-9]|1[0-2])",  # Hour 12h: 01-12 (zero-padded)
            "%M": r"[0-5][0-9]",  # Minute: 00-59 (zero-padded)
            "%S": r"[0-5][0-9]",  # Second: 00-59 (zero-padded)
            "%f": r"[0-9]{6}",  # Microsecond: 000000-999999
            "%p": r"(AM|PM)",  # AM/PM indicator
            "%B": r"\w+",  # Full month name (variable length)
            "%b": r"\w{3}",  # Abbreviated month (3 chars)
            "%A": r"\w+",  # Full weekday name (variable length)
            "%a": r"\w{3}",  # Abbreviated weekday (3 chars)
        }

        # Escape special regex characters in the format string
        pattern = re.escape(strftime_format)

        # Replace escaped strftime directives with strict regex patterns
        for directive, regex_pattern in replacements.items():
            escaped_directive = re.escape(directive)
            pattern = pattern.replace(escaped_directive, regex_pattern)

        return pattern

    def _validate_variable(self, var_name: str, value: str) -> tuple[bool, str]:
        """
        Validate variable value against expected format.

        Uses TWO-STAGE validation for date/time variables:
        1. Strict ISO format check (regex) - ensures zero-padding
        2. Semantic validation (strptime) - ensures valid values (e.g., rejects Feb 31)

        Args:
            var_name: Name of the variable
            value: User-provided value

        Returns:
            Tuple of (is_valid, error_message)
            If valid: (True, "")
            If invalid: (False, "error message")
        """
        mask = self._get_variable_mask(var_name)

        # No mask = no validation (always valid)
        if mask is None:
            return (True, "")

        # Empty value is invalid if mask exists
        if not value:
            return (False, f"Value for '{var_name}' cannot be empty")

        # STAGE 1: Strict ISO format validation (regex)
        # This enforces zero-padding and valid ranges
        if not re.fullmatch(mask, value):
            # Provide specific error message for date/time
            if var_name.lower() == "date":
                return (
                    False,
                    f"Invalid date format for '{var_name}'. Must use zero-padded ISO format (e.g., 2025-01-09, not 2025-1-9)",
                )
            elif var_name.lower() == "time":
                return (
                    False,
                    f"Invalid time format for '{var_name}'. Must use zero-padded ISO format (e.g., 01:05:09, not 1:5:9)",
                )
            else:
                return (False, f"Invalid format for '{var_name}'.")

        settings = SettingsManager.get_instance()

        # STAGE 2: Semantic validation for date variables (after format check)
        if var_name.lower() == "date":
            date_format = settings.get("date_format", DEFAULT_DATE_FORMAT)
            try:
                datetime.strptime(value, date_format)
                return (True, "")
            except ValueError:
                return (False, f"Invalid date for '{var_name}'. Expected format: {date_format}")

        # STAGE 2: Semantic validation for time variables (after format check)
        if var_name.lower() == "time":
            time_format = settings.get("time_format", DEFAULT_TIME_FORMAT)
            try:
                datetime.strptime(value, time_format)
                return (True, "")
            except ValueError:
                return (False, f"Invalid time for '{var_name}'. Expected format: {time_format}")

        # Other variables: only regex validation (already passed above)
        return (True, "")

    def _inject_pattern_in_panel(
        self,
        window: sublime.Window,
        panel_type: str,
        resolved_pattern: str,
        pattern_name: str,
    ) -> None:
        """
        Inject pattern into specified panel type.

        Args:
            window: Sublime Text window instance
            panel_type: "find", "replace", or "find_in_files"
            resolved_pattern: The resolved regex pattern
            pattern_name: Name of the pattern (for status message)
        """
        if panel_type == "find":
            inject_into_find_panel(window, resolved_pattern, pattern_name)
        elif panel_type == "replace":
            inject_into_replace_panel(window, resolved_pattern, pattern_name)
        elif panel_type == "find_in_files":
            inject_into_find_in_files_panel(window, resolved_pattern, pattern_name)
        else:
            # Should never happen due to validation, but safety fallback
            window.status_message(f"Regex Lab: Unknown panel type '{panel_type}', using Find panel")
            inject_into_find_panel(window, resolved_pattern, pattern_name)

    def _show_variable_input(
        self,
        window: sublime.Window,
        var_name: str,
        hint: str,
        on_done: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        """
        Show input panel with optional popup guidance for variable.

        Displays a helpful popup with format information and examples if enabled,
        then shows an enhanced input panel with emojis and format hints.

        Args:
            window: Sublime Text window instance
            var_name: Name of the variable to collect
            hint: Pre-filled value for input panel
            on_done: Callback when user submits value
            on_cancel: Callback when user cancels
        """
        try:
            import sublime  # pyright: ignore[reportMissingImports]
        except ModuleNotFoundError:
            # Fallback without popup support
            window.show_input_panel(
                f"Enter value for '{var_name}':",
                hint,
                on_done,
                None,
                on_cancel,
            )
            return

        settings = SettingsManager.get_instance()

        # Determine emoji and format info based on variable name
        # Icons consistent with Quick Panel:
        #   📄 = Static pattern
        #   🧪 = Dynamic pattern
        #   ✏️ = Generic variable input (used here for all variable types)
        emoji = "✏️"
        format_info = ""
        example = ""

        if var_name.lower() == "date":
            format_info = settings.get("date_format", DEFAULT_DATE_FORMAT)
            example = datetime.now().strftime(format_info)
        elif var_name.lower() == "time":
            format_info = settings.get("time_format", DEFAULT_TIME_FORMAT)
            example = datetime.now().strftime(format_info)

        # Build enhanced caption with emoji and format hint
        caption = f"{emoji} Enter value for '{var_name}'"
        if format_info:
            caption += f" (Format: {format_info}, ex: {example})"
        caption += ":"

        # Show popup guidance if enabled
        if settings.get("show_input_help_popup", DEFAULT_SHOW_INPUT_HELP_POPUP):
            view = window.active_view()
            if view:
                # Build HTML popup content
                popup_html = f"""
                <body style="margin: 0; padding: 10px; font-family: system-ui;">
                    <div style="background: var(--background); color: var(--foreground);">
                        <h3 style="margin: 0 0 8px 0; color: var(--bluish);">
                            {emoji} {var_name.title()}
                        </h3>
                """

                if format_info:
                    popup_html += f"""
                        <p style="margin: 4px 0;">
                            <b>Format:</b> <code style="background: var(--background); padding: 2px 4px; border-radius: 3px;">{format_info}</code>
                        </p>
                        <p style="margin: 4px 0;">
                            <b>Example:</b> <span style="color: var(--greenish);">{example}</span>
                        </p>
                    """
                else:
                    popup_html += """
                        <p style="margin: 4px 0; font-style: italic;">
                            Enter any value for this variable
                        </p>
                    """

                popup_html += """
                    </div>
                </body>
                """

                # Show popup at cursor position
                view.show_popup(
                    popup_html,
                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    location=-1,  # at cursor
                    max_width=400,
                )

                # Delay input panel slightly so popup appears first
                sublime.set_timeout(
                    lambda: window.show_input_panel(caption, hint, on_done, None, on_cancel),
                    100,
                )
            else:
                # No view, show input panel immediately
                window.show_input_panel(caption, hint, on_done, None, on_cancel)
        else:
            # Popup disabled, show input panel immediately
            window.show_input_panel(caption, hint, on_done, None, on_cancel)
