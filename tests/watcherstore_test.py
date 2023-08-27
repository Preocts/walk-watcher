from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from walk_watcher.watchermodel import Directory
from walk_watcher.watchermodel import File
from walk_watcher.watcherstore import WatcherStore

MAX_IS_RUNNING_AGE = 5 * 60  # 5 minutes

# Predefine some rows for testing.
NOW_TS = int(datetime.now().timestamp())
THIRTYONE_DAYS = 31 * 24 * 60 * 60
NOW_TX_PLUS_31_DAYS = NOW_TS - THIRTYONE_DAYS

FILE_ROWS = [
    [1, "/home/user/obiwan", "file1", NOW_TS, NOW_TS + 3, 3, 0],
    [2, "/home/user/obiwan", "file2", NOW_TS, NOW_TS, 1, 0],
    [3, "/home/user/obiwan", "file3", NOW_TS, NOW_TX_PLUS_31_DAYS, THIRTYONE_DAYS, 1],
    [4, "/home/user/luke", "file1", NOW_TS, NOW_TS, 1, 0],
    [5, "/home/user/luke", "file2", NOW_TS, NOW_TS + 4, 4, 0],
    [6, "/home/user/luke", "file3", NOW_TS, NOW_TX_PLUS_31_DAYS, THIRTYONE_DAYS, 1],
]
EXPECTED_DIRECTORIES: Any = [
    ["/home/user/obiwan", 2, 0],
    ["/home/user/luke", 2, 0],
]


@pytest.fixture
def store_db() -> WatcherStore:
    return WatcherStore(
        ":memory:",
        max_is_running_age=MAX_IS_RUNNING_AGE,
    )


@pytest.fixture
def store_db_full() -> WatcherStore:
    db = WatcherStore(
        ":memory:",
        max_is_running_age=MAX_IS_RUNNING_AGE,
    )
    db._connection.executemany(
        "INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?)",
        FILE_ROWS,
    )
    db._connection.commit()
    return db


def test_storedb_built_from_config() -> None:
    config = MagicMock(
        database_path=":memory:",
        max_is_running_seconds=1,
        oldest_directory_row_days=2,
        oldest_file_row_days=3,
    )
    store_db = WatcherStore.from_config(config)

    assert store_db._max_is_running_age == 1


def test_storedb_works_with_context_manager() -> None:
    with patch("walk_watcher.watcherstore.WatcherStore.start_run") as start_run_mock:
        with patch("walk_watcher.watcherstore.WatcherStore.stop_run") as stop_run_mock:
            with WatcherStore(":memory:") as store_db:
                store_db.start_run()
                store_db.stop_run()

    assert start_run_mock.call_count == 2
    assert stop_run_mock.call_count == 2


def test_create_file_table(store_db: WatcherStore) -> None:
    cursor = store_db._connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [name[0] for name in cursor.fetchall()]

    assert "files" in tables


def test_create_system_table(store_db: WatcherStore) -> None:
    cursor = store_db._connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [name[0] for name in cursor.fetchall()]

    assert "system" in tables


def test_system_table_is_saved_on_init(store_db: WatcherStore) -> None:
    cursor = store_db._connection.cursor()
    cursor.execute("SELECT * FROM system")
    rows = cursor.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == ":memory:"  # database path is correct
    assert rows[0][2] == 0  # is_running is False
    # We don't check the last_seen timestamp for simplicity.


def test_start_run_updates_system_table(store_db: WatcherStore) -> None:
    store_db.start_run()
    cursor = store_db._connection.cursor()
    cursor.execute("SELECT is_running FROM system")
    rows = cursor.fetchone()

    assert rows[0] == 1  # is_running is True


def test_start_run_with_stale_is_running_flag_updates_system_table(
    store_db: WatcherStore,
) -> None:
    store_db.start_run()
    cursor = store_db._connection.cursor()
    new_timestamp = datetime.now().timestamp() - MAX_IS_RUNNING_AGE - 1
    cursor.execute(
        "UPDATE system SET last_run = ?",
        (new_timestamp,),
    )

    store_db.start_run()

    cursor.execute("SELECT last_run FROM system")
    rows = cursor.fetchone()

    assert rows[0] != new_timestamp  # last_seen was updated


def test_start_run_while_running_raises(store_db: WatcherStore) -> None:
    store_db.start_run()

    with pytest.raises(RuntimeError):
        store_db.start_run()


def test_end_run_updates_system_table(store_db: WatcherStore) -> None:
    cursor = store_db._connection.cursor()
    cursor.execute("UPDATE system SET is_running = 1")

    store_db.stop_run()
    cursor.execute("SELECT is_running FROM system")
    rows = cursor.fetchone()

    assert rows[0] == 0  # is_running is False


def test_save_files_empty_rows(store_db: WatcherStore) -> None:
    files = [
        File("/home/user/magamind", "file1", 1618224000),
        File("/home/user/magamind", "file2", 1618224000),
        File("/home/user/magamind", "file3", 1618224000),
    ]
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
            file.first_seen,
            file.last_seen,
            file.last_seen - file.first_seen,
            0,
        )
        for row, file in zip(rows, files)
    )


def test_save_file_existing_row_updated(store_db: WatcherStore) -> None:
    files = [
        File("/home/user/magamind", "file1", 1618224000, 1618224000),
        File("/home/user/magamind", "file2", 1618224000, 1618224000),
        File("/home/user/magamind", "file3", 1618224000, 1618224000),
    ]
    print("first files", files[-1])
    store_db.save_files(files)

    # Replace last with new: the same root and filename but 300 seconds older.
    popped_file = files.pop()
    new_age = 600
    files.append(
        File(
            root=popped_file.root,
            filename=popped_file.filename,
            last_seen=popped_file.last_seen + new_age,
        )
    )
    store_db.save_files(files)

    cursor = store_db._connection.cursor()
    cursor.execute("SELECT last_seen, age_seconds FROM files")
    last_row = cursor.fetchall()[-1]

    assert last_row == (files[-1].last_seen, new_age)


def test_save_file_add_new_row_with_existing_rows(store_db: WatcherStore) -> None:
    files = [
        File("/home/user/magamind", "file1", 1618224000),
        File("/home/user/magamind", "file2", 1618224000),
        File("/home/user/magamind", "file3", 1618224000),
    ]
    store_db.save_files(files)

    # Add a new file with a different root and filename
    new_file = File("new_root", "new_file", 1234567890)
    files.append(new_file)

    store_db.save_files(files)

    cursor = store_db._connection.cursor()
    cursor.execute("SELECT * FROM files")
    last_row = cursor.fetchall()[-1]

    assert last_row[1:] == (
        new_file.root,
        new_file.filename,
        new_file.first_seen,
        new_file.last_seen,
        new_file.last_seen - new_file.first_seen,
        0,
    )


def test_save_files_marks_all_removed(store_db: WatcherStore) -> None:
    files = [
        File("/home/user/magamind", "file1", 1618224000),
        File("/home/user/magamind", "file2", 1618224000),
        File("/home/user/magamind", "file3", 1618224000),
    ]
    store_db.save_files(files)

    # Save an empty list of files
    store_db.save_files([])

    cursor = store_db._connection.cursor()
    cursor.execute("SELECT removed FROM files")
    removed = [value[0] for value in cursor.fetchall()]

    assert all(removed)


def test_get_directories(store_db_full: WatcherStore) -> None:
    rows = store_db_full.get_directories()
    expected = {Directory(*row) for row in EXPECTED_DIRECTORIES}

    # Reference DIRECTORY_ROWS for the expected result
    assert len(rows) == len(EXPECTED_DIRECTORIES)
    assert not (set(rows) - expected)


def test_get_oldest_files(store_db_full: WatcherStore) -> None:
    rows = store_db_full.get_oldest_files()

    # Reference FILE_ROWS for the expected result
    assert len(rows) == 2
    assert rows[0].root == "/home/user/luke"
    assert rows[0].filename == "file2"
    assert rows[1].root == "/home/user/obiwan"
    assert rows[1].filename == "file1"


def test_clean_removed_files(store_db_full: WatcherStore) -> None:
    store_db_full.clean_removed_files()

    cursor = store_db_full._connection.cursor()
    cursor.execute("SELECT * FROM files")
    rows = cursor.fetchall()

    assert len(rows) == 4
