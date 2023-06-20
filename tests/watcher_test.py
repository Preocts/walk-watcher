from __future__ import annotations

import os
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from walk_watcher.watcher import Watcher
from walk_watcher.watcherstore import Directory
from walk_watcher.watcherstore import File


@pytest.fixture
def watcher() -> Watcher:
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
    return Watcher(config)


def test_walk_directory_strip_root(watcher: Watcher) -> None:
    cwd = os.getcwd()
    root = os.path.join(cwd, "tests/fixture")

    with patch.object(watcher._config, "root_directory", root):
        with patch.object(watcher._config, "remove_prefix", cwd):
            all_directories, all_files = watcher._walk_directories()

    assert len(all_directories) == 3
    assert len(all_files) == 3

    for directory in all_directories:
        assert not directory.root.startswith(root)

    for file in all_files:
        assert not file.root.startswith(root)


def test_walk_directory_keep_root(watcher: Watcher) -> None:
    cwd = os.getcwd()
    root = os.path.join(cwd, "tests/fixture")

    with patch.object(watcher._config, "root_directory", root):
        with patch.object(watcher._config, "remove_prefix", ""):
            all_directories, all_files = watcher._walk_directories()

    assert len(all_directories) == 3
    assert len(all_files) == 3

    for directory in all_directories:
        assert directory.root.startswith(root)

    for file in all_files:
        assert file.root.startswith(root)


def test_filter_files(watcher: Watcher) -> None:
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


def test_filter_directories(watcher: Watcher) -> None:
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
