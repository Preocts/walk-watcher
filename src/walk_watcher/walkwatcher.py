from __future__ import annotations

import dataclasses
import logging
import os
import re
import sqlite3
from configparser import ConfigParser
from contextlib import closing
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import TracebackType
    from typing import Protocol

    class _WatcherConfig(Protocol):
        @property
        def database_path(self) -> str:
            ...

        @property
        def max_is_running_seconds(self) -> int:
            ...

        @property
        def oldest_directory_row_days(self) -> int:
            ...

        @property
        def oldest_file_row_days(self) -> int:
            ...


@dataclasses.dataclass(frozen=True)
class Directory:
    """A directory row in the database."""

    root: str
    last_seen: int
    file_count: int

    def __str__(self) -> str:
        """Return a string representation of the directory."""
        lastseen = datetime.fromtimestamp(self.last_seen).strftime("%Y-%m-%d %H:%M:%S")
        return f"{self.root} ({self.file_count} files, last seen {lastseen})"

    def as_metric_line(self, metric_name: str) -> str:
        """Return a string representation of the directory in metric format."""
        if re.search(r"\s", metric_name):
            raise ValueError("Metric name cannot contain whitespace")

        return f"{metric_name},directory.file.count={self.root} {self.file_count}"

    @staticmethod
    def _sanitize_directory_path(path: str) -> str:
        """
        Sanitize a directory path, removing all non-alphanumeric characters and
        replacing `/` and `\\` with `.`.

        Args:
            path: The directory path to sanitize.

        Returns:
            The sanitized directory path.
        """
        path = re.sub(r"[\/\\]", ".", path)
        path = re.sub(r"\s+", "_", path)
        return re.sub(r"[^a-zA-Z0-9._]", "", path.lower())


@dataclasses.dataclass(frozen=True)
class File:
    """A file row in the database."""

    root: str
    filename: str
    last_seen: int
    first_seen: int = 0
    age_seconds: int = 0
    removed: int = 0

    def __str__(self) -> str:
        """Return a string representation of the file."""
        lastseen = datetime.fromtimestamp(self.last_seen).strftime("%Y-%m-%d %H:%M:%S")

        return (
            f"{self.root}/{self.filename}"
            f" ({self.age_seconds} seconds old, last seen {lastseen})"
            f" {'(removed)' if self.removed else '(present)'}"
        )

    def as_metric_line(self, metric_name: str) -> str:
        """Return a string representation of the file in metric format."""
        if re.search(r"\s", metric_name):
            raise ValueError("Metric name cannot contain whitespace")

        return f"{metric_name},oldest.file.seconds={self.root} {self.age_seconds}"


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
        return self._config.get("system", "path", fallback=":memory:")

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


class StoreDB:
    """Database for storing data about files and directories."""

    logger = logging.getLogger("walk_watcher.StoreDB")

    def __init__(
        self,
        database_path: str = ":memory:",
        *,
        max_is_running_age: int = 300,
        oldest_directory_row_age: int = 30,
        oldest_file_row_age: int = 30,
    ) -> None:
        """
        Initialize a new StoreDB connected to the given path.

        It is recommended to use the `with` statement to ensure the database
        connection is closed properly and that start_run(), stop_run(), and
        cleanup() are called at the appropriate times. For example:

            with StoreDB() as db:
                ...

        Args:
            database_path: The path to the database file. Defaults to an
                in-memory database.

        Keyword Args:
            max_is_running_age: The maximum age of the is_running flag in
                seconds. If the is_running flag is older than this, it will be
                reset to 0. Defaults to 300 (5 minutes).
            oldest_directory_row_age: The maximum age of a directory row in
                days. If a directory row is older than this, it will be
                removed on cleanup. Defaults to 30.
            oldest_file_row_age: The maximum age of a file row in days. If a
                file row is older than this, it will be removed on cleanup.
                Defaults to 30.

        """
        self.logger.debug("Initializing StoreDB at %s", database_path)
        self._connection = sqlite3.connect(database_path)

        self._max_is_running_age = max_is_running_age
        self._oldest_directory_row_age = oldest_directory_row_age
        self._oldest_file_row_age = oldest_file_row_age

        self._create_file_table()
        self._create_directory_table()
        self._create_system_table()

        self._save_system_info(database_path)

    @classmethod
    def from_config(cls, config: _WatcherConfig) -> StoreDB:
        """Build a StoreDB from the given configuration."""
        return cls(
            config.database_path,
            max_is_running_age=config.max_is_running_seconds,
            oldest_directory_row_age=config.oldest_directory_row_days,
            oldest_file_row_age=config.oldest_file_row_days,
        )

    def __enter__(self) -> StoreDB:
        """Enter a context manager."""
        self.start_run()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit a context manager."""
        self.stop_run()

    def _create_file_table(self) -> None:
        """Create the file table if it does not already exist."""
        # We care about the age of files so we need to store the first and last
        # time we saw them. We also need to store the root directory so we can
        # tell if a file has been moved.
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                root TEXT NOT NULL,
                filename TEXT NOT NULL,
                first_seen INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                age_seconds INTEGER NOT NULL,
                removed INTEGER NOT NULL,
                UNIQUE(root, filename)
            )
            """
        )
        self.logger.debug("Created file table")

    def _create_directory_table(self) -> None:
        """Create the directory table if it does not already exist."""
        # We care about the file count of the directory so that we can map
        # the activity of the directory over time.
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS directories (
                id INTEGER PRIMARY KEY,
                root TEXT NOT NULL,
                last_seen INTEGER NOT NULL,
                file_count INTEGER NOT NULL,
                UNIQUE(root, last_seen)
            )
            """
        )
        self.logger.debug("Created directory table")

    def _create_system_table(self) -> None:
        """Create a table to store system information."""
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS system (
                database_path TEXT NOT NULL,
                last_run INTEGER NOT NULL,
                is_running INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(database_path)
            )
            """
        )
        self.logger.debug("Created system table")

    def _save_system_info(self, database_path: str) -> None:
        """Save system information to the database. (only at startup)"""
        self._connection.execute(
            """
            INSERT OR REPLACE INTO system
            ( database_path, last_run, is_running, created_at )
            VALUES (?, ?, ?, ?)
            """,
            (
                database_path,
                int(datetime.now().timestamp()),
                0,
                int(datetime.now().timestamp()),
            ),
        )
        self._connection.commit()
        self.logger.debug("Saved system information")

    def _get_last_run(self) -> tuple[int, int]:
        """Return the last run timestamp and is_running flag."""
        with closing(self._connection.cursor()) as cursor:
            cursor.execute("SELECT last_run, is_running FROM system")
            return cursor.fetchone()

    def start_run(self) -> None:
        """Set the is_running flag to True, raise error if already running."""
        # Ignore is_running if last_run is more than MAX_IS_RUNNING_AGE minutes ago
        last_run, is_running = self._get_last_run()

        if last_run < int(datetime.now().timestamp()) - self._max_is_running_age:
            is_running = False

        if is_running:
            raise RuntimeError(f"Already running (last run {last_run})")

        with closing(self._connection.cursor()) as cursor:
            cursor.execute(
                "UPDATE system SET is_running = 1, last_run = ?",
                (int(datetime.now().timestamp()),),
            )
            self._connection.commit()

    def stop_run(self) -> None:
        """Set the is_running flag to False."""
        with closing(self._connection.cursor()) as cursor:
            cursor.execute("UPDATE system SET is_running = 0")
            self._connection.commit()

    def save_directories(self, directories: list[Directory]) -> None:
        """Save the given directories to the database."""
        self.logger.debug("Saving %s directories", len(directories))
        with closing(self._connection.cursor()) as cursor:
            cursor.executemany(
                """
                INSERT OR IGNORE INTO directories (root, last_seen, file_count)
                VALUES (?, ?, ?)
                """,
                [
                    (directory.root, directory.last_seen, directory.file_count)
                    for directory in directories
                ],
            )
            self._connection.commit()

    def save_files(self, files: list[File]) -> None:
        """Save the given files to the database."""
        # We run a batch update followed by a batch insert which ignores
        # errors. This is because we want to update the last_seen time and
        # removed of existing files and insert new files.
        self.logger.debug("Saving %s files", len(files))
        with closing(self._connection.cursor()) as cursor:
            self._mark_all_removed(cursor)
            self._update_files(cursor, files)
            self._insert_files(cursor, files)

            self._connection.commit()

    def _mark_all_removed(self, cursor: sqlite3.Cursor) -> None:
        """Mark all files as removed, to be updated later."""
        self.logger.debug("Marking all files as removed")
        cursor.execute("UPDATE files SET removed = 1 WHERE removed = 0")

    def _insert_files(self, cursor: sqlite3.Cursor, files: list[File]) -> None:
        """Insert the given files into the database."""
        # We can make some assumptions here because we have already marked all
        # files as removed. We can assume that any file that is not in the
        # database is new and can be inserted with first/last seen as the
        # being equal, and age_seconds as 0, and the removed flag as 0.
        self.logger.debug("Inserting %s files", len(files))
        cursor.executemany(
            """
            INSERT OR IGNORE INTO files (root, filename, first_seen,
                last_seen, age_seconds, removed)
            VALUES (?, ?, ?, ?, 0, 0)
            """,
            [
                (
                    file.root,
                    file.filename,
                    file.last_seen,
                    file.last_seen,
                )
                for file in files
            ],
        )

    def _update_files(self, cursor: sqlite3.Cursor, files: list[File]) -> None:
        """Update the given files in the database."""
        self.logger.debug("Updating %s files", len(files))
        cursor.executemany(
            """
            UPDATE files
            SET last_seen = ?, removed = 0, age_seconds = ? - first_seen
            WHERE root = ? AND filename = ?
            """,
            [
                (file.last_seen, file.last_seen, file.root, file.filename)
                for file in files
            ],
        )

    def get_directory_rows(self) -> list[Directory]:
        """Get most recently seen directories and their file counts."""
        self.logger.debug("Getting directory rows")
        with closing(self._connection.cursor()) as cursor:
            cursor.execute(
                """
                WITH ptn_directories AS
                    (
                        SELECT root, last_seen, file_count,
                            ROW_NUMBER() OVER
                                ( PARTITION BY root ORDER BY last_seen DESC ) rn
                        FROM directories
                    )
                SELECT root, last_seen, file_count
                FROM ptn_directories
                WHERE rn = 1
                """
            )
            return [
                Directory(root, last_seen, file_count)
                for root, last_seen, file_count in cursor.fetchall()
            ]

    def get_file_rows(self, directory: Directory) -> list[File]:
        """Get all present files for the given directory sorted by age descending."""
        self.logger.debug("Getting file rows for %s", directory.root)
        with closing(self._connection.cursor()) as cursor:
            cursor.execute(
                """
                SELECT root, filename, last_seen, first_seen, age_seconds, removed
                FROM files
                WHERE root = ? AND removed = 0
                ORDER BY age_seconds DESC
                """,
                (directory.root,),
            )
            # Watch the order of the columns here
            return [File(*row) for row in cursor.fetchall()]

    def get_oldest_files(self) -> list[File]:
        """Get the oldest file per directory that are not removed."""
        self.logger.debug("Getting oldest files")
        with closing(self._connection.cursor()) as cursor:
            cursor.execute(
                """
                WITH ptn_files AS
                    (
                        SELECT root, filename, last_seen, first_seen, age_seconds,
                            ROW_NUMBER() OVER
                                ( PARTITION BY root ORDER BY age_seconds DESC ) rn
                        FROM files
                        WHERE removed = 0
                    )
                SELECT root, filename, first_seen, last_seen, age_seconds
                FROM ptn_files
                WHERE rn = 1
                ORDER BY age_seconds DESC
                """
            )
            # Watch the order of the columns here
            return [File(*row) for row in cursor.fetchall()]


class WalkWatcher:
    """Track file counts and file ages for a given directory."""

    logger = logging.getLogger(__name__)

    def __init__(self, config: WatcherConfig) -> None:
        """
        Initialize a new WalkWatcher.

        Args:
            config: The configuration to use for this watcher.
        """
        self._config = config
        self._store = StoreDB.from_config(config)

    def _walk_directory(self) -> Generator[tuple[Directory, list[File]], None, None]:
        """
        Walk the config defined directory and yield each directory and its files.

        Yields:
            A tuple of the directory and its files.
        """
        root = self._config.root_directory
        remove_prefix = self._config.remove_prefix

        for dirpath, _, filenames in os.walk(root):
            now = int(datetime.now().timestamp())
            if remove_prefix:
                dirpath = dirpath.lstrip(remove_prefix)
                dirpath = dirpath or "/"

            directory = Directory(dirpath, now, len(filenames))
            files = [File(dirpath, filename, now) for filename in filenames]

            yield directory, files
