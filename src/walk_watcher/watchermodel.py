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
