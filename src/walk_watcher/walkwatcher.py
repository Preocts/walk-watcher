from __future__ import annotations

import logging
import re
import sqlite3


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
                UNIQUE(root)
            )
            """
        )
        self.logger.debug("Created directory table")


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
