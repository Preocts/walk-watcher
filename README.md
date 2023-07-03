[![Python 3.8 | 3.9 | 3.10 | 3.11](https://img.shields.io/badge/Python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11-blue)](https://www.python.org/downloads)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Preocts/walk-watcher/main.svg)](https://results.pre-commit.ci/latest/github/Preocts/walk-watcher/main)
[![Python tests](https://github.com/Preocts/walk-watcher/actions/workflows/python-tests.yml/badge.svg?branch=main)](https://github.com/Preocts/walk-watcher/actions/workflows/python-tests.yml)

# walk-watcher

A monitoring solution when directories and files are used as queues. Tracks the
number of files in a directory and the oldest age of a file in the directory.

The emitted metrics are in line protocal format with an interval size of
seconds. This should be compatible with most ingest agents.

## Supported output

- stdout
- file target

## Installation

```console
$ pip install git+https://github.com/Preocts/walk-watcher@0.1.0
```

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

### Makefile

This repo has a Makefile with some quality of life scripts if the system
supports `make`.  Please note there are no checks for an active `venv` in the
Makefile.  If you are on Windows you can install make using scoop or chocolatey.

| PHONY         | Description                                                           |
| ------------- | --------------------------------------------------------------------- |
| `install-dev` | install development/test requirements and project as editable install |
| `update-dev`  | regenerate requirements-*.txt (will keep existing pins)               |
| `upgrade-dev` | attempt to update all dependencies, regenerate requirements-*.txt     |
| `coverage`    | Run tests with coverage, generate console report                      |
| `docker-test` | Run coverage and tests in a docker container.                         |
| `build-dist`  | Build source distribution and wheel distribution                      |
| `clean`       | Deletes build, tox, coverage, pytest, mypy, cache, and pyc artifacts  |


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

### With Makefile:

```console
make install-dev
```

### Without Makefile:

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
$ tox
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

## Updating dependencies

New dependencys can be added to the `requirements-*.in` file. It is recommended
to only use pins when specific versions or upgrades beyond a certain version are
to be avoided. Otherwise, allow `pip-compile` to manage the pins in the
generated `requirements-*.txt` files.

Once updated following the steps below, the package can be installed if needed.

### With Makefile

To update the generated files with a dependency:

```console
make update-dev
```

To attempt to upgrade all generated dependencies:

```console
make upgrade-dev
```

### Without Makefile

To update the generated files with a dependency:

```console
pip-compile --no-emit-index-url requirements/requirements.in
pip-compile --no-emit-index-url requirements/requirements-dev.in
pip-compile --no-emit-index-url requirements/requirements-test.in
```

To attempt to upgrade all generated dependencies:

```console
pip-compile --upgrade --no-emit-index-url requirements/requirements.in
pip-compile --upgrade --no-emit-index-url requirements/requirements-dev.in
pip-compile --upgrade --no-emit-index-url requirements/requirements-test.in
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
