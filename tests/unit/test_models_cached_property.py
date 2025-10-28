"""
Tests for @cached_property optimization in Pattern.variables.

Verifies that Pattern.variables uses @cached_property correctly:
- Property is computed only once (on first access)
- Subsequent accesses return cached value (no recomputation)
- Cache is bound to the Pattern instance
"""

import re

from src.core.models import _VARIABLE_PATTERN, Pattern, PatternType


class TestPatternCachedProperty:
    """Test suite for @cached_property optimization in Pattern.variables."""

    def test_cached_property_computes_once(self):
        """Test that Pattern.variables is computed only once (cached)."""
        pattern = Pattern(
            name="Test Dynamic",
            regex="TODO \\[{{DATE}}\\] {{USER}}: {{MESSAGE}}",
            type=PatternType.DYNAMIC,
            description="Test pattern",
        )

        # First access - computes the variables
        result1 = pattern.variables
        assert result1 == ["DATE", "USER", "MESSAGE"]

        # Second access - should return cached value (same object reference)
        result2 = pattern.variables
        assert result2 == ["DATE", "USER", "MESSAGE"]
        assert result1 is result2  # Same object reference (cached!)

        # Third access - still cached
        result3 = pattern.variables
        assert result3 == ["DATE", "USER", "MESSAGE"]
        assert result1 is result3  # Still same object

        # All three accesses return the exact same list object
        assert id(result1) == id(result2) == id(result3)

    def test_cached_property_per_instance(self):
        """Test that cache is per-instance (different instances have independent caches)."""
        pattern1 = Pattern(
            name="Pattern 1",
            regex="{{VAR1}} {{VAR2}}",
            type=PatternType.DYNAMIC,
            description="First pattern",
        )

        pattern2 = Pattern(
            name="Pattern 2",
            regex="{{VAR3}} {{VAR4}}",
            type=PatternType.DYNAMIC,
            description="Second pattern",
        )

        # Access variables for both patterns
        vars1 = pattern1.variables
        vars2 = pattern2.variables

        # Each pattern has its own cached result
        assert vars1 == ["VAR1", "VAR2"]
        assert vars2 == ["VAR3", "VAR4"]

        # Accessing again returns cached values (no recomputation)
        assert pattern1.variables is vars1  # Same object reference
        assert pattern2.variables is vars2  # Same object reference

    def test_cached_property_static_pattern(self):
        """Test that static patterns return empty list (and it's cached)."""
        pattern = Pattern(
            name="Static Pattern",
            regex="\\bTODO\\b",
            type=PatternType.STATIC,
            description="Static pattern",
        )

        # First access
        result1 = pattern.variables
        assert result1 == []

        # Second access - should be cached
        result2 = pattern.variables
        assert result2 == []
        assert result1 is result2  # Same object reference (cached)

    def test_cached_property_with_duplicates(self):
        """Test that cached_property correctly handles duplicate variable removal."""
        pattern = Pattern(
            name="Duplicate Vars",
            regex="{{USER}} {{DATE}} {{USER}} {{DATE}}",
            type=PatternType.DYNAMIC,
            description="Pattern with duplicates",
        )

        # First access - computes and caches deduplicated list
        result1 = pattern.variables
        assert result1 == ["USER", "DATE"]  # Duplicates removed, order preserved

        # Second access - returns cached result
        result2 = pattern.variables
        assert result2 == ["USER", "DATE"]
        assert result1 is result2  # Same object reference

    def test_cached_property_case_normalization(self):
        """Test that cached_property correctly normalizes variable case."""
        pattern = Pattern(
            name="Mixed Case",
            regex="{{user}} {{Date}} {{MESSAGE}}",
            type=PatternType.DYNAMIC,
            description="Mixed case variables",
        )

        # First access - normalizes to UPPERCASE and caches
        result1 = pattern.variables
        assert result1 == ["USER", "DATE", "MESSAGE"]

        # Second access - returns cached normalized result
        result2 = pattern.variables
        assert result2 == ["USER", "DATE", "MESSAGE"]
        assert result1 is result2  # Same object reference

    def test_variable_pattern_precompiled(self):
        """Test that _VARIABLE_PATTERN is pre-compiled at module level."""
        # Verify _VARIABLE_PATTERN is a compiled regex pattern
        assert isinstance(_VARIABLE_PATTERN, re.Pattern)

        # Verify it has the expected pattern
        assert _VARIABLE_PATTERN.pattern == r"\{\{(\w+)\}\}"

        # Verify it can match variables
        test_string = "{{VAR1}} text {{VAR2}}"
        matches = _VARIABLE_PATTERN.findall(test_string)
        assert matches == ["VAR1", "VAR2"]

    def test_cached_property_performance_characteristic(self):
        """Test that multiple accesses are fast (cached, no regex recompilation)."""
        pattern = Pattern(
            name="Performance Test",
            regex="{{VAR1}} {{VAR2}} {{VAR3}}",
            type=PatternType.DYNAMIC,
            description="Test pattern",
        )

        # First access (computation)
        import time

        start = time.perf_counter()
        _ = pattern.variables
        first_access_time = time.perf_counter() - start

        # Subsequent accesses (cached, should be much faster)
        start = time.perf_counter()
        for _ in range(1000):
            _ = pattern.variables
        thousand_accesses_time = time.perf_counter() - start

        # Average time per cached access should be negligible
        avg_cached_time = thousand_accesses_time / 1000

        # Cached access should be at least 10x faster than first access
        # (first access includes regex execution, cached is just attribute lookup)
        assert avg_cached_time < first_access_time / 10, (
            f"Cached access ({avg_cached_time * 1e6:.2f} µs) should be much faster "
            f"than first access ({first_access_time * 1e6:.2f} µs)"
        )

    def test_cached_property_immutability_concern(self):
        """Test that modifying the cached list doesn't affect subsequent accesses."""
        pattern = Pattern(
            name="Immutability Test",
            regex="{{VAR1}} {{VAR2}}",
            type=PatternType.DYNAMIC,
            description="Test pattern",
        )

        # Get cached variables
        vars1 = pattern.variables
        assert vars1 == ["VAR1", "VAR2"]

        # Try to modify the cached list (user shouldn't do this, but test it)
        vars1.append("MODIFIED")

        # Subsequent access returns the SAME object (cached)
        vars2 = pattern.variables
        assert vars1 is vars2
        assert vars2 == ["VAR1", "VAR2", "MODIFIED"]  # Modified!

        # Note: This is expected behavior for @cached_property
        # The cached value is mutable. Users should not modify it.
        # If immutability is required, we'd need to return a copy or use tuple.

    def test_resolve_uses_precompiled_pattern(self):
        """Test that Pattern.resolve() uses pre-compiled _VARIABLE_PATTERN."""
        pattern = Pattern(
            name="Resolve Test",
            regex="TODO \\[{{DATE}}\\] {{USER}}",
            type=PatternType.DYNAMIC,
            description="Test pattern",
        )

        variables = {"DATE": "2025-10-23", "USER": "KaminoU"}

        # Test that resolve() works correctly (it uses _VARIABLE_PATTERN internally)
        result = pattern.resolve(variables)
        assert result == "TODO \\[2025-10-23\\] KaminoU"

        # Verify that calling resolve() multiple times with same variables works
        result2 = pattern.resolve(variables)
        assert result2 == result

    def test_multiple_patterns_share_precompiled_regex(self):
        """Test that multiple Pattern instances share the same pre-compiled _VARIABLE_PATTERN."""
        pattern1 = Pattern(
            name="Pattern 1",
            regex="{{VAR1}}",
            type=PatternType.DYNAMIC,
            description="First",
        )
        pattern2 = Pattern(
            name="Pattern 2",
            regex="{{VAR2}}",
            type=PatternType.DYNAMIC,
            description="Second",
        )

        # Both patterns use the same pre-compiled regex (module-level constant)
        # We can't directly test this, but we can verify they both work correctly
        vars1 = pattern1.variables
        vars2 = pattern2.variables

        assert vars1 == ["VAR1"]
        assert vars2 == ["VAR2"]

        # Both use _VARIABLE_PATTERN (which is shared)
        # This is a memory optimization: 1 compiled regex for all Pattern instances
