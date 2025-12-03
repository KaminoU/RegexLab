"""
Helper utilities for RegexLab.

Contains common utility functions used across multiple modules.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def is_builtin_portfolio_path(portfolio_path: str | Path | None) -> bool:
    """
    Check if a portfolio path points to a builtin portfolio.

    Builtin portfolios are located in RegexLab/data/portfolios/ directory
    within the Packages folder. This function handles both Unix and Windows
    path separators for cross-platform compatibility.

    Args:
        portfolio_path: Path to the portfolio file (can be str, Path, or None)

    Returns:
        True if the path points to a builtin portfolio, False otherwise

    Examples:
        >>> is_builtin_portfolio_path("Packages/RegexLab/data/portfolios/regexlab.json")
        True
        >>> is_builtin_portfolio_path("C:\\...\\Packages\\RegexLab\\data\\portfolios\\rxl.json")
        True
        >>> is_builtin_portfolio_path("Packages/User/RegexLab/portfolios/custom.json")
        False
        >>> is_builtin_portfolio_path(None)
        False
    """
    if not portfolio_path:
        return False

    path_str = str(portfolio_path)

    # Check for builtin portfolio directory patterns (both Unix and Windows separators)
    return (
        "RegexLab/data/portfolios" in path_str
        or "RegexLab\\data\\portfolios" in path_str
        or "Packages/RegexLab" in path_str
        or "Packages\\RegexLab" in path_str
        or "User/RegexLab/builtin_portfolios" in path_str
        or "User\\RegexLab\\builtin_portfolios" in path_str
    )


def normalize_portfolio_name(portfolio_name: str) -> str:
    """
    Normalize portfolio name for safe filesystem usage with Unicode support.

    Handles:
    - Unicode normalization (NFD) to decompose accented characters
    - Diacritic removal (é→e, ñ→n, ç→c, etc.)
    - Lowercase conversion
    - Space to underscore
    - Special character removal (keep only alphanumeric and underscore)
    - Consecutive underscore cleanup
    - .json extension enforcement

    Examples:
        >>> normalize_portfolio_name("Français Général")
        'francais_general.json'
        >>> normalize_portfolio_name("España-2024")
        'espana_2024.json'
        >>> normalize_portfolio_name("Tëst Pörtfolio!!!")
        'test_portfolio.json'

    Args:
        portfolio_name: Original portfolio name (may contain accents, spaces, special chars)

    Returns:
        Normalized filename safe for filesystem (ASCII, lowercase, .json extension)
    """
    # 1. Remove .json extension if present (we'll add it back at the end)
    name = portfolio_name.lower()
    if name.endswith(".json"):
        name = name[:-5]

    # 2. Unicode normalization: NFD (Canonical Decomposition)
    #    é (U+00E9) → e (U+0065) + ́ (U+0301 combining acute accent)
    #    ñ (U+00F1) → n (U+006E) + ̃ (U+0303 combining tilde)
    name = unicodedata.normalize("NFD", name)

    # 3. Remove diacritics (combining marks)
    #    Filter out category 'Mn' (Mark, Nonspacing)
    #    é → e + ́ → e (acute accent removed)
    name = "".join(char for char in name if unicodedata.category(char) != "Mn")

    # 4. Replace spaces with underscores
    name = name.replace(" ", "_")

    # 5. Remove special characters (keep only alphanumeric and underscore)
    name = re.sub(r"[^a-z0-9_]", "", name)

    # 6. Remove consecutive underscores (multiple spaces → single underscore)
    name = re.sub(r"_+", "_", name)

    # 7. Remove leading/trailing underscores
    name = name.strip("_")

    # 8. Fallback if name is empty after normalization
    if not name:
        name = "portfolio"

    # 9. Add .json extension
    return f"{name}.json"


def format_centered_separator(label: str, panel_width: int) -> str:
    """
    Format a centered separator line with dashes.

    Creates a horizontal separator with centered text for Quick Panels:
    ──────────── Label ────────────

    Args:
        label: Text to center in separator
        panel_width: Total width of separator (from settings)

    Returns:
        Formatted separator string

    Example:
        >>> format_centered_separator("Portfolio", 50)
        '──────────────────── Portfolio ────────────────────'
        >>> format_centered_separator("My Label", 30)
        '─────────── My Label ───────────'
    """
    label_with_spaces = f" {label} "
    remaining = panel_width - len(label_with_spaces)
    padding_left = remaining // 2
    padding_right = remaining - padding_left
    return f"{'─' * padding_left}{label_with_spaces}{'─' * padding_right}"


def find_portfolio_file_by_name(
    portfolios_dir: Path,
    portfolio_name: str,
    validate_func: Callable[[str], tuple[bool, dict[str, Any] | str]],
) -> Path | None:
    """
    Find portfolio file by name in directory.

    Searches all .json files in directory and validates them using provided function.
    Returns first matching portfolio file or None if not found.

    Args:
        portfolios_dir: Directory to search for portfolio files
        portfolio_name: Target portfolio name to match
        validate_func: Function to validate portfolio files (returns tuple of valid flag and result)

    Returns:
        Path to matching portfolio file or None if not found

    Example:
        >>> validate = lambda path: portfolio_service.validate_portfolio_file(path)
        >>> file = find_portfolio_file_by_name(Path("/portfolios"), "MyPortfolio", validate)
        >>> if file:
        ...     print(f"Found: {file}")
    """
    for json_file in portfolios_dir.glob("*.json"):
        valid, result = validate_func(str(json_file))
        if valid and isinstance(result, dict) and result.get("name") == portfolio_name:
            return json_file
    return None


def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    """
    Return singular or plural form based on count.

    Args:
        count: Number of items
        singular: Singular form (e.g., "pattern", "child")
        plural: Plural form (e.g., "patterns", "children"). If None, adds 's' to singular.

    Returns:
        Appropriate form based on count (without the count number)

    Example:
        >>> pluralize(1, "pattern")
        'pattern'
        >>> pluralize(5, "pattern")
        'patterns'
        >>> pluralize(1, "child", "children")
        'child'
        >>> pluralize(3, "child", "children")
        'children'
        >>> f"{count} {pluralize(count, 'item')}"
        '3 items'
    """
    if count == 1:
        return singular
    return plural if plural else f"{singular}s"


def format_aligned_summary(title: str, items: list[tuple[str, str]]) -> list[str]:
    """
    Format summary with right-aligned labels for consistent display.

    Creates a formatted summary block with dynamically aligned key-value pairs:
    Summary Title:

            Name : Value 1
     Description : Value 2
          Author : Value 3

    Args:
        title: Summary title (e.g., "Portfolio Summary", "Pattern Summary")
        items: List of (label, value) tuples to display

    Returns:
        List of formatted lines ready for display in Quick Panel

    Example:
        >>> items = [("Name", "Test"), ("Description", "A test pattern")]
        >>> lines = format_aligned_summary("Pattern Summary", items)
        >>> for line in lines:
        ...     print(line)
        Pattern Summary:
        <BLANKLINE>
                 Name : Test
          Description : A test pattern
    """
    lines = [f"{title}:", ""]

    if not items:
        return lines

    # Find longest label for alignment
    max_label_length = max(len(label) for label, _ in items)

    # Format lines with right-aligned labels
    for label, value in items:
        padded_label = label.rjust(max_label_length)
        lines.append(f"  {padded_label} : {value}")

    return lines


def shorten_path(
    path: str | Path,
    mode: str = "auto",
    packages_path: str | Path | None = None,
    settings_manager: Any | None = None,
) -> str:
    """
    Shorten file paths for cleaner display in logs and UI.

    Removes verbose path prefixes to improve readability in debug logs,
    status messages, and Quick Panels.

    Modes:
    - "relative": Remove Sublime Text prefix, show as ./Packages/...
    - "ellipsis": Show start + ... + end (e.g., C:\\Users\\...\\file.json)
    - "full": Return full path unchanged
    - "auto": Use setting from path_display_mode (default: "relative")

    Args:
        path: Path to shorten (string or Path object)
        mode: Display mode (relative/ellipsis/full/auto)
        packages_path: Sublime packages path (auto-detected if None)
        settings_manager: Optional SettingsManager instance

    Returns:
        Shortened path string

    Example:
        >>> # Relative mode (default)
        >>> shorten_path("C:\\...\\Packages\\User\\RegexLab\\portfolios\\test.json")
        './Packages/User/RegexLab/portfolios/test.json'

        >>> # Ellipsis mode
        >>> shorten_path("C:\\...\\very\\long\\path\\file.json", mode="ellipsis")
        'C:\\Users\\...\\file.json'

        >>> # Full mode
        >>> shorten_path("C:\\...\\file.json", mode="full")
        'C:\\Users\\miche\\...\\file.json'
    """
    # Convert to string if Path object
    path_str = str(path)

    settings_lookup_failed = False

    def ensure_settings_manager() -> Any | None:
        """Lazy-load SettingsManager only when required."""

        nonlocal settings_manager, settings_lookup_failed

        if settings_manager is not None or settings_lookup_failed:
            return settings_manager

        try:
            from .settings_manager import SettingsManager

            settings_manager = SettingsManager.get_instance()
        except Exception:
            settings_lookup_failed = True
            settings_manager = None

        return settings_manager

    # Auto mode: get from settings
    if mode == "auto":
        manager = ensure_settings_manager()
        mode = "relative" if manager is None else manager.get("path_display_mode", "relative")

    # Full mode: return unchanged
    if mode == "full":
        return path_str

    # Relative mode: remove Sublime Text prefix
    if mode == "relative":
        # Auto-detect packages_path if not provided
        if packages_path is None:
            try:
                import sublime  # pyright: ignore[reportMissingImports]

                packages_path = sublime.packages_path()
            except (ImportError, AttributeError):
                # Fallback: can't detect packages path
                return path_str

        # Ensure packages_path is valid before proceeding
        if packages_path is None:
            return path_str

        # Detect if we're dealing with Windows-style paths (contains backslashes or drive letters)
        # This handles cross-platform testing (e.g., Windows paths tested on Linux)
        is_windows_path = "\\" in path_str or (len(path_str) > 1 and path_str[1] == ":")
        is_windows_packages = "\\" in str(packages_path) or (
            len(str(packages_path)) > 1 and str(packages_path)[1] == ":"
        )

        # If path formats don't match, can't compute relative path
        if is_windows_path != is_windows_packages:
            return path_str

        # For Windows-style paths, use string manipulation (works cross-platform)
        if is_windows_path:
            packages_path_str = str(packages_path)

            # On Linux, Path.parent doesn't work with Windows paths
            # Use string manipulation to find parent directory
            normalized_packages = packages_path_str.replace("/", "\\")
            if "\\" in normalized_packages:
                sublime_text_dir = normalized_packages.rsplit("\\", 1)[0]
            else:
                # No backslash, can't find parent
                return path_str

            # Normalize both paths to use backslashes for comparison
            normalized_path = path_str.replace("/", "\\")

            # Case-insensitive comparison for Windows paths
            if normalized_path.lower().startswith(sublime_text_dir.lower() + "\\"):
                # Remove prefix (including trailing backslash) and normalize to forward slashes
                relative = normalized_path[len(sublime_text_dir) + 1 :]
                return f"./{relative.replace(chr(92), '/')}"  # chr(92) = backslash
            return path_str

        # For Unix-style paths, use Path.relative_to() with try/except
        path_obj = Path(path_str)
        sublime_text_dir_obj = Path(packages_path).parent

        try:
            relative_path = path_obj.relative_to(sublime_text_dir_obj)
            # Success: path is under sublime_text_dir
            # Use as_posix() to normalize to forward slashes cross-platform
            return f"./{relative_path.as_posix()}"
        except ValueError:
            # Path is not under Sublime Text directory, return as-is
            return path_str

    # Ellipsis mode: truncate middle with ...
    if mode == "ellipsis":
        manager = ensure_settings_manager()
        max_length = 60
        keep_start = 20
        keep_end = 35

        if manager is not None:
            max_length = manager.get("ellipsis_max_length", max_length)
            keep_start = manager.get("ellipsis_keep_start", keep_start)
            keep_end = manager.get("ellipsis_keep_end", keep_end)

        # Only truncate if path exceeds max_length
        if len(path_str) <= int(max_length):
            return path_str

        # Truncate: keep_start + "..." + keep_end
        start = path_str[: int(keep_start)]
        end = path_str[-int(keep_end) :]
        return f"{start}...{end}"

    # Unknown mode: return as-is
    return path_str


def _create_counted_repeater(
    window: Any,
    message: str,
    repeat_interval: int,
    sublime: Any,
) -> Any:
    """
    Factory function to create a counted message repeater.

    Returns a closure that repeats status message for a fixed number of times.

    Args:
        window: Sublime Text window instance
        message: Status message to display
        repeat_interval: Milliseconds between repeats
        sublime: Sublime module reference

    Returns:
        Repeater function (takes count: int)
    """

    def repeat_message(count: int) -> None:
        """Repeat status message for fixed count."""
        if count > 0:
            # Defensive: Check if window is still valid before accessing
            try:
                if not hasattr(window, "status_message"):
                    # Window deleted/closed, stop timer chain gracefully
                    return
                window.status_message(message)
            except (AttributeError, RuntimeError):
                # Window no longer accessible, stop timer chain
                return

            sublime.set_timeout(lambda: repeat_message(count - 1), repeat_interval)

    return repeat_message


def show_persistent_status(
    window: Any,
    message: str,
    duration_ms: int | None = None,
    settings_manager: Any | None = None,
) -> None:
    """
    Show status message persistently by repeating it at intervals.

    Sublime Text status messages disappear automatically after ~2-3 seconds.
    This function keeps the message visible by repeating it at regular intervals
    for a fixed duration.

    Args:
        window: Sublime Text window instance
        message: Status message to display
        duration_ms: Total duration in milliseconds (default: from settings or 13000ms)
        settings_manager: Optional SettingsManager instance (default: get singleton)

    Example:
        >>> show_persistent_status(window, "RegexLab: Processing...", 10000)
        # Message repeats every 2s for 10 seconds total
    """
    try:
        import sublime  # pyright: ignore[reportMissingImports]
    except ModuleNotFoundError:
        # Fallback for testing without sublime module
        window.status_message(message)
        return

    # Import constants here to avoid circular imports
    from .constants import DEFAULT_STATUS_MESSAGE_DURATION, DEFAULT_STATUS_REPEAT_INTERVAL

    # Get duration from settings if not specified
    if duration_ms is None:
        if settings_manager is None:
            from .settings_manager import SettingsManager

            settings_manager = SettingsManager.get_instance()
        duration_ms = settings_manager.get("status_message_duration", DEFAULT_STATUS_MESSAGE_DURATION)

    # Ensure duration_ms is valid (fallback if get() returned None)
    if duration_ms is None:
        duration_ms = DEFAULT_STATUS_MESSAGE_DURATION

    # Show initial message
    window.status_message(message)

    # Repeat interval
    repeat_interval = DEFAULT_STATUS_REPEAT_INTERVAL

    # Calculate number of repeats
    repeats = max(1, int(duration_ms) // repeat_interval)
    repeater = _create_counted_repeater(window, message, repeat_interval, sublime)

    # Start repeating (skip first one since already shown)
    sublime.set_timeout(lambda: repeater(repeats - 1), repeat_interval)


def format_quick_panel_line(
    left_text: str,
    right_text: str,
    panel_width: int,
    left_icon: str | None = None,
    right_icon: str | None = None,
) -> str:
    """Format a Quick Panel item line with right-aligned suffix.  # noqa: RUF002

    Unifies formatting logic across all command files.
    Eliminates 75% code duplication (89 → 47 lines total).

    This helper provides consistent alignment for Quick Panel items where:
    - Left part: Main text (pattern name, portfolio name, action label)
    - Right part: Suffix (type, status, metadata)
    - Padding: Dynamic spacing to align right parts consistently

    Args:
        left_text: Main text displayed on the left (e.g., "Find Emails")
        right_text: Suffix text displayed on the right (e.g., "Static 📄")
        panel_width: Total width for the panel (from settings, typically 80-120)
        left_icon: Optional icon prefix for left text (e.g., "+" for actions)  # noqa: RUF002
        right_icon: Optional icon prefix for right text (e.g., "[Portfolio]")

    Returns:
        Formatted line with dynamic padding between left and right parts.

    Examples:
        >>> # Simple pattern line
        >>> format_quick_panel_line("MyPattern", "Static 📄", 80)
        'MyPattern                                        Static 📄'

        >>> # Pattern with portfolio tag
        >>> format_quick_panel_line("EmailFinder", "[MyPortfolio] 🧪 Dynamic", 80)
        'EmailFinder                       [MyPortfolio] 🧪 Dynamic'

        >>> # Action with icon  # noqa: RUF002
        >>> format_quick_panel_line("New Portfolio", "Create empty portfolio", 80, left_icon="+")
        '+ New Portfolio                         Create empty portfolio'  # noqa: RUF002

        >>> # Full example with both icons
        >>> format_quick_panel_line("Pattern", "Status", 80, left_icon="📄", right_icon="[Tag]")
        '📄 Pattern                                   [Tag] Status'

    Note:
        Minimum padding is 2 spaces to ensure readability even with long text.
        If combined text exceeds panel_width, padding is still applied for consistency.
    """
    # Build left part with optional icon
    left_part = f"{left_icon} {left_text}" if left_icon else left_text

    # Build right part with optional icon
    right_part = f"{right_icon} {right_text}" if right_icon else right_text

    # Calculate dynamic padding
    padding_length = panel_width - len(left_part) - len(right_part)

    # Ensure minimum padding for readability
    if padding_length < 2:
        padding_length = 2

    # Format final line with dynamic spacing
    return f"{left_part}{' ' * padding_length}{right_part}"


def truncate_for_log(value: str, max_len: int = 30) -> str:
    """
    Truncate a string for logging with ellipsis if too long.

    This helper centralizes the common pattern of truncating long strings
    in log messages to avoid cluttering the log output.

    Args:
        value: The string to potentially truncate
        max_len: Maximum length before truncation (default: 30)

    Returns:
        The original string if <= max_len, otherwise truncated with "..." suffix

    Examples:
        >>> truncate_for_log("short")
        'short'
        >>> truncate_for_log("this is a very long string that needs truncation")
        'this is a very long string th...'
        >>> truncate_for_log("exactly 30 characters here!!", 30)
        'exactly 30 characters here!!'
        >>> truncate_for_log("exactly 31 characters here!!!", 30)
        'exactly 31 characters here!!...'
    """
    return value[:max_len] + "..." if len(value) > max_len else value


def get_current_timestamp() -> str:
    """
    Get current timestamp in ISO format (UTC timezone).

    This helper centralizes timestamp generation to ensure consistency
    across the codebase and proper timezone handling.

    Returns:
        Current timestamp in ISO 8601 format with UTC timezone

    Examples:
        >>> timestamp = get_current_timestamp()
        >>> timestamp  # doctest: +SKIP
        '2025-10-23T14:30:00.123456+00:00'

    Note:
        Always uses UTC timezone for consistency across systems.
        Format is compatible with JSON serialization and sorting.
    """
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries (override takes precedence, recursively).

    This function solves the critical issue where Sublime Text's load_settings()
    does SHALLOW merge, causing user settings to completely override nested dicts
    instead of merging keys.

    Without deep merge:
        base = {"variables_assertion": {"DATE": {...}, "TIME": {...}}}
        override = {"variables_assertion": {"MY_VAR": {...}}}
        result = {"variables_assertion": {"MY_VAR": {...}}}  # DATE/TIME LOST! ❌

    With deep merge:
        result = {"variables_assertion": {"DATE": {...}, "TIME": {...}, "MY_VAR": {...}}}  # ✅

    Behavior:
    - Scalars (str, int, bool, None): override wins
    - Lists: override completely replaces base (no list merging)
    - Dicts: recursive merge (base keys + override keys, override wins on conflicts)

    Args:
        base: Base dictionary (typically builtin settings)
        override: Override dictionary (typically user settings)

    Returns:
        Deep-merged dictionary (new dict, inputs not modified)

    Examples:
        >>> base = {"a": 1, "b": {"x": 10, "y": 20}, "c": [1, 2]}
        >>> override = {"b": {"y": 99, "z": 30}, "d": 4}
        >>> result = deep_merge_dicts(base, override)
        >>> result
        {'a': 1, 'b': {'x': 10, 'y': 99, 'z': 30}, 'c': [1, 2], 'd': 4}

        >>> # Nested dicts merge recursively
        >>> base = {"vars": {"DATE": {"regex": "..."}, "TIME": {"regex": "..."}}}
        >>> override = {"vars": {"MY_VAR": {"regex": "..."}}}
        >>> result = deep_merge_dicts(base, override)
        >>> sorted(result["vars"].keys())
        ['DATE', 'MY_VAR', 'TIME']

        >>> # Scalars: override wins
        >>> deep_merge_dicts({"a": 1}, {"a": 2})
        {'a': 2}

        >>> # Lists: override replaces (no merging)
        >>> deep_merge_dicts({"list": [1, 2]}, {"list": [3, 4]})
        {'list': [3, 4]}
    """
    # Create new dict to avoid modifying inputs
    result = base.copy()

    for key, override_value in override.items():
        if key in result:
            base_value = result[key]

            # If both are dicts: recursive merge
            if isinstance(base_value, dict) and isinstance(override_value, dict):
                result[key] = deep_merge_dicts(base_value, override_value)
            else:
                # Scalar or list: override wins (no list merging)
                result[key] = override_value
        else:
            # New key from override
            result[key] = override_value

    return result
