"""
Panel Injection Utilities for Sublime Text.

This module provides utilities to inject regex patterns into Sublime Text
panels (Find, Replace, Find in Files) without escaping issues.

The key trick: Open panel with regex mode OFF, slurp the pattern, then toggle regex ON.
This prevents Sublime from escaping special regex characters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.constants import (
    MSG_PATTERN_CLIPBOARD_NO_VIEW,
    MSG_PATTERN_LOADED_FIND,
    MSG_PATTERN_LOADED_FIND_IN_FILES,
    MSG_PATTERN_LOADED_REPLACE,
)
from ..core.logger import get_logger

if TYPE_CHECKING:
    import sublime  # pyright: ignore[reportMissingImports]

logger = get_logger()


def inject_into_find_panel(
    window: sublime.Window,
    resolved_pattern: str,
    pattern_name: str,
) -> None:
    """
    Inject resolved pattern into Find panel.

    Args:
        window: Sublime Text window instance
        resolved_pattern: The resolved regex pattern
        pattern_name: Name of the pattern (for status message)

    Note:
        Trick: Use slurp_find_string with regex mode OFF to avoid escaping,
        then turn regex mode back ON. This is the ONLY way that works.
    """
    _inject_into_panel(
        window=window,
        resolved_pattern=resolved_pattern,
        pattern_name=pattern_name,
        panel_type="find",
        panel_command="find",
        success_message=MSG_PATTERN_LOADED_FIND.format(name=pattern_name),
    )


def inject_into_replace_panel(
    window: sublime.Window,
    resolved_pattern: str,
    pattern_name: str,
) -> None:
    """
    Inject resolved pattern into Replace panel.

    Uses same technique as Find panel: slurp with regex OFF, then toggle ON.

    Args:
        window: Sublime Text window instance
        resolved_pattern: The resolved regex pattern
        pattern_name: Name of the pattern (for status message)
    """
    _inject_into_panel(
        window=window,
        resolved_pattern=resolved_pattern,
        pattern_name=pattern_name,
        panel_type="Replace",
        panel_command="replace",
        success_message=MSG_PATTERN_LOADED_REPLACE.format(name=pattern_name),
    )


def inject_into_find_in_files_panel(
    window: sublime.Window,
    resolved_pattern: str,
    pattern_name: str,
) -> None:
    """
    Inject resolved pattern into Find in Files panel.

    Uses same technique as Find panel: slurp with regex OFF, then toggle ON.

    Args:
        window: Sublime Text window instance
        resolved_pattern: The resolved regex pattern
        pattern_name: Name of the pattern (for status message)
    """
    _inject_into_panel(
        window=window,
        resolved_pattern=resolved_pattern,
        pattern_name=pattern_name,
        panel_type="Find in Files",
        panel_command="find_in_files",
        success_message=MSG_PATTERN_LOADED_FIND_IN_FILES.format(name=pattern_name),
    )


def _inject_into_panel(
    window: sublime.Window,
    resolved_pattern: str,
    pattern_name: str,
    panel_type: str,
    panel_command: str,
    success_message: str,
) -> None:
    """
    Core implementation for pattern injection into any panel.

    This function implements the critical trick: open panel with regex OFF,
    slurp pattern, then toggle regex ON. This prevents Sublime from escaping.

    Args:
        window: Sublime Text window instance
        resolved_pattern: The resolved regex pattern
        pattern_name: Name of the pattern (for logging)
        panel_type: Panel type name for logging ("Find", "Replace", "Find in Files")
        panel_command: Sublime command name ("find", "replace", "find_in_files")
        success_message: Message to display on success
    """
    try:
        import sublime  # pyright: ignore[reportMissingImports]
    except ModuleNotFoundError:
        # Allow testing without sublime module
        sublime = None  # TYPE_CHECKING already handles type safety

    logger.debug("Injecting pattern '%s' into %s panel: %s", pattern_name, panel_type, resolved_pattern)

    view = window.active_view()
    if not view:
        logger.error("No active view available for pattern injection")
        if sublime:
            sublime.set_clipboard(resolved_pattern)
        window.status_message(MSG_PATTERN_CLIPBOARD_NO_VIEW)
        return

    # Save original state
    original_selection = list(view.sel())
    original_read_only = view.is_read_only()

    # Make sure view is writable
    if original_read_only:
        view.set_read_only(False)

    try:
        # STEP 1: Open panel with regex mode OFF (critical!)
        window.run_command("show_panel", {"panel": panel_command, "regex": False})
        logger.debug("%s panel opened with regex OFF", panel_type)

        # STEP 2: Insert pattern in document and select it
        view.sel().clear()
        if sublime:
            view.sel().add(sublime.Region(0, 0))
        view.run_command("insert", {"characters": resolved_pattern})

        view.sel().clear()
        if sublime:
            view.sel().add(sublime.Region(0, len(resolved_pattern)))

        logger.debug("Pattern inserted and selected in document")

        # STEP 3: Slurp into panel (won't escape because regex is OFF)
        window.run_command("slurp_find_string")
        logger.debug("Pattern slurped into %s panel (unescaped)", panel_type)

        # STEP 4: Undo the insertion to restore document
        view.run_command("undo")
        logger.debug("Document restored to original state")

    finally:
        # Restore original selection
        view.sel().clear()
        for region in original_selection:
            view.sel().add(region)

        # Restore read-only state
        if original_read_only:
            view.set_read_only(True)

    # STEP 5: Turn regex mode ON (now that pattern is already in panel)
    window.run_command("toggle_regex")
    logger.debug("Regex mode toggled ON")

    window.status_message(success_message)
