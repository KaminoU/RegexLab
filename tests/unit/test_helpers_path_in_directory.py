"""
Unit tests for is_path_directly_in_directory() of src/core/helpers.py.

The Portfolio Manager deletes or moves a portfolio's file only if it sits directly in its folder (issue #16).
The parent of the path is resolved, its last component is not: a symlink placed in the folder is an entry of
it, and deleting or moving it acts on the link, never on its target.

Tests cover:
- plain paths, without symlinks: a file of the folder, a missing file, a subfolder, '..' out of and back
  into the folder, an absolute path elsewhere, a sibling with the same prefix, the folder itself, the names
  '.', '..' and '' (trailing separator), a relative path
- symlinks (skipped where the system refuses them): a link to a file outside, a dangling link, a linked
  subfolder, the folder reached through a link, '..' after a linked subfolder
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest
from src.core.helpers import is_path_directly_in_directory


def _symlinks_refused(error: BaseException) -> bool:
    """Tell whether an error raised by os.symlink means the system refuses symlinks, not a faulty test setup."""
    if isinstance(error, NotImplementedError):
        return True
    # 1314 is ERROR_PRIVILEGE_NOT_HELD: Windows without the symlink privilege or Developer Mode
    refusals = (errno.EPERM, errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP)
    return isinstance(error, OSError) and (getattr(error, "winerror", None) == 1314 or error.errno in refusals)


def _symlink_or_skip(link: Path, target: Path) -> None:
    """Create a symlink, or skip the test where the system refuses symlinks; any other error fails it."""
    try:
        os.symlink(str(target), str(link), target_is_directory=target.is_dir())
    except (OSError, NotImplementedError) as e:
        if not _symlinks_refused(e):
            raise
        pytest.skip(f"symlinks not available here: {e}")


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """A portfolios/ folder in a throwaway directory."""
    path = tmp_path / "portfolios"
    path.mkdir()
    return path


# ============================================================================
# Plain paths, without symlinks
# ============================================================================


class TestPlainPaths:
    """is_path_directly_in_directory() on paths that go through no symlink."""

    def test_file_in_folder(self, folder: Path) -> None:
        """A file of the folder is in it."""
        (folder / "mine.json").write_text("{}", encoding="utf-8")

        assert is_path_directly_in_directory(folder / "mine.json", folder) is True

    def test_missing_file_in_folder(self, folder: Path) -> None:
        """The file does not need to exist."""
        assert is_path_directly_in_directory(folder / "not_yet.json", folder) is True

    def test_file_in_subfolder_is_not_directly_in(self, folder: Path) -> None:
        """A file of a subfolder is not directly in the folder."""
        (folder / "sub").mkdir()

        assert is_path_directly_in_directory(folder / "sub" / "mine.json", folder) is False

    def test_dot_dot_climbs_out(self, folder: Path) -> None:
        """'..' is resolved before the comparison."""
        assert is_path_directly_in_directory(folder / ".." / "victim.json", folder) is False

    def test_dot_dot_back_into_folder(self, folder: Path) -> None:
        """A parent that resolves to the folder, through 'sub/..', is the folder."""
        (folder / "sub").mkdir()

        assert is_path_directly_in_directory(folder / "sub" / ".." / "mine.json", folder) is True

    def test_absolute_path_elsewhere(self, tmp_path: Path, folder: Path) -> None:
        """An absolute path outside the folder is not in it."""
        assert is_path_directly_in_directory(tmp_path / "victim.json", folder) is False

    def test_sibling_with_same_prefix(self, tmp_path: Path, folder: Path) -> None:
        """portfolios_evil/ starts with the letters of portfolios/ but is another folder."""
        (tmp_path / "portfolios_evil").mkdir()

        assert is_path_directly_in_directory(tmp_path / "portfolios_evil" / "x.json", folder) is False

    def test_folder_itself(self, folder: Path) -> None:
        """The folder is not a file of itself."""
        assert is_path_directly_in_directory(folder, folder) is False

    @pytest.mark.parametrize("last", [os.curdir, os.pardir, ""])
    def test_name_that_names_no_file(self, folder: Path, last: str) -> None:
        """'.', '..' and '' (a trailing separator) name the folder, its parent or nothing: never a file of it."""
        assert is_path_directly_in_directory(str(folder) + os.sep + last, folder) is False

    def test_relative_path(self, folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A relative path starts from the current directory, as it does for the system."""
        monkeypatch.chdir(folder)

        assert is_path_directly_in_directory("mine.json", folder) is True
        assert is_path_directly_in_directory(os.path.join(os.pardir, "mine.json"), folder) is False


# ============================================================================
# Symlinks
# ============================================================================


class TestSymlinks:
    """is_path_directly_in_directory() through symlinks: skipped where the system refuses to create them."""

    def test_link_to_file_outside_is_in(self, tmp_path: Path, folder: Path) -> None:
        """A link placed in the folder is a file of it, wherever it points: the last component is not resolved."""
        target = tmp_path / "victim.json"
        target.write_text("{}", encoding="utf-8")
        _symlink_or_skip(folder / "link.json", target)

        assert is_path_directly_in_directory(folder / "link.json", folder) is True

    def test_dangling_link_is_in(self, tmp_path: Path, folder: Path) -> None:
        """A link whose target has gone is still a file of the folder."""
        _symlink_or_skip(folder / "link.json", tmp_path / "gone.json")

        assert is_path_directly_in_directory(folder / "link.json", folder) is True

    def test_linked_subfolder_pointing_outside(self, tmp_path: Path, folder: Path) -> None:
        """A file reached through a linked subfolder is where the link leads, not in the folder."""
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        _symlink_or_skip(folder / "sub_link", elsewhere)

        assert is_path_directly_in_directory(folder / "sub_link" / "x.json", folder) is False

    def test_folder_reached_through_link(self, tmp_path: Path, folder: Path) -> None:
        """Both sides are resolved: the folder, named through a link, is the same folder."""
        alias = tmp_path / "alias"
        _symlink_or_skip(alias, folder)

        assert is_path_directly_in_directory(alias / "x.json", folder) is True
        assert is_path_directly_in_directory(folder / "x.json", alias) is True

    def test_dot_dot_after_linked_subfolder(self, tmp_path: Path, folder: Path) -> None:
        """
        'sub_link/..' is resolved the way the system resolves it when it opens the path.

        Platform: POSIX follows the link, then climbs from its target, out of the folder; Windows removes
        'sub_link/..' from the path before it looks at any link, which leaves the folder.
        """
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        _symlink_or_skip(folder / "sub_link", elsewhere)

        expected = os.name == "nt"
        assert is_path_directly_in_directory(folder / "sub_link" / ".." / "x.json", folder) is expected
