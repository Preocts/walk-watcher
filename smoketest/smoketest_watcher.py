from __future__ import annotations

import logging
import time

from smoketest_queues import smoketest_runner

from walk_watcher.watcher import Watcher
from walk_watcher.watcherconfig import WatcherConfig


CONFIG = "smoketest.ini"
WATCHER_SECONDS_INTERVAL = 5
EMIT_SECONDS_INTERVAL = 60


def main() -> int:
    """Run the smoketest watcher."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    config = WatcherConfig(CONFIG)
    watcher = Watcher(config)
    next_run = time.time() + WATCHER_SECONDS_INTERVAL
    next_emit = time.time() + EMIT_SECONDS_INTERVAL

    with smoketest_runner():
        while "the world keeps turning":
            try:
                if time.time() >= next_run:
                    print("Running smoketest watcher")
                    watcher.run()
                    next_run = time.time() + WATCHER_SECONDS_INTERVAL

                if time.time() >= next_emit:
                    print("Emitting smoketest watcher metrics")
                    watcher.emit()
                    next_emit = time.time() + EMIT_SECONDS_INTERVAL

                time.sleep(0.1)

            except KeyboardInterrupt:
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
