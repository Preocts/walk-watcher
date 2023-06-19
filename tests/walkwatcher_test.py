from __future__ import annotations

import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from walk_watcher import walkwatcher
from walk_watcher.walkwatcher import Directory
from walk_watcher.walkwatcher import File
from walk_watcher.walkwatcher import WalkWatcher


@pytest.fixture
def watcher() -> WalkWatcher:
    config = MagicMock(
        database_path=":memory:",
        max_is_running_seconds=1,
        oldest_directory_row_days=2,
        oldest_file_row_days=3,
        metric_name="walk_watcher_test",
        root_directory="tests/fixture",
        remove_prefix="tests/",
        exclude_file_pattern="file01",
        exclude_directory_pattern=r"directory02|fixture\/$",
    )
    return WalkWatcher(config)


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
        ("foo", "foo"),
        ("foo/bar", "foo.bar"),
        ("foo/bar/baz", "foo.bar.baz"),
        ("Foo/Bar/Baz", "foo.bar.baz"),
        ("Foo\\Bar\\Baz", "foo.bar.baz"),
        ("Foo Bar baz", "foo_bar_baz"),
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


def test_walk_directory_strip_root(watcher: WalkWatcher) -> None:
    cwd = os.getcwd()
    root = os.path.join(cwd, "tests/fixture")
    all_directories: list[Directory] = []
    all_files: list[File] = []

    with patch.object(watcher._config, "root_directory", root):
        with patch.object(watcher._config, "remove_prefix", cwd):
            for directory, files in watcher._walk_directory():
                all_directories.append(directory)
                all_files.extend(files)

    assert len(all_directories) == 3
    assert len(all_files) == 3

    for directory in all_directories:
        assert not directory.root.startswith(root)

    for file in files:
        assert not file.root.startswith(root)


def test_walk_directory_keep_root(watcher: WalkWatcher) -> None:
    cwd = os.getcwd()
    root = os.path.join(cwd, "tests/fixture")
    all_directories: list[Directory] = []
    all_files: list[File] = []

    with patch.object(watcher._config, "root_directory", root):
        with patch.object(watcher._config, "remove_prefix", ""):
            for directory, files in watcher._walk_directory():
                all_directories.append(directory)
                all_files.extend(files)

    assert len(all_directories) == 3
    assert len(all_files) == 3

    for directory in all_directories:
        assert directory.root.startswith(root)

    for file in files:
        assert file.root.startswith(root)


def test_filter_files(watcher: WalkWatcher) -> None:
    mock_files = [
        File("/foo/bar", "file01.txt", 1234567890, 1234567890, 0, 0),
        File("/foo/bar", "file02.txt", 1234567890, 1234567890, 0, 0),
    ]
    with patch.object(watcher._config, "exclude_file_pattern", "file0.*"):
        result_all = watcher._filter_files(mock_files)

    with patch.object(watcher._config, "exclude_file_pattern", "file01"):
        result_one = watcher._filter_files(mock_files)

    with patch.object(watcher._config, "exclude_file_pattern", ""):
        result_none = watcher._filter_files(mock_files)

    assert len(result_all) == 0
    assert len(result_one) == 1
    assert len(result_none) == 2


def test_filter_directories(watcher: WalkWatcher) -> None:
    mock_directories = [
        Directory("/foo", 1234567890, 0),
        Directory("/foo/bar", 1234567890, 0),
        Directory("/foo/bar/baz", 1234567890, 0),
    ]
    with patch.object(watcher._config, "exclude_directory_pattern", r"\/foo$|\/bar"):
        result_all = watcher._filter_directories(mock_directories)

    with patch.object(watcher._config, "exclude_directory_pattern", r"\/bar"):
        result_one = watcher._filter_directories(mock_directories)

    with patch.object(watcher._config, "exclude_directory_pattern", ""):
        result_none = watcher._filter_directories(mock_directories)

    assert len(result_all) == 0
    assert len(result_one) == 1
    assert len(result_none) == 3


def test_write_new_config() -> None:
    try:
        fd, filename = tempfile.mkstemp(suffix=".ini")
        os.close(fd)
        os.remove(filename)
        expected = walkwatcher.NEW_CONFIG.format(
            filename=filename.replace(".ini", ".db")
        )

        walkwatcher.write_new_config(filename)

        with open(filename) as f:
            content = f.read()

        assert content == expected

    finally:
        os.remove(filename)


def test_write_new_config_early_exit_when_exists() -> None:
    try:
        fd, filename = tempfile.mkstemp(suffix=".ini")
        os.close(fd)

        walkwatcher.write_new_config(filename)

        with open(filename) as f:
            content = f.read()

        assert content == ""

    finally:
        os.remove(filename)
