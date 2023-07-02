from __future__ import annotations

import os
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from walk_watcher.watcheremitter import Metric
from walk_watcher.watcheremitter import WatcherEmitter


@pytest.fixture
def mock_config() -> MagicMock:
    config = MagicMock()
    config.emit_stdout = True
    config.emit_file = True
    config.metric_name = "test"
    return config


@pytest.fixture
def emitter() -> WatcherEmitter:
    """Build an emitter with two lines for testing."""
    emitter = WatcherEmitter()
    emitter._metric_lines.append(
        Metric("metric.name", ["key1=test"], ["value1=100"], 1234567890),
    )
    emitter._metric_lines.append(
        Metric("metric.name", ["key1=test"], ["value1=100"], 1234567890),
    )
    return emitter


def test_emit_calls_all_methods(emitter: WatcherEmitter) -> None:
    with patch.object(emitter, "to_stdout") as mock_stdout:
        with patch.object(emitter, "to_file") as mock_file:
            emitter.emit(batch_size=1)

    assert mock_stdout.call_count == 2
    assert mock_file.call_count == 2


def test_build_from_config(mock_config: MagicMock) -> None:
    emitter = WatcherEmitter.from_config(mock_config)
    assert emitter.emit_to_stdout is True
    assert emitter.emit_to_file is True


def test_add_line() -> None:
    emitter = WatcherEmitter()
    emitter.add_line("metric.name", ["key1", "key2"], ["value1", "value2"])
    assert len(emitter._metric_lines) == 1
    assert emitter._metric_lines[0].metric_name == "metric.name"
    assert emitter._metric_lines[0].dimensions == ["key1", "key2"]
    assert emitter._metric_lines[0].guage_values == ["value1", "value2"]
    assert emitter._metric_lines[0].timestamp != 0


def test_get_lines_pops_left(emitter: WatcherEmitter) -> None:
    lines = emitter._get_lines(max_lines=1)
    assert len(lines) == 1
    assert lines[0] == "metric.name,key1=test value1=100 1234567890"


def test_to_file(emitter: WatcherEmitter) -> None:
    lines = [
        "metric.name,key1=test value1=100 1234567890",
        "metric.name,key1=test value1=100 1234567890",
    ]
    try:
        fd, temp_file_name = tempfile.mkstemp()
        emitter.emit_to_file = True
        emitter.file_name = temp_file_name
        expected_file = f"{temp_file_name}_metric_lines.txt"
        os.close(fd)  # close for Windows

        emitter.to_file(lines)

        with open(expected_file) as temp_file:
            results = temp_file.read()

    finally:
        os.remove(temp_file_name)

    assert results == (
        "metric.name,key1=test value1=100 1234567890\n"
        "metric.name,key1=test value1=100 1234567890\n"
    )


def test_to_file_early_exit(emitter: WatcherEmitter) -> None:
    try:
        fd, temp_file_name = tempfile.mkstemp()
        emitter.emit_to_file = False
        emitter.file_name = temp_file_name
        expected_file = f"{temp_file_name}_metric_lines.txt"
        os.close(fd)  # close for Windows

        emitter.to_file(["empty"])

        assert not os.path.exists(expected_file)

    finally:
        os.remove(temp_file_name)


def test_to_stdout(emitter: WatcherEmitter) -> None:
    lines = [
        "metric.name,key1=test value1=100 1234567890",
        "metric.name,key1=test value1=100 1234567890",
    ]
    emitter.emit_to_stdout = True
    with redirect_stdout(StringIO()) as temp_file:
        emitter.to_stdout(lines)
        results = temp_file.getvalue()

    assert results == (
        "metric.name,key1=test value1=100 1234567890\n"
        "metric.name,key1=test value1=100 1234567890\n"
    )


def test_to_stdout_early_exit(emitter: WatcherEmitter) -> None:
    emitter.emit_to_stdout = False
    with redirect_stdout(StringIO()) as temp_file:
        emitter.to_stdout(["empty"])
        results = temp_file.getvalue()

    assert results == ""
