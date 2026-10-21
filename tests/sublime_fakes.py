"""
Stand-ins for sublime and sublime_plugin, the modules that only exist inside Sublime Text.

``installed_sublime_fakes()`` puts fresh stand-ins in ``sys.modules`` for a block, then puts ``sys.modules`` back
exactly as it was, so that no module imported against them outlives the block. The fixture ``sublime_fakes``
(``tests/conftest.py``) does the same for a whole test. The rest of the suite runs without them, as outside Sublime
Text.
"""

from __future__ import annotations

import contextlib
import sys
import types
from typing import Any, Iterator, NamedTuple
from unittest.mock import MagicMock

# The part of the sublime API that RegexLab.py, src/ and the tests use: any other name raises AttributeError, as it
# would on the real module. Each one is a fresh MagicMock, which records its calls.
SUBLIME_CALLABLES = (
    "Region",
    "Window",
    "error_message",
    "find_resources",
    "get_clipboard",
    "load_binary_resource",
    "load_resource",
    "load_settings",
    "message_dialog",
    "packages_path",
    "run_command",
    "save_settings",
    "set_clipboard",
    "set_timeout",
    "yes_no_cancel_dialog",
)

# The values of Sublime Text's own sublime.py
SUBLIME_CONSTANTS = {
    "COOPERATE_WITH_AUTO_COMPLETE": 2,
    "DIALOG_YES": 1,
    "HIDE_ON_MOUSE_MOVE_AWAY": 8,
    "MONOSPACE_FONT": 1,
}


class ApplicationCommand:
    """Stand-in for sublime_plugin.ApplicationCommand."""


class EventListener:
    """Stand-in for sublime_plugin.EventListener."""


class TextCommand:
    """Stand-in for sublime_plugin.TextCommand: Sublime Text creates one per view."""

    def __init__(self, view: Any) -> None:
        """Keep the view, as Sublime Text does."""
        self.view = view


class WindowCommand:
    """Stand-in for sublime_plugin.WindowCommand: Sublime Text creates one per window."""

    def __init__(self, window: Any) -> None:
        """Keep the window, as Sublime Text does."""
        self.window = window


class SublimeFakes(NamedTuple):
    """The stand-ins that one test or one block gets."""

    sublime: types.ModuleType
    sublime_plugin: types.ModuleType


def make_sublime() -> types.ModuleType:
    """Build a fresh stand-in for the sublime module."""
    module = types.ModuleType("sublime")
    for name in SUBLIME_CALLABLES:
        setattr(module, name, MagicMock(name=f"sublime.{name}"))
    for name, value in SUBLIME_CONSTANTS.items():
        setattr(module, name, value)
    return module


def make_sublime_plugin() -> types.ModuleType:
    """Build a fresh stand-in for the sublime_plugin module, whose classes a plugin can subclass."""
    module = types.ModuleType("sublime_plugin")
    for cls in (ApplicationCommand, EventListener, TextCommand, WindowCommand):
        setattr(module, cls.__name__, cls)
    return module


def restore_modules(saved: dict[str, types.ModuleType]) -> None:
    """Put sys.modules back as it was: remove what was added, restore what was replaced or removed."""
    for name in list(sys.modules):
        if name not in saved:
            del sys.modules[name]
    sys.modules.update(saved)


@contextlib.contextmanager
def installed_sublime_fakes() -> Iterator[SublimeFakes]:
    """Put fresh stand-ins for sublime and sublime_plugin in sys.modules for the block, then restore sys.modules."""
    saved = dict(sys.modules)
    fakes = SublimeFakes(make_sublime(), make_sublime_plugin())
    sys.modules["sublime"] = fakes.sublime
    sys.modules["sublime_plugin"] = fakes.sublime_plugin
    try:
        yield fakes
    finally:
        restore_modules(saved)
