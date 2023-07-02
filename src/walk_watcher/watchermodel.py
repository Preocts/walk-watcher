from __future__ import annotations

import dataclasses
import re
from datetime import datetime


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

    @staticmethod
    def _sanitize_directory_path(path: str) -> str:
        """
        Remove invalid characters from a directory path and double backslashes.

        Args:
            path: The directory path to sanitize.

        Returns:
            The sanitized directory path.
        """
        path = re.sub(r"\s+", "_", path)
        path = path.replace("\\", "\\\\")
        return re.sub(r"[^a-zA-Z0-9\/\\_:]", "", path)


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
