"""
Portfolio Manager Command - Central hub for portfolio management.

Main entry point for all portfolio operations:
- View loaded/available portfolios
- Navigate to create/edit/delete actions
- Manage loading/unloading

Extensible architecture to facilitate adding new features.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.constants import (
    DEFAULT_EXPORT_DIRECTORY,
    DEFAULT_QUICK_PANEL_WIDTH,
    ICON_ADD,
    ICON_AVAILABLE,
    ICON_BACK,
    ICON_BROWSE,
    ICON_BUILTIN_BOOK,
    ICON_DEFAULT,
    ICON_DELETE,
    ICON_DISABLED,
    ICON_DYNAMIC_PATTERN,
    ICON_EDIT,
    ICON_EDITABLE,
    ICON_EXPORT,
    ICON_FIND_IN_FILES_PANEL,
    ICON_FIND_PANEL,
    ICON_FOLDER,
    ICON_IMPORT,
    ICON_READONLY,
    ICON_RELOAD,
    ICON_REPLACE_PANEL,
    ICON_SECTION_ACTIONS,
    ICON_SECTION_DISABLED,
    ICON_SECTION_LOADED,
    ICON_SETTINGS,
    ICON_STATIC_PATTERN,
    ICON_SUCCESS,
)
from ..core.helpers import (
    find_portfolio_file_by_name,
    format_aligned_summary,
    format_centered_separator,
    format_quick_panel_line,
    is_builtin_portfolio_path,
    normalize_portfolio_name,
    pluralize,
)
from ..core.logger import get_logger
from ..core.models import PatternType
from ..core.settings_manager import SettingsManager
from ..services.pattern_service import PatternService
from ..services.portfolio_service import PortfolioService
from .portfolio_manager_command_helper import (
    collect_variables_for_pattern,
    inject_pattern_in_panel,
)

if TYPE_CHECKING:
    import sublime  # pyright: ignore[reportMissingImports]

    from ..core.models import Pattern, PatternType, Portfolio

logger = get_logger()


class PortfolioManagerCommand:
    """
    Command hub for portfolio management.

    Displays a Quick Panel with 3 sections:
    1. Loaded Portfolios (currently loaded portfolios)
    2. Disabled Portfolios (disabled portfolios in disabled_portfolios/)
    3. Actions (New Portfolio, Import, Reload, Settings)

    Each item routes to the appropriate command based on its action_type.
    """

    def __init__(
        self,
        portfolio_service: PortfolioService | None = None,
        settings_manager: SettingsManager | None = None,
        pattern_service: PatternService | None = None,
    ) -> None:
        """
        Initialize the command.

        Args:
            portfolio_service: Optional PortfolioService instance (for testing)
            settings_manager: Optional SettingsManager instance (for testing)
            pattern_service: Optional PatternService instance (for testing)
        """
        self.portfolio_service = portfolio_service or PortfolioService()
        self.settings_manager = settings_manager or SettingsManager.get_instance()
        self.pattern_service = pattern_service or PatternService()
        self.logger = get_logger()

    def run(self, window: sublime.Window) -> None:
        """
        Execute the command - Display portfolio management hub.

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Portfolio Manager: Command invoked")

        # Get Quick Panel width from settings
        panel_width = self.settings_manager.get("quick_panel_width", DEFAULT_QUICK_PANEL_WIDTH)
        self.logger.debug("Portfolio Manager: Quick Panel width = %s", panel_width)

        # Build Quick Panel items (3 sections)
        items: list[list[str]] = []
        action_map: list[dict[str, Any]] = []

        # === SECTION 1: Loaded Portfolios ===
        loaded_portfolios = self.portfolio_service.get_all_portfolios()
        self.logger.debug("Portfolio Manager: Found %s loaded portfolios", len(loaded_portfolios))

        if loaded_portfolios:
            # Section separator
            separator = self._format_separator(f"{ICON_SECTION_LOADED} Loaded Portfolios", panel_width)
            count = len(loaded_portfolios)
            items.append([separator, f"{count} {pluralize(count, 'portfolio')} loaded"])
            action_map.append({"type": "separator"})

            # Portfolios already sorted by get_all_portfolios() (builtin first, alphabetical)
            # No need to re-sort here
            self.logger.debug("Portfolio Manager: Using pre-sorted portfolios from get_all_portfolios()")

            # Add each loaded portfolio
            for portfolio in loaded_portfolios:
                is_builtin = self._is_builtin_portfolio(portfolio.name)
                formatted_line = self._format_portfolio_line(
                    portfolio, panel_width, is_loaded=True, is_builtin=is_builtin
                )
                pattern_count = len(portfolio.patterns)
                description = f"{pattern_count} {pluralize(pattern_count, 'pattern')} • Readonly: {portfolio.readonly}"

                self.logger.debug(
                    "Portfolio Manager: Adding loaded portfolio '%s' (%s patterns, readonly=%s)",
                    portfolio.name,
                    pattern_count,
                    portfolio.readonly,
                )

                items.append([formatted_line, description])
                action_map.append(
                    {
                        "type": "loaded_portfolio",
                        "portfolio": portfolio,
                        "name": portfolio.name,
                    }
                )
        else:
            self.logger.debug("Portfolio Manager: No loaded portfolios found")

        # === SECTION 2: Disabled Portfolios ===
        try:
            import sublime  # pyright: ignore[reportMissingImports]

            packages_path = sublime.packages_path()
        except (ImportError, AttributeError):
            # Fallback for tests
            packages_path = str(Path.home() / ".config" / "sublime-text" / "Packages")

        disabled_portfolios = self.portfolio_service.get_disabled_portfolios(packages_path)
        self.logger.debug("Portfolio Manager: Found %s disabled portfolios", len(disabled_portfolios))

        # Only show section if there are disabled portfolios
        if disabled_portfolios:
            # Section separator
            separator = self._format_separator(f"{ICON_SECTION_DISABLED} Disabled Portfolios", panel_width)
            count = len(disabled_portfolios)
            items.append([separator, f"{count} {pluralize(count, 'portfolio')} disabled"])
            action_map.append({"type": "separator"})

            # Add each disabled portfolio
            for filepath, metadata in disabled_portfolios:
                name = metadata.get("name", Path(filepath).stem)
                pattern_count = metadata.get("pattern_count", 0)
                formatted_line = self._format_disabled_portfolio_line(name, panel_width)
                description = f"{pattern_count} {pluralize(pattern_count, 'pattern')} • Click to enable"

                self.logger.debug(
                    "Portfolio Manager: Adding disabled portfolio '%s' from %s (%s patterns)",
                    name,
                    Path(filepath).name,
                    pattern_count,
                )

                items.append([formatted_line, description])
                # Fix closure bug: capture loop variables by value using default parameters
                action_map.append(self._make_disabled_portfolio_action(filepath, name, metadata))
        else:
            self.logger.debug("Portfolio Manager: No available portfolios found")

        # === SECTION 3: Actions ===
        separator = self._format_separator(f"{ICON_SECTION_ACTIONS} Actions", panel_width)
        items.append([separator, "Portfolio management operations"])
        action_map.append({"type": "separator"})

        self.logger.debug("Portfolio Manager: Adding %s action items", 5)

        # Action: New Portfolio
        new_portfolio_line = self._format_action_line("New Portfolio", "Create New", panel_width)
        items.append([new_portfolio_line, "Create a new empty portfolio with the interactive wizard"])
        action_map.append({"type": "action", "action": "new_portfolio"})

        # Action: Import Portfolio
        import_line = self._format_action_line("Import Portfolio", "Load File", panel_width)
        items.append([import_line, "Import an external portfolio .json file"])
        action_map.append({"type": "action", "action": "import_portfolio"})

        # Action: Reload Portfolios
        reload_line = self._format_action_line("Reload Portfolios", "Refresh All", panel_width)
        items.append([reload_line, "Reload all portfolios from disk (refresh external changes)"])
        action_map.append({"type": "action", "action": "reload_portfolios"})

        # Action: Open Settings
        settings_line = self._format_action_line("Settings", "Configure", panel_width)
        items.append([settings_line, "Open RegexLab settings (loaded_portfolios, etc.)"])
        action_map.append({"type": "action", "action": "open_settings"})

        # Action: About
        about_line = self._format_action_line("About", "Version Info", panel_width)
        items.append([about_line, "Show RegexLab version and installation guide"])
        action_map.append({"type": "action", "action": "about"})

        # Show Quick Panel
        self.logger.debug("Portfolio Manager: Displaying Quick Panel with %s items", len(items))

        def on_select(index: int) -> None:
            if index == -1:
                # User cancelled
                self.logger.debug("Portfolio Manager: User cancelled selection")
                return

            action = action_map[index]
            action_type = action.get("type")
            self.logger.debug("Portfolio Manager: User selected index %s (type: %s)", index, action_type)

            # Route to appropriate handler
            self._handle_selection(window, action)

        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
            self.logger.debug("Portfolio Manager: Quick Panel shown with MONOSPACE_FONT flag")
        except (ImportError, AttributeError):
            # Fallback for tests
            window.show_quick_panel(items, on_select)
            self.logger.debug("Portfolio Manager: Quick Panel shown (test mode - no flags)")

    def _format_separator(self, label: str, panel_width: int) -> str:
        """
        Format a centered separator line.

        Delegates to helpers.format_centered_separator() for consistency.

        Args:
            label: Label text for the separator
            panel_width: Total width for Quick Panel (from settings)

        Returns:
            Centered separator string
        """
        return format_centered_separator(label, panel_width)

    def _format_portfolio_line(
        self, portfolio: Portfolio, panel_width: int, is_loaded: bool = False, is_builtin: bool = False
    ) -> str:
        """
        Format a portfolio line with aligned columns.

        Format for loaded portfolios:
        Portfolio Name                                             🔒 Built-in
        Portfolio Name                                             🔒 Custom
        Portfolio Name                                             📝 Custom

        Args:
            portfolio: Portfolio to format
            panel_width: Total width for Quick Panel (from settings)
            is_loaded: Whether this portfolio is currently loaded
            is_builtin: Whether this portfolio is builtin (from data/portfolios/)

        Returns:
            Formatted line string
        """
        # Determine icon and type label based on state
        if is_loaded:
            # Determine label based on ACTUAL location (is_builtin), not readonly flag
            if is_builtin:
                icon = ICON_READONLY
                type_label = "Built-in"
            elif portfolio.readonly:
                # Custom portfolio with readonly=true
                icon = ICON_READONLY
                type_label = "Custom"
            else:
                # Custom portfolio with readonly=false
                icon = ICON_EDITABLE
                type_label = "Custom"
        else:
            icon = ICON_AVAILABLE
            type_label = "Available"

        # Build right text: Icon Type
        right_text = f"{icon} {type_label}"

        # Delegate to unified formatter
        return format_quick_panel_line(portfolio.name, right_text, panel_width)

    def _format_disabled_portfolio_line(self, name: str, panel_width: int) -> str:
        """
        Format a disabled (not loaded) portfolio line.

        Format:
        Portfolio Name                                             🚫 Disabled

        Args:
            name: Portfolio name
            panel_width: Total width for Quick Panel

        Returns:
            Formatted line string
        """
        # Delegate to unified formatter
        return format_quick_panel_line(name, f"{ICON_DISABLED} Disabled", panel_width)

    def _make_disabled_portfolio_action(self, filepath: str, name: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        Create action dict for disabled portfolio with captured loop variables.

        This method exists to fix a closure bug: when loop variables are captured
        directly in a dict/lambda, they are captured by reference and will all
        point to the last iteration's values when the callback executes.

        By using default parameters, we capture by value at the time of creation.

        Args:
            filepath: Path to portfolio file (captured by value)
            name: Portfolio name (captured by value)
            metadata: Portfolio metadata (captured by value)

        Returns:
            Action dict with type, filepath, name, and metadata
        """
        return {
            "type": "disabled_portfolio",
            "filepath": filepath,
            "name": name,
            "metadata": metadata,
        }

    def _format_action_line(self, action_name: str, action_label: str, panel_width: int) -> str:
        """
        Format an action line with aligned columns.

        Format:
        🔧 Action Name                                             Action Label

        Icons are selected based on action name:
        - New Portfolio: ➕
        - Reload: 🔄
        - Settings: ⚙️

        Args:
            action_name: Name of the action (e.g., "New Portfolio")
            action_label: Short label for the action (e.g., "Create New")
            panel_width: Total width for Quick Panel (from settings)

        Returns:
            Formatted line string
        """  # noqa: RUF002
        # Select icon based on action name
        icon_map = {
            "New Portfolio": ICON_ADD,
            "Import Portfolio": ICON_IMPORT,
            "Export Portfolio": ICON_EXPORT,
            "Reload Portfolios": ICON_RELOAD,
            "Settings": ICON_SETTINGS,
        }
        icon = icon_map.get(action_name, ICON_DEFAULT)

        # Delegate to unified formatter (icon as left_icon)
        return format_quick_panel_line(action_name, action_label, panel_width, left_icon=icon)

    def _handle_selection(self, window: sublime.Window, action: dict[str, Any]) -> None:
        """
        Route selection to appropriate handler based on action type.

        This is the central routing logic - extensible for new features.

        Args:
            window: Sublime Text window instance
            action: Action dictionary with type and associated data
        """
        action_type = action.get("type")

        # Skip separators
        if action_type == "separator":
            self.logger.debug("Portfolio Manager: Separator clicked, ignoring")
            return

        # Handle loaded portfolio selection
        if action_type == "loaded_portfolio":
            self._handle_loaded_portfolio(window, action)
            return

        # Handle available portfolio selection
        if action_type == "disabled_portfolio":
            self._handle_disabled_portfolio(window, action)
            return

        # Handle action items
        if action_type == "action":
            action_name = action.get("action")
            self._handle_action(window, action_name)
            return

        # Unknown action type
        self.logger.warning("Portfolio Manager: Unknown action type: %s", action_type)
        window.status_message(f"Regex Lab: Unknown action type '{action_type}'")

    def _handle_loaded_portfolio(self, window: sublime.Window, action: dict[str, Any]) -> None:
        """
        Handle selection of a loaded portfolio.

        Shows context menu with actions based on portfolio type:

        BUILTIN (from data/portfolios/):
        - Browse Patterns
        - Export Portfolio
        - Back

        CUSTOM (from User/RegexLab/portfolios/):
        - Browse Patterns
        - Add Pattern (if editable)
        - Export Portfolio
        - Toggle Read-Only (protect/unprotect)
        - Disable Portfolio
        - Delete Portfolio (if editable)
        - Back

        Args:
            window: Sublime Text window instance
            action: Action dictionary with portfolio data
        """
        portfolio = action.get("portfolio")
        portfolio_name = action.get("name", "Unknown")

        self.logger.debug("Portfolio Manager: Handling loaded portfolio selection: '%s'", portfolio_name)

        if not portfolio:
            self.logger.error("Portfolio Manager: No portfolio data provided")
            window.status_message("Regex Lab: Error - No portfolio data")
            return

        pattern_count = len(portfolio.patterns)
        is_readonly = portfolio.readonly

        # Detect if portfolio is builtin by checking loaded portfolios metadata
        # Builtin portfolios come from data/portfolios/, custom from User/RegexLab/portfolios/
        is_builtin = self._is_builtin_portfolio(portfolio_name)

        self.logger.debug(
            "Portfolio Manager: Portfolio '%s' has %s patterns (readonly=%s, builtin=%s)",
            portfolio_name,
            pattern_count,
            is_readonly,
            is_builtin,
        )

        # Build context menu based on portfolio type (builtin vs custom)
        items: list[list[str]] = []
        action_map: list[str] = []

        # 1. Browse Patterns (ALL portfolios)
        description = f"View {pattern_count} {pluralize(pattern_count, 'pattern')} in this portfolio"
        items.append([f"{ICON_BROWSE} Browse Patterns", description])
        action_map.append("browse_patterns")

        if not is_builtin:
            # CUSTOM PORTFOLIO actions only

            if not is_readonly:
                # 2. Add Pattern (editable custom only)
                items.append([f"{ICON_ADD} Add Pattern", "Create a new pattern in this portfolio"])
                action_map.append("add_pattern")

                # 3. Edit Pattern (editable custom only)
                items.append([f"{ICON_EDIT} Edit Pattern", "Modify an existing pattern"])
                action_map.append("edit_pattern")

                # 4. Delete Pattern (editable custom only)
                items.append([f"{ICON_DELETE} Delete Pattern", "Remove a pattern from this portfolio"])
                action_map.append("delete_pattern")

            # 5. Export Portfolio (custom)
            items.append([f"{ICON_EXPORT} Export Portfolio", "Copy portfolio to external location"])
            action_map.append("export_portfolio")

            # 6. Toggle Read-Only (ALL custom portfolios)
            if is_readonly:
                items.append([f"{ICON_EDITABLE} Toggle Read-Only", "Remove protection (allow editing)"])
            else:
                items.append([f"{ICON_READONLY} Toggle Read-Only", "Protect portfolio from editing"])
            action_map.append("toggle_readonly")

            # 7. Disable Portfolio (custom - move to disabled folder)
            items.append([f"{ICON_DISABLED} Disable Portfolio", "Move to disabled_portfolios/ folder (unload)"])
            action_map.append("disable_portfolio")

            if not is_readonly:
                # 8. Delete Portfolio (editable custom only)
                items.append(
                    [f"{ICON_DELETE} Delete Portfolio", "Permanently delete this portfolio (with confirmation)"]
                )
                action_map.append("delete_portfolio")
        else:
            # BUILTIN PORTFOLIO actions only

            # 2. Export Portfolio (builtin)
            items.append([f"{ICON_EXPORT} Export Portfolio", "Copy builtin portfolio to external location"])
            action_map.append("export_portfolio")

        # 9. Back to main menu (ALL portfolios)
        items.append([f"{ICON_BACK} Back", "Return to Portfolio Manager"])
        action_map.append("back")

        self.logger.debug(
            "Portfolio Manager: Showing context menu with %s actions (builtin=%s)", len(items), is_builtin
        )

        def on_select(index: int) -> None:
            if index == -1:
                self.logger.debug("Portfolio Manager: Context menu cancelled")
                return

            selected_action = action_map[index]
            self.logger.debug("Portfolio Manager: Selected action: %s", selected_action)

            # Route to action handlers
            if selected_action == "back":
                # Reopen main Portfolio Manager
                self.run(window)
            elif selected_action == "browse_patterns":
                self._browse_patterns(window, portfolio, is_readonly, is_builtin)
            elif selected_action == "add_pattern":
                # Launch Add Pattern wizard
                from .add_pattern_command import AddPatternCommand

                add_command = AddPatternCommand()
                add_command.run(window, portfolio.name)
            elif selected_action == "edit_pattern":
                self._show_pattern_selection_for_edit(window, portfolio)
            elif selected_action == "delete_pattern":
                self._show_pattern_selection_for_delete(window, portfolio)
            elif selected_action == "export_portfolio":
                self._action_export_portfolio(window, portfolio)
            elif selected_action == "toggle_readonly":
                self._toggle_portfolio_readonly(window, portfolio)
            elif selected_action == "disable_portfolio":
                self._disable_portfolio(window, portfolio)
            elif selected_action == "delete_portfolio":
                self._delete_portfolio(window, portfolio.name, portfolio.readonly)

        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
        except (ImportError, AttributeError):
            window.show_quick_panel(items, on_select)

    def _handle_disabled_portfolio(self, window: sublime.Window, action: dict[str, Any]) -> None:
        """
        Handle selection of a disabled portfolio.

        Shows context menu with preview/management actions:
        - Browse Patterns (preview mode)
        - Export Portfolio
        - Enable Portfolio (move to portfolios/)
        - Delete Portfolio (non-readonly only)

        Args:
            window: Sublime Text window instance
            action: Action dictionary with filepath and metadata
        """
        filepath = action.get("filepath")
        name = action.get("name", "Unknown")
        metadata = action.get("metadata", {})

        self.logger.debug("Portfolio Manager: Handling disabled portfolio selection: '%s'", name)
        self.logger.debug("Portfolio Manager: Portfolio filepath: %s", filepath)

        if not filepath:
            self.logger.error("Portfolio Manager: No filepath provided for portfolio '%s'", name)
            window.status_message("Regex Lab: Error - No filepath provided")
            return

        pattern_count = metadata.get("pattern_count", 0)
        is_readonly = metadata.get("readonly", False)

        self.logger.debug(
            "Portfolio Manager: Disabled portfolio '%s' has %s patterns (readonly=%s)",
            name,
            pattern_count,
            is_readonly,
        )

        # Build context menu for disabled portfolio
        items: list[list[str]] = []
        action_map: list[str] = []

        # 1. Browse Patterns (preview mode)
        description = f"Preview {pattern_count} {pluralize(pattern_count, 'pattern')} (read-only)"
        items.append([f"{ICON_BROWSE} Browse Patterns", description])
        action_map.append("browse_patterns")

        # 2. Export Portfolio
        items.append([f"{ICON_EXPORT} Export Portfolio", "Copy portfolio to external location"])
        action_map.append("export_portfolio")

        # 3. Enable Portfolio (main action for disabled portfolios)
        items.append([f"{ICON_SUCCESS} Enable Portfolio", "Move to portfolios/ folder and load"])
        action_map.append("enable_portfolio")

        if not is_readonly:
            # 4. Delete Portfolio (non-readonly only)
            items.append([f"{ICON_DELETE} Delete Portfolio", "Permanently delete this portfolio (with confirmation)"])
            action_map.append("delete_portfolio")

        # 5. Back to main menu
        items.append([f"{ICON_BACK} Back", "Return to Portfolio Manager"])
        action_map.append("back")

        self.logger.debug("Portfolio Manager: Showing disabled context menu with %s actions", len(items))

        def on_select(index: int) -> None:
            if index == -1:
                self.logger.debug("Portfolio Manager: Disabled context menu cancelled")
                return

            selected_action = action_map[index]
            self.logger.debug("Portfolio Manager: Selected action: %s", selected_action)

            # Route to action handlers
            if selected_action == "back":
                # Reopen main Portfolio Manager
                self.run(window)
            elif selected_action == "enable_portfolio":
                self._enable_portfolio(window, filepath, name)
            elif selected_action == "browse_patterns":
                # Load portfolio from file (temporary, don't add to loaded portfolios)
                try:
                    # Use load_portfolio_from_file() for temporary read-only access
                    # This DOES NOT add the portfolio to _loaded_portfolios
                    portfolio = self.portfolio_service.portfolio_manager.load_portfolio_from_file(Path(filepath))
                    # Browse disabled portfolio in readonly mode (preview) - not builtin
                    self._browse_patterns(window, portfolio, is_readonly=True, is_builtin=False)
                except (OSError, ValueError) as e:
                    error_msg = f"Cannot load portfolio: {e}"
                    window.status_message(f"Regex Lab: {error_msg}")
                    self.logger.error("Browse disabled portfolio failed: %s", error_msg)
            elif selected_action == "export_portfolio":
                # Load portfolio from file (temporary, don't add to loaded portfolios)
                try:
                    # Use load_portfolio_from_file() for temporary read-only access
                    portfolio = self.portfolio_service.portfolio_manager.load_portfolio_from_file(Path(filepath))
                    self._action_export_portfolio(window, portfolio)
                except (OSError, ValueError) as e:
                    error_msg = f"Cannot load portfolio: {e}"
                    window.status_message(f"Regex Lab: {error_msg}")
                    self.logger.error("Export disabled portfolio failed: %s", error_msg)
            elif selected_action == "delete_portfolio":
                # For disabled portfolios, get readonly status from metadata
                is_readonly = metadata.get("readonly", False)
                self._delete_portfolio(window, name, is_readonly, filepath)

        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
        except (ImportError, AttributeError):
            window.show_quick_panel(items, on_select)

    def _enable_portfolio(self, window: sublime.Window, filepath: str, name: str) -> None:
        """
        Enable a disabled portfolio by moving it to portfolios/ folder.

        Args:
            window: Sublime Text window instance
            filepath: Path to the disabled portfolio file
            name: Portfolio name
        """
        import shutil

        try:
            # Move file from disabled_portfolios/ to portfolios/
            source_path = Path(filepath)
            packages_path = Path(window.extract_variables()["packages"])
            dest_dir = packages_path / "User" / "RegexLab" / "portfolios"
            dest_path = dest_dir / source_path.name

            self.logger.debug("Portfolio Manager: Moving portfolio from %s to %s", source_path, dest_path)

            # Ensure destination directory exists
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Move file
            shutil.move(str(source_path), str(dest_path))
            self.logger.info("Portfolio '%s' moved to portfolios/ (enabled)", name)

            # Auto-load the portfolio (V2.2.1+ auto-discovery)
            portfolio = self.portfolio_service.portfolio_manager.load_portfolio(
                dest_path, set_as_builtin=False, reload=False
            )

            pattern_count = len(portfolio.patterns)
            window.status_message(f"Regex Lab: Portfolio '{name}' enabled ({pattern_count} patterns)")
            self.logger.info("Portfolio '%s' enabled and loaded successfully (%s patterns)", name, pattern_count)

            # Reopen Portfolio Manager to show updated state
            self.run(window)

        except (OSError, ValueError, FileNotFoundError) as e:
            # OSError: File I/O errors (permissions, disk full, etc.)
            # ValueError: Invalid portfolio data format
            # FileNotFoundError: Portfolio file missing or moved
            window.status_message(f"Regex Lab: Error enabling portfolio - {e}")
            self.logger.error("Error enabling portfolio '%s' from %s - %s: %s", name, filepath, type(e).__name__, e)

    def _disable_portfolio(self, window: sublime.Window, portfolio: Portfolio) -> None:
        """
        Disable a loaded portfolio by moving it to disabled_portfolios/ folder.

        Inverse operation of _enable_portfolio:
        - Move file from portfolios/ to disabled_portfolios/
        - Unload portfolio from memory

        Args:
            window: Sublime Text window instance
            portfolio: Portfolio object to disable
        """
        import shutil

        try:
            # Get portfolio file path from portfolio manager
            # Need to find the source file in portfolios/ folder
            packages_path = Path(window.extract_variables()["packages"])
            portfolios_dir = packages_path / "User" / "RegexLab" / "portfolios"

            # Find the portfolio file by name (should match portfolio.name)
            # Convert portfolio name to filename using Unicode-aware normalization
            # Note: This is a heuristic - ideally we'd store the original filepath in Portfolio object
            portfolio_filename = normalize_portfolio_name(portfolio.name)
            source_path = portfolios_dir / portfolio_filename

            # Check if file exists (validation)
            if not source_path.exists():
                # Fallback: search all .json files in portfolios/ directory
                self.logger.debug("Portfolio file not found at expected path: %s", source_path)
                self.logger.debug("Searching for portfolio file in %s", portfolios_dir)

                found_file = find_portfolio_file_by_name(
                    portfolios_dir, portfolio.name, self.portfolio_service.validate_portfolio_file
                )

                if found_file is None:
                    error_msg = f"Portfolio file not found for '{portfolio.name}'"
                    window.status_message(f"Regex Lab: {error_msg}")
                    self.logger.error("Disable portfolio failed: %s", error_msg)
                    return

                source_path = found_file
                self.logger.debug("Found portfolio file: %s", source_path)

            # Create destination directory
            disabled_dir = packages_path / "User" / "RegexLab" / "disabled_portfolios"
            disabled_dir.mkdir(parents=True, exist_ok=True)
            dest_path = disabled_dir / source_path.name

            self.logger.debug("Portfolio Manager: Moving portfolio from %s to %s", source_path, dest_path)

            # Check if destination already exists (conflict)
            if dest_path.exists():
                error_msg = f"A disabled portfolio with filename '{source_path.name}' already exists"
                window.status_message(f"Regex Lab: {error_msg}")
                self.logger.error("Disable portfolio failed: %s", error_msg)
                return

            # Move file
            shutil.move(str(source_path), str(dest_path))
            self.logger.info("Portfolio '%s' moved to disabled_portfolios/ (disabled)", portfolio.name)

            # Unload portfolio from memory using PortfolioManager's unload method
            try:
                self.portfolio_service.portfolio_manager.unload_portfolio(portfolio.name)
                self.logger.info("Portfolio '%s' unloaded from memory", portfolio.name)
            except ValueError as unload_error:
                # Built-in portfolio cannot be unloaded - this shouldn't happen as we filter builtins
                self.logger.error("Cannot unload portfolio '%s': %s", portfolio.name, unload_error)
                window.status_message(f"Regex Lab: Error - {unload_error}")
                return

            pattern_count = len(portfolio.patterns)
            window.status_message(f"Regex Lab: Portfolio '{portfolio.name}' disabled ({pattern_count} patterns)")
            self.logger.info("Portfolio '%s' disabled successfully (%s patterns)", portfolio.name, pattern_count)

            # Reopen Portfolio Manager to show updated state
            self.run(window)

        except (OSError, ValueError, FileNotFoundError) as e:
            # OSError: File I/O errors (permissions, disk full, etc.)
            # ValueError: Invalid portfolio data format
            # FileNotFoundError: Portfolio file missing or moved
            window.status_message(f"Regex Lab: Error disabling portfolio - {e}")
            self.logger.error("Error disabling portfolio '%s' - %s: %s", portfolio.name, type(e).__name__, e)

    def _toggle_portfolio_readonly(self, window: sublime.Window, portfolio: Portfolio) -> None:
        """
        Toggle readonly flag for a Custom portfolio.

        Changes readonly=true to readonly=false or vice versa.
        Updates the portfolio file directly on disk.

        Args:
            window: Sublime Text window instance
            portfolio: Portfolio to toggle
        """
        import json
        from datetime import datetime

        old_value = portfolio.readonly
        new_value = not old_value

        self.logger.debug("Toggle Readonly: Portfolio '%s' from %s to %s", portfolio.name, old_value, new_value)

        # Update flag
        portfolio.readonly = new_value

        # Update timestamp
        portfolio.updated = datetime.now().strftime("%Y-%m-%d")

        # Get portfolio path
        portfolio_path = self.portfolio_service.portfolio_manager._portfolio_paths.get(portfolio.name)

        if not portfolio_path:
            window.status_message(f"RegexLab: Portfolio path not found for '{portfolio.name}'")
            self.logger.error("Toggle Readonly: Portfolio path not found")
            portfolio.readonly = old_value
            return

        # Save directly to disk (bypass readonly check in save_portfolio)
        try:
            portfolio_path.parent.mkdir(parents=True, exist_ok=True)

            data = portfolio.to_dict()
            with portfolio_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            status = "protected" if new_value else "editable"
            icon = ICON_READONLY if new_value else ICON_EDITABLE
            window.status_message(f"RegexLab: Portfolio '{portfolio.name}' is now {status} {icon}")

            self.logger.info(
                "Toggle Readonly: '%s' changed from %s to %s - saved to %s",
                portfolio.name,
                old_value,
                new_value,
                portfolio_path,
            )

        except Exception as e:
            window.status_message(f"RegexLab: Failed to update portfolio: {e}")
            self.logger.error("Toggle Readonly: Failed to save '%s': %s", portfolio.name, e)
            # Revert change
            portfolio.readonly = old_value

    def _delete_portfolio(
        self, window: sublime.Window, portfolio_name: str, is_readonly: bool, filepath: str | None = None
    ) -> None:
        """
        Delete a portfolio permanently with user confirmation.

        Can delete both loaded and disabled portfolios.
        Protection: Cannot delete builtin or readonly portfolios.

        Args:
            window: Sublime Text window instance
            portfolio_name: Name of the portfolio to delete
            is_readonly: Whether portfolio is readonly (protection flag)
            filepath: Optional path to portfolio file (for disabled portfolios)
        """
        self.logger.debug(
            "Delete portfolio requested: '%s' (readonly=%s, filepath=%s)", portfolio_name, is_readonly, filepath
        )

        # Protection: Cannot delete readonly portfolios
        if is_readonly:
            error_msg = f"Cannot delete readonly portfolio '{portfolio_name}'"
            window.status_message(f"Regex Lab: {error_msg}")
            self.logger.warning("Delete blocked: %s", error_msg)
            return

        # Show confirmation dialog
        self._show_delete_confirmation(window, portfolio_name, filepath)

    def _show_delete_confirmation(self, window: sublime.Window, portfolio_name: str, filepath: str | None) -> None:
        """
        Show confirmation dialog before deleting portfolio.

        Args:
            window: Sublime Text window instance
            portfolio_name: Name of portfolio to delete
            filepath: Optional path to portfolio file (for disabled portfolios)
        """
        # Get portfolio info for summary
        portfolio = self.portfolio_service.get_portfolio_by_name(portfolio_name)
        pattern_count = len(portfolio.patterns) if portfolio else 0

        # Build confirmation summary
        summary_items = [
            ("Portfolio Name", portfolio_name),
            ("Patterns", f"{pattern_count} pattern{'s' if pattern_count != 1 else ''}"),
            ("Location", filepath if filepath else "User/RegexLab/portfolios/"),
        ]

        summary_lines = format_aligned_summary("⚠️ Confirm Portfolio Deletion", summary_items)

        # Build Quick Panel items with summary + warnings + actions
        items = [
            *summary_lines,
            "",
            "⚠️ This action cannot be undone.",
            "⚠️ All patterns in this portfolio will be permanently lost.",
            "",
            "─" * 60,
            f"{ICON_DELETE} Delete this portfolio",
            f"{ICON_BACK} Cancel",
        ]

        def on_select(index: int) -> None:
            """Handle user confirmation response."""
            # User cancelled
            if index == -1:
                self.logger.debug("Delete cancelled by user for portfolio '%s'", portfolio_name)
                window.status_message("Regex Lab: Delete cancelled")
                return

            # Calculate action indices
            delete_index = len(summary_lines) + 5  # Delete button
            cancel_index = len(summary_lines) + 6  # Cancel button

            if index == delete_index:
                self.logger.debug("Delete confirmed for portfolio '%s'", portfolio_name)
                self._execute_delete(window, portfolio_name, filepath)
            elif index == cancel_index:
                self.logger.debug("Delete cancelled by user for portfolio '%s'", portfolio_name)
                window.status_message("Regex Lab: Delete cancelled")
            else:
                # User clicked on summary/warning line (re-show panel)
                self.logger.debug("Summary line clicked, re-showing confirmation")
                self._show_delete_confirmation(window, portfolio_name, filepath)

        self.logger.debug("Showing delete confirmation panel for portfolio '%s'", portfolio_name)

        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
        except (ImportError, AttributeError):
            window.show_quick_panel(items, on_select)

    def _execute_delete(self, window: sublime.Window, portfolio_name: str, filepath: str | None) -> None:
        """
        Execute portfolio deletion after confirmation.

        Handles both loaded and disabled portfolios.

        Args:
            window: Sublime Text window instance
            portfolio_name: Name of portfolio to delete
            filepath: Optional path to portfolio file (for disabled portfolios)
        """
        import os

        try:
            packages_path = Path(window.extract_variables()["packages"])

            # Determine file path based on whether it's loaded or disabled
            if filepath:
                # Disabled portfolio - filepath provided directly
                file_to_delete = Path(filepath)
                self.logger.debug("Deleting disabled portfolio from: %s", file_to_delete)
            else:
                # Loaded portfolio - find in portfolios/ folder
                portfolios_dir = packages_path / "User" / "RegexLab" / "portfolios"
                portfolio_filename = f"{portfolio_name.lower().replace(' ', '_')}.json"
                file_to_delete = portfolios_dir / portfolio_filename

                # Fallback: search for exact match if heuristic fails
                if not file_to_delete.exists():
                    self.logger.debug("Portfolio file not found at expected path: %s", file_to_delete)
                    self.logger.debug("Searching for portfolio file in %s", portfolios_dir)

                    found_file = find_portfolio_file_by_name(
                        portfolios_dir, portfolio_name, self.portfolio_service.validate_portfolio_file
                    )

                    if found_file is None:
                        error_msg = f"Portfolio file not found for '{portfolio_name}'"
                        window.status_message(f"Regex Lab: {error_msg}")
                        self.logger.error("Delete failed: %s", error_msg)
                        return

                    file_to_delete = found_file
                    self.logger.debug("Found portfolio file: %s", file_to_delete)

            # Verify file exists before deletion
            if not file_to_delete.exists():
                error_msg = f"Portfolio file does not exist: {file_to_delete}"
                window.status_message(f"Regex Lab: {error_msg}")
                self.logger.error("Delete failed: %s", error_msg)
                return

            self.logger.debug("Deleting portfolio file: %s", file_to_delete)

            # Delete the file
            os.remove(str(file_to_delete))
            self.logger.info("Portfolio '%s' deleted from disk (%s)", portfolio_name, file_to_delete.name)

            # If it's a loaded portfolio, unload from memory
            if not filepath:
                try:
                    self.portfolio_service.portfolio_manager.unload_portfolio(portfolio_name)
                    self.logger.info("Portfolio '%s' unloaded from memory", portfolio_name)
                except ValueError as unload_error:
                    # Built-in portfolio - should not happen due to readonly protection
                    self.logger.warning("Unload warning for '%s': %s", portfolio_name, unload_error)

            window.status_message(f"Regex Lab: Portfolio '{portfolio_name}' deleted")
            self.logger.info("Portfolio '%s' deleted successfully", portfolio_name)

            # Reopen Portfolio Manager to show updated state
            self.run(window)

        except (OSError, FileNotFoundError) as e:
            # OSError: File I/O errors (permissions, file in use, etc.)
            # FileNotFoundError: File was moved/deleted between check and delete
            error_msg = f"Error deleting portfolio - {e}"
            window.status_message(f"Regex Lab: {error_msg}")
            self.logger.error("Delete failed for '%s' - %s: %s", portfolio_name, type(e).__name__, e)

    def _handle_action(self, window: sublime.Window, action_name: str | None) -> None:
        """
        Handle generic action selection.

        Routes to appropriate action handler based on action_name.

        Args:
            window: Sublime Text window instance
            action_name: Name of the action to execute
        """
        if not action_name:
            self.logger.warning("Portfolio Manager: No action name provided")
            return

        self.logger.debug("Portfolio Manager: Action selected: %s", action_name)

        # Route to action handlers
        if action_name == "new_portfolio":
            self._action_new_portfolio(window)
        elif action_name == "import_portfolio":
            self._action_import_portfolio(window)
        elif action_name == "reload_portfolios":
            self._action_reload_portfolios(window)
        elif action_name == "open_settings":
            self._action_open_settings(window)
        elif action_name == "about":
            self._action_about(window)
        else:
            self.logger.warning("Portfolio Manager: Unknown action: %s", action_name)
            window.status_message(f"Regex Lab: Unknown action '{action_name}'")

    def _action_new_portfolio(self, window: sublime.Window) -> None:
        """
        Action: Create a new portfolio.

        Invokes the New Portfolio Wizard command.

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Portfolio Manager: Executing 'New Portfolio' action")
        self.logger.debug("Portfolio Manager: Invoking New Portfolio Wizard")

        window.run_command("regex_lab_new_portfolio_wizard")

    def _action_import_portfolio(self, window: sublime.Window) -> None:
        """
        Action: Import an external portfolio file.

        Opens file picker to select a .json portfolio file,
        then copies it to User/RegexLab/portfolios/ and loads it.

        Workflow:
        1. Show file picker to select .json file
        2. Validate portfolio file format
        3. Check for duplicate portfolio names
        4. Copy file to User/RegexLab/portfolios/
        5. Auto-load via discovery system (V2.2.1+)

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Portfolio Manager: Executing 'Import Portfolio' action")

        import os
        import shutil
        from pathlib import Path

        def on_done(selected_path: str) -> None:
            """Handle file picker selection."""
            if not selected_path:
                self.logger.debug("Import cancelled - no file selected")
                window.status_message("Regex Lab: Import cancelled")
                return

            self.logger.debug("Import Portfolio: Selected file: %s", selected_path)

            try:
                # Step 1: Validate file exists
                if not os.path.exists(selected_path):
                    error = "File not found"
                    self.logger.error("Import failed: %s", error)
                    window.status_message(f"Regex Lab: {error}")
                    return

                # Step 2: Validate .json extension
                if not selected_path.lower().endswith(".json"):
                    error = "Invalid file type (must be .json)"
                    self.logger.error("Import failed: %s", error)
                    window.status_message(f"Regex Lab: {error}")
                    return

                # Step 3: Validate portfolio file format
                valid, result = self.portfolio_service.validate_portfolio_file(selected_path)
                if not valid:
                    self.logger.error("Import failed: Invalid portfolio - %s", result)
                    window.status_message(f"Regex Lab: Invalid portfolio - {result}")
                    return

                # result is Dict when valid is True
                metadata = result
                assert isinstance(metadata, dict)
                portfolio_name = metadata["name"]
                pattern_count = metadata["pattern_count"]

                self.logger.debug("Import Portfolio: Valid portfolio '%s' (%s patterns)", portfolio_name, pattern_count)

                # Step 4: Check for duplicate portfolio names
                packages_path = window.extract_variables()["packages"]
                if self.portfolio_service.portfolio_exists(portfolio_name, packages_path):
                    error = f"Portfolio '{portfolio_name}' already exists"
                    self.logger.error("Import failed: %s", error)
                    window.status_message(f"Regex Lab: {error}")
                    return

                # Step 5: Copy to User/RegexLab/portfolios/
                dest_dir = Path(packages_path) / "User" / "RegexLab" / "portfolios"
                dest_dir.mkdir(parents=True, exist_ok=True)

                # Use original filename (avoid name conflicts)
                source_path = Path(selected_path)
                dest_path = dest_dir / source_path.name

                # Check if filename already exists (different portfolio name)
                if dest_path.exists():
                    # Add suffix to avoid overwrite
                    base_name = source_path.stem
                    suffix = 1
                    while dest_path.exists():
                        dest_path = dest_dir / f"{base_name}_{suffix}.json"
                        suffix += 1
                    self.logger.debug("Filename conflict, using: %s", dest_path.name)

                shutil.copy2(selected_path, dest_path)
                self.logger.info("Portfolio copied to: %s", dest_path)

                # Step 6: Auto-load via discovery system (V2.2.1+)
                self.portfolio_service.portfolio_manager.load_portfolio(dest_path, set_as_builtin=False, reload=False)

                self.logger.info("Portfolio '%s' imported and loaded successfully", portfolio_name)
                window.status_message(f"Regex Lab: Portfolio '{portfolio_name}' imported ({pattern_count} patterns)")

                # Reopen Portfolio Manager to show updated state
                self.run(window)

            except (OSError, ValueError, FileNotFoundError) as e:
                # OSError: File I/O errors (permissions, disk issues)
                # ValueError: Invalid portfolio format/data
                # FileNotFoundError: Portfolio file not found at path
                self.logger.error("Import failed - %s: %s", type(e).__name__, e)
                window.status_message(f"Regex Lab: Import failed - {e}")

        # Show input panel for file path
        # Sublime Text doesn't have a native file picker dialog in Python API
        # Use input panel with initial path
        self.logger.debug("Showing input panel for portfolio import")
        initial_path = str(Path.home())
        window.show_input_panel(
            "Import Portfolio - Enter full path to .json file:",
            initial_path,
            on_done,  # on_done callback
            None,  # on_change callback
            None,  # on_cancel callback
        )

    def _action_export_portfolio(self, window: sublime.Window, portfolio: Portfolio | None = None) -> None:
        """
        Action: Export a portfolio to an external location.

        Workflow:
        1. Show Quick Panel to select portfolio to export (if portfolio not provided)
        2. Show input panel for destination path
        3. Validate destination and export
        4. Show success/error message

        Args:
            window: Sublime Text window instance
            portfolio: Optional portfolio to export directly (skips selection)
        """
        self.logger.debug("Portfolio Manager: Executing 'Export Portfolio' action")

        # If portfolio provided, skip selection and go directly to export
        if portfolio:
            self.logger.debug(
                "Export Portfolio: Portfolio provided directly '%s' (readonly: %s, %s patterns)",
                portfolio.name,
                portfolio.readonly,
                len(portfolio.patterns),
            )
            self._show_export_path_input(window, portfolio)
            return

        # Get all loaded portfolios
        portfolios = self.portfolio_service.get_all_portfolios()
        self.logger.debug("Export Portfolio: Found %s loaded portfolios", len(portfolios))

        if not portfolios:
            window.status_message("Regex Lab: No portfolios available to export")
            self.logger.info("Export Portfolio: No portfolios available")
            return

        # Portfolios already sorted by get_all_portfolios() (builtin first, alphabetical)
        # No need to re-sort here

        # Build Quick Panel items
        items: list[list[str]] = []
        portfolio_map: list[Portfolio] = []

        for portfolio in portfolios:
            # Check if portfolio is builtin (based on file location, not readonly flag)
            is_builtin = self._is_builtin_portfolio(portfolio.name)

            # Icon and label based on actual location
            if is_builtin:
                icon = ICON_BUILTIN_BOOK
                type_label = " (Built-in)"
            elif portfolio.readonly:
                icon = ICON_READONLY
                type_label = " (Custom - Protected)"
            else:
                icon = ICON_FOLDER
                type_label = ""

            # Pattern count
            pattern_count = len(portfolio.patterns)
            patterns_label = f"{pattern_count} {pluralize(pattern_count, 'pattern')}"

            items.append([f"{icon} {portfolio.name}{type_label}", patterns_label])
            portfolio_map.append(portfolio)

        self.logger.debug("Export Portfolio: Showing portfolio selection panel (%s items)", len(items))

        # Show portfolio selection
        def on_portfolio_select(index: int) -> None:
            if index == -1:
                self.logger.debug("Export Portfolio: User cancelled portfolio selection")
                return

            selected_portfolio = portfolio_map[index]
            self.logger.debug(
                "Export Portfolio: Selected portfolio '%s' (readonly: %s, %s patterns)",
                selected_portfolio.name,
                selected_portfolio.readonly,
                len(selected_portfolio.patterns),
            )

            # Show input panel for destination path
            self._show_export_path_input(window, selected_portfolio)

        window.show_quick_panel(items, on_portfolio_select)

    def _show_export_path_input(self, window: sublime.Window, portfolio: Portfolio) -> None:
        """
        Show input panel for export destination path and export portfolio.

        Args:
            window: Sublime Text window instance
            portfolio: Portfolio to export
        """
        # Get export directory from settings
        export_dir = self.settings_manager.get("export_default_directory", DEFAULT_EXPORT_DIRECTORY)
        self.logger.debug("Export Portfolio: Using export directory from settings: %s", export_dir)

        # Expand special paths
        if export_dir.startswith("~/") or export_dir.startswith("${HOME}"):
            # Home directory
            export_dir = export_dir.replace("~/", str(Path.home()) + "/")
            export_dir = export_dir.replace("${HOME}", str(Path.home()))
        elif export_dir == "${DOWNLOADS}":
            # Downloads directory (platform-specific)
            export_dir = str(Path.home() / "Downloads")

        # Create directory if it doesn't exist
        export_path = Path(export_dir)
        try:
            if not export_path.exists():
                self.logger.debug("Export Portfolio: Creating export directory: %s", export_path)
                export_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.logger.warning("Export Portfolio: Cannot create export directory: %s", e)
            # Fallback to home directory
            export_path = Path.home()

        # Show input panel for destination path
        def on_path_done(user_path: str) -> None:
            if not user_path.strip():
                self.logger.debug("Export Portfolio: Empty path provided, cancelling")
                return

            self.logger.debug("Export Portfolio: User entered destination path: %s", user_path)

            # Export portfolio
            self.logger.debug("Export Portfolio: Calling portfolio_service.export_portfolio_to_path()")
            success, message = self.portfolio_service.export_portfolio_to_path(portfolio, user_path)

            if success:
                window.status_message(f"Regex Lab: {message}")
                self.logger.info("Export Portfolio: Success - %s", message)
            else:
                window.status_message(f"Regex Lab: {message}")
                self.logger.warning("Export Portfolio: Failed - %s", message)

        # Suggest filename based on portfolio name (Unicode-aware normalization)
        suggested_name = normalize_portfolio_name(portfolio.name)
        suggested_path = str(export_path / suggested_name)
        self.logger.debug("Export Portfolio: Suggested path: %s", suggested_path)

        self.logger.debug("Export Portfolio: Showing input panel for destination path")
        window.show_input_panel(
            f"Export '{portfolio.name}' - Enter destination path:",
            suggested_path,
            on_path_done,
            None,
            None,
        )

    def _action_reload_portfolios(self, window: sublime.Window) -> None:
        """
        Action: Reload all portfolios from disk.

        Refreshes all loaded portfolios to pick up external changes.
        Delegates to the global reload command for consistency.

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Portfolio Manager: Executing 'Reload Portfolios' action")

        try:
            # Use the global reload command for consistency
            # This ensures the same reload logic is used everywhere
            window.run_command("regex_lab_reload_portfolios")
            self.logger.debug("Portfolio Manager: Reload command executed")

        except (OSError, ValueError) as e:
            # OSError: File I/O errors during portfolio reload
            # ValueError: Invalid portfolio data encountered
            window.status_message(f"Regex Lab: Error reloading portfolios - {e}")
            self.logger.error("Error reloading portfolios - %s: %s", type(e).__name__, e)

    def _action_open_settings(self, window: sublime.Window) -> None:
        """
        Action: Open RegexLab settings file.

        Opens the settings in split view (base settings + user overrides).

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Portfolio Manager: Executing 'Open Settings' action")

        try:
            # Use Sublime's built-in edit_settings command
            self.logger.debug("Portfolio Manager: Invoking edit_settings command")

            window.run_command(
                "edit_settings",
                {
                    "base_file": "${packages}/RegexLab/RegexLab.sublime-settings",
                    "default": '// Settings in here override those in "RegexLab.sublime-settings"\n{\n\t$0\n}\n',
                },
            )

            window.status_message("Regex Lab: Settings opened")
            self.logger.info("Portfolio Manager: Settings file opened successfully")

        except (OSError, AttributeError) as e:
            # OSError: File system errors (settings file access)
            # AttributeError: Sublime Text API unavailable or method missing
            window.status_message(f"Regex Lab: Error opening settings - {e}")
            self.logger.error("Portfolio Manager: Error opening settings - %s: %s", type(e).__name__, e)

    def _action_about(self, window: sublime.Window) -> None:
        """
        Action: Show About RegexLab.

        Opens the installation message in a new buffer.

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("Portfolio Manager: Executing 'About' action")

        try:
            # Invoke the regexlab_about command
            self.logger.debug("Portfolio Manager: Invoking regexlab_about command")
            window.run_command("regexlab_about")

            self.logger.info("Portfolio Manager: About dialog displayed successfully")

        except (OSError, AttributeError) as e:
            window.status_message(f"Regex Lab: Error showing about - {e}")
            self.logger.error("Portfolio Manager: Error showing about - %s: %s", type(e).__name__, e)

    def _show_pattern_selection_for_edit(self, window: sublime.Window, portfolio: Portfolio) -> None:
        """
        Show Quick Panel to select a pattern to edit.

        Displays all patterns in portfolio, then launches EditPatternCommand
        for the selected pattern.

        Args:
            window: Sublime Text window instance
            portfolio: Portfolio containing patterns
        """
        self.logger.debug("Portfolio Manager: Showing pattern selection for edit (portfolio: %s)", portfolio.name)

        if not portfolio.patterns:
            window.status_message(f"Regex Lab: Portfolio '{portfolio.name}' has no patterns to edit")
            self.logger.info("Edit Pattern: No patterns in portfolio '%s'", portfolio.name)
            return

        # Build Quick Panel items
        items: list[list[str]] = []
        pattern_map: list[Pattern] = []

        for pattern in portfolio.patterns:
            # Type icon
            type_icon = ICON_STATIC_PATTERN if pattern.type == PatternType.STATIC else ICON_DYNAMIC_PATTERN

            # Panel icon
            panel_icons = {
                "find": ICON_FIND_PANEL,
                "replace": ICON_REPLACE_PANEL,
                "find_in_files": ICON_FIND_IN_FILES_PANEL,
            }
            panel_icon = panel_icons.get(pattern.default_panel or "find", ICON_FIND_PANEL)

            # Truncate regex for display
            regex_display = pattern.regex if len(pattern.regex) <= 50 else pattern.regex[:47] + "..."

            # Description
            description = pattern.description or "No description"

            items.append(
                [
                    f"{type_icon} {pattern.name} {panel_icon}",
                    f"{regex_display} • {description}",
                ]
            )
            pattern_map.append(pattern)

        self.logger.debug("Edit Pattern: Showing %s patterns", len(items))

        def on_select(index: int) -> None:
            if index == -1:
                self.logger.debug("Edit Pattern: Selection cancelled")
                return

            selected_pattern = pattern_map[index]
            self.logger.debug("Edit Pattern: Selected pattern '%s'", selected_pattern.name)

            # Launch EditPatternCommand
            from .edit_pattern_command import EditPatternCommand

            command = EditPatternCommand()
            command.run(window, selected_pattern, portfolio)

        window.show_quick_panel(items, on_select)

    def _show_pattern_selection_for_delete(self, window: sublime.Window, portfolio: Portfolio) -> None:
        """
        Show Quick Panel to select a pattern to delete.

        Displays all patterns in portfolio, then launches DeletePatternCommand
        for the selected pattern.

        Args:
            window: Sublime Text window instance
            portfolio: Portfolio containing patterns
        """
        self.logger.debug("Portfolio Manager: Showing pattern selection for delete (portfolio: %s)", portfolio.name)

        if not portfolio.patterns:
            window.status_message(f"Regex Lab: Portfolio '{portfolio.name}' has no patterns to delete")
            self.logger.info("Delete Pattern: No patterns in portfolio '%s'", portfolio.name)
            return

        # Build Quick Panel items
        items: list[list[str]] = []
        pattern_map: list[Pattern] = []

        for pattern in portfolio.patterns:
            # Type icon
            type_icon = ICON_STATIC_PATTERN if pattern.type == PatternType.STATIC else ICON_DYNAMIC_PATTERN

            # Panel icon
            panel_icons = {
                "find": ICON_FIND_PANEL,
                "replace": ICON_REPLACE_PANEL,
                "find_in_files": ICON_FIND_IN_FILES_PANEL,
            }
            panel_icon = panel_icons.get(pattern.default_panel or "find", ICON_FIND_PANEL)

            # Truncate regex for display
            regex_display = pattern.regex if len(pattern.regex) <= 50 else pattern.regex[:47] + "..."

            # Description
            description = pattern.description or "No description"

            items.append(
                [
                    f"{ICON_DELETE} {type_icon} {pattern.name} {panel_icon}",
                    f"{regex_display} • {description}",
                ]
            )
            pattern_map.append(pattern)

        self.logger.debug("Delete Pattern: Showing %s patterns", len(items))

        def on_select(index: int) -> None:
            if index == -1:
                self.logger.debug("Delete Pattern: Selection cancelled")
                return

            selected_pattern = pattern_map[index]
            self.logger.debug("Delete Pattern: Selected pattern '%s'", selected_pattern.name)

            # Launch DeletePatternCommand
            from .delete_pattern_command import DeletePatternCommand

            command = DeletePatternCommand()
            command.run(window, selected_pattern, portfolio)

        window.show_quick_panel(items, on_select)

    def _browse_patterns(
        self, window: sublime.Window, portfolio: Portfolio, is_readonly: bool, is_builtin: bool = False
    ) -> None:
        """
        Browse patterns in a portfolio.

        Shows a Quick Panel with all patterns in the portfolio.
        - Builtin portfolios: Allow pattern injection (Find/Replace/Find in Files) but no CRUD
        - Custom editable portfolios: Allow injection + CRUD (Edit/Delete)
        - Custom readonly portfolios: Allow injection only
        - Disabled portfolios: Preview mode only (no actions)

        Args:
            window: Sublime Text window instance
            portfolio: Portfolio to browse
            is_readonly: Whether portfolio is readonly (custom protected or disabled)
            is_builtin: Whether portfolio is builtin (from data/portfolios/)
        """
        self.logger.debug("Portfolio Manager: Browsing patterns in portfolio '%s'", portfolio.name)

        if not portfolio.patterns:
            window.status_message(f"Regex Lab: Portfolio '{portfolio.name}' has no patterns")
            self.logger.info("Portfolio '%s' has no patterns to browse", portfolio.name)
            return

        # Build Quick Panel items for patterns
        items: list[list[str]] = []
        pattern_map: list[Pattern] = []

        for pattern in portfolio.patterns:
            # Get pattern type icon (using proper enum comparison)
            type_icon = ICON_STATIC_PATTERN if pattern.type == PatternType.STATIC else ICON_DYNAMIC_PATTERN

            # Truncate regex for display (max 60 chars)
            regex_display = pattern.regex if len(pattern.regex) <= 60 else pattern.regex[:57] + "..."

            # First line: Icon + Name + Type
            name_line = f"{type_icon} {pattern.name}"

            # Second line: Regex + Description
            description = pattern.description or "No description"
            second_line = f"{regex_display} • {description}"

            items.append([name_line, second_line])
            pattern_map.append(pattern)

        self.logger.debug("Portfolio Manager: Showing %s patterns", len(items))

        def on_select(index: int) -> None:
            if index == -1:
                self.logger.debug("Portfolio Manager: Pattern browsing cancelled")
                # Reopen portfolio context menu
                self._handle_loaded_portfolio(window, {"portfolio": portfolio, "name": portfolio.name})
                return

            selected_pattern = pattern_map[index]
            self.logger.debug("Portfolio Manager: Selected pattern '%s'", selected_pattern.name)

            # Detect if this is a builtin portfolio (not just disabled)
            is_builtin = self._is_builtin_portfolio(portfolio.name)

            # Show pattern actions menu (Find/Replace/Edit/Delete)
            # For builtin: allow injection actions, block CRUD
            # For disabled: block all actions (preview mode only)
            self._show_pattern_actions(window, portfolio, selected_pattern, pattern_map, is_readonly, is_builtin)

        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
        except (ImportError, AttributeError):
            window.show_quick_panel(items, on_select)

    def _show_pattern_actions(
        self,
        window: sublime.Window,
        portfolio: Portfolio,
        pattern: Pattern,
        all_patterns: list[Pattern],
        is_readonly: bool = False,
        is_builtin: bool = False,
    ) -> None:
        """
        Show actions menu for a selected pattern.

        Actions available for builtin patterns:
        - Find (load in Find panel)
        - Replace (load in Replace panel)
        - Find in Files (load in Find in Files panel)

        Actions available for editable custom patterns:
        - Find, Replace, Find in Files (same as builtin)
        - Edit Pattern
        - Delete Pattern

        Disabled portfolios (preview mode):
        - No actions available (blocked in _browse_patterns)

        Args:
            window: Sublime Text window instance
            portfolio: Portfolio containing the pattern
            pattern: Selected pattern
            all_patterns: List of all patterns (for navigation back)
            is_readonly: Whether the portfolio is readonly (custom protected or disabled)
            is_builtin: Whether the portfolio is builtin (from data/portfolios/)
        """
        self.logger.debug(
            "Portfolio Manager: Showing actions for pattern '%s' (readonly=%s, builtin=%s)",
            pattern.name,
            is_readonly,
            is_builtin,
        )

        items: list[list[str]] = []
        action_map: list[str] = []

        # DISABLED PORTFOLIOS: Block all actions (preview mode only)
        # Check if this is a disabled portfolio by verifying it's readonly but NOT builtin
        # Builtin portfolios are always readonly but should allow injection
        is_disabled_portfolio = is_readonly and not is_builtin

        if is_disabled_portfolio:
            # Preview mode - no actions, just show info
            items.append([f"{ICON_BACK} Back", "Return to pattern list (preview mode)"])
            action_map.append("back")

            self.logger.debug("Portfolio Manager: Disabled portfolio - showing preview mode (no actions)")

            def on_select_disabled(index: int) -> None:
                # Only action is Back
                self._browse_patterns(window, portfolio, is_readonly=True, is_builtin=False)

            try:
                import sublime  # pyright: ignore[reportMissingImports]

                window.show_quick_panel(items, on_select_disabled, flags=sublime.MONOSPACE_FONT)
            except (ImportError, AttributeError):
                window.show_quick_panel(items, on_select_disabled)
            return

        # BUILTIN or EDITABLE CUSTOM portfolios: Show injection actions
        # 1. Find
        items.append([f"{ICON_FIND_PANEL} Find", "Load this pattern in the Find panel"])
        action_map.append("find")

        # 2. Replace
        items.append([f"{ICON_REPLACE_PANEL} Replace", "Load this pattern in the Replace panel"])
        action_map.append("replace")

        # 3. Find in Files
        items.append([f"{ICON_FIND_IN_FILES_PANEL} Find in Files", "Load this pattern in the Find in Files panel"])
        action_map.append("find_in_files")

        # Additional actions for EDITABLE CUSTOM portfolios only (not builtin, not readonly custom)
        if not is_builtin and not is_readonly:
            # 4. Edit Pattern
            items.append([f"{ICON_EDIT} Edit Pattern", "Modify this pattern with the Pattern Edit Wizard"])
            action_map.append("edit_pattern")

            # 5. Delete Pattern
            items.append([f"{ICON_DELETE} Delete Pattern", "Remove this pattern from the portfolio"])
            action_map.append("delete_pattern")

        # 6. Back
        items.append([f"{ICON_BACK} Back", "Return to pattern list"])
        action_map.append("back")

        def on_select(index: int) -> None:
            if index == -1:
                # Cancelled - back to pattern list
                self._browse_patterns(window, portfolio, is_readonly, is_builtin)
                return

            selected_action = action_map[index]
            self.logger.debug("Portfolio Manager: Pattern action selected: %s", selected_action)

            if selected_action == "find":
                self._load_pattern_in_panel(window, pattern, "find")
            elif selected_action == "find_in_files":
                self._load_pattern_in_panel(window, pattern, "find_in_files")
            elif selected_action == "replace":
                self._load_pattern_in_panel(window, pattern, "replace")
            elif selected_action == "edit_pattern":
                # Launch EditPatternCommand for the selected pattern
                from .edit_pattern_command import EditPatternCommand

                edit_command = EditPatternCommand()
                edit_command.run(window, pattern, portfolio)
            elif selected_action == "delete_pattern":
                # Launch DeletePatternCommand for the selected pattern
                from .delete_pattern_command import DeletePatternCommand

                delete_command = DeletePatternCommand()
                delete_command.run(window, pattern, portfolio)
            elif selected_action == "back":
                self._browse_patterns(window, portfolio, is_readonly, is_builtin)

        try:
            import sublime  # pyright: ignore[reportMissingImports]

            window.show_quick_panel(items, on_select, flags=sublime.MONOSPACE_FONT)
        except (ImportError, AttributeError):
            window.show_quick_panel(items, on_select)

    def _is_builtin_portfolio(self, portfolio_name: str) -> bool:
        """
        Check if portfolio is builtin (from data/portfolios/).

        Builtin portfolios are read-only and cannot be edited, disabled, or deleted.

        Args:
            portfolio_name: Name of the portfolio to check

        Returns:
            True if builtin, False if custom
        """
        # Use portfolio_paths from PortfolioManager (no file I/O needed)
        portfolio_path = self.portfolio_service.portfolio_manager._portfolio_paths.get(portfolio_name)
        is_builtin = is_builtin_portfolio_path(portfolio_path)

        if is_builtin:
            self.logger.debug("Portfolio '%s' is builtin", portfolio_name)
        else:
            self.logger.debug("Portfolio '%s' is custom", portfolio_name)

        return is_builtin

    def _load_pattern_in_panel(self, window: sublime.Window, pattern: Pattern, panel_type: str) -> None:
        """
        Load a pattern into a Sublime Text panel (Find, Find in Files, or Replace).

        Handles both static and dynamic patterns with variable resolution.

        Args:
            window: Sublime Text window instance
            pattern: Pattern to load
            panel_type: Type of panel - "find", "find_in_files", or "replace"
        """
        self.logger.debug("Portfolio Manager: Loading pattern '%s' into '%s' panel", pattern.name, panel_type)

        try:
            # Handle static patterns - direct injection
            if not pattern.is_dynamic():
                resolved_pattern = self.pattern_service.format_for_find_panel(pattern)
                inject_pattern_in_panel(window, panel_type, resolved_pattern, pattern.name)
                return

            # Handle dynamic patterns - collect variables first
            variables_to_collect = pattern.variables or []
            if not variables_to_collect:
                window.status_message("Regex Lab: Dynamic pattern has no variables")
                return

            # Start collecting variables (will inject after resolution)
            collect_variables_for_pattern(window, pattern, variables_to_collect, {}, panel_type, self.pattern_service)

        except (ValueError, KeyError, AttributeError) as e:
            # ValueError: Invalid pattern data or configuration
            # KeyError: Missing required pattern fields
            # AttributeError: Pattern object missing required attributes
            self.logger.error("Error loading pattern '%s' - %s: %s", pattern.name, type(e).__name__, e)
            window.status_message(f"Regex Lab: Error loading pattern - {e}")
