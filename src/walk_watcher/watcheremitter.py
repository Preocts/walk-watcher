from __future__ import annotations

import dataclasses
import logging
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

    def __init__(self) -> None:
        """Initialize the emitter."""
        self._metric_lines: deque[Metric] = deque()
        self.emit_to_stdout = False
        self.emit_to_file = False
        self.file_name: str | None = None

    @classmethod
    def from_config(cls, config: WatcherConfig) -> WatcherEmitter:
        """Initialize the emitter from a config."""
        emitter = cls()
        emitter.emit_to_stdout = config.emit_stdout
        emitter.emit_to_file = config.emit_file
        emitter.file_name = config.metric_name
        return emitter

    def emit(self) -> None:
        """Emit the metric lines to the configured targets."""
        self.to_stdout()
        self.to_file()

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
        """
        self._metric_lines.append(
            Metric(
                metric_name=metric_name,
                dimensions=dimensions,
                guage_values=guage_values,
                timestamp=timestamp or int(datetime.now().timestamp()),
            )
        )

    def _get_lines(self, max_lines: int = 1_000) -> list[str]:
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

    def to_file(self) -> None:
        """
        Emit all added metric lines to a file in line protocol format.

        Args:
            filename: The name of the file to write to. If None, a filename
                will be generated based on the current date.
        """
        if not self.emit_to_file or not self._metric_lines:
            return

        _filename = datetime.now().strftime("%Y%m%d")
        filename = (self.file_name or _filename) + "_metric_lines.txt"
        count = 0

        with open(filename, "a") as file_out:
            while self._metric_lines:
                lines = self._get_lines()
                count += len(lines)
                file_out.write("\n".join(lines) + "\n")

        self.logger.info("Emitted %d lines to %s", count, filename)

    def to_stdout(self) -> None:
        """Emit all added metric lines to stdout in line protocol format."""
        if not self.emit_to_stdout or not self._metric_lines:
            return

        while self._metric_lines:
            print("\n".join(self._get_lines()))
