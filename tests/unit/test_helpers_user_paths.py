import os
import sys
import unittest
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from src.core.helpers import is_builtin_portfolio_path


class TestHelpersUserPaths(unittest.TestCase):
    def test_is_builtin_portfolio_path_user_dir(self):
        """Test that User/RegexLab/builtin_portfolios is recognized as builtin."""
        # Test the new User directory path
        path = Path("Packages/User/RegexLab/builtin_portfolios/regexlab.json")
        self.assertTrue(is_builtin_portfolio_path(path), "Path object should be recognized")

        path_str = "Packages/User/RegexLab/builtin_portfolios/regexlab.json"
        self.assertTrue(is_builtin_portfolio_path(path_str), "String path should be recognized")

        # Windows style
        path_win = "Packages\\User\\RegexLab\\builtin_portfolios\\regexlab.json"
        self.assertTrue(is_builtin_portfolio_path(path_win), "Windows path should be recognized")

    def test_is_builtin_portfolio_path_legacy(self):
        """Test that legacy package paths are still recognized."""
        path = "Packages/RegexLab/data/portfolios/regexlab.json"
        self.assertTrue(is_builtin_portfolio_path(path))

    def test_is_custom_portfolio(self):
        """Test that normal user portfolios are NOT recognized as builtin."""
        path = "Packages/User/RegexLab/portfolios/my_custom.json"
        self.assertFalse(is_builtin_portfolio_path(path))


if __name__ == "__main__":
    unittest.main()
