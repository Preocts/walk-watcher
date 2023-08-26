from __future__ import annotations

import dataclasses
from datetime import datetime


@dataclasses.dataclass(frozen=True)
class Directory:
    """Represents a unique directory."""

    root: str
    file_count: int
    size_bytes: int


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
