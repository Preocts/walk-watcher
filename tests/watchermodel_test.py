from __future__ import annotations

from datetime import datetime

import pytest

from walk_watcher.watchermodel import Directory
from walk_watcher.watchermodel import File


def test_model_directory_str() -> None:
    directory = Directory("/foo/bar", 1234567890, 42)
    expected_ts = datetime.fromtimestamp(1234567890).strftime("%Y-%m-%d %H:%M:%S")
    expected = f"/foo/bar (42 files, last seen {expected_ts})"

    assert str(directory) == expected


@pytest.mark.parametrize(
    "path, expected",
    [
        ("", ""),
        ("foo?", "foo"),
        ("foo/bar", "foo/bar"),
        ("foo/bar/baz", "foo/bar/baz"),
        ("Foo/Bar/Baz", "Foo/Bar/Baz"),
        ("Foo\\Bar\\Baz", "Foo\\\\Bar\\\\Baz"),
        ("Foo Bar baz", "Foo_Bar_baz"),
    ],
)
def test_sanitize_directory_path(path: str, expected: str) -> None:
    assert Directory._sanitize_directory_path(path) == expected


def test_model_file_str() -> None:
    file_present = File("/foo/bar", "baz.txt", 1234568190, 1234567890, 300, 0)
    file_removed = File("/foo/bar", "baz.txt", 1234568190, 1234567890, 300, 1)
    expected_ts = datetime.fromtimestamp(1234568190).strftime("%Y-%m-%d %H:%M:%S")
    expected = f"/foo/bar/baz.txt (300 seconds old, last seen {expected_ts})"
    expected_preset = "(present)"
    expected_removed = "(removed)"

    assert str(file_present) == f"{expected} {expected_preset}"
    assert str(file_removed) == f"{expected} {expected_removed}"
