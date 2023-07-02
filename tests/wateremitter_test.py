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


def test_emit_skips_false(emitter: WatcherEmitter) -> None:
    emitter.emit_to_stdout = False
    emitter.emit_to_file = False
    with patch.object(emitter, "to_stdout") as mock_stdout:
        with patch.object(emitter, "to_file") as mock_file:
            emitter.emit()

    mock_stdout.assert_not_called()
    mock_file.assert_not_called()


def test_emit_calls_all_when_true(emitter: WatcherEmitter) -> None:
    emitter.emit_to_stdout = True
    emitter.emit_to_file = True
    with patch.object(emitter, "to_stdout") as mock_stdout:
        with patch.object(emitter, "to_file") as mock_file:
            emitter.emit()

    mock_stdout.assert_called_once()
    mock_file.assert_called_once()


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
    try:
        fd, temp_file_name = tempfile.mkstemp()
        os.close(fd)  # close for Windows
        emitter.to_file(temp_file_name)
        with open(temp_file_name) as temp_file:
            results = temp_file.read()

    finally:
        os.remove(temp_file_name)

    assert results == (
        "metric.name,key1=test value1=100 1234567890\n"
        "metric.name,key1=test value1=100 1234567890\n"
    )


def test_to_stdout(emitter: WatcherEmitter) -> None:
    with redirect_stdout(StringIO()) as temp_file:
        emitter.to_stdout()
        results = temp_file.getvalue()

    assert results == (
        "metric.name,key1=test value1=100 1234567890\n"
        "metric.name,key1=test value1=100 1234567890\n"
    )
