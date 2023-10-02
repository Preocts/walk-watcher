[![Python 3.8 | 3.9 | 3.10 | 3.11 | 3.12](https://img.shields.io/badge/Python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/downloads)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Preocts/walk-watcher/main.svg)](https://results.pre-commit.ci/latest/github/Preocts/walk-watcher/main)
[![Python tests](https://github.com/Preocts/walk-watcher/actions/workflows/python-tests.yml/badge.svg?branch=main)](https://github.com/Preocts/walk-watcher/actions/workflows/python-tests.yml)

# walk-watcher

A monitoring solution when directories and files are used as queues. Tracks the
number of files in a directory and the oldest age of a file in the directory.

The emitted metrics are in line protocal format with an interval size of
milliseconds. This should be compatible with most ingest agents.

## Supported output

- stdout
- file target
- telegraf agent
- Dynatrace OneAgent

## Limitation: file age

As this was designed to track files moving through a queue of directories is it
assumed that the file is being moved instead of being created new. Because of
this there is a limitation on determining the age of the file. While linux
systems will return the last time a file was moved in the modified date of the
file, Windows systems do not. In fact, there is no easy way to get that
information from a Windows filesystem.

Because of this, file age is based on the first time the watcher sees the file
and not when the file was created. This means that on startup the file ages will
not be as accurate as they are after the watcher has been running. The length of
time for the accuracy to increase depends on the rate at which the files move
through the directory queues.

This default behavior can altered with the configration file. By setting
`treat_files_as_new = true` the first seen timestamp will look at the file
creation time.

## Installation

```console
$ pip install git+https://github.com/Preocts/walk-watcher@x.x.x
```

*replace `@x.x.x` with the desired tag version or `@main` for latest (unstable)*

## CLI use

```console
$ walk-watcher --help
usage: walk-watcher [-h] [--loop] [--debug] [--make-config] config

Watch directories for file count and oldest file age. Emit to configured destinations.

positional arguments:
  config         The path to the configuration file.

optional arguments:
  -h, --help     show this help message and exit
  --loop         Run the watcher in a loop. Default: False (block until exit).
  --debug        Enable debug logging.
  --make-config  Create a default configuration file.
```

1. $ `walk-watcher config-file-name.ini --make-config`
2. Edit config file to track desired directories
3. Selected desired emitted outputs
4. $ `walk-watcher config-file-name.ini [--loop]`

---

## Configuration

### \[system\]

| key                      | value                                                                                                             |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `config_name`            | A unique name for the configuration                                                                               |
| `database_path`          | Name and path of the sqlite3 database file. Used for file age tracking. Set to `:memory:` for in-memory database. |
| `max_is_running_seconds` | Time before the database lock expires. Prevents jobs from attempting to access the sqlite3 simultaneously.        |
| `max_emit_line_count`    | Maximum number of metric lines emitted in a single batch.                                                         |
| `treat_files_as_new`     | When true, create time is used for first_seen.                                                                    |

### \[intervals\]

| key                | value                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------------- |
| `collect_interval` | Number of seconds between collecting meterics (`--loop` mode only)                                |
| `emit_interval`    | Number of seconds between emitting meterics. All cached metrics are emitted. (`--loop` mode only) |

### \[dimensions\]

| key                   | value             |
| --------------------- | ----------------- |
| `some.dimension.name` | some.static.value |

Optional, additional dimensions to add in the metric line. Added as `key=value`.
Spaces are not permitted.

### \[watcher\]

| key                   | value                                                   |
| --------------------- | ------------------------------------------------------- |
| `metric_name`         | Name of the metric being emitted                        |
| `root_directories`    | Location of the directories to scan for files           |
| `exclude_directories` | regex expression of directories to exclude from walking |
| `exclude_files`       | regex expression of files to exclude from tracking      |

### \[emit\]

| key             | value                                                                            |
| --------------- | -------------------------------------------------------------------------------- |
| `file`          | When true metrics lines are emitted to `<config_name>_<YYmmdd>_metric_lines.txt` |
| `stdout`        | When true metric lines are emitted to standard out (console)                     |
| `telegraf`      | When true metric lines are emitted to a local telegraf agent                     |
| `telegraf_host` | defaults to `127.0.0.1`                                                          |
| `telegraf_port` | defaults to `8080`                                                               |
| `telegraf_path` | defaults to `/telegraf`                                                          |
| `oneagent`      | When true metric lines are emitted to a local Dynatrace OneAgent agent           |
| `oneagent_host` | defaults to `127.0.0.1`                                                          |
| `oneagent_port` | defaults to `14499`                                                              |
| `oneagent_path` | defaults to `/metrics/ingest`                                                    |

---

# Local developer installation

It is **strongly** recommended to use a virtual environment
([`venv`](https://docs.python.org/3/library/venv.html)) when working with python
projects. Leveraging a `venv` will ensure the installed dependency files will
not impact other python projects or any system dependencies.

The following steps outline how to install this repo for local development. See
the [CONTRIBUTING.md](CONTRIBUTING.md) file in the repo root for information on
contributing to the repo.

**Windows users**: Depending on your python install you will use `py` in place
of `python` to create the `venv`.

**Linux/Mac users**: Replace `python`, if needed, with the appropriate call to
the desired version while creating the `venv`. (e.g. `python3` or `python3.8`)

**All users**: Once inside an active `venv` all systems should allow the use of
`python` for command line instructions. This will ensure you are using the
`venv`'s python and not the system level python.

---

## Installation steps

Clone this repo and enter root directory of repo:

```console
$ git clone https://github.com/Preocts/walk-watcher
$ cd walk-watcher
```

Create the `venv`:

```console
$ python -m venv venv
```

Activate the `venv`:

```console
# Linux/Mac
$ . venv/bin/activate

# Windows
$ venv\Scripts\activate
```

The command prompt should now have a `(venv)` prefix on it. `python` will now
call the version of the interpreter used to create the `venv`

Install editable library and development requirements:

```console
$ python -m pip install --editable .[dev,test]
```

Install pre-commit [(see below for details)](#pre-commit):

```console
$ pre-commit install
```

---

## Misc Steps

Run pre-commit on all files:

```console
$ pre-commit run --all-files
```

Run tests (quick):

```console
$ pytest
```

Run tests (slow):

```console
$ nox
```

Build dist:

```console
$ python -m pip install --upgrade build

$ python -m build
```

To deactivate (exit) the `venv`:

```console
$ deactivate
```

---

## [pre-commit](https://pre-commit.com)

> A framework for managing and maintaining multi-language pre-commit hooks.

This repo is setup with a `.pre-commit-config.yaml` with the expectation that
any code submitted for review already passes all selected pre-commit checks.
`pre-commit` is installed with the development requirements and runs seemlessly
with `git` hooks.

---

## Error: File "setup.py" not found.

If you recieve this error while installing an editible version of this project you have two choices:

1. Update your `pip` to *at least* version 22.3.1
2. Add the following empty `setup.py` to the project if upgrading pip is not an option

```py
from setuptools import setup

setup()
```
