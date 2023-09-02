from __future__ import annotations

import logging
import os
import re
import time

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

        files, empty_dirs = self._walk_directories()

        with self._store as data_store:
            data_store.save_files(files)

            self._add_directory_file_count_lines(data_store, empty_dirs)
            self._add_directory_size_lines(data_store, empty_dirs)
            self._add_file_lines(data_store)

        toc = time.perf_counter()
        self.logger.info("Watcher finished in %s seconds", toc - tic)
        self.logger.info("Detected %s files", len(files))

    def emit(self) -> None:
        """Emit the current metrics of the watcher to defined outputs."""
        self.logger.info("Emitting metrics...")
        tic = time.perf_counter()

        self._emitter.emit()

        toc = time.perf_counter()
        self.logger.info("Emitting finished in %s seconds", toc - tic)

    def _add_directory_size_lines(
        self,
        datastore: WatcherStore,
        empty_dirs: list[Directory],
    ) -> None:
        """Add the directory lines with size in bytes to the emitter."""
        directories = datastore.get_directories()
        directories.extend(empty_dirs)

        for directory in directories:
            root = self._sanitize_directory_path(directory.root)
            dimension = f"root={root}"
            gauge_value = f"directory.size.bytes={directory.size_bytes}"
            self._emitter.add_line(
                metric_name=self._config.metric_name,
                dimensions=[self._config.dimensions, dimension],
                guage_values=[gauge_value],
            )

    def _add_directory_file_count_lines(
        self,
        datastore: WatcherStore,
        empty_dirs: list[Directory],
    ) -> None:
        """Add the directory lines with file count to the emitter."""
        directories = datastore.get_directories()
        directories.extend(empty_dirs)
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

    def _is_ignored_filename(self, filename: str) -> bool:
        """True if the filename is in the excluded pattern."""
        ptn = self._config.exclude_file_pattern
        if ptn and re.search(ptn, filename):
            return True

        return False

    def _is_ignored_directory(self, dirpath: str) -> bool:
        """True if the directory path is in the excluded pattern."""
        ptn = self._config.exclude_directory_pattern
        if ptn and re.search(ptn, dirpath):
            return True

        return False

    def _walk_directories(self) -> tuple[list[File], list[Directory]]:
        """
        Walk the root directory and return the files and empty directories.

        Returns:
            A tuple of files and empty directories.
        """
        target_directories = self._config.root_directories

        files: list[File] = []
        empty_dirs: list[Directory] = []

        for root in target_directories:
            self.logger.debug("Walking directory: %s", root)

            for dirpath, _, filenames in os.walk(root):
                if self._is_ignored_directory(dirpath):
                    self.logger.debug("Ignoring directory '%s'", root)
                    continue

                file_models = self._build_file_models(dirpath, filenames)

                # Track empty directories that were not ignored
                if not len(file_models):
                    empty_dirs.append(Directory(dirpath, 0, 0))

                files.extend(file_models)

        return files, empty_dirs

    def _build_file_models(self, dirpath: str, filenames: list[str]) -> list[File]:
        """Parses the filenames into File objects."""
        now = int(time.time())
        files: list[File] = []

        for filename in filenames:
            if self._is_ignored_filename(filename):
                self.logger.debug("Ignoring file `%s`", filename)
                continue

            filepath = os.path.join(dirpath, filename)

            try:
                firstseen = self._get_first_seen(filepath, now)
                size_in_bytes = self._get_file_size_in_bytes(filepath)

            except FileNotFoundError:
                # The file has been moved after the walk completed
                self.logger.debug("'%s' moved during walk.", filepath)
                continue

            files.append(
                File(
                    root=dirpath,
                    filename=filename,
                    first_seen=firstseen,
                    last_seen=now,
                    size_bytes=size_in_bytes,
                )
            )

        self.logger.debug("Found %s files", len(files))

        return files

    def _get_first_seen(self, filepath: str, now: int) -> int:
        """
        Defaults to returning now. If treat_files_as_new is set, returns ctime().

        Raises:
            FileNotFoundError
        """
        if self._config.treat_files_as_new:
            # Files are newly created between queues, safe to use ctime for timestamp
            return int(os.path.getctime(filepath))

        # Files are moved between queues, Windows fails to report ctime correctly
        return now

    def _get_file_size_in_bytes(self, filepath: str) -> int:
        """
        Return the reported file size of the file.

        Raises:
            FileNotFoundError
        """
        return os.path.getsize(filepath)

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
