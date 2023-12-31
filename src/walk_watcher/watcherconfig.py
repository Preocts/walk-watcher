from __future__ import annotations

import logging
import os
from configparser import ConfigParser

NEW_CONFIG = """\
[system]
# config_name should be unique for each configuration file.
config_name = {filename}

# :memory: can be used here to use an in-memory database.
database_path = {filename}

# Controls how long the is_running flag is valid for.
max_is_running_seconds = 60

# Controls how many lines are emitted in a single batch.
max_emit_line_count = 500

# If true, file age is based on creation time (see README.md)
treat_files_as_new = false

[intervals]
# Intervals are only used when running with the `--loop` flag.
# Intervals are in seconds.
collect_interval = 10
emit_interval = 60

[dimensions]
# Dimensions are optional and can be used to add additional context to the metric.
# By default "root=..." is added as a dimension.
config.file.name = {filename}

[watcher]
# Metric names cannot contain spaces or commas.
metric_name = file.watcher
root_directories =

# Exclude directories and files from being watched.
# The following are regular expressions and are matched against the full path.
# Multiline values are combined into a single regular expression.
exclude_directories =
exclude_files =

[emit]
# Emit metrics to the following destinations.
# Filename will be <config_name>_<YYmmdd>_metric_lines.txt
file = true
stdout = false

# Telegraf agent must be running on the following host and port.
telegraf = false
telegraf_host = 127.0.0.1
telegraf_port = 8080
telegraf_path = /telegraf

# OneAgent must be running on the following host and port.
oneagent = false
oneagent_host = 127.0.0.1
oneagent_port = 14499
oneagent_path = /metrics/ingest
"""


class WatcherConfig:
    """Configuration for the Watcher."""

    logger = logging.getLogger("walk_watcher.WatcherConfig")

    def __init__(self, filepath: str) -> None:
        """Load the configuration from the given file."""
        self._config = ConfigParser()
        success = self._config.read(filepath)

        if not success:
            raise ValueError(f"Could not read config file at {filepath}")

        self.logger.debug("Loaded config from %s", filepath)

    @property
    def config_name(self) -> str:
        """Return the name of the config."""
        return self._config.get("system", "config_name", fallback="walk_watcher")

    @property
    def database_path(self) -> str:
        """Return the path to the database file, or ":memory:" if not set."""
        return self._config.get("system", "database_path", fallback=":memory:")

    @property
    def max_is_running_seconds(self) -> int:
        """Return the maximum age of the is_running flag in seconds."""
        return self._config.getint("system", "max_is_running_seconds", fallback=300)

    @property
    def max_emit_line_count(self) -> int:
        """Return the maximum number of lines to emit at once."""
        return self._config.getint("system", "max_emit_line_count", fallback=500)

    @property
    def treat_files_as_new(self) -> bool:
        """Return the flag for how first_seen timestamps are calculated."""
        return self._config.getboolean("system", "treat_files_as_new", fallback=False)

    @property
    def collect_interval(self) -> int:
        """Return the interval to collect metrics at."""
        return self._config.getint("intervals", "collect_interval", fallback=10)

    @property
    def emit_interval(self) -> int:
        """Return the interval to emit metrics at."""
        return self._config.getint("intervals", "emit_interval", fallback=60)

    @property
    def metric_name(self) -> str:
        """Return the name of the metric to use."""
        return self._config.get("watcher", "metric_name", fallback="walk_watcher")

    @property
    def root_directories(self) -> list[str]:
        """Return the root directories to watch. Will raise if not set."""
        config_line = self._config.get("watcher", "root_directories")
        lines = [line.strip() for line in config_line.split("\n") if line.strip()]
        return lines

    @property
    def exclude_directory_pattern(self) -> str | None:
        """Return the pattern to exclude directories from the walk."""
        config_line = self._config.get("watcher", "exclude_directories", fallback="")
        lines = [line.strip() for line in config_line.splitlines() if line.strip()]
        return "|".join(lines) or None

    @property
    def exclude_file_pattern(self) -> str | None:
        """Return the pattern to exclude files from the walk."""
        config_line = self._config.get("watcher", "exclude_files", fallback="")
        lines = [line.strip() for line in config_line.splitlines() if line.strip()]
        return "|".join(lines) or None

    @property
    def dimensions(self) -> str:
        """Return a string of any additional dimensions to add to the metric."""
        if not self._config.has_section("dimensions"):
            return ""
        dimensions = self._config["dimensions"]
        return ",".join(f"{key}={value}" for key, value in dimensions.items())

    @property
    def emit_stdout(self) -> bool:
        """Return whether to emit metrics to stdout."""
        return self._config.getboolean("emit", "stdout", fallback=False)

    @property
    def emit_file(self) -> bool:
        """Return whether to emit metrics to a file."""
        return self._config.getboolean("emit", "file", fallback=False)

    @property
    def emit_telegraf(self) -> bool:
        """Return whether to emit metrics to a telegraf listener."""
        return self._config.getboolean("emit", "telegraf", fallback=False)

    @property
    def telegraf_host(self) -> str:
        """Return the host to send telegraf metrics to."""
        return self._config.get("emit", "telegraf_host", fallback="127.0.0.1")

    @property
    def telegraf_port(self) -> int:
        """Return the port to send telegraf metrics to."""
        return self._config.getint("emit", "telegraf_port", fallback=8080)

    @property
    def telegraf_path(self) -> str:
        """Return the path to send telegraf metrics to."""
        return self._config.get("emit", "telegraf_path", fallback="/telegraf")

    @property
    def emit_oneagent(self) -> bool:
        """Return whether to emit metrics to a OneAgent listener."""
        return self._config.getboolean("emit", "oneagent", fallback=False)

    @property
    def oneagent_host(self) -> str:
        """Return the host to send OneAgent metrics to."""
        return self._config.get("emit", "oneagent_host", fallback="127.0.0.1")

    @property
    def oneagent_port(self) -> int:
        """Return the port to send OneAgent metrics to."""
        return self._config.getint("emit", "oneagent_port", fallback=14499)

    @property
    def oneagent_path(self) -> str:
        """Return the path to send OneAgent metrics to."""
        return self._config.get("emit", "oneagent_path", fallback="/metrics/ingest")


def write_new_config(filename: str) -> None:
    """Write a new config file if one does not exist."""
    if os.path.exists(filename):
        return

    config_name = filename.replace(".ini", ".db")
    config = NEW_CONFIG.format(filename=config_name)

    with open(filename, "w") as config_file:
        config_file.write(config)
