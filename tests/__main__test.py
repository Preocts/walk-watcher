from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

from walk_watcher import __main__


def test_parse_arges():
    args = __main__.parse_args(["config", "--loop"])
    assert args.config == "config"
    assert args.loop is True


def test_parse_arges_no_loop():
    args = __main__.parse_args(["config"])
    assert args.config == "config"
    assert args.loop is False


def test_main_no_loop():
    cli_args = ["tests/test_config.ini"]

    with patch("walk_watcher.__main__.Watcher.run_once") as mock_watcher:
        result = __main__.main(cli_args=cli_args)

    assert result == 0
    assert mock_watcher.call_count == 1


def test_main_loop():
    cli_args = ["tests/test_config.ini", "--loop"]

    with patch("walk_watcher.__main__.Watcher.run_loop") as mock_watcher:
        result = __main__.main(cli_args=cli_args)

    assert result == 0
    assert mock_watcher.call_count == 1


def test_main_create_config():
    cli_args = ["tests/new_test_config.ini", "--make-config"]

    with patch("walk_watcher.__main__.write_new_config") as mock_watcher:
        result = __main__.main(cli_args=cli_args)

    assert result == 0
    mock_watcher.assert_called_once_with("tests/new_test_config.ini")


def test_main_creates_log_file_with_config():
    cli_args = ["tests/test_config.ini", "--log-file"]

    try:
        with patch("walk_watcher.__main__.Watcher.run_once") as mock_watcher:
            result = __main__.main(cli_args=cli_args)

        assert result == 0
        assert mock_watcher.call_count == 1
        assert Path("tests/test_config.log").exists()

    finally:
        for handler in logging.root.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.close()
                logging.root.handlers.remove(handler)

        Path("tests/test_config.log").unlink(missing_ok=True)
