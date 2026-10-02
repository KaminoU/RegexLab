"""
Reloading the plugin as Sublime Text does: RegexLab.py runs again, under the name RegexLab.RegexLab.

Sublime Text keeps in sys.modules the modules that a plugin imported. A reload that reused the src modules found
there would keep their state and their code: the portfolio manager's singleton would still hold the portfolios, so
that every one of them is "already loaded" and none is counted, and the previous version would stay active until a
restart.
"""

import importlib
import sys
import types
import unittest
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[2]


class _WindowCommand:
    """Stand-in for sublime_plugin.WindowCommand."""

    def __init__(self, window: Optional[Any] = None) -> None:
        """Keep the window, as Sublime Text does."""
        self.window = window


class _ApplicationCommand:
    """Stand-in for sublime_plugin.ApplicationCommand."""


class TestPluginReload(unittest.TestCase):
    """RegexLab.py loaded as Sublime Text loads it, then run again as Sublime Text reloads it."""

    # Modules whose names look like the plugin's src modules, without being them
    LOOKALIKES = ("RegexLab.srcx", "RegExLink.src", "RegExLink.src.core", "regexlab.src.core")

    def setUp(self) -> None:
        """Save sys.modules, then provide sublime, sublime_plugin and the package RegexLab, rooted at the repository."""
        self.addCleanup(self._restore_modules, dict(sys.modules))
        self.addCleanup(setattr, sys, "dont_write_bytecode", sys.dont_write_bytecode)
        # No bytecode written next to RegexLab.py, at the root of the repository
        sys.dont_write_bytecode = True

        sublime_plugin = types.ModuleType("sublime_plugin")
        sublime_plugin.WindowCommand = _WindowCommand  # type: ignore[attr-defined]
        sublime_plugin.ApplicationCommand = _ApplicationCommand  # type: ignore[attr-defined]
        sys.modules["sublime"] = MagicMock()
        sys.modules["sublime_plugin"] = sublime_plugin

        self.package = types.ModuleType("RegexLab")
        self.package.__path__ = [str(REPO_ROOT)]
        sys.modules["RegexLab"] = self.package

        self.lookalikes = {name: types.ModuleType(name) for name in self.LOOKALIKES}
        sys.modules.update(self.lookalikes)

    @staticmethod
    def _restore_modules(saved: Dict[str, Any]) -> None:
        """Put sys.modules back as it was: remove what the test added, restore what it replaced."""
        for name in list(sys.modules):
            if name not in saved:
                del sys.modules[name]
        sys.modules.update(saved)

    def _assert_nothing_else_forgotten(self, plugin: types.ModuleType, absolute: types.ModuleType) -> None:
        """The package, the plugin, the src modules imported by absolute name and the lookalikes stay."""
        self.assertIs(sys.modules.get("RegexLab"), self.package, "the package RegexLab was forgotten")
        self.assertIs(sys.modules.get("RegexLab.RegexLab"), plugin, "the plugin module was forgotten")
        self.assertIs(sys.modules.get("src.core.portfolio_manager"), absolute, "an absolute src module was forgotten")
        for name, module in self.lookalikes.items():
            self.assertIs(sys.modules.get(name), module, f"{name} was forgotten")

    def test_reload_imports_fresh_src_modules(self) -> None:
        """
        The portfolio manager's singleton holds portfolios when Sublime Text reloads the plugin: after the reload,
        sys.modules holds a new portfolio manager module, whose singleton is empty, and the plugin's names point to
        the new code. Nothing else is forgotten, at the first load as at the reload.
        """
        # Imported by absolute name, as the other tests import it
        import src.core.portfolio_manager as absolute

        plugin = importlib.import_module("RegexLab.RegexLab")
        self._assert_nothing_else_forgotten(plugin, absolute)
        old_src_package = sys.modules["RegexLab.src"]
        old_manager_module = sys.modules["RegexLab.src.core.portfolio_manager"]
        old_command_module = sys.modules["RegexLab.src.commands.portfolio_manager_command"]
        holding = old_manager_module.PortfolioManager()
        holding._loaded_portfolios["Loaded before the reload"] = MagicMock()
        old_manager_module.PortfolioManager._instance = holding

        importlib.reload(plugin)

        self.assertIsNot(sys.modules["RegexLab.src"], old_src_package, "the reload reused the cached src package")
        new_manager_module = sys.modules["RegexLab.src.core.portfolio_manager"]
        self.assertIsNot(new_manager_module, old_manager_module, "the reload reused the cached src module")
        self.assertIsNone(new_manager_module.PortfolioManager._instance, "the singleton kept its portfolios")
        new_command_module = sys.modules["RegexLab.src.commands.portfolio_manager_command"]
        self.assertIsNot(new_command_module, old_command_module, "the reload reused the cached command module")
        self.assertIs(
            plugin.PortfolioManagerCommand, new_command_module.PortfolioManagerCommand, "the plugin runs the old code"
        )
        self._assert_nothing_else_forgotten(plugin, absolute)


if __name__ == "__main__":
    unittest.main()
