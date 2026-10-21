"""
Input handling shared by the checker and the generator of the coverage gate.

Every input is bounded before it is decoded: a file is refused on its size before it is opened, then read no further
than its bound. Every defect of an input raises InputError, which the commands turn into exit code 2 with its cause.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Any, NamedTuple

# Bounds in bytes, checked on the size of a file before it is read. Measured on 2026-10-14, the whole suite measuring
# src/, tools/ and RegexLab.py: the JSON report weighed 272,038 bytes (coverage 7.6.1) and 341,849 bytes (7.16.2), the
# table of its 32 modules 4,852 bytes, the largest measured module 82,513 bytes.
MAX_REPORT_BYTES = 16 * 1024 * 1024
MAX_TABLE_BYTES = 1024 * 1024
MAX_SOURCE_BYTES = 1024 * 1024

# Bound in digits, checked on each integer of a JSON input before it is converted. The value is CPython's default
# bound, which an interpreter older than 3.8.14 does not apply, and which PYTHONINTMAXSTRDIGITS can lift.
MAX_INTEGER_DIGITS = 4300

TABLE_FORMAT = 1
TABLE_KEYS = ("branch_coverage_version", "cells", "format", "modules")
ENTRY_KEYS = ("excluded_lines", "missing_branches", "missing_lines", "pragmas")
CELL_NAME = re.compile(r"[A-Za-z0-9._-]+")

# The two coverage pragmas, assembled from parts: written whole in a measured file, they would make coverage.py exclude
# the very line that holds them, and the gate would count that line.
PRAGMAS = (b"pragma: no " + b"cover", b"pragma: no " + b"branch")

# The measured code, relative to the repository root: every .py file under these directories, and this file.
MEASURED_DIRECTORIES = ("src", "tools")
MEASURED_FILE = "RegexLab.py"
SKIPPED_DIRECTORY = "__pycache__"

_ABSENT = object()  # the value of a missing key, in messages


class InputError(Exception):
    """An input cannot be used as it is: the command exits 2 with this message."""


class Summary(NamedTuple):
    """The counts of one file in a coverage.py JSON report (its "summary")."""

    covered_lines: int
    num_statements: int
    missing_lines: int
    covered_branches: int
    num_branches: int
    missing_branches: int
    excluded_lines: int


class Report(NamedTuple):
    """A coverage.py JSON report: its path, the coverage.py version that wrote it, and its files, keyed by module."""

    path: str
    version: str
    files: dict[str, Summary]


class Entry(NamedTuple):
    """One module of the table: its two ceilings and its two frozen counts."""

    missing_lines: int
    missing_branches: int
    excluded_lines: int
    pragmas: int


class Table(NamedTuple):
    """The table of the gate (format 1)."""

    branch_coverage_version: str
    cells: list[str]
    modules: dict[str, Entry]


def printable(text: str) -> str:
    """The text, every character outside printable ASCII escaped: the output stays plain ASCII, one line per item."""
    return "".join(char if " " <= char <= "~" else ascii(char)[1:-1] for char in text)


def plural(count: int, word: str) -> str:
    """'1 module', '2 modules'."""
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def normalise(key: str) -> str:
    """A module path with "/" separators: coverage.py writes "\\" on Windows."""
    return key.replace("\\", "/")


def file_size(path: str) -> int:
    """The size of the file in bytes (a function of its own, so that a test can make the file grow after the check)."""
    return os.stat(path).st_size


def read_bounded(path: str, limit: int, what: str) -> bytes:
    """The bytes of the file, refused over limit: on its size before it is opened, then on what reading returned."""
    try:
        size = file_size(path)
    except OSError as exc:
        raise InputError(f"cannot read the {what} {path}: {exc}") from exc
    if size > limit:
        raise InputError(f"the {what} {path} weighs {size} bytes, over its bound of {limit} bytes")
    try:
        with open(path, "rb") as stream:
            data = stream.read(limit + 1)
    except OSError as exc:
        raise InputError(f"cannot read the {what} {path}: {exc}") from exc
    if len(data) > limit:
        raise InputError(f"the {what} {path} grew over its bound of {limit} bytes while it was read")
    return data


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """An object of the JSON document, every key once (json.loads would keep the last value of a repeated key)."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {json.dumps(key)}")
        result[key] = value
    return result


def _bounded_integer(text: str) -> int:
    """An integer of the JSON document, refused over MAX_INTEGER_DIGITS digits before it is converted."""
    digits = len(text.lstrip("-"))
    if digits > MAX_INTEGER_DIGITS:
        raise ValueError(f"an integer of {digits} digits, over its bound of {MAX_INTEGER_DIGITS} digits")
    return int(text)


def read_json(path: str, limit: int, what: str) -> Any:
    """The JSON document of the file: bounded, UTF-8, every key once, no integer over MAX_INTEGER_DIGITS digits.

    The digits of an integer are counted before it is converted, whatever bound the interpreter applies: a longer one
    raises ValueError, refused here like any other invalid JSON.
    """
    data = read_bounded(path, limit, what)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"the {what} {path} is not valid UTF-8: {exc}") from exc
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicates, parse_int=_bounded_integer)
    except (ValueError, RecursionError) as exc:
        raise InputError(f"the {what} {path} is not valid JSON: {exc}") from exc


def _shown(value: object) -> str:
    """A short rendering of a JSON value, for a message."""
    if value is _ABSENT:
        return "no value (missing key)"
    if isinstance(value, dict):
        return "an object"
    if isinstance(value, list):
        return "an array"
    text = json.dumps(value)
    return text if len(text) <= 40 else text[:37] + "..."


def _object(value: object, where: str) -> dict[str, Any]:
    """value, which must be a JSON object."""
    if isinstance(value, dict):
        return value
    raise InputError(f"{where} must be an object, got {_shown(value)}")


def _count(value: object, where: str) -> int:
    """value, which must be a non-negative integer (true is not one, nor is 1.0)."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise InputError(f"{where} must be a non-negative integer, got {_shown(value)}")


def _text(value: object, where: str) -> str:
    """value, which must be a non-empty string."""
    if isinstance(value, str) and value:
        return value
    raise InputError(f"{where} must be a non-empty string, got {_shown(value)}")


def _exact_keys(value: dict[str, Any], keys: tuple[str, ...], where: str) -> None:
    """Refuse a missing key or an unknown one."""
    problems = [f"missing key {json.dumps(key)}" for key in keys if key not in value]
    problems += [f"unknown key {json.dumps(key)}" for key in sorted(value) if key not in keys]
    if problems:
        raise InputError(f"{where}: {', '.join(problems)}")


def load_report(path: str) -> Report:
    """The coverage.py JSON report: its version, branch coverage, and the summary counts of each file."""
    where = f"the report {path}"
    data = _object(read_json(path, MAX_REPORT_BYTES, "report"), where)
    meta = _object(data.get("meta", _ABSENT), f"{where}: meta")
    version = _text(meta.get("version", _ABSENT), f"{where}: meta.version")
    branch_coverage = meta.get("branch_coverage", _ABSENT)
    if branch_coverage is False:
        raise InputError(f"{where} was measured without branch coverage (meta.branch_coverage is false)")
    if branch_coverage is not True:
        raise InputError(f"{where}: meta.branch_coverage must be true or false, got {_shown(branch_coverage)}")
    files = _object(data.get("files", _ABSENT), f"{where}: files")
    measured: dict[str, Summary] = {}
    for key, value in files.items():
        file_where = f"{where}: files[{json.dumps(key)}]"
        summary = _object(_object(value, file_where).get("summary", _ABSENT), f"{file_where}.summary")
        counts = [_count(summary.get(field, _ABSENT), f"{file_where}.summary.{field}") for field in Summary._fields]
        module = normalise(key)
        if module in measured:
            raise InputError(f"{where}: two keys become {json.dumps(module)} once separators are normalised")
        measured[module] = Summary(*counts)
    return Report(path, version, measured)


def load_table(path: str) -> Table:
    """The table of the gate: format 1, its exact keys, non-negative integer counts."""
    where = f"the table {path}"
    data = _object(read_json(path, MAX_TABLE_BYTES, "table"), where)
    table_format = data.get("format", _ABSENT)
    if not (isinstance(table_format, int) and not isinstance(table_format, bool) and table_format == TABLE_FORMAT):
        raise InputError(
            f"{where} has the unknown format {_shown(table_format)}: this gate reads format {TABLE_FORMAT}"
        )
    _exact_keys(data, TABLE_KEYS, where)
    version = _text(data["branch_coverage_version"], f"{where}: branch_coverage_version")
    cells = data["cells"]
    if not (
        isinstance(cells, list)
        and cells
        and all(isinstance(cell, str) and CELL_NAME.fullmatch(cell) for cell in cells)
        and len(set(cells)) == len(cells)
    ):
        raise InputError(
            f"{where}: cells must be a non-empty array of distinct cell names (letters, digits, '.', '_' and '-'), "
            f"got {_shown(cells)}"
        )
    modules = _object(data["modules"], f"{where}: modules")
    entries: dict[str, Entry] = {}
    for key, value in modules.items():
        entry_where = f"{where}: modules[{json.dumps(key)}]"
        fields = _object(value, entry_where)
        _exact_keys(fields, ENTRY_KEYS, entry_where)
        module = normalise(key)
        if module in entries:
            raise InputError(f"{where}: two keys become {json.dumps(module)} once separators are normalised")
        entries[module] = Entry(**{name: _count(fields[name], f"{entry_where}.{name}") for name in ENTRY_KEYS})
    return Table(version, list(cells), entries)


def render_table(table: Table) -> str:
    """The text of the table file: JSON, keys sorted, indented by 2, ending with a newline."""
    document = {
        "branch_coverage_version": table.branch_coverage_version,
        "cells": sorted(table.cells),
        "format": TABLE_FORMAT,
        "modules": {module: entry._asdict() for module, entry in table.modules.items()},
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def write_table(path: str, table: Table, replace: bool) -> None:
    """Write the table into a temporary file next to path, then move it over path (an existing path only if replace)."""
    if not replace and os.path.lexists(path):
        raise InputError(f"the table {path} exists: pass --replace to overwrite it")
    data = render_table(table).encode("utf-8")
    try:
        handle, temporary = tempfile.mkstemp(
            prefix=".coverage-gate-", suffix=".tmp", dir=os.path.dirname(os.path.abspath(path))
        )
    except OSError as exc:
        raise InputError(f"cannot write the table {path}: {exc}") from exc
    try:
        with open(handle, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    except OSError as exc:
        raise InputError(f"cannot write the table {path}: {exc}") from exc
    finally:
        if os.path.lexists(temporary):
            os.remove(temporary)


def count_pragmas(path: str) -> int:
    """The number of lines of the source file holding a coverage pragma (no cover, no branch), with any line ending."""
    data = read_bounded(path, MAX_SOURCE_BYTES, "source file")
    return sum(1 for line in data.splitlines() if any(pragma in line for pragma in PRAGMAS))


def modules_on_disk() -> set[str]:
    """The modules the report must hold: the .py files under src/ and tools/, and RegexLab.py, from the current directory.

    __pycache__ directories are skipped; a directory that cannot be listed is an input error, never a silent hole.
    """
    absent = [f"{name}/" for name in MEASURED_DIRECTORIES if not os.path.isdir(name)]
    if not os.path.isfile(MEASURED_FILE):
        absent.append(MEASURED_FILE)
    if absent:
        raise InputError(f"{', '.join(absent)} not found in {os.getcwd()}: run from the repository root")
    found = {MEASURED_FILE}
    try:
        for directory in MEASURED_DIRECTORIES:
            _collect_python_files(directory, found)
    except OSError as exc:
        raise InputError(f"cannot list the measured files: {exc}") from exc
    return found


def _collect_python_files(directory: str, found: set[str]) -> None:
    """Add the .py files under directory to found, recursively, symbolic links to directories not followed."""
    subdirectories = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                if entry.name != SKIPPED_DIRECTORY:
                    subdirectories.append(entry.path)
            elif entry.name.endswith(".py"):
                found.add(normalise(entry.path))
    for subdirectory in subdirectories:
        _collect_python_files(subdirectory, found)
