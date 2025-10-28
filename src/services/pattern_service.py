"""
Pattern Service - Business logic for pattern operations.

This service orchestrates Pattern and PatternEngine to provide
high-level operations for the UI layer.
"""

from __future__ import annotations

import re

from ..core.constants import LOG_TRUNCATE_LONG
from ..core.helpers import truncate_for_log
from ..core.logger import get_logger
from ..core.models import Pattern, PatternType
from ..core.pattern_engine import PatternEngine
from ..core.settings_manager import SettingsManager

logger = get_logger()


class PatternService:
    """
    Service for pattern operations and transformations.

    This service provides business logic operations for:
    - Resolving dynamic patterns with variables
    - Creating patterns from text selections
    - Validating regex patterns
    - Formatting patterns for use in Sublime Text Find panel
    """

    def __init__(
        self,
        pattern_engine: PatternEngine | None = None,
        settings_manager: SettingsManager | None = None,
    ) -> None:
        """
        Initialize the pattern service.

        Args:
            pattern_engine: Optional pattern engine instance.
                            If None, creates a new instance using SettingsManager.
            settings_manager: Optional settings manager (defaults to singleton).
                            Used to configure PatternEngine if pattern_engine is None.
        """
        self.settings = settings_manager or SettingsManager.get_instance()

        # PatternEngine will use SettingsManager internally
        self.pattern_engine = pattern_engine or PatternEngine(settings_manager=self.settings)

    def resolve_pattern(self, pattern: Pattern, custom_variables: dict[str, str] | None = None) -> str:
        """
        Resolve a pattern to a ready-to-use regex string.

        For static patterns, returns the regex as-is.
        For dynamic patterns, resolves all variables and returns the final regex.

        Args:
            pattern: The pattern to resolve.
            custom_variables: Optional custom variables to override built-in ones.

        Returns:
            The resolved regex string, ready for use in regex operations.

        Raises:
            ValueError: If pattern contains unknown variables.
        """
        logger.debug("Resolving pattern '%s' (type: %s)", pattern.name, pattern.type)
        if pattern.type == PatternType.STATIC:
            logger.debug("Static pattern, returning regex as-is")
            return pattern.regex

        # For dynamic patterns, resolve using the pattern engine
        logger.debug("Dynamic pattern with variables: %s", pattern.variables)
        if custom_variables:
            logger.debug("Custom variables provided: %s", list(custom_variables.keys()))
        resolved = self.pattern_engine.resolve_pattern(pattern, custom_variables)
        logger.debug("Pattern resolved successfully: %s", truncate_for_log(resolved, LOG_TRUNCATE_LONG))
        return resolved

    def get_pattern_variables(self, pattern: Pattern) -> list[str]:
        """
        Get the list of variables used in a pattern.

        Args:
            pattern: The pattern to analyze.

        Returns:
            List of variable names found in the pattern.
        """
        return pattern.variables

    def resolve_variables(self, pattern: Pattern, custom_variables: dict[str, str] | None = None) -> dict[str, str]:
        """
        Resolve all variables for a pattern to their actual values.

        Args:
            pattern: The pattern containing variables to resolve.
            custom_variables: Optional custom variables to override built-in ones.

        Returns:
            Dictionary mapping variable names to their resolved values.

        Raises:
            ValueError: If pattern contains unknown variables.
        """
        logger.debug("Resolving variables for pattern '%s'", pattern.name)
        if custom_variables:
            # Temporarily update pattern engine with custom variables
            logger.debug("Temporarily overriding with custom variables: %s", list(custom_variables.keys()))
            original_vars = self.pattern_engine.custom_variables.copy()
            self.pattern_engine.custom_variables.update(custom_variables)

        try:
            resolved = self.pattern_engine.resolve_variables(pattern)
            # Truncate long values for logging
            truncated = {k: v[:20] + "..." if len(v) > 20 else v for k, v in resolved.items()}
            logger.debug("Variables resolved: %s", truncated)
            return resolved
        finally:
            if custom_variables:
                # Restore original custom variables
                logger.debug("Restoring original custom variables")
                self.pattern_engine.custom_variables = original_vars

    def validate_regex(self, regex: str) -> bool:
        """
        Validate that a regex string is syntactically correct.

        Args:
            regex: The regex string to validate.

        Returns:
            True if the regex is valid, False otherwise.
        """
        try:
            re.compile(regex)
            logger.debug("Regex validation successful")
            return True
        except re.error as e:
            logger.debug("Regex validation failed: %s", e)
            return False

    def create_pattern_from_text(
        self,
        text: str,
        name: str,
        exact_match: bool = False,
        word_boundary: bool = False,
        case_insensitive: bool = False,
        description: str = "",
    ) -> Pattern:
        """
        Create a static pattern from a text selection.

        Args:
            text: The text to create a pattern from.
            name: Name for the new pattern.
            exact_match: If True, creates pattern for exact text match.
            word_boundary: If True, adds word boundaries (\\b).
            case_insensitive: If True, uses case-insensitive flag.
            description: Optional description for the pattern.

        Returns:
            A new Pattern instance.

        Raises:
            ValueError: If text is empty.
        """
        logger.debug("Creating pattern '%s' from text (%d chars)", name, len(text))
        if not text:
            logger.debug("Empty text provided, raising ValueError")
            raise ValueError("Cannot create pattern from empty text")

        # Escape special regex characters
        escaped = re.escape(text)

        # Add word boundaries if requested
        if word_boundary:
            logger.debug("Adding word boundaries")
            escaped = rf"\b{escaped}\b"

        # For case insensitive, we could add (?i) flag or handle it in the command
        # For now, we'll just create the pattern and let the command handle flags
        regex = escaped

        logger.debug("Pattern created successfully: %s", truncate_for_log(regex, LOG_TRUNCATE_LONG))
        return Pattern(
            name=name,
            regex=regex,
            type=PatternType.STATIC,
            description=description or f"Pattern created from selection: {truncate_for_log(text, LOG_TRUNCATE_LONG)}",
        )

    def is_dynamic_pattern(self, pattern: Pattern) -> bool:
        """
        Check if a pattern is dynamic (contains variables).

        Args:
            pattern: The pattern to check.

        Returns:
            True if the pattern is dynamic, False otherwise.
        """
        return pattern.type == PatternType.DYNAMIC

    def format_for_find_panel(self, pattern: Pattern, custom_variables: dict[str, str] | None = None) -> str:
        """
        Format a pattern for use in Sublime Text Find panel.

        Resolves dynamic patterns and returns a ready-to-use regex string.

        Args:
            pattern: The pattern to format.
            custom_variables: Optional custom variables for dynamic patterns.

        Returns:
            Regex string ready for the Find panel.

        Raises:
            ValueError: If pattern is dynamic and contains unknown variables.
        """
        return self.resolve_pattern(pattern, custom_variables)

    def add_custom_variable(self, name: str, value: str) -> None:
        """
        Add or update a custom variable in the pattern engine.

        Args:
            name: Variable name (without braces).
            value: Variable value.
        """
        logger.debug("Adding custom variable: %s = %s", name, truncate_for_log(value))
        self.pattern_engine.add_custom_variable(name, value)

    def remove_custom_variable(self, name: str) -> bool:
        """
        Remove a custom variable from the pattern engine.

        Args:
            name: Variable name to remove.

        Returns:
            True if the variable was removed, False if it didn't exist.
        """
        logger.debug("Removing custom variable: %s", name)
        removed = self.pattern_engine.remove_custom_variable(name)
        logger.debug("Variable %s: %s", name, "removed" if removed else "not found")
        return removed

    def get_custom_variables(self) -> dict[str, str]:
        """
        Get all custom variables currently defined.

        Returns:
            Dictionary of custom variable names to values.
        """
        return self.pattern_engine.custom_variables.copy()
