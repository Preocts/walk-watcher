from __future__ import annotations

import datetime
import os
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from pytest import LogCaptureFixture

from walk_watcher.watcheremitter import Metric
from walk_watcher.watcheremitter import WatcherEmitter


@pytest.fixture
def mock_config_true() -> MagicMock:
    config = MagicMock()
    config.config_name = "test"
    config.emit_stdout = True
    config.emit_file = True
    config.emit_telegraf = True
    config.emit_oneagent = True
    config.telegraf_host = "127.0.0.1"
    config.telegraf_port = 8080
    config.telegraf_path = "/telegraf"
    config.oneagent_host = "127.0.0.1"
    config.oneagent_port = 14499
    config.oneagent_path = "/metrics/ingest"
    return config


@pytest.fixture
def mock_config_false(mock_config_true: MagicMock) -> MagicMock:
    mock_config_true.emit_stdout = False
    mock_config_true.emit_file = False
    mock_config_true.emit_telegraf = False
    mock_config_true.emit_oneagent = False
    return mock_config_true


def test_emit_calls_all_methods(mock_config_true: MagicMock) -> None:
    emitter = WatcherEmitter(mock_config_true)
    emitter._metric_lines.append(Metric("metric.name", ["key1=test"], ["value=1"], 12))
    emitter._metric_lines.append(Metric("metric.name", ["key1=test"], ["value=2"], 12))

    with patch.object(emitter, "to_stdout") as mock_stdout:
        with patch.object(emitter, "to_file") as mock_file:
            with patch.object(emitter, "to_telegraf") as mock_telegraf:
                with patch.object(emitter, "to_oneagent") as mock_oneagent:
                    emitter.emit(batch_size=1)

    assert mock_stdout.call_count == 2
    assert mock_file.call_count == 2
    assert mock_telegraf.call_count == 2
    assert mock_oneagent.call_count == 2


def test_add_line(mock_config_false: MagicMock) -> None:
    emitter = WatcherEmitter(mock_config_false)
    emitter.add_line("metric.name", ["key1", "key2"], ["value1", "value2"])
    assert len(emitter._metric_lines) == 1
    assert emitter._metric_lines[0].metric_name == "metric.name"
    assert emitter._metric_lines[0].dimensions == ["key1", "key2"]
    assert emitter._metric_lines[0].guage_values == ["value1", "value2"]
    assert emitter._metric_lines[0].timestamp != 0


def test_get_lines_pops_left(mock_config_false: MagicMock) -> None:
    emitter = WatcherEmitter(mock_config_false)
    emitter._metric_lines.append(Metric("metric.name", ["key1=test"], ["value=1"], 12))
    emitter._metric_lines.append(Metric("metric.name", ["key1=test"], ["value=2"], 12))
    lines = emitter._get_lines(max_lines=1)
    assert len(lines) == 1
    assert lines[0] == "metric.name,key1=test value=1 12"


def test_to_file(mock_config_true: MagicMock) -> None:
    lines = [
        "metric.name,key1=test value1=100 1234567890",
        "metric.name,key1=test value1=100 1234567890",
    ]
    try:
        fd, temp_file_name = tempfile.mkstemp()
        os.close(fd)  # close for Windows
        date = datetime.datetime.now().strftime("%Y%m%d")
        expected_file = f"{temp_file_name}_{date}_metric_lines.txt"
        mock_config_true.config_name = temp_file_name
        emitter = WatcherEmitter(mock_config_true)

        emitter.to_file(lines)

        with open(expected_file) as temp_file:
            results = temp_file.read()

    finally:
        os.remove(temp_file_name)
        os.remove(expected_file)

    assert results == (
        "metric.name,key1=test value1=100 1234567890\n"
        "metric.name,key1=test value1=100 1234567890\n"
    )


def test_to_file_early_exit(mock_config_false: MagicMock) -> None:
    try:
        fd, temp_file_name = tempfile.mkstemp()
        os.close(fd)  # close for Windows
        expected_file = f"{temp_file_name}_metric_lines.txt"
        mock_config_false.config_name = temp_file_name
        emitter = WatcherEmitter(mock_config_false)

        emitter.to_file(["empty"])

        assert not os.path.exists(expected_file)

    finally:
        os.remove(temp_file_name)


def test_to_stdout(mock_config_true: MagicMock) -> None:
    lines = [
        "metric.name,key1=test value1=100 1234567890",
        "metric.name,key1=test value1=100 1234567890",
    ]
    emitter = WatcherEmitter(mock_config_true)
    with redirect_stdout(StringIO()) as temp_file:
        emitter.to_stdout(lines)
        results = temp_file.getvalue()

    assert results == (
        "metric.name,key1=test value1=100 1234567890\n"
        "metric.name,key1=test value1=100 1234567890\n"
    )


def test_to_stdout_early_exit(mock_config_false: MagicMock) -> None:
    emitter = WatcherEmitter(mock_config_false)
    with redirect_stdout(StringIO()) as temp_file:
        emitter.to_stdout(["empty"])
        results = temp_file.getvalue()

    assert results == ""


def test_emit_lines_success(
    mock_config_true: MagicMock,
    caplog: LogCaptureFixture,
) -> None:
    lines = ["metric.name,key1=test value1=100 1234567890"]
    emitter = WatcherEmitter(mock_config_true)
    host = "mock.host"
    port = 1234
    path = "/mock/path"
    with patch("walk_watcher.watcheremitter.http.client.HTTPConnection") as mock_http:
        mock_http.return_value.getresponse.return_value.status = 204
        emitter._emit_lines(lines, host, port, path, [204])

    mock_http.assert_called_once_with(host=host, port=port, timeout=3)
    mock_http.return_value.request.assert_called_once_with(
        "POST",
        path,
        b"metric.name,key1=test value1=100 1234567890\n",
    )
    assert "Failed to emit" not in caplog.text


def test_emit_lines_failed(
    mock_config_true: MagicMock,
    caplog: LogCaptureFixture,
) -> None:
    emitter = WatcherEmitter(mock_config_true)
    host = "mock.host"
    port = 1234
    path = "/mock/path"
    with patch("walk_watcher.watcheremitter.http.client.HTTPConnection") as mock_http:
        mock_http.return_value.getresponse.return_value.status = 400
        emitter._emit_lines(["empty"], host, port, path, [204])

    mock_http.assert_called_once_with(host=host, port=port, timeout=3)
    mock_http.return_value.request.assert_called_once_with(
        "POST",
        path,
        b"empty\n",
    )
    assert "Failed to emit" in caplog.text


def test_emit_lines_early_exit(
    mock_config_false: MagicMock,
    caplog: LogCaptureFixture,
) -> None:
    emitter = WatcherEmitter(mock_config_false)
    host = "mock.host"
    port = 1234
    path = "/mock/path"
    with patch("walk_watcher.watcheremitter.http.client.HTTPConnection") as mock_http:
        emitter._emit_lines([], host, port, path, [204])

    assert mock_http.call_count == 0
    assert "Failed to emit" not in caplog.text


def test_to_telegraf(mock_config_true: MagicMock) -> None:
    lines = [
        "metric.name,key1=test value1=100 1234567890",
        "metric.name,key1=test value1=100 1234567890",
    ]
    emitter = WatcherEmitter(mock_config_true)

    with patch.object(emitter, "_emit_lines") as mock_emit:
        emitter.to_telegraf(lines)

    mock_emit.assert_called_once_with(
        metric_lines=lines,
        host=mock_config_true.telegraf_host,
        port=mock_config_true.telegraf_port,
        path=mock_config_true.telegraf_path,
        valid_status_codes=[204],
    )


def test_to_telegraf_early_exit(mock_config_false: MagicMock) -> None:
    emitter = WatcherEmitter(mock_config_false)
    with patch.object(emitter, "_emit_lines") as mock_emit:
        emitter.to_telegraf(["empty"])

    assert mock_emit.call_count == 0


def test_to_oneagent(mock_config_true: MagicMock) -> None:
    lines = [
        "metric.name,key1=test value1=100 1234567890",
        "metric.name,key1=test value2=100 1234567890",
    ]
    expected_lines = [
        "value1,key1=test 100 1234567890",
        "value2,key1=test 100 1234567890",
    ]
    emitter = WatcherEmitter(mock_config_true)

    with patch.object(emitter, "_emit_lines") as mock_emit:
        emitter.to_oneagent(lines)

    mock_emit.assert_called_once_with(
        metric_lines=expected_lines,
        host=mock_config_true.oneagent_host,
        port=mock_config_true.oneagent_port,
        path=mock_config_true.oneagent_path,
        valid_status_codes=[202],
    )


def test_to_oneagent_early_exit(mock_config_false: MagicMock) -> None:
    emitter = WatcherEmitter(mock_config_false)
    with patch.object(emitter, "_emit_lines") as mock_emit:
        emitter.to_oneagent(["empty"])

    assert mock_emit.call_count == 0
