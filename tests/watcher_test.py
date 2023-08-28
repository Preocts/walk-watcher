from __future__ import annotations

import os
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from walk_watcher.watcher import Watcher


@pytest.fixture
def watcher() -> Watcher:
    config = MagicMock(
        database_path=":memory:",
        max_is_running_seconds=1,
        treat_files_as_new=False,
        metric_name="walk_watcher_test",
        root_directories=["tests/fixture"],
        remove_prefix="tests/",
        exclude_file_pattern="file01",
        exclude_directory_pattern=r"directory02|fixture\/$",
        collect_interval=10,
        emit_interval=10,
    )
    return Watcher(config)


def test_walk_directory(watcher: Watcher) -> None:
    cwd = os.getcwd()
    root = os.path.join(cwd, "tests/fixture")

    with patch.object(watcher._config, "root_directories", [root, "mock/dir"]):
        with patch.object(watcher._config, "remove_prefix", ""):
            all_files = watcher._walk_directories()

    # directory02 is ignored
    # file01 is ignored
    assert len(all_files) == 1

    for file in all_files:
        assert file.root.startswith(root)


def test_is_ignored_file(watcher: Watcher) -> None:
    with patch.object(watcher._config, "exclude_file_pattern", "file0.*"):
        result = watcher._is_ignored_filename("file01.txt")

    assert result is True

    with patch.object(watcher._config, "exclude_file_pattern", ""):
        result = watcher._is_ignored_filename("file01.txt")

    assert result is False


def test_is_ignored_directory(watcher: Watcher) -> None:
    with patch.object(watcher._config, "exclude_directory_pattern", r"\/foo$|\/bar"):
        result = watcher._is_ignored_directory("/foo")

    assert result is True

    with patch.object(watcher._config, "exclude_directory_pattern", r"\/bar"):
        result = watcher._is_ignored_directory("/foo/bar/baz")

    assert result is True

    with patch.object(watcher._config, "exclude_directory_pattern", ""):
        result = watcher._is_ignored_directory("/foo/bar/baz")

    assert result is False


def test_emit_calls_emitter(watcher: Watcher) -> None:
    with patch.object(watcher._emitter, "emit") as mock_emit:
        watcher.emit()

    assert mock_emit.call_count == 1


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
    assert Watcher._sanitize_directory_path(path) == expected


def test_run_once(watcher: Watcher) -> None:
    with patch.object(watcher, "walk") as mock_walk:
        with patch.object(watcher, "emit") as mock_emit:
            watcher.run_once()

    assert mock_walk.call_count == 1
    assert mock_emit.call_count == 1


def test_run_loop_waits_for_interval(watcher: Watcher) -> None:
    with patch.object(watcher, "walk") as mock_walk:
        with patch.object(watcher, "emit") as mock_emit:
            with patch("time.sleep") as mock_sleep:
                mock_sleep.side_effect = KeyboardInterrupt

                watcher.run_loop()

    assert mock_walk.call_count == 0
    assert mock_emit.call_count == 0


def test_run_loop_with_no_interval() -> None:
    config = MagicMock(
        database_path=":memory:",
        collect_interval=-1,
        emit_interval=-1,
    )
    watcher = Watcher(config)
    with patch.object(watcher, "walk") as mock_walk:
        with patch.object(watcher, "emit") as mock_emit:
            with patch("time.sleep") as mock_sleep:
                mock_sleep.side_effect = KeyboardInterrupt

                watcher.run_loop()

    assert mock_walk.call_count == 1
    assert mock_emit.call_count == 1


def test_run_loop_bubbles_unexpected_exceptions(watcher: Watcher) -> None:
    with patch.object(watcher, "walk"):
        with patch.object(watcher, "emit"):
            with patch("time.sleep") as mock_sleep:
                mock_sleep.side_effect = ValueError("Unexpected error")

                with pytest.raises(ValueError, match="Unexpected error"):
                    watcher.run_loop()


def test_build_file_models_file_not_found(watcher: Watcher) -> None:
    """Assert that existing file is modeled and missing file is skipped."""
    filenames = [
        "watcher_test.py",
        "nota_test.py",
    ]
    dirpath = "./tests"

    result = watcher._build_file_models(dirpath, filenames)

    assert len(result) == 1


def test_get_first_seen_uses_config_flag(watcher: Watcher) -> None:
    """Assert that treat_files_as_new flag changes returned value."""
    filepath = "./tests/watcher_test.py"
    now = 123

    with patch.object(watcher._config, "treat_files_as_new", False):
        moved_files = watcher._get_first_seen(filepath, now)
    with patch.object(watcher._config, "treat_files_as_new", True):
        new_files = watcher._get_first_seen(filepath, now)

    assert moved_files == now
    assert new_files != now
