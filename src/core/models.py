"""
Core data models for Regex Lab.

This module defines the core data structures used throughout the application:
- Pattern: Represents a regex pattern with metadata
- Portfolio: A collection of patterns
- PatternType: Enumeration of pattern types (static vs dynamic)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import Any

# ============================================================================
# Performance Optimization: Pre-compiled regex patterns
# ============================================================================
# These patterns are compiled once at module load time instead of being
# recompiled on every Pattern.variables access or Pattern.resolve() call.
# This significantly improves performance for dynamic pattern operations.
_VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


class PatternType(Enum):
    """Type of regex pattern."""

    STATIC = "static"  # Fixed pattern, no variables
    DYNAMIC = "dynamic"  # Pattern with placeholders {variable}

    def __str__(self) -> str:
        """String representation."""
        return self.value


@dataclass
class Pattern:
    """
    Represents a regex pattern with its metadata.

    A pattern can be:
    - Static: fixed regex (e.g., \\bTODO\\b)
    - Dynamic: contains variables (e.g., TODO \\({username}\\))

    The pattern can optionally specify a default panel for injection.
    """

    name: str
    regex: str
    type: PatternType
    description: str = ""
    default_panel: str | None = None  # "find", "replace", or "find_in_files"

    def __post_init__(self) -> None:
        """Validation after initialization."""
        if not self.name:
            raise ValueError("Pattern name cannot be empty")

        if not self.regex:
            raise ValueError("Pattern regex cannot be empty")

        # Convert type if it's a string
        if isinstance(self.type, str):
            self.type = PatternType(self.type)

        # Validate default_panel if provided
        if self.default_panel is not None:
            valid_panels = ["find", "replace", "find_in_files"]
            if self.default_panel not in valid_panels:
                raise ValueError(f"Invalid default_panel '{self.default_panel}'. Must be one of: {valid_panels}")

        # Validate regex syntax (without resolving variables)
        self._validate_regex()

    @cached_property
    def variables(self) -> list[str]:
        """
        Auto-detect and return variable names from the pattern.

        Variables format: {{VARIABLE_NAME}} (case-insensitive, normalized to UPPERCASE)

        Returns:
            List of found variable names (in UPPERCASE)

        Note:
            Uses @cached_property to avoid recompiling regex on every access.
            Result is computed once and cached for the lifetime of the Pattern instance.
        """
        if self.type != PatternType.DYNAMIC:
            return []

        # Use pre-compiled pattern for better performance
        matches = _VARIABLE_PATTERN.findall(self.regex)
        # Normalize to uppercase for consistency, remove duplicates, preserve order
        return list(dict.fromkeys([var.upper() for var in matches]))

    def _validate_regex(self) -> None:
        """
        Validate regex syntax.

        For dynamic patterns, temporarily replaces variables with 'X'.
        """
        test_regex = self.regex

        if self.type == PatternType.DYNAMIC:
            # Replace all variables {{VAR}} with a valid placeholder (case-insensitive)
            var_pattern = r"\{\{(\w+)\}\}"
            test_regex = re.sub(var_pattern, "X", test_regex)

        try:
            re.compile(test_regex)
        except re.error as e:
            raise ValueError(f"Invalid regex syntax: {e}") from e

    def is_dynamic(self) -> bool:
        """Return True if the pattern is dynamic."""
        return self.type == PatternType.DYNAMIC

    def resolve(self, variables: dict[str, str] | None = None) -> str:
        """
        Resolve dynamic variables in the pattern (Jinja-style).

        Variables are replaced as-is (no escaping). Users can use regex
        special chars in their variable values if needed.

        Format: {{VARIABLE_NAME}} (UPPERCASE convention, case-insensitive matching)

        Args:
            variables: Dictionary {variable_name: value}
                    Keys are case-insensitive (normalized to UPPERCASE)

        Returns:
            Regex with variables replaced by their values

        Raises:
            ValueError: If missing variables or static pattern

        Example:
            Pattern: "LOG \\[{{DATE}}\\] {{LEVEL}}: {{MESSAGE}}"
            Variables: {"DATE": "2025-10-17", "LEVEL": "ERROR", "MESSAGE": "Failed"}
            Result: "LOG \\[2025-10-17\\] ERROR: Failed"
        """
        if self.type == PatternType.STATIC:
            return self.regex

        if not variables:
            raise ValueError(f"Pattern '{self.name}' requires variables: {self.variables}")

        # Normalize variable keys to UPPERCASE for case-insensitive matching
        normalized_vars = {k.upper(): v for k, v in variables.items()}

        # Check that all required variables are provided
        required_vars = self.variables  # Auto-detected from regex
        missing_vars = set(required_vars) - set(normalized_vars.keys())
        if missing_vars:
            raise ValueError(f"Missing variables for pattern '{self.name}': {missing_vars}")

        # Replace variables (case-insensitive) - NO re.escape() !
        # If user wants regex special chars, they can use them
        resolved = self.regex

        # Use regex substitution for case-insensitive replacement
        def replacer(match: re.Match[str]) -> str:
            var_name = match.group(1).upper()  # Normalize to uppercase
            value = normalized_vars.get(var_name)
            if value is None:
                return str(match.group(0))  # Keep original if not found (shouldn't happen due to validation)
            return value

        # Use pre-compiled pattern for better performance
        resolved = _VARIABLE_PATTERN.sub(replacer, resolved)

        return resolved

    def to_dict(self) -> dict[str, Any]:
        """Convert pattern to dictionary (for JSON)."""
        data = {
            "name": self.name,
            "regex": self.regex,
            "type": self.type.value,
            "description": self.description,
        }
        # Only include default_panel if set
        if self.default_panel is not None:
            data["default_panel"] = self.default_panel
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pattern:
        """
        Create a Pattern from a dictionary.

        Note: 'variables' key is ignored if present (legacy support).
        Variables are auto-detected from regex.
        """
        return cls(
            name=data["name"],
            regex=data["regex"],
            type=PatternType(data["type"]),
            description=data.get("description", ""),
            default_panel=data.get("default_panel"),
        )


@dataclass
class Portfolio:
    """
    Collection of regex patterns with metadata.

    A portfolio is saved in a JSON file and contains
    multiple organized patterns with metadata for:
    - Attribution (author)
    - Versioning (version, created, updated)
    - Organization (tags)
    - Protection (readonly flag for built-in portfolios)
    """

    name: str
    description: str = ""
    version: str = "1.0.0"
    patterns: list[Pattern] = field(default_factory=list)
    author: str = ""
    created: str = ""  # ISO date format YYYY-MM-DD
    updated: str = ""  # ISO date format YYYY-MM-DD
    tags: list[str] = field(default_factory=list)
    readonly: bool = False  # Soft immutability flag

    def __post_init__(self) -> None:
        """Validation after initialization."""
        if not self.name:
            raise ValueError("Portfolio name cannot be empty")

        # Check pattern name uniqueness (O(n) algorithm with set)
        pattern_names = [p.name for p in self.patterns]
        seen: set[str] = set()
        duplicates: set[str] = set()  # Use set for O(1) lookup
        for name in pattern_names:
            if name in seen:
                duplicates.add(name)
            seen.add(name)
        if duplicates:
            raise ValueError(f"Duplicate pattern names: {duplicates}")

        # Build pattern cache for O(1) lookups
        self._pattern_cache: dict[str, Pattern] = {p.name: p for p in self.patterns}

    def add_pattern(self, pattern: Pattern) -> None:
        """
        Add a pattern to the portfolio.

        Raises:
            ValueError: If portfolio is readonly or pattern name already exists
        """
        if self.readonly:
            raise ValueError(f"Cannot add pattern to readonly portfolio '{self.name}'")

        if self.get_pattern(pattern.name):
            raise ValueError(f"Pattern '{pattern.name}' already exists in portfolio")

        self.patterns.append(pattern)
        self._pattern_cache[pattern.name] = pattern  # Update cache

    def remove_pattern(self, name: str) -> bool:
        """
        Remove a pattern by its name.

        Returns:
            True if removed, False if not found

        Raises:
            ValueError: If portfolio is readonly
        """
        if self.readonly:
            raise ValueError(f"Cannot remove pattern from readonly portfolio '{self.name}'")

        pattern = self.get_pattern(name)
        if pattern:
            self.patterns.remove(pattern)
            del self._pattern_cache[name]  # Update cache
            return True
        return False

    def get_pattern(self, name: str) -> Pattern | None:
        """
        Get a pattern by its name - O(1) lookup via cache.

        Returns:
            Found pattern or None
        """
        return self._pattern_cache.get(name)

    def list_patterns(self, pattern_type: PatternType | None = None) -> list[Pattern]:
        """
        List patterns, optionally filtered by type.

        Args:
            pattern_type: Filter by type (None = all)

        Returns:
            List of patterns
        """
        if pattern_type is None:
            return self.patterns.copy()

        return [p for p in self.patterns if p.type == pattern_type]

    def to_dict(self) -> dict[str, Any]:
        """
        Convert portfolio to dictionary (for JSON).

        Keys are ordered: metadata first (name, description, version, author, etc.),
        then patterns array at the end for better readability.
        """
        # Build ordered dict: metadata first, patterns last
        data: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }

        # Add optional metadata fields (always include, even if empty, for consistent order)
        data["author"] = self.author
        data["created"] = self.created
        data["updated"] = self.updated
        data["tags"] = self.tags
        data["readonly"] = self.readonly

        # Patterns array at the end (more readable in JSON file)
        data["patterns"] = [p.to_dict() for p in self.patterns]

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Portfolio:
        """
        Create a Portfolio from a dictionary.

        Supports both V1 (legacy) and V2 (with metadata) formats.
        Missing metadata fields default to empty/default values.
        """
        patterns = [Pattern.from_dict(p) for p in data.get("patterns", [])]

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            patterns=patterns,
            author=data.get("author", ""),
            created=data.get("created", ""),
            updated=data.get("updated", ""),
            tags=data.get("tags", []),
            readonly=data.get("readonly", False),
        )
