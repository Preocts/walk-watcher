from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime

from .watcherconfig import WatcherConfig
from .watcheremitter import WatcherEmitter
from .watchermodel import Directory
from .watchermodel import File
from .watcherstore import WatcherStore


class Watcher:
    """Track file counts and file ages for a given directory."""

    logger = logging.getLogger(__name__)

    def __init__(self, config: WatcherConfig) -> None:
        """
        Initialize a new WalkWatcher.

        Args:
            config: The configuration to use for this watcher.

        NOTE: The config should not be used by multiple instances of this
            class. This is because the config is used to determine the
            database path and we don't want multiple instances of this class
            writing to the same database.
        """
        self._config = config
        self._store = WatcherStore.from_config(config)
        self._emitter = WatcherEmitter(config)

    def run_once(self) -> None:
        """Run the watcher once."""
        self.walk()
        self.emit()

    def run_loop(self) -> None:
        """Run the watcher untli ctrl-c is pressed. This is blocking."""
        next_walk = time.time() + self._config.collect_interval
        next_emit = time.time() + self._config.emit_interval

        self.logger.info("Starting watcher...")
        try:
            while True:
                if time.time() >= next_walk:
                    self.walk()
                    next_walk = time.time() + self._config.collect_interval

                if time.time() >= next_emit:
                    self.emit()
                    next_emit = time.time() + self._config.emit_interval

                time.sleep(0.1)

        except KeyboardInterrupt:
            self.logger.info("Watcher stopped")

        except Exception as error:
            self.logger.exception("Watcher stopped due to an error: %s", error)
            raise error

    def walk(self) -> None:
        """Walk the given directory and store the results."""
        self.logger.info("Running watcher...")
        tic = time.perf_counter()

        with self._store as data_store:
            directories, files = self._walk_directories()

            self.logger.debug("Filtering and Saving file data...")
            files = self._filter_files(files)
            data_store.save_files(files)

            self.logger.debug("Filtering and Saving directory data...")
            directories = self._filter_directories(directories)
            data_store.save_directories(directories)

            self._add_directory_lines(data_store)
            self._add_file_lines(data_store)

        toc = time.perf_counter()
        self.logger.info("Watcher finished in %s seconds", toc - tic)
        self.logger.info("Detected %s directories", len(directories))
        self.logger.info("Detected %s files", len(files))

    def emit(self) -> None:
        """Emit the current metrics of the watcher to defined outputs."""
        self.logger.info("Emitting metrics...")
        tic = time.perf_counter()

        self._emitter.emit()

        toc = time.perf_counter()
        self.logger.info("Emitting finished in %s seconds", toc - tic)

    def _add_directory_lines(self, datastore: WatcherStore) -> None:
        """Add the directory lines to the emitter."""
        directories = datastore.get_directory_rows()
        for directory in directories:
            root = self._sanitize_directory_path(directory.root)
            dimension = f"root={root}"
            gauge_value = f"directory.file.count={directory.file_count}"
            self._emitter.add_line(
                metric_name=self._config.metric_name,
                dimensions=[self._config.dimensions, dimension],
                guage_values=[gauge_value],
            )

    def _add_file_lines(self, datastore: WatcherStore) -> None:
        """Add the file lines to the emitter."""
        files = datastore.get_oldest_files()
        for file in files:
            root = self._sanitize_directory_path(file.root)
            dimension = f"oldest.file.seconds={root}"
            guage_value = f"oldest.file.seconds={file.age_seconds}"
            dimension = f"root={root}"
            self._emitter.add_line(
                metric_name=self._config.metric_name,
                dimensions=[self._config.dimensions, dimension],
                guage_values=[guage_value],
            )

    def _filter_files(self, files: list[File]) -> list[File]:
        """Filter the given files based on the config."""
        if not self._config.exclude_file_pattern:
            return files

        exlude_ptn = re.compile(self._config.exclude_file_pattern)

        return [file for file in files if not exlude_ptn.search(file.filename)]

    def _filter_directories(self, directories: list[Directory]) -> list[Directory]:
        """Filter the given directories based on the config."""
        if not self._config.exclude_directory_pattern:
            return directories
        exlude_ptn = re.compile(self._config.exclude_directory_pattern)

        return [
            directory
            for directory in directories
            if not exlude_ptn.search(directory.root)
        ]

    def _walk_directories(self) -> tuple[list[Directory], list[File]]:
        """
        Walk the root directory and return the directories and files.

        Returns:
            A tuple of directories and files.
        """
        target_directories = self._config.root_directories

        files: list[File] = []
        directories: list[Directory] = []

        for root in target_directories:
            self.logger.debug("Walking directory: %s", root)

            for dirpath, _, filenames in os.walk(root):
                now = int(datetime.now().timestamp())

                directories.append(Directory(dirpath, now, len(filenames)))
                files.extend([File(dirpath, filename, now) for filename in filenames])

            self.logger.debug("Found %s directories", len(directories))
            self.logger.debug("Found %s files", len(files))

        return directories, files

    @staticmethod
    def _sanitize_directory_path(path: str) -> str:
        """
        Remove invalid characters from a directory path and double backslashes.

        Args:
            path: The directory path to sanitize.

        Returns:
            The sanitized directory path.
        """
        path = re.sub(r"\s+", "_", path)
        path = path.replace("\\", "\\\\")
        return re.sub(r"[^a-zA-Z0-9\/\\_:]", "", path)
