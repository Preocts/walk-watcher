from __future__ import annotations

import os
import tempfile

import pytest

from walk_watcher.watcherconfig import NEW_CONFIG
from walk_watcher.watcherconfig import WatcherConfig
from walk_watcher.watcherconfig import write_new_config

CONFIG_PATH = "tests/test_config.ini"


def test_watcherconfig_raises_on_invalid_config_path() -> None:
    with pytest.raises(ValueError):
        WatcherConfig("foo/bar")


def test_watcherconfig_loads_test_fixture_completely() -> None:
    config = WatcherConfig(CONFIG_PATH)

    assert config.config_name == "test_watcher"
    assert config.database_path == ":memory:"
    assert config.oldest_directory_row_days == 14
    assert config.oldest_file_row_days == 14

    assert config.max_is_running_seconds == 60
    assert config.max_emit_line_count == 1000

    assert config.collect_interval == 5
    assert config.emit_interval == 20

    assert config.metric_name == "test_watcher"
    assert config.root_directory == "tests/fixture"
    assert config.remove_prefix == "tests/"

    assert config.exclude_directory_pattern == r"\/directory02|fixture$|\\directory02"
    assert config.exclude_file_pattern == "file01.*"

    assert config.dimensions == "config.file.name=:memory:,config.type=testing"

    assert config.emit_file is True
    assert config.emit_stdout is True


def test_dimensions_with_no_section() -> None:
    config = WatcherConfig(CONFIG_PATH)
    del config._config["dimensions"]

    assert config.dimensions == ""


def test_write_new_config() -> None:
    try:
        fd, filename = tempfile.mkstemp(suffix=".ini")
        os.close(fd)
        os.remove(filename)
        expected = NEW_CONFIG.format(filename=filename.replace(".ini", ".db"))

        write_new_config(filename)

        with open(filename) as f:
            content = f.read()

        assert content == expected

    finally:
        os.remove(filename)


def test_write_new_config_early_exit_when_exists() -> None:
    try:
        fd, filename = tempfile.mkstemp(suffix=".ini")
        os.close(fd)

        write_new_config(filename)

        with open(filename) as f:
            content = f.read()

        assert content == ""

    finally:
        os.remove(filename)
