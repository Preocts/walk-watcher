from __future__ import annotations

import argparse
import logging

from . import Watcher
from . import WatcherConfig


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Watch directories for file count and oldest file age. Emit to configured destinations.",
    )
    parser.add_argument(
        "config",
        type=str,
        help="The path to the configuration file.",
    )
    parser.add_argument(
        "--loop",
        help="Run the watcher in a loop. Default: False (block until exit).",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--debug",
        help="Enable debug logging.",
        default=False,
        action="store_true",
    )
    return parser.parse_args(args)


def main(*, cli_args: list[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(cli_args)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config = WatcherConfig(args.config)
    watcher = Watcher(config)

    if args.loop:
        watcher.run_loop()

    else:
        watcher.run_once()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
