"""
Helper methods for Portfolio Manager Command - Pattern injection into panels.

These methods are adapted from LoadPatternCommand to allow the Portfolio Manager
to directly inject patterns into Find/Replace/Find in Files panels.

Includes variable validation support via 'variables_assertion' settings.
Supports "NOW" keyword for automatic date/time substitution.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from ..core.constants import (
    DEFAULT_DATE_FORMAT,
    DEFAULT_DATETIME_FORMAT,
    DEFAULT_POPUP_DISPLAY_DURATION,
    DEFAULT_SHOW_INPUT_HELP_POPUP,
    DEFAULT_TIME_FORMAT,
)
from ..core.logger import get_logger
from ..core.settings_manager import SettingsManager
from ..utils.panel_injection import (
    inject_into_find_in_files_panel,
    inject_into_find_panel,
    inject_into_replace_panel,
)

if TYPE_CHECKING:
    import sublime  # pyright: ignore[reportMissingImports]

    from ..core.models import Pattern


def inject_pattern_in_panel(
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


def _get_variable_config(variable_name: str, settings: SettingsManager) -> dict[str, str]:
    """
    Get variable configuration from settings with backward compatibility.

    Supports both old and new formats:
    - Old: "DATE": "regex_pattern"
    - New: "DATE": {"regex": "...", "default": "...", "hint": "...", "example": "..."}

    Also merges legacy 'variables_assertion_defaults' if present.

    Args:
        variable_name: Name of the variable (uppercase)
        settings: SettingsManager instance

    Returns:
        Dict with keys: regex, default, hint, example (all optional, empty strings if not set)
    """
    logger = get_logger()
    assertions = settings.get("variables_assertion", {})
    var_upper = variable_name.upper()

    # Initialize empty config
    config = {
        "regex": "",
        "default": "",
        "hint": "",
        "example": "",
    }

    # Get assertion config
    assertion_value = assertions.get(var_upper)

    if assertion_value is None:
        # No assertion for this variable
        logger.debug("Variable '%s': No assertion config found", var_upper)
    elif isinstance(assertion_value, str):
        # OLD FORMAT: "DATE": "regex_pattern"
        config["regex"] = assertion_value
        logger.debug("Variable '%s': Using old format (string regex)", var_upper)
    elif isinstance(assertion_value, dict):
        # NEW FORMAT: "DATE": {"regex": "...", "default": "...", ...}
        config["regex"] = assertion_value.get("regex", "")
        config["default"] = assertion_value.get("default", "")
        config["hint"] = assertion_value.get("hint", "")
        config["example"] = assertion_value.get("example", "")
        logger.debug("Variable '%s': Using new format (dict config)", var_upper)
    else:
        logger.warning("Variable '%s': Invalid assertion format (not string or dict)", var_upper)

    # BACKWARD COMPATIBILITY: Merge with legacy 'variables_assertion_defaults'
    if not config["default"]:
        defaults = settings.get("variables_assertion_defaults", {})
        legacy_default = defaults.get(var_upper, "")
        if legacy_default:
            config["default"] = legacy_default
            logger.debug("Variable '%s': Merged legacy default from variables_assertion_defaults", var_upper)

    return config


def _resolve_now_keyword(variable_name: str, settings: Any) -> str:
    """
    Resolve the 'NOW' keyword to current date/time based on variable name.

    Args:
        variable_name: Name of the variable (uppercase)
        settings: SettingsManager instance to get date/time format settings

    Returns:
        Current date, time, or datetime string according to variable name
    """
    now = datetime.now()

    # Check variable name to determine format
    if "DATE" in variable_name and "TIME" in variable_name:
        # DATETIME, TIMESTAMP, etc. → Full datetime
        format_str = settings.get("variables.datetime_format", DEFAULT_DATETIME_FORMAT)
        return now.strftime(format_str)
    elif "DATE" in variable_name:
        # DATE, DATELOG, etc. → Date only
        format_str = settings.get("variables.date_format", DEFAULT_DATE_FORMAT)
        return now.strftime(format_str)
    elif "TIME" in variable_name:
        # TIME, TIMESTAMP, etc. → Time only
        format_str = settings.get("variables.time_format", DEFAULT_TIME_FORMAT)
        return now.strftime(format_str)
    else:
        # Unknown variable with NOW → default to datetime
        return now.strftime("%Y-%m-%d %H:%M:%S")


def _show_variable_popup(
    window: sublime.Window,
    var_name: str,
    default_value: str,
    pattern_hint: str,
    settings: SettingsManager,
) -> None:
    """
    Show optional HTML popup with variable guidance.

    Displays a helpful popup near the cursor with:
    - Variable name (title)
    - Format/pattern hint (if available)
    - Example value (if available)

    The popup is controlled by the 'show_input_help_popup' setting and will
    auto-hide when the user moves the mouse away.

    Args:
        window: Sublime Text window instance
        var_name: Name of the variable being collected
        default_value: Default/example value (may be empty)
        pattern_hint: Human-readable pattern description (may be empty)
        settings: Settings manager instance
    """
    # Check if popup is enabled in settings
    if not settings.get("show_input_help_popup", DEFAULT_SHOW_INPUT_HELP_POPUP):
        return

    try:
        import sublime  # pyright: ignore[reportMissingImports]
    except (ImportError, ModuleNotFoundError):
        # No popup support without sublime module (tests)
        return

    view = window.active_view()
    if not view:
        return

    # Build HTML popup content with VS Code-style variables
    emoji = "✏️"  # Pencil for input
    popup_html = f"""
    <body style="margin: 0; padding: 10px; font-family: system-ui;">
        <div style="background: var(--background); color: var(--foreground);">
            <h3 style="margin: 0 0 8px 0; color: var(--bluish);">
                {emoji} {var_name.title()}
            </h3>
    """

    # Add pattern hint if available
    if pattern_hint:
        popup_html += f"""
            <p style="margin: 4px 0;">
                <b>Valid values:</b> <span style="color: var(--greenish);">{pattern_hint}</span>
            </p>
        """

    # Add example if available
    if default_value:
        code_style = "background: var(--background); padding: 2px 4px; border-radius: 3px;"
        popup_html += f"""
            <p style="margin: 4px 0;">
                <b>Example:</b> <code style="{code_style}">{default_value}</code>
            </p>
        """

    # No pattern or example - show generic help
    if not pattern_hint and not default_value:
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
    # Keep it visible longer (don't auto-hide on mouse move)
    # User can click outside or press ESC to close it
    view.show_popup(
        popup_html,
        flags=sublime.COOPERATE_WITH_AUTO_COMPLETE,  # Don't auto-hide on mouse move
        location=-1,  # at cursor
        max_width=500,
    )


def collect_variables_for_pattern(
    window: sublime.Window,
    pattern: Pattern,
    variables: list[str],
    collected_values: dict[str, str],
    target_panel: str,
    pattern_service: Any,
    on_completion: Callable[[dict[str, str]], None] | None = None,
) -> None:
    """
    Recursively collect variable values from user via input panels.

    Validates input against 'variables_assertion' settings if defined.
    If validation fails, shows error and prompts again (retry).

    Pre-fills input with values from 'variables_assertion_defaults':
    - If default is "NOW" for DATE/TIME/DATETIME variables → auto-fills with current date/time
    - Otherwise uses the default value as-is
    - Displays default as example in prompt: "Enter value for {{VAR}} (e.g., 2025-10-20):"
    - User can press Enter to accept default, or modify it

    Args:
        window: Sublime Text window instance
        pattern: Pattern being resolved
        variables: List of variable names to collect
        collected_values: Dictionary of already collected values
        target_panel: Panel type to inject into after resolution
        pattern_service: PatternService instance for pattern formatting
        on_completion: Optional callback called when all variables collected,
                    receives collected_values dict. If None, uses inject_pattern_in_panel.
    """
    logger = get_logger()
    if not variables:
        # All variables collected → resolve and format/inject
        if on_completion:
            # Custom completion handler (e.g., from LoadPatternCommand)
            on_completion(collected_values)
        else:
            # Default behavior: resolve and inject using helper function
            try:
                # Use pattern_service to format the pattern with resolved variables
                resolved_pattern = pattern_service.format_for_find_panel(pattern, collected_values)
                logger.debug("Pattern '%s' resolved with variables: %s", pattern.name, collected_values)

                # Inject into target panel
                inject_pattern_in_panel(window, target_panel, resolved_pattern, pattern.name)

            except (ValueError, KeyError) as e:
                # ValueError: Pattern resolution/variable substitution failed
                # KeyError: Missing required variable in pattern
                logger.error("Error resolving pattern '%s' - %s: %s", pattern.name, type(e).__name__, e)
                window.status_message(f"Regex Lab: Error resolving pattern - {e}")

        return

    # Collect next variable
    current_var = variables[0]
    remaining_vars = variables[1:]

    # Get variable configuration from settings (NEW FORMAT with backward compatibility)
    settings = SettingsManager.get_instance()
    var_config = _get_variable_config(current_var, settings)

    # Extract config values
    assertion_pattern = var_config["regex"]
    default_value = var_config["default"]
    hint = var_config["hint"]
    example = var_config["example"]

    logger.debug(
        "Variable '%s': regex='%s', default='%s', hint='%s', example='%s'",
        current_var.upper(),
        assertion_pattern,
        default_value,
        hint,
        example,
    )

    # Resolve "NOW" in default value
    if isinstance(default_value, str) and default_value.upper() == "NOW":
        default_value = _resolve_now_keyword(current_var.upper(), settings)
        logger.debug("Variable '%s': Default 'NOW' resolved to '%s'", current_var, default_value)

    # Build user-friendly prompt
    # Priority: use 'example' if provided, otherwise use 'default' for display
    display_example = example if example else default_value

    # Build prompt based on available fields
    prompt_parts = [f"Enter value for {{{{{current_var}}}}}"]

    if hint and display_example:
        # Both hint and example: "Enter value for {{VAR}} (hint: ..., e.g. ...)"
        prompt_parts.append(f"(hint: {hint}, e.g. {display_example})")
    elif hint:
        # Only hint: "Enter value for {{VAR}} (hint: ...)"
        prompt_parts.append(f"(hint: {hint})")
    elif display_example:
        # Only example: "Enter value for {{VAR}} (e.g. ...)"
        prompt_parts.append(f"(e.g. {display_example})")
    else:
        # No hint or example: free input
        prompt_parts.append("(free input)")

    prompt = " ".join(prompt_parts) + ":"

    def on_done(value: str) -> None:
        # Empty value check - always require at least one character
        # User must either provide a value or press ESC to cancel explicitly
        if not value:
            # Show error and retry for same variable (don't cancel)
            window.status_message("Regex Lab: Value cannot be empty. Please enter a value or press ESC to cancel.")
            logger.debug("Variable '%s': Empty value rejected, prompting again", current_var)

            # Build retry prompt (same as initial prompt)
            retry_prompt = prompt

            # Re-show input panel for same variable
            # Need to call show_input again with delay if popup enabled
            def show_retry_input() -> None:
                window.show_input_panel(
                    retry_prompt,
                    "",  # Empty, user must type something
                    on_done,
                    None,
                    on_cancel,
                )

            # Check if popup is enabled to add delay for retry
            if settings.get("show_input_help_popup", DEFAULT_SHOW_INPUT_HELP_POPUP):
                try:
                    import sublime  # pyright: ignore[reportMissingImports]

                    # Re-show popup for retry
                    _show_variable_popup(window, current_var, display_example, hint, settings)
                    # Get popup display duration from settings (default: 20 seconds)
                    popup_duration = settings.get("popup_display_duration", DEFAULT_POPUP_DISPLAY_DURATION)
                    sublime.set_timeout(show_retry_input, popup_duration)
                except (ImportError, ModuleNotFoundError):
                    show_retry_input()
            else:
                show_retry_input()

            return

        logger.debug(
            "Variable '%s': User input='%s', assertion_pattern='%s', will_validate=%s",
            current_var,
            value,
            assertion_pattern,
            bool(assertion_pattern),
        )

        # Validate input if assertion exists
        if assertion_pattern:
            try:
                if not re.fullmatch(assertion_pattern, value):
                    # Validation failed → show error and retry
                    # Use hint if available, otherwise show regex pattern
                    expected_format = hint if hint else f"regex: {assertion_pattern}"
                    error_msg = (
                        f"Invalid format for {{{{{current_var}}}}}\nExpected: {expected_format}\nYour input: {value}"
                    )
                    window.status_message(f"Regex Lab: {error_msg}")
                    logger.debug(
                        "Variable '%s' validation failed: '%s' doesn't match '%s'",
                        current_var,
                        value,
                        assertion_pattern,
                    )

                    # Retry: show input panel again (reuse initial prompt)
                    retry_prompt = prompt

                    window.show_input_panel(
                        retry_prompt,
                        value,  # Pre-fill with previous attempt
                        on_done,
                        None,
                        on_cancel,
                    )
                    return
            except re.error as e:
                # Invalid regex in assertions → log warning and accept input
                logger.warning(
                    "Invalid regex in variables_assertion for '%s': %s - Accepting input without validation",
                    current_var,
                    e,
                )

        # Valid input or no assertion → continue
        logger.debug("Variable '%s' accepted: '%s'", current_var, value)
        collected_values[current_var] = value

        # Continue collecting remaining variables
        collect_variables_for_pattern(
            window, pattern, remaining_vars, collected_values, target_panel, pattern_service, on_completion
        )

    def on_cancel() -> None:
        window.status_message("Regex Lab: Variable input cancelled")

    # Show optional popup guidance if enabled
    _show_variable_popup(window, current_var, display_example, hint, settings)

    # Delay input panel so popup is visible for configured duration
    # User can press ESC or click outside to close popup earlier
    def show_input() -> None:
        window.show_input_panel(
            prompt,
            default_value,  # Pre-fill with default (empty string if no default)
            on_done,
            None,  # on_change callback (not needed)
            on_cancel,
        )

    # Check if popup is enabled to add delay
    if settings.get("show_input_help_popup", DEFAULT_SHOW_INPUT_HELP_POPUP):
        try:
            import sublime  # pyright: ignore[reportMissingImports]

            # Get popup display duration from settings (default: 20 seconds)
            popup_duration = settings.get("popup_display_duration", DEFAULT_POPUP_DISPLAY_DURATION)
            sublime.set_timeout(show_input, popup_duration)
        except (ImportError, ModuleNotFoundError):
            # No delay in tests
            show_input()
    else:
        # No popup, show immediately
        show_input()
