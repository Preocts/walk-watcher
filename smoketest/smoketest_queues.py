from __future__ import annotations

import argparse
import logging
import random
import shutil
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from string import ascii_lowercase
from typing import Any

BASE_DIR: Path = Path(__file__).resolve().parent
TEST_DIR: Path = BASE_DIR / "smoketest_queues"
FILE_COUNT_RANGE: tuple[int, int] = (1, 100)
CHANCE_OF_FAILURE = 0.1  # out of 1.0
MAX_SECONDS_TO_PROCESS = 30

# Time intervals in seconds
FILE_CREATE_INTERVAL = 10
FILE_MOVE_INTERVAL = 5
RETRY_INTERVAL = 30
OUTPUT_INTERVAL = 10

QUEUE_FOLDERS: dict[str, Any] = {
    "initial_documents": {
        "paths": [
            TEST_DIR / Path("initial_documents_stage1"),
            TEST_DIR / Path("initial_documents_stage2"),
            TEST_DIR / Path("initial_documents_stage3"),
        ],
        "retry": TEST_DIR / Path("initial_documents_retry"),
        "dead_letter": TEST_DIR / Path("initial_documents_dead_letter"),
        "max_retries": 3,
        "processed_count": 0,
    },
    "final_documents": {
        "paths": [
            TEST_DIR / Path("final_documents"),
            TEST_DIR / Path("final_documents_stage2"),
        ],
        "retry": TEST_DIR / Path("final_documents_retry"),
        "dead_letter": TEST_DIR / Path("final_documents_dead_letter"),
        "max_retries": 3,
        "processed_count": 0,
    },
    "additional_documents": {
        "paths": [TEST_DIR / Path("additional_documents")],
        "retry": TEST_DIR / Path("additional_documents_retry"),
        "dead_letter": TEST_DIR / Path("additional_documents_dead_letter"),
        "max_retries": 3,
        "processed_count": 0,
    },
}


# Enum class for four stages of file state
class FileState(Enum):
    WAITING = 1
    PROCESSED = 2
    RETRY = 3
    DEAD_LETTER = 4


logger = logging.getLogger(__name__)


def build_smoketest_directories() -> None:
    """Create the directories for the smoketest."""
    for folder in QUEUE_FOLDERS.values():
        for path in folder["paths"]:
            logger.debug("Creating %s", path)
            path.mkdir(parents=True, exist_ok=True)

        logger.debug("Creating %s", folder["retry"])
        folder["retry"].mkdir(parents=True, exist_ok=True)

        logger.debug("Creating %s", folder["dead_letter"])
        folder["dead_letter"].mkdir(parents=True, exist_ok=True)


def destroy_smoketest_directories() -> None:
    """Delete the directories for the smoketest."""
    logger.debug("Deleting %s", TEST_DIR)
    shutil.rmtree(TEST_DIR)


def _file_content() -> str:
    """File content for the smoketest."""
    # This is a random timestamp of then the file can progress to the next stage.
    # If this is 0 then the file will move to retry.
    is_failure = random.random() < CHANCE_OF_FAILURE

    if is_failure:
        return "0"

    time_to_process = random.randint(1, MAX_SECONDS_TO_PROCESS)
    return str(int(time.time()) + time_to_process)


def _file_name() -> str:
    """Create a random eight character file name."""
    return "".join(random.choices(ascii_lowercase, k=8))


def _move_file(file: Path, destination: Path, new_file_name: str | None = None) -> None:
    """Move the file to the destination, optionally renaming it."""
    file.write_text(_file_content())

    if new_file_name:
        destination = destination / Path(new_file_name)
    else:
        destination = destination / file.name

    logger.info("Moving %s to %s", file, destination)
    file.rename(destination)


def create_files_in_queue_dirctory(directory_name: str) -> None:
    """Create files in the queue directory."""
    # All files start in the first of any listed paths.
    folder = QUEUE_FOLDERS[directory_name]
    paths = folder["paths"]
    file_count = random.randint(*FILE_COUNT_RANGE)

    logger.info("Creating %s files in %s", file_count, paths[0])

    for _ in range(file_count):
        path = paths[0]
        file_name = _file_name()
        file_path = path / Path(file_name)
        file_path.write_text(_file_content())


def get_file_state(filename: str) -> FileState:
    """Read the file to see if it can move to the next stage."""
    file_content = Path(filename).read_text()
    file_state = FileState.WAITING

    if file_content == "0" or not file_content:
        file_state = FileState.RETRY
    elif int(file_content) <= int(time.time()):
        file_state = FileState.PROCESSED

    return file_state


def rename_for_retry(filepath: Path) -> tuple[str, int]:
    """Rename the file for retry and return the number of retries."""
    # File names are appended with "-{retry_count}"
    file_name = filepath.stem
    retry_count = 0

    if "-" in file_name:
        file_name, retry_count_str = file_name.split("-")
        retry_count = int(retry_count_str)

    retry_count += 1
    new_file_name = f"{file_name}-{retry_count}"

    return new_file_name, retry_count


def thread_file_creator(directory_name: str, stop_flag: threading.Event) -> None:
    """Thread handler: Create files in the queue directory at a regular interval."""
    next_run = time.time() + FILE_CREATE_INTERVAL

    while not stop_flag.is_set():
        if time.time() < next_run:
            time.sleep(1)
            continue
        next_run = time.time() + FILE_CREATE_INTERVAL

        logger.info("Creating files in %s", directory_name)
        create_files_in_queue_dirctory(directory_name)


def thread_file_mover(directory_name: str, stop_flag: threading.Event) -> None:
    """Thread handler: Move files between stages."""
    folder = QUEUE_FOLDERS[directory_name]
    paths = folder["paths"]
    retry = folder["retry"]
    dead_letter = folder["dead_letter"]
    max_retries = folder["max_retries"]
    next_run = time.time() + FILE_MOVE_INTERVAL

    while not stop_flag.is_set():
        if time.time() < next_run:
            time.sleep(1)
            continue
        next_run = time.time() + FILE_MOVE_INTERVAL

        logger.info("Moving files in %s", paths[0])
        for idx, path in enumerate(paths):
            for file in path.iterdir():
                file_state = get_file_state(file)

                if file_state == FileState.PROCESSED:
                    if idx + 1 < len(paths):
                        logger.debug("Moving %s to %s", file, paths[idx + 1])
                        _move_file(file, paths[idx + 1])

                    else:
                        logger.debug("Deleting %s", file)
                        folder["processed_count"] += 1
                        file.unlink()

                elif file_state == FileState.RETRY:
                    new_file_name, retry_count = rename_for_retry(file)
                    if retry_count < max_retries:
                        logger.debug("Moving %s to %s", file, retry)
                        _move_file(file, retry, new_file_name)
                    else:
                        logger.debug("Moving %s to %s", file, dead_letter)
                        _move_file(file, dead_letter, new_file_name)


def thread_redrive(directory_name: str, stop_flag: threading.Event) -> None:
    """Move files from retry to the first queue directory."""
    folder = QUEUE_FOLDERS[directory_name]
    paths = folder["paths"]
    retry = folder["retry"]
    next_run = time.time() + RETRY_INTERVAL

    while not stop_flag.is_set():
        if time.time() < next_run:
            time.sleep(1)
            continue
        next_run = time.time() + RETRY_INTERVAL

        logger.info("Redriving files in %s", retry)
        for file in retry.iterdir():
            _move_file(file, paths[0])


def thread_output_count_of_files(stop_flag: threading.Event) -> None:
    """Output the number of files in each directory."""
    # Sleep a moment to let the other threads start.
    time.sleep(1)
    next_run = time.time() + OUTPUT_INTERVAL

    while not stop_flag.is_set():
        if time.time() < next_run:
            time.sleep(1)
            continue
        next_run = time.time() + OUTPUT_INTERVAL

        print("*" * 79)
        for directory_name in QUEUE_FOLDERS:
            folder = QUEUE_FOLDERS[directory_name]
            paths = folder["paths"]
            retry = folder["retry"]
            dead_letter = folder["dead_letter"]
            print(f"Directory: {directory_name}")
            path_file_count = [
                f"\t{path.parts[-1]}: {len(list(path.iterdir()))}" for path in paths
            ]
            print("\n".join(path_file_count))
            print(f"\tretry: {len(list(retry.iterdir()))}")
            print(f"\tdead_letter: {len(list(dead_letter.iterdir()))}")
            print(f"\ttotal processed: {folder['processed_count']}")
        print("*" * 79)


def parse_args() -> tuple[str, bool]:
    """Parse command line arguments, return log level and verbose flag."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="ERROR",
        help="Set the logging level.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Output the number of files in each directory on a regular interval.",
    )
    args = parser.parse_args()
    return args.log_level, args.verbose


def start_threads(
    stop_flag: threading.Event,
    verbose: bool = False,
) -> list[threading.Thread]:
    """Start all threads."""
    threads = []
    for directory_name in QUEUE_FOLDERS:
        threads.append(
            threading.Thread(
                target=thread_file_creator,
                args=(directory_name, stop_flag),
            )
        )
        threads[-1].start()

        threads.append(
            threading.Thread(
                target=thread_file_mover,
                args=(directory_name, stop_flag),
            )
        )
        threads[-1].start()

        threads.append(
            threading.Thread(
                target=thread_redrive,
                args=(directory_name, stop_flag),
            )
        )
        threads[-1].start()

    if verbose:
        threads.append(
            threading.Thread(
                target=thread_output_count_of_files,
                args=(stop_flag,),
            )
        )
        threads[-1].start()

    return threads


def stop_threads(threads: list[threading.Thread]) -> None:
    """Join all threads, allowing them to stop."""
    for thread in threads:
        thread.join()


@contextmanager
def smoketest_runner(verbose: bool = False) -> Generator[None, None, None]:
    """Run the smoketest."""
    stop_flag = threading.Event()

    logger.debug("Building smoketest directories...")
    build_smoketest_directories()

    try:
        logger.debug("Starting threads...")
        threads = start_threads(stop_flag, verbose)

        yield None

    finally:
        logger.debug("Stopping threads...")
        stop_flag.set()
        stop_threads(threads)
        logger.debug("Destroying smoketest directories...")
        destroy_smoketest_directories()


def run() -> int:
    """Main function - blocking."""
    level, verbose = parse_args()
    logging.basicConfig(level=level, format="%(asctime)s %(message)s")

    with smoketest_runner(verbose):
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
