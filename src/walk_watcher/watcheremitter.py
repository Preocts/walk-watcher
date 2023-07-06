from __future__ import annotations

import dataclasses
import http.client
import logging
import re
from collections import deque
from datetime import datetime

from .watcherconfig import WatcherConfig


@dataclasses.dataclass(frozen=True)
class Metric:
    metric_name: str
    dimensions: list[str]
    guage_values: list[str]
    timestamp: int = 0


class WatcherEmitter:
    """A class to emit metrics to various targets."""

    logger = logging.getLogger(__name__)

    def __init__(self, config: WatcherConfig) -> None:
        """Initialize the emitter."""
        self._config = config
        self._metric_lines: deque[Metric] = deque()

    def emit(self, *, batch_size: int = 500) -> None:
        """
        Emit all stored metric lines to the configured targets. Empties the queue.

        Keyword Args:
            batch_size: The number of lines to emit at a time. Defaults to 500.
        """
        count = 0
        while self._metric_lines:
            lines = self._get_lines(batch_size)

            self.to_stdout(lines)
            self.to_file(lines)
            self.to_telegraf(lines)

            count += len(lines)

        self.logger.info(f"Emitted {count} metric lines.")

    def add_line(
        self,
        metric_name: str,
        dimensions: list[str],
        guage_values: list[str],
        timestamp: int = 0,
    ) -> None:
        """
        Add a line to the list of metric lines.

        Args:
            metric_name: The name of the metric.
            dimensions: A list of dimensions for the metric (aka keys/tags).
            guage_values: A list of guage values for the metric (aka fields).
            timestamp: The timestamp for the metric. If 0, the current time is used.
                This is expected to be in seconds and is converted to milliseconds.
        """
        self._metric_lines.append(
            Metric(
                metric_name=metric_name,
                dimensions=dimensions,
                guage_values=guage_values,
                timestamp=(timestamp or int(datetime.now().timestamp())) * 1000,
            )
        )

    def _get_lines(self, max_lines: int) -> list[str]:
        """Build a list of lines to emit, removing them from the emitter."""
        lines: list[str] = []
        while self._metric_lines and len(lines) < max_lines:
            metric = self._metric_lines.popleft()
            lines.append(
                f"{metric.metric_name},{','.join(metric.dimensions)} "
                f"{','.join(metric.guage_values)} "
                f"{metric.timestamp}"
            )

        return lines

    def to_file(self, metric_lines: list[str]) -> None:
        """
        Emit metric lines to a file in line protocol format.

        Args:
            metric_lines: A list of lines to emit.

        Output:
            A file named <config_name>_<date>_metric_lines.txt
        """
        if not self._config.emit_file or not metric_lines:
            return
        date = datetime.now().strftime("%Y%m%d")
        filename = f"{self._config.config_name}_{date}_metric_lines.txt"

        with open(filename, "a") as file_out:
            file_out.write("\n".join(metric_lines) + "\n")

        self.logger.debug("Emitted %d lines to %s", len(metric_lines), filename)

    def to_stdout(self, metric_lines: list[str]) -> None:
        """
        Emit metric lines to stdout in line protocol format.

        Args:
            metric_lines: A list of lines to emit.
        """
        if not self._config.emit_stdout or not metric_lines:
            return

        print("\n".join(metric_lines))

        self.logger.debug("Emitted %d lines to stdout", len(metric_lines))

    def to_telegraf(self, metric_lines: list[str]) -> None:
        """
        Emit metric lines to a telegraf listener.

        Args:
            metric_lines: A list of lines to emit.
        """
        if not self._config.emit_telegraf or not metric_lines:
            return

        self._emit_lines(
            metric_lines=metric_lines,
            host=self._config.telegraf_host,
            port=self._config.telegraf_port,
            path=self._config.telegraf_path,
            valid_status_codes=[204],
        )

    def to_oneagent(self, metric_lines: list[str]) -> None:
        """
        Emit metric lines to a Dynatrace OneAgent.

        Args:
            metric_lines: A list of lines to emit.
        """
        if not self._config.emit_oneagent or not metric_lines:
            return

        line_pattern = re.compile(r"[^,]+,([^\s]+)\s([^=]+)=(\d+)\s(\d+)")

        dt_lines = [line_pattern.sub(r"\2,\1 \3 \4", line) for line in metric_lines]

        self._emit_lines(
            metric_lines=dt_lines,
            host=self._config.oneagent_host,
            port=self._config.oneagent_port,
            path=self._config.oneagent_path,
            valid_status_codes=[202],
        )

    def _emit_lines(
        self,
        metric_lines: list[str],
        host: str,
        port: int,
        path: str,
        valid_status_codes: list[int],
    ) -> None:
        """Emit metric lines to a host."""
        if not metric_lines:
            return None

        payload = "\n".join(metric_lines) + "\n"

        conn = http.client.HTTPConnection(
            host=host,
            port=port,
            timeout=3,
        )
        conn.request("POST", path, payload.encode("utf-8"))

        response = conn.getresponse()
        if response.status not in valid_status_codes:
            self.logger.error(
                "Failed to emit %d lines to telegraf listener: %s",
                len(metric_lines),
                response.read(),
            )
        else:
            self.logger.debug(
                "Emitted %d lines to telegraf listener", len(metric_lines)
            )
