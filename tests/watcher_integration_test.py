from __future__ import annotations

from walk_watcher.watcher import Watcher
from walk_watcher.watcher import WatcherConfig

CONFIG_FILE = "tests/test_config.ini"


def test_integration_against_fixture_directory() -> None:
    config = WatcherConfig(CONFIG_FILE)
    watcher = Watcher(config)

    watcher.run()

    cursor = watcher._store._connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM directories")
    assert cursor.fetchone()[0] == 1

    cursor.execute("SELECT COUNT(*) FROM files")
    assert cursor.fetchone()[0] == 1

    cursor.execute("SELECT is_running FROM system")
    assert cursor.fetchone()[0] == 0
