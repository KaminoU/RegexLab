"""
Unit tests for is_builtin_portfolio_path helper function.
"""

from pathlib import Path

from src.core.helpers import is_builtin_portfolio_path


class TestIsBuiltinPortfolioPath:
    """Test is_builtin_portfolio_path function."""

    def test_builtin_path_unix_separator(self):
        """Should recognize builtin path with Unix separator."""
        path = "C:/Users/test/Packages/RegexLab/data/portfolios/rxl.json"
        assert is_builtin_portfolio_path(path) is True

    def test_builtin_path_windows_separator(self):
        """Should recognize builtin path with Windows separator."""
        path = "C:\\Users\\test\\Packages\\RegexLab\\data\\portfolios\\rxl.json"
        assert is_builtin_portfolio_path(path) is True

    def test_builtin_path_packages_regexlab_unix(self):
        """Should recognize Packages/RegexLab pattern (Unix)."""
        path = "/home/user/Packages/RegexLab/data/portfolios/test.json"
        assert is_builtin_portfolio_path(path) is True

    def test_builtin_path_packages_regexlab_windows(self):
        """Should recognize Packages\\RegexLab pattern (Windows)."""
        path = "D:\\Sublime\\Packages\\RegexLab\\data\\test.json"
        assert is_builtin_portfolio_path(path) is True

    def test_user_path_not_builtin(self):
        """Should recognize user path as NOT builtin."""
        path = "C:/Users/test/Packages/User/RegexLab/portfolios/custom.json"
        assert is_builtin_portfolio_path(path) is False

    def test_user_path_windows_not_builtin(self):
        """Should recognize user path with Windows separator as NOT builtin."""
        path = "C:\\Users\\test\\Packages\\User\\RegexLab\\portfolios\\custom.json"
        assert is_builtin_portfolio_path(path) is False

    def test_none_path_returns_false(self):
        """Should return False for None path."""
        assert is_builtin_portfolio_path(None) is False

    def test_empty_string_returns_false(self):
        """Should return False for empty string."""
        assert is_builtin_portfolio_path("") is False

    def test_path_object(self):
        """Should work with Path objects."""
        path = Path("C:/Packages/RegexLab/data/portfolios/test.json")
        assert is_builtin_portfolio_path(path) is True

    def test_unrelated_path_returns_false(self):
        """Should return False for unrelated paths."""
        path = "/home/user/Documents/random/file.json"
        assert is_builtin_portfolio_path(path) is False
