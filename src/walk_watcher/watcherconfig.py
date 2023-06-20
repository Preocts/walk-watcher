from __future__ import annotations

import logging
from configparser import ConfigParser


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
    def max_files_per_directory(self) -> int:
        """Return the maximum number of files to store per directory."""
        return self._config.getint("system", "max_files_per_directory", fallback=1000)

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
