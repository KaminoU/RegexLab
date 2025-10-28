"""
RegexLab - Pattern management plugin for Sublime Text.

A comprehensive plugin for managing and using regex patterns with portfolios,
dynamic variables, and seamless Find panel integration.
"""

import sublime  # pyright: ignore[reportMissingImports]
import sublime_plugin  # pyright: ignore[reportMissingImports]

# Support both ST package loading (RegexLab.RegexLab) and direct execution
if __name__ == "RegexLab.RegexLab":
    # Normal ST loading: use relative imports
    from .src.commands.about_command import RegexlabAboutCommand as AboutCommandImpl
    from .src.commands.generate_integrity_command import RegexlabGenerateIntegrityCommand  # noqa: F401
    from .src.commands.load_pattern_command import LoadPatternCommand
    from .src.commands.new_portfolio_wizard_command import NewPortfolioWizardCommand
    from .src.commands.portfolio_manager_command import PortfolioManagerCommand
    from .src.commands.use_selection_command import RegexLabUseSelectionCommand as UseSelectionCommandImpl
else:
    # Direct import (tests, UnitTesting reload): use absolute imports
    from src.commands.about_command import RegexlabAboutCommand as AboutCommandImpl
    from src.commands.generate_integrity_command import RegexlabGenerateIntegrityCommand  # noqa: F401
    from src.commands.load_pattern_command import LoadPatternCommand
    from src.commands.new_portfolio_wizard_command import NewPortfolioWizardCommand
    from src.commands.portfolio_manager_command import PortfolioManagerCommand
    from src.commands.use_selection_command import RegexLabUseSelectionCommand as UseSelectionCommandImpl


class RegexLabLoadPatternCommand(sublime_plugin.WindowCommand):
    """
    Load a pattern from active portfolio into Find panel.

    Supports both static and dynamic patterns with variable resolution.
    """

    def run(self) -> None:
        """Execute the command."""
        command = LoadPatternCommand()
        command.run(self.window)


class RegexLabPortfolioManagerCommand(sublime_plugin.WindowCommand):
    """
    Portfolio Manager - Central hub for portfolio management.

    Entry point for:
    - View loaded/available portfolios
    - Load/unload portfolios
    - Create new portfolios
    - Access management actions
    """

    def run(self) -> None:
        """Execute the command."""
        command = PortfolioManagerCommand()
        command.run(self.window)


class RegexLabNewPortfolioWizardCommand(sublime_plugin.WindowCommand):
    """
    New Portfolio Wizard - Multi-step wizard for creating new portfolios.

    Guides the user through 5 steps:
    1. Portfolio Name (validated)
    2. Description (optional)
    3. Author (optional, defaults to username)
    4. Tags (optional, comma-separated)
    5. Confirmation (summary + create)
    """

    def run(self) -> None:
        """Execute the command."""
        command = NewPortfolioWizardCommand()
        command.run(self.window)


class RegexLabUseSelectionCommand(sublime_plugin.WindowCommand):
    """
    Use Selection - Create pattern from selected text.

    Provides quick pattern creation workflow:
    1. Quick Panel: Choose action (Create Pattern / Use as Find Pattern)
    2. If Create Pattern: Simplified wizard (name + portfolio selection)
    3. Pattern saved with selected text as regex

    Context-aware: Only available when text is selected.
    """

    def run(self) -> None:
        """Execute the command."""
        command = UseSelectionCommandImpl()
        command.run(self.window)


class RegexlabAboutCommand(sublime_plugin.WindowCommand):
    """
    About - Display RegexLab version and installation guide.

    Opens the installation message in a new buffer.
    Accessible from Portfolio Manager and Command Palette.
    """

    def run(self) -> None:
        """Execute the command."""
        command = AboutCommandImpl()
        command.run(self.window)


class RegexLabReloadPortfoliosCommand(sublime_plugin.WindowCommand):
    """
    Reload Portfolios - Force refresh of all portfolios.

    Re-scans portfolio directories and reloads all .json files:
    - RegexLab/data/portfolios/ (builtin)
    - User/RegexLab/portfolios/ (custom active)

    Useful when portfolio files are modified outside Sublime Text.
    """

    def run(self) -> None:
        """Execute the command to reload all portfolios."""
        from pathlib import Path

        from .src.core.logger import get_logger
        from .src.services.portfolio_service import PortfolioService

        logger = get_logger()
        service = PortfolioService()
        packages_path = Path(sublime.packages_path())

        logger.info("RegexLab: Manual portfolio reload triggered")

        # Clear existing portfolios
        service.portfolio_manager._loaded_portfolios.clear()
        service.portfolio_manager._builtin_portfolio = None
        service.portfolio_manager._portfolio_paths.clear()
        logger.debug("Cleared existing portfolios from memory")

        # STEP 0 - Multi-Portfolio Integrity Verification (v2)
        regexlab_dir_v2 = packages_path / "RegexLab" / "data" / ".regexlab"  # BUILTIN location!
        from .src.core.integrity_manager import IntegrityManager

        integrity_manager_v2 = IntegrityManager(regexlab_dir_v2)

        # A) Built-in portfolios
        builtin_dir = packages_path / "RegexLab" / "data" / "portfolios"

        # Verify integrity if keystore exists
        if integrity_manager_v2.keystore_file.exists():
            logger.info("Verifying multi-portfolio integrity (reload)...")
            all_ok, verified, restored = integrity_manager_v2.verify_and_restore(builtin_dir)
            if all_ok:
                logger.info("✓ All %s builtin portfolios verified", len(verified))
            else:
                logger.warning("⚠ Restored %s portfolios:", len(restored))
                for portfolio_name, reason in restored:
                    logger.warning("  - %s - %s", portfolio_name, reason)

        # Reload portfolios using same logic as plugin_loaded
        portfolios_to_load = []
        loaded_count = 0
        failed_count = 0

        builtin_files = sorted(builtin_dir.glob("*.json"))
        for filepath in builtin_files:
            portfolios_to_load.append((filepath, True))

        # B) Custom portfolios
        user_regexlab = packages_path / "User" / "RegexLab"
        portfolios_dir = user_regexlab / "portfolios"
        custom_files = sorted(portfolios_dir.glob("*.json"))
        for filepath in custom_files:
            portfolios_to_load.append((filepath, False))

        logger.debug("Reloading %s portfolio(s)...", len(portfolios_to_load))

        # Load all portfolios
        first_builtin = True
        for portfolio_path, is_builtin in portfolios_to_load:
            try:
                # First builtin portfolio becomes the "builtin principal" (backward compat)
                set_as_builtin_flag = is_builtin and first_builtin
                service.portfolio_manager.load_portfolio(
                    portfolio_path, set_as_builtin=set_as_builtin_flag, reload=True
                )
                if is_builtin and first_builtin:
                    first_builtin = False
                loaded_count += 1
            except Exception as e:
                failed_count += 1
                logger.error("Failed to reload portfolio: %s - %s", portfolio_path.name, e)

        # Show result to user
        if failed_count == 0:
            self.window.status_message(f"RegexLab: Successfully reloaded {loaded_count} portfolio(s)")
            logger.info("✓ Portfolio reload complete: %s loaded", loaded_count)
        else:
            self.window.status_message(
                f"RegexLab: Reloaded {loaded_count} portfolio(s), {failed_count} failed (see console)"
            )
            logger.warning("⚠ Portfolio reload: %s loaded, %s failed", loaded_count, failed_count)


def plugin_loaded() -> None:
    """
    Initialize plugin on load.

    AUTO-DISCOVERY MODE:
    - Scans and loads ALL .json files from RegexLab/data/portfolios/ (builtin)
    - Scans and loads ALL .json files from User/RegexLab/portfolios/ (custom active)
    - Ignores User/RegexLab/disabled_portfolios/ (user-disabled portfolios)
    - Creates disabled_portfolios/ folder if it doesn't exist

    MULTI-PORTFOLIO INTEGRITY (v2):
    - Verifies ALL builtin portfolios integrity on startup
    - Auto-restores corrupted or missing files from rxl.kst
    - First builtin portfolio (alphabetical order) becomes the "builtin principal"
    """
    from pathlib import Path

    from .src.core.integrity_manager import IntegrityManager
    from .src.core.logger import get_logger
    from .src.core.settings_manager import SettingsManager
    from .src.services.portfolio_service import PortfolioService

    logger = get_logger()
    settings = SettingsManager.get_instance()
    service = PortfolioService()
    packages_path = Path(sublime.packages_path())

    logger.info("RegexLab - Auto-Discovery Mode")
    logger.debug("Packages path: %s", packages_path)

    # ========== STEP 0: Verify builtin portfolios integrity (v2) ==========
    try:
        builtin_dir = packages_path / "RegexLab" / "data" / "portfolios"
        regexlab_dir_v2 = packages_path / "RegexLab" / "data" / ".regexlab"  # BUILTIN location!
        integrity_manager_v2 = IntegrityManager(regexlab_dir_v2)

        if integrity_manager_v2.keystore_file.exists():
            logger.info("Verifying multi-portfolio integrity...")
            all_ok, verified, restored = integrity_manager_v2.verify_and_restore(builtin_dir)

            if all_ok:
                logger.info("✓ All %s builtin portfolios verified", len(verified))
            else:
                logger.warning("⚠ Restored %s portfolios:", len(restored))
                for path, reason in restored:
                    logger.warning("  - %s: %s", path.name, reason)
    except Exception as e:
        logger.error("Multi-portfolio integrity check failed: %s", e)

    # ========== STEP 1: Ensure User/RegexLab directories exist ==========
    user_regexlab = packages_path / "User" / "RegexLab"
    portfolios_dir = user_regexlab / "portfolios"
    disabled_dir = user_regexlab / "disabled_portfolios"

    portfolios_dir.mkdir(parents=True, exist_ok=True)
    disabled_dir.mkdir(parents=True, exist_ok=True)
    logger.debug("User directories ensured: portfolios/ and disabled_portfolios/")

    # ========== STEP 2: Discover all portfolios to load ==========
    portfolios_to_load = []
    loaded_count = 0
    failed_count = 0
    error_messages = []

    # A) Built-in portfolios (RegexLab/data/portfolios/*.json)
    builtin_dir = packages_path / "RegexLab" / "data" / "portfolios"
    builtin_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists

    builtin_files = sorted(builtin_dir.glob("*.json"))
    logger.debug("Found %s builtin portfolio(s) in: %s", len(builtin_files), builtin_dir)

    # Add all builtin portfolios found (auto-discovery, no hardcoded names)
    for filepath in builtin_files:
        portfolios_to_load.append((filepath, True))  # (path, is_builtin)

    # B) Custom active portfolios (User/RegexLab/portfolios/*.json)
    custom_files = sorted(portfolios_dir.glob("*.json"))
    logger.debug("Found %s custom portfolio(s) in: %s", len(custom_files), portfolios_dir)
    for filepath in custom_files:
        portfolios_to_load.append((filepath, False))  # (path, is_builtin)

    # C) Log disabled portfolios (for user info, not loaded)
    disabled_files = list(disabled_dir.glob("*.json"))
    if disabled_files:
        logger.debug("Found %s disabled portfolio(s) in: %s", len(disabled_files), disabled_dir)
        logger.debug("  Disabled portfolios will not be loaded")

    logger.info("Total portfolios to load: %s", len(portfolios_to_load))

    # ========== STEP 3: Load all discovered portfolios ==========
    regexlab_dir = packages_path / "RegexLab" / "data" / ".regexlab"
    integrity_manager = IntegrityManager(regexlab_dir)
    builtin_integrity_checked = False

    for i, (portfolio_path, is_builtin) in enumerate(portfolios_to_load):
        logger.debug("Loading portfolio %s/%s: %s", i + 1, len(portfolios_to_load), portfolio_path.name)

        try:
            # Load portfolio
            # set_as_builtin=True only for FIRST builtin portfolio (backward compat)
            set_as_builtin_flag = is_builtin and not builtin_integrity_checked
            portfolio = service.portfolio_manager.load_portfolio(
                portfolio_path, set_as_builtin=set_as_builtin_flag, reload=False
            )

            # Mark first builtin as checked
            if is_builtin and not builtin_integrity_checked:
                builtin_integrity_checked = True

            loaded_count += 1
            builtin_marker = " (Built-in)" if is_builtin else ""
            logger.info("✓ Portfolio loaded: %s%s", portfolio.name, builtin_marker)
            logger.info("  Patterns: %s", len(portfolio.patterns))
            logger.debug("  Author: %s", portfolio.author if hasattr(portfolio, "author") else "N/A")
            logger.debug("  Version: %s", portfolio.version if hasattr(portfolio, "version") else "N/A")
            logger.debug("  Readonly: %s", portfolio.readonly)

        except FileNotFoundError:
            failed_count += 1
            error_msg = f"Portfolio file not found:\n{portfolio_path}\n\nFile may have been deleted."
            error_messages.append(error_msg)
            logger.error("✗ Portfolio not found: %s", portfolio_path)
        except ValueError as e:
            # Portfolio validation errors: JSON syntax, missing fields, etc.
            failed_count += 1
            error_str = str(e)

            # Make the error more user-friendly
            if "Invalid JSON" in error_str:
                logger.error("✗ Portfolio '%s' has JSON syntax errors:", portfolio_path.name)
                logger.error("  → %s", error_str)
                logger.error("  → Location: %s", portfolio_path)
                logger.error("  → Fix: Check for missing commas, extra commas, or unclosed brackets")
            elif "already loaded" in error_str:
                # This is expected during reload, don't spam
                logger.debug("⚠ Portfolio '%s' already loaded (skipped)", portfolio_path.name)
                failed_count -= 1  # Don't count as failure
            else:
                logger.warning("⚠ Portfolio issue: %s - %s", portfolio_path.name, e)
        except Exception as e:
            # Unexpected errors
            failed_count += 1
            logger.error("✗ Error loading portfolio: %s - %s", portfolio_path.name, e)

    # ========== STEP 4: Summary and Error Reporting ==========
    if loaded_count > 0:
        logger.info("━" * 40)
        logger.info("RegexLab initialized: %s portfolio(s) loaded", loaded_count)
        if failed_count > 0:
            logger.warning("  %s portfolio(s) failed to load", failed_count)
        if disabled_files:
            logger.info("  %s portfolio(s) disabled (in disabled_portfolios/)", len(disabled_files))
    else:
        logger.error("✗ No portfolios loaded")
        if not error_messages:
            error_messages.append(
                "No portfolios could be loaded!\n\n"
                "RegexLab requires at least one valid portfolio.\n"
                "Check that RegexLab/data/portfolios/ contains valid .json files."
            )

    # Show error dialog to user if critical errors occurred
    if error_messages:
        display_errors = error_messages[:3]
        if len(error_messages) > 3:
            display_errors.append(f"\n... and {len(error_messages) - 3} more error(s).")

        error_dialog = "RegexLab: Portfolio Loading Errors\n\n" + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n".join(
            display_errors
        )

        sublime.error_message(error_dialog)
