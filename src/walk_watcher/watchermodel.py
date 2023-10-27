from __future__ import annotations

import dataclasses


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
    first_seen: int
    last_seen: int
    size_bytes: int = 0
    age_seconds: int = 0
    removed: int = 0
