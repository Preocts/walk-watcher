from __future__ import annotations

import pytest

from walk_watcher import walkwatcher


@pytest.mark.parametrize(
    "path, expected",
    [
        ("", ""),
        ("foo", "foo"),
        ("foo/bar", "foo.bar"),
        ("foo/bar/baz", "foo.bar.baz"),
        ("Foo/Bar/Baz", "foo.bar.baz"),
        ("Foo\\Bar\\Baz", "foo.bar.baz"),
        ("Foo Bar baz", "foo_bar_baz"),
    ],
)
def test_sanitize_directory_path(path: str, expected: str) -> None:
    assert walkwatcher._sanitize_directory_path(path) == expected
