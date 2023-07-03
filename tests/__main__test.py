from __future__ import annotations

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
