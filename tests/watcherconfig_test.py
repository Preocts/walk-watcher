from __future__ import annotations

import pytest

from walk_watcher.walkwatcher import WatcherConfig

CONFIG_PATH = "tests/test_config.ini"


def test_watcherconfig_raises_on_invalid_config_path() -> None:
    with pytest.raises(ValueError):
        WatcherConfig("foo/bar")


def test_watcherconfig_loads_test_fixture_completely() -> None:
    config = WatcherConfig(CONFIG_PATH)

    assert config.database_path == ":memory:"
    assert config.max_is_running_seconds == 60
    assert config.oldest_directory_row_days == 15
    assert config.oldest_file_row_days == 15
    assert config.max_files_per_directory == 10_000

    assert config.metric_name == "test_watcher"
    assert config.root_directory == "tests/fixture"
    assert config.remove_prefix == "tests/"

    assert config.exlude_directory_pattern == r"directory02|fixture\/$"
    assert config.exclude_file_pattern == "file.*"
