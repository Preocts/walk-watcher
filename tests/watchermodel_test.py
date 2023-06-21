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


def test_model_directory_as_metric_line() -> None:
    directory = Directory("/foo/bar", 1234567890, 42)
    expected = "walk_watcher_test,directory.file.count=/foo/bar 42"

    result = directory.as_metric_line("walk_watcher_test")

    assert result == expected


def test_model_directory_raises_on_invalid_metric_name() -> None:
    directory = Directory("/foo/bar", 1234567890, 42)
    with pytest.raises(ValueError):
        directory.as_metric_line("walk_watcher test")


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


def test_model_file_as_metric_line() -> None:
    file = File("/foo/bar", "baz.txt", 1234567890, 1234568190, 300, 0)
    expected = "walk_watcher_test,oldest.file.seconds=/foo/bar 300"

    result = file.as_metric_line("walk_watcher_test")

    assert result == expected


def test_model_file_as_metric_line_raises_on_invalid_metric_name() -> None:
    file = File("/foo/bar", "baz.txt", 1234567890, 1234568190, 0, 0)
    with pytest.raises(ValueError):
        file.as_metric_line("walk_watcher test")
