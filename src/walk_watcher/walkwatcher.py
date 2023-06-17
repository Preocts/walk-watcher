from __future__ import annotations

import re


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
