from __future__ import annotations

import json
from pathlib import Path
from random import shuffle

import pytest

from walk_watcher import walkwatcher
from walk_watcher.walkwatcher import Directory
from walk_watcher.walkwatcher import File

DIRECTORIES_FILE = Path(__file__).parent / "directories.json"
FILES_FILE = Path(__file__).parent / "files.json"


@pytest.fixture
def store_db() -> walkwatcher.StoreDB:
    return walkwatcher.StoreDB(":memory:")


@pytest.fixture
def directories() -> list[Directory]:
    """Provide a shuffled list of directories."""
    with DIRECTORIES_FILE.open() as f:
        directories = [Directory(**d) for d in json.load(f)]
    shuffle(directories)
    return directories


@pytest.fixture
def files() -> list[File]:
    """Provide a shuffled list of files."""
    with FILES_FILE.open() as f:
        files = [File(**d) for d in json.load(f)]
    shuffle(files)
    return files


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


def test_model_directory_str() -> None:
    directory = Directory("/foo/bar", 1234567890, 42)
    assert str(directory) == "/foo/bar (42 files, last seen 2009-02-13 18:31:30)"


def test_model_file_str() -> None:
    file_present = File("/foo/bar", "baz.txt", 1234567890, 1234568190, 0)
    file_removed = File("/foo/bar", "baz.txt", 1234567890, 1234568190, 1)

    assert (
        str(file_present)
        == "/foo/bar/baz.txt (5 minutes old, last seen 2009-02-13 18:36:30) (present)"
    )
    assert (
        str(file_removed)
        == "/foo/bar/baz.txt (5 minutes old, last seen 2009-02-13 18:36:30) (removed)"
    )


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


def test_save_directories(
    store_db: walkwatcher.StoreDB,
    directories: list[Directory],
) -> None:
    # We save the directories twice to ensure that the
    # UNIQUE(root, last_seen) constraint is working.
    store_db.save_directories(directories)
    store_db.save_directories(directories)
    cursor = store_db._connection.cursor()
    cursor.execute("SELECT * FROM directories")
    rows = cursor.fetchall()

    assert len(rows) == len(directories)
    assert all(
        row[1:] == (directory.root, directory.last_seen, directory.file_count)
        for row, directory in zip(rows, directories)
    )


def test_save_files_empty_rows(
    store_db: walkwatcher.StoreDB,
    files: list[File],
) -> None:
    store_db.save_files(files)
    cursor = store_db._connection.cursor()
    cursor.execute("SELECT * FROM files")
    rows = cursor.fetchall()

    assert len(rows) == len(files)
    assert all(
        row[1:]
        == (
            file.root,
            file.filename,
            file.last_seen,
            file.last_seen,
            0,
        )
        for row, file in zip(rows, files)
    )


def test_save_file_existing_row_updated(
    store_db: walkwatcher.StoreDB,
    files: list[File],
) -> None:
    store_db.save_files(files)

    # Replace last file with a new one with the same root and filename
    expected_first_seen = files[-1].last_seen
    files[-1] = File(
        root=files[-1].root,
        filename=files[-1].filename,
        first_seen=expected_first_seen,
        last_seen=1234567890,
        removed=0,
    )

    store_db.save_files(files)

    cursor = store_db._connection.cursor()
    cursor.execute("SELECT * FROM files")
    last_row = cursor.fetchall()[-1]

    assert last_row[1:] == (
        files[-1].root,
        files[-1].filename,
        expected_first_seen,
        files[-1].last_seen,
        0,
    )


def test_save_file_add_new_row_with_existing_rows(
    store_db: walkwatcher.StoreDB,
    files: list[File],
) -> None:
    store_db.save_files(files)

    # Add a new file with a different root and filename
    new_file = File(
        root="new_root",
        filename="new_file",
        first_seen=1234567890,
        last_seen=1234567890,
        removed=0,
    )
    files.append(new_file)

    store_db.save_files(files)

    cursor = store_db._connection.cursor()
    cursor.execute("SELECT * FROM files")
    last_row = cursor.fetchall()[-1]

    assert last_row[1:] == (
        new_file.root,
        new_file.filename,
        new_file.last_seen,
        new_file.last_seen,
        0,
    )


def test_save_files_marks_all_removed(
    store_db: walkwatcher.StoreDB,
    files: list[File],
) -> None:
    store_db.save_files(files)

    # Save an empty list of files
    store_db.save_files([])

    cursor = store_db._connection.cursor()
    cursor.execute("SELECT removed FROM files")
    removed = [value[0] for value in cursor.fetchall()]

    assert all(removed)


def test_get_directory_rows(store_db: walkwatcher.StoreDB) -> None:
    directories = [
        Directory(root="root1", last_seen=1234567891, file_count=0),
        Directory(root="root1", last_seen=1234567890, file_count=0),
    ]

    store_db.save_directories(directories)

    rows = store_db.get_directory_rows()

    assert len(rows) == 1
    assert rows[0] == directories[0]
