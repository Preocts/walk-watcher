from __future__ import annotations

import logging

from smoketest_queues import smoketest_runner

from walk_watcher.watcher import Watcher
from walk_watcher.watcherconfig import WatcherConfig


CONFIG = "smoketest.ini"


def main() -> int:
    """Run the smoketest watcher."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    config = WatcherConfig(CONFIG)
    watcher = Watcher(config)

    with smoketest_runner():
        watcher.run_loop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
