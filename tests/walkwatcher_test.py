from __future__ import annotations

import pytest

from walk_watcher import walkwatcher


@pytest.fixture
def store_db() -> walkwatcher.StoreDB:
    return walkwatcher.StoreDB(":memory:")


@pytest.mark.parametrize(
    "path, expected",
    [
        ("", ""),
        ("foo", "foo"),
        ("foo/bar", "foo.bar"),
        ("foo/bar/baz", "foo.bar.baz"),
        ("Foo/Bar/Baz", "foo.bar.baz"),
        ("Foo\\Bar\\Baz", "foo.bar.baz"),
        ("Foo Bar baz", "foo_bar_baz"),
    ],
)
def test_sanitize_directory_path(path: str, expected: str) -> None:
    assert walkwatcher._sanitize_directory_path(path) == expected


def test_create_file_table(store_db: walkwatcher.StoreDB) -> None:
    store_db._create_file_table()
    cursor = store_db._connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [name[0] for name in cursor.fetchall()]

    assert "files" in tables


def test_create_directory_table(store_db: walkwatcher.StoreDB) -> None:
    store_db._create_directory_table()
    cursor = store_db._connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [name[0] for name in cursor.fetchall()]

    assert "directories" in tables
