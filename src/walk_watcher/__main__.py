from __future__ import annotations

import argparse
import logging
from pathlib import Path

from walk_watcher.watcher import Watcher
from walk_watcher.watcherconfig import WatcherConfig
from walk_watcher.watcherconfig import write_new_config

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


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
    parser.add_argument(
        "--log-file",
        help="Enable logging to a file next to the config file.",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--make-config",
        help="Create a default configuration file.",
        default=False,
        action="store_true",
    )
    return parser.parse_args(args)


def add_file_handler_to_logging(config_filepath: str) -> None:
    """Add a file handler to the root logger next to the config file provided."""
    filepath = Path(config_filepath).absolute()
    log_filepath = filepath.parent / f"{filepath.stem}.log"
    file_handler = logging.FileHandler(log_filepath)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logging.getLogger().addHandler(file_handler)


def main(*, cli_args: list[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(cli_args)

    if args.make_config:
        write_new_config(args.config)
        return 0

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )

    if args.log_file:
        add_file_handler_to_logging(args.config)

    config = WatcherConfig(args.config)
    watcher = Watcher(config)

    if args.loop:
        watcher.run_loop()

    else:
        watcher.run_once()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
