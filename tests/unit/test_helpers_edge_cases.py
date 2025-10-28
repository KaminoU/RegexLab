# Test helpers edge cases

from src.core.helpers import shorten_path


def test_shorten_path_unknown_mode():
    result = shorten_path("/path/file.json", mode="invalid")
    assert result == "/path/file.json"
