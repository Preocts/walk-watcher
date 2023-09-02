from __future__ import annotations

from walk_watcher.watcher import Watcher
from walk_watcher.watcher import WatcherConfig

CONFIG_FILE = "tests/test_config.ini"


def test_integration_against_fixture_directory() -> None:
    config = WatcherConfig(CONFIG_FILE)
    watcher = Watcher(config)

    watcher.walk()

    cursor = watcher._store._connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM files")
    assert cursor.fetchone()[0] == 1

    cursor.execute("SELECT is_running FROM system")
    assert cursor.fetchone()[0] == 0

    # 5 lines expected from fixture setup
    # 2 directories with size/count = 4
    # 1 file age = 1
    assert len(watcher._emitter._metric_lines) == 5
