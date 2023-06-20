from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime

from .watcherconfig import WatcherConfig
from .watcherstore import Directory
from .watcherstore import File
from .watcherstore import WatcherStore


class WalkWatcher:
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

    def run(self) -> None:
        """Run the watcher, walking the directory and saving the results."""
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

        toc = time.perf_counter()
        self.logger.info("Watcher finished in %s seconds", toc - tic)
        self.logger.info("Detected %s directories", len(directories))
        self.logger.info("Detected %s files", len(files))

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
        root = self._config.root_directory
        remove_prefix = self._config.remove_prefix

        files: list[File] = []
        directories: list[Directory] = []

        for dirpath, _, filenames in os.walk(root):
            now = int(datetime.now().timestamp())
            if remove_prefix:
                dirpath = dirpath.lstrip(remove_prefix)
                dirpath = dirpath or "/"

            directories.append(Directory(dirpath, now, len(filenames)))
            files.extend([File(dirpath, filename, now) for filename in filenames])

        self.logger.debug("Found %s directories", len(directories))
        self.logger.debug("Found %s files", len(files))

        return directories, files
