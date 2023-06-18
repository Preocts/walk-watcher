from __future__ import annotations

import dataclasses
import logging
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from datetime import timedelta
from types import TracebackType

MAX_IS_RUNNING_AGE = 5 * 60  # 5 minutes


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
    first_seen: int
    last_seen: int
    removed: int

    def __str__(self) -> str:
        """Return a string representation of the file."""
        lastseen = datetime.fromtimestamp(self.last_seen).strftime("%Y-%m-%d %H:%M:%S")
        age = timedelta(seconds=self.last_seen - self.first_seen)
        age_minutes = age.seconds // 60

        return (
            f"{self.root}/{self.filename}"
            f" ({age_minutes} minutes old, last seen {lastseen})"
            f" {'(removed)' if self.removed else '(present)'}"
        )

    def as_metric_line(self, metric_name: str) -> str:
        """Return a string representation of the file in metric format."""
        if re.search(r"\s", metric_name):
            raise ValueError("Metric name cannot contain whitespace")
        age = timedelta(seconds=self.last_seen - self.first_seen)
        age_minutes = age.seconds // 60

        return f"{metric_name},directory.oldest.file.minutes={self.root} {age_minutes}"


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
        self.logger.debug("Inserting %s files", len(files))
        cursor.executemany(
            """
            INSERT OR IGNORE INTO files (root, filename, first_seen, last_seen, removed)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    file.root,
                    file.filename,
                    file.first_seen,
                    file.last_seen,
                    file.removed,
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
            SET last_seen = ?, removed = 0
            WHERE root = ? AND filename = ?
            """,
            [(file.last_seen, file.root, file.filename) for file in files],
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
