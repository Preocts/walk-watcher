from __future__ import annotations

import dataclasses
import logging
import re
import sqlite3
from contextlib import closing


@dataclasses.dataclass(frozen=True)
class Directory:
    """A directory."""

    root: str
    last_seen: int
    file_count: int


@dataclasses.dataclass(frozen=True)
class File:
    """A file."""

    root: str
    filename: str
    last_seen: int


class StoreDB:
    """Database for storing data about files and directories."""

    logger = logging.getLogger("walk_watcher.StoreDB")

    def __init__(self, path: str) -> None:
        """Initialize a new StoreDB connected to the given path."""
        self.logger.debug("Initializing StoreDB at %s", path)
        self._connection = sqlite3.connect(path)
        self._create_file_table()
        self._create_directory_table()

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
            VALUES (?, ?, ?, ?, 0)
            """,
            [
                (file.root, file.filename, file.last_seen, file.last_seen)
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
