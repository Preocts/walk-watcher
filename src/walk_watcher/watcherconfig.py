from __future__ import annotations

import logging
import os
from configparser import ConfigParser

NEW_CONFIG = """\
[system]
# config_name should be unique for each configuration file.
config_name = {filename}
database_path = {filename}
max_is_running_seconds = 60
oldest_directory_row_days = 14
oldest_file_row_days = 14

[dimensions]
# Dimensions are optional and can be used to add additional context to the metric.
# By default directory file counts use "directory.file.count" as a dimension.
# By default oldest file age uses "oldest.file.seconds" as a dimension.
config.file.name = {filename}

[watcher]
# Metric names cannot contain spaces or commas.
metric_name = file.watcher
root_directory = .
remove_prefix = .

# Exclude directories and files from being watched.
# The following are regular expressions and are matched against the full path.
# Multiline values are combined into a single regular expression.
exclude_directories = ^\\..*$
exclude_files = ^\\..*$

[emit]
# Emit metrics to the following destinations.
stdout = false
file = true

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
    def oldest_directory_row_days(self) -> int:
        """Return the maximum age of a directory row in days."""
        return self._config.getint("system", "oldest_directory_row_days", fallback=30)

    @property
    def oldest_file_row_days(self) -> int:
        """Return the maximum age of a file row in days."""
        return self._config.getint("system", "oldest_file_row_days", fallback=30)

    @property
    def metric_name(self) -> str:
        """Return the name of the metric to use."""
        return self._config.get("watcher", "metric_name", fallback="walk_watcher")

    @property
    def root_directory(self) -> str:
        """Return the root directory to watch. Will raise if not set."""
        return self._config.get("watcher", "root_directory")

    @property
    def remove_prefix(self) -> str | None:
        """Return the prefix to remove from the root directory when reporting."""
        return self._config.get("watcher", "remove_prefix", fallback=None)

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


def write_new_config(filename: str) -> None:
    """Write a new config file if one does not exist."""
    if os.path.exists(filename):
        return

    config_name = filename.replace(".ini", ".db")
    config = NEW_CONFIG.format(filename=config_name)

    with open(filename, "w") as config_file:
        config_file.write(config)
