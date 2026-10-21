"""
Shared fixtures of the test suite.

``sublime_fakes``: stand-ins for sublime and sublime_plugin (``tests/sublime_fakes.py``) for one test. A test asks
for it as an argument, or with ``@pytest.mark.usefixtures("sublime_fakes")``, which also works on a
``unittest.TestCase`` method and then covers ``setUp`` too. When the stand-ins must be absent from part of a test,
``installed_sublime_fakes()`` installs them for a block only.
"""

from __future__ import annotations

from typing import Iterator

import pytest

from tests.sublime_fakes import SublimeFakes, installed_sublime_fakes


@pytest.fixture
def sublime_fakes() -> Iterator[SublimeFakes]:
    """Put fresh stand-ins for sublime and sublime_plugin in sys.modules for one test, then restore sys.modules."""
    with installed_sublime_fakes() as fakes:
        yield fakes
