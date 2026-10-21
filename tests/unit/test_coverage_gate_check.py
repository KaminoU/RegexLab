"""
Tests of tools/coverage_gate/check.py: the per-module coverage gate.

The gate compares, module by module, the missing lines and the missing branches of a coverage.py JSON report with the
ceilings of a table; it compares branches from Python 3.10 on only; it freezes the excluded lines and the lines holding
a coverage pragma; and it requires the report to hold exactly the measured files found on disk. Each test runs it in a
temporary repository. The helpers of this module are shared with test_coverage_gate_generate.py.
"""

from __future__ import annotations

import builtins
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest
from tools.coverage_gate import _report, check

GATE_VERSION = "7.16.2"  # coverage.py version of the table's branch ceilings
OLD_VERSION = "7.6.1"  # coverage.py version of the Python 3.8 cells
NEW_PYTHON = (3, 14)
OLD_PYTHON = (3, 8)

# The temporary repository. Its modules: every .py file under src/ and tools/, and RegexLab.py; neither the .py file
# in __pycache__ nor the README.
TREE_FILES = {
    "RegexLab.py": "import sys\n",
    "src/__init__.py": "",
    "src/a.py": "A = 1\n",
    "src/core/b.py": "B = 2\n",
    "src/__pycache__/stale.py": "S = 3\n",
    "src/README.md": "not a module\n",
    "tools/__init__.py": "",
    "tools/gate.py": "G = 4\n",
}
MODULES = ["RegexLab.py", "src/__init__.py", "src/a.py", "src/core/b.py", "tools/__init__.py", "tools/gate.py"]

# Runs a module of the gate as "python -m" does, but with the package under test first on sys.path: the current
# directory of the child is the temporary repository, which has a tools/ directory of its own.
BOOTSTRAP = (
    "import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); "
    "runpy.run_module(sys.argv.pop(1), run_name='__main__', alter_sys=True)"
)
PACKAGE_ROOT = str(Path(check.__file__).resolve().parents[2])

ALL_OK = "OK: 6 modules within their ceilings, 0 BETTER; structure equal (6 modules); branches gated"
DELETE = object()  # edited(): remove the key


def shown(text: str) -> str:
    """The text as the gate prints it: every character outside printable ASCII escaped."""
    return "".join(char if " " <= char <= "~" else ascii(char)[1:-1] for char in text)


def summary(
    statements: int = 10, missing: int = 2, branches: int = 4, missing_branches: int = 1, excluded: int = 0
) -> dict[str, Any]:
    """The summary of one file in a coverage.py JSON report (format 3, branch coverage)."""
    return {
        "covered_lines": statements - missing,
        "num_statements": statements,
        "percent_covered": 0.0,
        "percent_covered_display": "0",
        "missing_lines": missing,
        "excluded_lines": excluded,
        "num_branches": branches,
        "num_partial_branches": 0,
        "covered_branches": branches - missing_branches,
        "missing_branches": missing_branches,
    }


def make_report(summaries: dict[str, dict[str, Any]], version: str = GATE_VERSION) -> dict[str, Any]:
    """A coverage.py JSON report whose files are keyed exactly as given."""
    return {
        "meta": {
            "format": 3,
            "version": version,
            "timestamp": "2026-10-14T22:00:00",
            "branch_coverage": True,
            "show_contexts": False,
        },
        "files": {
            key: {"executed_lines": [], "summary": value, "missing_lines": [], "excluded_lines": []}
            for key, value in summaries.items()
        },
        "totals": {},
    }


def entry(missing: int = 2, missing_branches: int = 1, excluded: int = 0, pragmas: int = 0) -> dict[str, int]:
    """One module of the table."""
    return {
        "excluded_lines": excluded,
        "missing_branches": missing_branches,
        "missing_lines": missing,
        "pragmas": pragmas,
    }


def make_table(
    entries: dict[str, dict[str, Any]], version: str = GATE_VERSION, cells: list[str] | None = None
) -> dict[str, Any]:
    """A table of ceilings, keyed exactly as given."""
    return {
        "branch_coverage_version": version,
        "cells": ["windows-3.14"] if cells is None else cells,
        "format": 1,
        "modules": entries,
    }


def base_summaries() -> dict[str, dict[str, Any]]:
    """Every module of the temporary repository: 2 lines missing of 10, 1 branch missing of 4."""
    return {module: summary() for module in MODULES}


def base_entries() -> dict[str, dict[str, Any]]:
    """Every module of the temporary repository, its ceilings equal to its base summary."""
    return {module: entry() for module in MODULES}


def base_line(module: str, status: str = "OK", branches: str = "ceiling 1") -> str:
    """The line the gate prints for a module of the base summary and the base table."""
    return (
        f"{status:<6} {module}: lines missing 2 / ceiling 2 (80.00%); branches missing 1 / {branches} (75.00%); "
        "excluded 0 / frozen 0; pragmas 0 / frozen 0"
    )


def edited(document: Any, keys: tuple[str, ...], value: Any) -> Any:
    """A copy of the JSON document, the value at the keys replaced (removed when value is DELETE)."""
    copy = json.loads(json.dumps(document))
    target = copy
    for key in keys[:-1]:
        target = target[key]
    if value is DELETE:
        del target[keys[-1]]
    else:
        target[keys[-1]] = value
    return copy


def write(directory: Path, name: str, content: Any) -> Path:
    """Write bytes as they are, a text in UTF-8, anything else as JSON; return the path."""
    path = directory / name
    if isinstance(content, bytes):
        data = content
    elif isinstance(content, str):
        data = content.encode("utf-8")
    else:
        data = json.dumps(content).encode("utf-8")
    path.write_bytes(data)
    return path


def build_tree(root: Path) -> Path:
    """Create the temporary repository under root."""
    for name, text in TREE_FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    return root


def run_module(module: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a module of the gate in a child process, coverage.py kept out of the child."""
    env = {key: value for key, value in os.environ.items() if not key.startswith(("COV_CORE_", "COVERAGE_"))}
    return subprocess.run(
        [sys.executable, "-c", BOOTSTRAP, PACKAGE_ROOT, module, *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def failures(out: str) -> list[str]:
    """The failure lines and the summary line of a failed run."""
    return [line for line in out.splitlines() if line.startswith("FAIL")]


def header(
    tmp_path: Path,
    python: str = "3.14",
    version: str = GATE_VERSION,
    gated: bool = True,
    on_disk: int = 6,
    in_report: int = 6,
    cells: str = "windows-3.14",
) -> list[str]:
    """The three lines the gate prints first."""
    report = shown(str(tmp_path / "report.json"))
    table = shown(str(tmp_path / "table.json"))
    if gated:
        branches = f"branches: gated (Python {python} >= 3.10, report and table on coverage {GATE_VERSION})"
    else:
        branches = f"branches: NOT GATED on Python {python} (< 3.10): missing branches are printed, never compared"
    return [
        f"coverage gate: report {report} (coverage {version}); table {table} (branch ceilings for coverage "
        f"{GATE_VERSION}; cells {cells}); Python {python}",
        branches,
        f"structure: {on_disk} modules on disk (.py files under src/ and tools/, and RegexLab.py), {in_report} in the "
        "report",
    ]


def spy_open(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every path the gate's reader opens; return the record."""
    opened: list[str] = []

    def spy(path: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(str(path))
        return builtins.open(path, *args, **kwargs)

    monkeypatch.setattr(_report, "open", spy, raising=False)
    return opened


Run = Callable[..., "tuple[int, str, str]"]


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The temporary repository, as the current directory."""
    root = build_tree(tmp_path / "repo")
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def run(tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Run:
    """Run the checker on a report and a table (dicts, texts or bytes); return (exit code, stdout, stderr)."""

    def _run(report: Any, table: Any, python: tuple[int, int] | None = NEW_PYTHON) -> tuple[int, str, str]:
        report_path = write(tmp_path, "report.json", report)
        table_path = write(tmp_path, "table.json", table)
        code = check.main([str(report_path), str(table_path)], python=python)
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return _run


# ============================================================================
# Ceilings
# ============================================================================


def test_every_module_at_its_ceilings_passes(run: Run, tmp_path: Path) -> None:
    code, out, err = run(make_report(base_summaries()), make_table(base_entries()))
    assert (code, err) == (0, "")
    assert out.splitlines() == [*header(tmp_path), *[base_line(module) for module in MODULES], ALL_OK]


def test_one_line_over_its_ceiling_fails_that_module_only(run: Run) -> None:
    summaries = base_summaries()
    summaries["src/a.py"] = summary(missing=3)
    code, out, err = run(make_report(summaries), make_table(base_entries()))
    assert (code, err) == (1, "")
    assert (
        "OVER   src/a.py: lines missing 3 / ceiling 2 (70.00%); branches missing 1 / ceiling 1 (75.00%); "
        "excluded 0 / frozen 0; pragmas 0 / frozen 0"
    ) in out.splitlines()
    assert base_line("src/core/b.py") in out.splitlines()
    assert failures(out) == [
        "FAIL OVER src/a.py: lines missing 3 > ceiling 2",
        "FAIL: 1 failure (OVER 1, EXCLUDED 0, PRAGMAS 0, NEW 0, GONE 0, STRUCTURE 0); 6 modules in the report, "
        "6 in the table, 6 on disk; branches gated",
    ]


@pytest.mark.parametrize(
    ("python", "version", "gated"),
    [
        ((3, 14), GATE_VERSION, True),
        ((3, 10), GATE_VERSION, True),
        ((3, 9), OLD_VERSION, False),
        ((3, 8), OLD_VERSION, False),
    ],
)
def test_one_branch_over_its_ceiling_fails_from_python_3_10_on_only(
    run: Run, tmp_path: Path, python: tuple[int, int], version: str, gated: bool
) -> None:
    summaries = base_summaries()
    summaries["src/core/b.py"] = summary(missing_branches=2)
    code, out, err = run(make_report(summaries, version=version), make_table(base_entries()), python=python)
    label = f"{python[0]}.{python[1]}"
    lines = out.splitlines()
    assert lines[:3] == header(tmp_path, python=label, version=version, gated=gated)
    if gated:
        assert (code, err) == (1, "")
        assert (
            "OVER   src/core/b.py: lines missing 2 / ceiling 2 (80.00%); branches missing 2 / ceiling 1 (50.00%); "
            "excluded 0 / frozen 0; pragmas 0 / frozen 0"
        ) in lines
        assert failures(out) == [
            "FAIL OVER src/core/b.py: branches missing 2 > ceiling 1",
            "FAIL: 1 failure (OVER 1, EXCLUDED 0, PRAGMAS 0, NEW 0, GONE 0, STRUCTURE 0); 6 modules in the report, "
            "6 in the table, 6 on disk; branches gated",
        ]
    else:
        assert (code, err) == (0, "")
        assert (
            "OK     src/core/b.py: lines missing 2 / ceiling 2 (80.00%); branches missing 2 / not gated (50.00%); "
            "excluded 0 / frozen 0; pragmas 0 / frozen 0"
        ) in lines
        assert base_line("src/a.py", branches="not gated") in lines
        assert lines[-1] == (
            f"OK: 6 modules within their ceilings, 0 BETTER; structure equal (6 modules); branches not gated "
            f"(Python {label})"
        )


def test_a_module_under_a_ceiling_is_better(run: Run) -> None:
    summaries = base_summaries()
    summaries["src/a.py"] = summary(missing=1)
    summaries["tools/gate.py"] = summary(missing_branches=0)
    code, out, err = run(make_report(summaries), make_table(base_entries()))
    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert (
        "BETTER src/a.py: lines missing 1 / ceiling 2 (90.00%); branches missing 1 / ceiling 1 (75.00%); "
        "excluded 0 / frozen 0; pragmas 0 / frozen 0"
    ) in lines
    assert (
        "BETTER tools/gate.py: lines missing 2 / ceiling 2 (80.00%); branches missing 0 / ceiling 1 (100.00%); "
        "excluded 0 / frozen 0; pragmas 0 / frozen 0"
    ) in lines
    assert base_line("src/core/b.py") in lines
    assert lines[-1] == "OK: 6 modules within their ceilings, 2 BETTER; structure equal (6 modules); branches gated"


def test_branches_under_their_ceiling_are_not_better_when_not_gated(run: Run) -> None:
    summaries = base_summaries()
    summaries["tools/gate.py"] = summary(missing_branches=0)
    code, out, err = run(make_report(summaries, version=OLD_VERSION), make_table(base_entries()), python=OLD_PYTHON)
    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert (
        "OK     tools/gate.py: lines missing 2 / ceiling 2 (80.00%); branches missing 0 / not gated (100.00%); "
        "excluded 0 / frozen 0; pragmas 0 / frozen 0"
    ) in lines
    assert lines[-1] == (
        "OK: 6 modules within their ceilings, 0 BETTER; structure equal (6 modules); branches not gated (Python 3.8)"
    )


def test_nothing_to_cover_counts_as_100_percent(run: Run) -> None:
    summaries = base_summaries()
    summaries["src/__init__.py"] = summary(statements=0, missing=0, branches=0, missing_branches=0)
    entries = base_entries()
    entries["src/__init__.py"] = entry(missing=0, missing_branches=0)
    code, out, err = run(make_report(summaries), make_table(entries))
    assert (code, err) == (0, "")
    assert (
        "OK     src/__init__.py: lines missing 0 / ceiling 0 (100.00%); branches missing 0 / ceiling 0 (100.00%); "
        "excluded 0 / frozen 0; pragmas 0 / frozen 0"
    ) in out.splitlines()
    assert out.splitlines()[-1] == ALL_OK


def test_percentages_are_rounded_down(run: Run) -> None:
    summaries = base_summaries()
    summaries["src/a.py"] = summary(statements=3, missing=1, branches=3, missing_branches=1)  # 66.666...%
    summaries["src/core/b.py"] = summary(statements=100000, missing=1, branches=4, missing_branches=1)  # 99.999%
    code, out, err = run(make_report(summaries), make_table(base_entries()))
    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert (
        "BETTER src/a.py: lines missing 1 / ceiling 2 (66.66%); branches missing 1 / ceiling 1 (66.66%); "
        "excluded 0 / frozen 0; pragmas 0 / frozen 0"
    ) in lines
    assert (
        "BETTER src/core/b.py: lines missing 1 / ceiling 2 (99.99%); branches missing 1 / ceiling 1 (75.00%); "
        "excluded 0 / frozen 0; pragmas 0 / frozen 0"
    ) in lines


# ============================================================================
# NEW, GONE and the structure witness
# ============================================================================


def test_a_measured_module_without_a_table_entry_is_new(run: Run, tree: Path) -> None:
    (tree / "src" / "new.py").write_bytes(b"N = 1\n")
    summaries = base_summaries()
    summaries["src/new.py"] = summary(missing=3)
    code, out, err = run(make_report(summaries), make_table(base_entries()))
    assert (code, err) == (1, "")
    assert (
        "NEW    src/new.py: lines missing 3 / no entry (70.00%); branches missing 1 / no entry (75.00%); "
        "excluded 0 / no entry; pragmas 0 / no entry"
    ) in out.splitlines()
    assert failures(out) == [
        "FAIL NEW src/new.py: measured, without a table entry",
        "FAIL: 1 failure (OVER 0, EXCLUDED 0, PRAGMAS 0, NEW 1, GONE 0, STRUCTURE 0); 7 modules in the report, "
        "6 in the table, 7 on disk; branches gated",
    ]


def test_a_table_entry_without_a_measured_module_is_gone(run: Run) -> None:
    entries = base_entries()
    entries["src/old.py"] = entry(missing=3, missing_branches=2, excluded=1, pragmas=1)
    code, out, err = run(make_report(base_summaries()), make_table(entries))
    assert (code, err) == (1, "")
    assert (
        "GONE   src/old.py: not in the report; ceilings: lines 3, branches 2; frozen: excluded 1, pragmas 1"
    ) in out.splitlines()
    assert failures(out) == [
        "FAIL GONE src/old.py: in the table, not in the report",
        "FAIL: 1 failure (OVER 0, EXCLUDED 0, PRAGMAS 0, NEW 0, GONE 1, STRUCTURE 0); 6 modules in the report, "
        "7 in the table, 6 on disk; branches gated",
    ]


def test_a_file_on_disk_missing_from_the_report_fails_the_structure(run: Run, tree: Path, tmp_path: Path) -> None:
    (tree / "tools" / "forgotten.py").write_bytes(b"F = 1\n")
    code, out, err = run(make_report(base_summaries()), make_table(base_entries()))
    assert (code, err) == (1, "")
    assert out.splitlines()[2] == header(tmp_path, on_disk=7)[2]
    assert failures(out) == [
        "FAIL STRUCTURE tools/forgotten.py: on disk, missing from the report",
        "FAIL: 1 failure (OVER 0, EXCLUDED 0, PRAGMAS 0, NEW 0, GONE 0, STRUCTURE 1); 6 modules in the report, "
        "6 in the table, 7 on disk; branches gated",
    ]


def test_a_report_module_absent_from_disk_fails_the_structure(run: Run, tree: Path) -> None:
    (tree / "src" / "a.py").unlink()
    code, out, err = run(make_report(base_summaries()), make_table(base_entries()))
    assert (code, err) == (1, "")
    assert (
        "OK     src/a.py: lines missing 2 / ceiling 2 (80.00%); branches missing 1 / ceiling 1 (75.00%); "
        "excluded 0 / frozen 0; pragmas n/a (not on disk) / frozen 0"
    ) in out.splitlines()
    assert failures(out) == [
        "FAIL STRUCTURE src/a.py: in the report, not on disk",
        "FAIL: 1 failure (OVER 0, EXCLUDED 0, PRAGMAS 0, NEW 0, GONE 0, STRUCTURE 1); 6 modules in the report, "
        "6 in the table, 5 on disk; branches gated",
    ]


def test_only_files_ending_in_py_are_modules(run: Run, tree: Path, tmp_path: Path) -> None:
    (tree / "src" / "a.pyc").write_bytes(b"")
    (tree / "tools" / "gate.py.orig").write_bytes(b"G = 4\n")
    code, out, err = run(make_report(base_summaries()), make_table(base_entries()))
    assert (code, err) == (0, "")
    assert out.splitlines()[2] == header(tmp_path)[2]
    assert out.splitlines()[-1] == ALL_OK


def test_every_failure_is_listed_structure_first_then_by_module(run: Run, tree: Path) -> None:
    (tree / "src" / "new.py").write_bytes(b"")
    (tree / "tools" / "forgotten.py").write_bytes(b"")
    (tree / "src" / "a.py").write_bytes(b"A = 1  # pragma: no cover\n")
    summaries = base_summaries()
    summaries["src/new.py"] = summary()
    summaries["src/ghost.py"] = summary()
    summaries["RegexLab.py"] = summary(missing=3, missing_branches=2, excluded=1)
    entries = base_entries()
    entries["src/old.py"] = entry()
    code, out, err = run(make_report(summaries), make_table(entries))
    assert (code, err) == (1, "")
    assert (
        "NEW    src/ghost.py: lines missing 2 / no entry (80.00%); branches missing 1 / no entry (75.00%); "
        "excluded 0 / no entry; pragmas n/a (not on disk) / no entry"
    ) in out.splitlines()
    assert failures(out) == [
        "FAIL STRUCTURE tools/forgotten.py: on disk, missing from the report",
        "FAIL STRUCTURE src/ghost.py: in the report, not on disk",
        "FAIL OVER RegexLab.py: lines missing 3 > ceiling 2",
        "FAIL OVER RegexLab.py: branches missing 2 > ceiling 1",
        "FAIL EXCLUDED RegexLab.py: excluded lines 1 > frozen 0",
        "FAIL PRAGMAS src/a.py: lines with a coverage pragma 1 > frozen 0",
        "FAIL NEW src/ghost.py: measured, without a table entry",
        "FAIL NEW src/new.py: measured, without a table entry",
        "FAIL GONE src/old.py: in the table, not in the report",
        "FAIL: 9 failures (OVER 2, EXCLUDED 1, PRAGMAS 1, NEW 2, GONE 1, STRUCTURE 2); 8 modules in the report, "
        "7 in the table, 8 on disk; branches gated",
    ]


@pytest.mark.parametrize("missing", ["src", "tools", "RegexLab.py"])
def test_the_measured_roots_must_be_in_the_current_directory(run: Run, tree: Path, missing: str) -> None:
    path = tree / missing
    if path.is_dir():
        shutil.rmtree(str(path))
    else:
        path.unlink()
    shown_name = missing + "/" if missing != "RegexLab.py" else missing
    code, out, err = run(make_report(base_summaries()), make_table(base_entries()))
    assert (code, out) == (2, "")
    assert f"ERROR: {shown_name} not found in {shown(os.getcwd())}: run from the repository root" in err


def test_a_directory_that_cannot_be_listed_is_an_input_error(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    real_scandir = os.scandir

    def scandir(path: Any) -> Any:
        if Path(path) == Path("src", "core"):
            raise PermissionError(13, "Permission denied", str(path))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", scandir)
    code, out, err = run(make_report(base_summaries()), make_table(base_entries()))
    assert (code, out) == (2, "")
    assert "ERROR: cannot list the measured files: " in err
    assert "Permission denied" in err


# ============================================================================
# Frozen exclusions
# ============================================================================


def test_excluded_lines_above_their_frozen_count_fail(run: Run) -> None:
    summaries = base_summaries()
    summaries["src/a.py"] = summary(excluded=1)
    summaries["src/core/b.py"] = summary(excluded=2)
    entries = base_entries()
    entries["src/core/b.py"] = entry(excluded=2)
    code, out, err = run(make_report(summaries), make_table(entries))
    assert (code, err) == (1, "")
    lines = out.splitlines()
    assert (
        "OVER   src/a.py: lines missing 2 / ceiling 2 (80.00%); branches missing 1 / ceiling 1 (75.00%); "
        "excluded 1 / frozen 0; pragmas 0 / frozen 0"
    ) in lines
    assert (
        "OK     src/core/b.py: lines missing 2 / ceiling 2 (80.00%); branches missing 1 / ceiling 1 (75.00%); "
        "excluded 2 / frozen 2; pragmas 0 / frozen 0"
    ) in lines
    assert failures(out) == [
        "FAIL EXCLUDED src/a.py: excluded lines 1 > frozen 0",
        "FAIL: 1 failure (OVER 0, EXCLUDED 1, PRAGMAS 0, NEW 0, GONE 0, STRUCTURE 0); 6 modules in the report, "
        "6 in the table, 6 on disk; branches gated",
    ]


def test_lines_holding_a_coverage_pragma_above_their_frozen_count_fail(run: Run, tree: Path) -> None:
    (tree / "src" / "a.py").write_bytes(b"A = 1  # pragma: no cover\nif A:  # pragma: no branch\n    pass\n")
    (tree / "tools" / "gate.py").write_bytes(b"G = 1  # pragma: no cover; pragma: no branch\nH = 2\n")
    entries = base_entries()
    entries["tools/gate.py"] = entry(pragmas=1)
    code, out, err = run(make_report(base_summaries()), make_table(entries))
    assert (code, err) == (1, "")
    lines = out.splitlines()
    assert (
        "OVER   src/a.py: lines missing 2 / ceiling 2 (80.00%); branches missing 1 / ceiling 1 (75.00%); "
        "excluded 0 / frozen 0; pragmas 2 / frozen 0"
    ) in lines
    # one line holding both pragmas counts once
    assert (
        "OK     tools/gate.py: lines missing 2 / ceiling 2 (80.00%); branches missing 1 / ceiling 1 (75.00%); "
        "excluded 0 / frozen 0; pragmas 1 / frozen 1"
    ) in lines
    assert failures(out) == [
        "FAIL PRAGMAS src/a.py: lines with a coverage pragma 2 > frozen 0",
        "FAIL: 1 failure (OVER 0, EXCLUDED 0, PRAGMAS 1, NEW 0, GONE 0, STRUCTURE 0); 6 modules in the report, "
        "6 in the table, 6 on disk; branches gated",
    ]


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_pragma_lines_are_counted_with_any_line_ending(run: Run, tree: Path, newline: bytes) -> None:
    lines = [b"a = 1  # pragma: no cover", b"b = 2", b"c = 3  # pragma: no branch", b""]
    (tree / "src" / "a.py").write_bytes(newline.join(lines))
    entries = base_entries()
    entries["src/a.py"] = entry(pragmas=2)
    code, out, err = run(make_report(base_summaries()), make_table(entries))
    assert (code, err) == (0, "")
    assert (
        "OK     src/a.py: lines missing 2 / ceiling 2 (80.00%); branches missing 1 / ceiling 1 (75.00%); "
        "excluded 0 / frozen 0; pragmas 2 / frozen 2"
    ) in out.splitlines()
    assert out.splitlines()[-1] == ALL_OK


def test_an_oversized_source_file_is_an_input_error(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _report.MAX_SOURCE_BYTES == 1024 * 1024
    monkeypatch.setattr(_report, "MAX_SOURCE_BYTES", 10)
    code, out, err = run(make_report(base_summaries()), make_table(base_entries()))
    assert (code, out) == (2, "")
    assert "ERROR: the source file RegexLab.py weighs 11 bytes, over its bound of 10 bytes" in err


# ============================================================================
# Keys
# ============================================================================


def test_keys_with_backslashes_are_normalised(run: Run) -> None:
    summaries = {module.replace("/", "\\"): summary() for module in MODULES}
    entries = base_entries()
    entries["src\\core\\b.py"] = entries.pop("src/core/b.py")
    code, out, err = run(make_report(summaries), make_table(entries))
    assert (code, err) == (0, "")
    assert base_line("src/core/b.py") in out.splitlines()
    assert out.splitlines()[-1] == ALL_OK


@pytest.mark.parametrize("which", ["report", "table"])
def test_two_keys_equal_once_normalised_are_refused(run: Run, which: str) -> None:
    summaries = base_summaries()
    entries = base_entries()
    if which == "report":
        summaries["src\\a.py"] = summary()
    else:
        entries["src\\a.py"] = entry()
    code, out, err = run(make_report(summaries), make_table(entries))
    assert (code, out) == (2, "")
    assert 'two keys become "src/a.py" once separators are normalised' in err
    assert f"ERROR: the {which} " in err


# ============================================================================
# Bounded and valid inputs
# ============================================================================


@pytest.mark.parametrize(
    ("which", "bound", "default"),
    [("report", "MAX_REPORT_BYTES", 16 * 1024 * 1024), ("table", "MAX_TABLE_BYTES", 1024 * 1024)],
)
def test_an_input_is_read_up_to_its_bound_and_refused_unopened_over_it(
    run: Run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, which: str, bound: str, default: int
) -> None:
    assert getattr(_report, bound) == default
    report = json.dumps(make_report(base_summaries())).encode("utf-8")
    table = json.dumps(make_table(base_entries())).encode("utf-8")
    size = len(report) if which == "report" else len(table)
    path = str(tmp_path / f"{which}.json")
    opened = spy_open(monkeypatch)
    monkeypatch.setattr(_report, bound, size)
    code, out, err = run(report, table)
    assert (code, err) == (0, "")
    assert out.splitlines()[-1] == ALL_OK
    assert path in opened  # witness: the spy sees what the gate reads
    opened.clear()
    monkeypatch.setattr(_report, bound, size - 1)
    code, out, err = run(report, table)
    assert (code, out) == (2, "")
    assert f"ERROR: the {which} {shown(path)} weighs {size} bytes, over its bound of {size - 1} bytes" in err
    assert path not in opened


def test_an_input_that_grows_after_its_size_check_is_refused(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_report, "MAX_REPORT_BYTES", 10)
    monkeypatch.setattr(_report, "file_size", lambda path: 0)
    code, out, err = run(make_report(base_summaries()), make_table(base_entries()))
    assert (code, out) == (2, "")
    assert "grew over its bound of 10 bytes while it was read" in err


@pytest.mark.parametrize("which", ["report", "table"])
def test_a_missing_input_is_an_input_error(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], which: str
) -> None:
    paths = {
        "report": write(tmp_path, "report.json", make_report(base_summaries())),
        "table": write(tmp_path, "table.json", make_table(base_entries())),
    }
    paths[which] = tmp_path / "absent.json"
    code = check.main([str(paths["report"]), str(paths["table"])], python=NEW_PYTHON)
    captured = capsys.readouterr()
    assert (code, captured.out) == (2, "")
    assert f"ERROR: cannot read the {which} {shown(str(tmp_path / 'absent.json'))}: " in captured.err


def test_a_directory_given_as_the_report_is_an_input_error(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    table = write(tmp_path, "table.json", make_table(base_entries()))
    code = check.main([str(tmp_path), str(table)], python=NEW_PYTHON)
    captured = capsys.readouterr()
    assert (code, captured.out) == (2, "")
    assert f"ERROR: cannot read the report {shown(str(tmp_path))}: " in captured.err


@pytest.mark.parametrize("which", ["report", "table"])
@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b'{"meta": "' + bytes([0xFF]) + b'"}', "is not valid UTF-8"),
        (b'{"files": ', "is not valid JSON"),
        (b'{"meta": {}, "meta": {}}', 'is not valid JSON: duplicate key "meta"'),
    ],
    ids=["invalid-utf8", "truncated", "duplicate-key"],
)
def test_an_input_that_is_not_utf8_json_is_refused(run: Run, which: str, content: bytes, message: str) -> None:
    report = content if which == "report" else make_report(base_summaries())
    table = content if which == "table" else make_table(base_entries())
    code, out, err = run(report, table)
    assert (code, out) == (2, "")
    assert f"ERROR: the {which} " in err
    assert message in err


@pytest.mark.parametrize("which", ["report", "table"])
def test_a_deeply_nested_input_is_refused_without_a_traceback(run: Run, which: str) -> None:
    """The decoder raises RecursionError at this depth (measured on Windows, Python 3.8.20 and 3.14.7); where the stack
    would allow it, the document is an array, which the shape check refuses."""
    nested = b"[" * 100000 + b"]" * 100000
    report = nested if which == "report" else make_report(base_summaries())
    table = nested if which == "table" else make_table(base_entries())
    code, out, err = run(report, table)
    assert (code, out) == (2, "")
    assert f"ERROR: the {which} " in err
    assert "is not valid JSON" in err or "must be an object, got an array" in err


def test_a_huge_integer_is_refused(run: Run) -> None:
    """The interpreter bounds the digits of an integer it converts (CPython 3.8.14 and later): a count of 5000 digits."""
    report = json.dumps(make_report(base_summaries())).replace('"missing_lines": 2', '"missing_lines": 1' + "0" * 5000)
    code, out, err = run(report, make_table(base_entries()))
    assert (code, out) == (2, "")
    assert "is not valid JSON" in err


REPORT = make_report(base_summaries())
SUMMARY = ("files", "src/a.py", "summary")


@pytest.mark.parametrize(
    ("report", "message"),
    [
        ([], "the report {path} must be an object, got an array"),
        (edited(REPORT, ("meta",), DELETE), "the report {path}: meta must be an object, got no value (missing key)"),
        (edited(REPORT, ("meta",), []), "the report {path}: meta must be an object, got an array"),
        (edited(REPORT, ("meta", "version"), DELETE), "meta.version must be a non-empty string, got no value"),
        (edited(REPORT, ("meta", "version"), 7), "meta.version must be a non-empty string, got 7"),
        (edited(REPORT, ("meta", "version"), ""), 'meta.version must be a non-empty string, got ""'),
        (
            edited(REPORT, ("meta", "branch_coverage"), False),
            "the report {path} was measured without branch coverage (meta.branch_coverage is false)",
        ),
        (edited(REPORT, ("meta", "branch_coverage"), DELETE), "meta.branch_coverage must be true or false, got no"),
        (edited(REPORT, ("meta", "branch_coverage"), "true"), 'meta.branch_coverage must be true or false, got "true"'),
        (edited(REPORT, ("meta", "branch_coverage"), 1), "meta.branch_coverage must be true or false, got 1"),
        (edited(REPORT, ("files",), DELETE), "the report {path}: files must be an object, got no value"),
        (edited(REPORT, ("files",), []), "the report {path}: files must be an object, got an array"),
        (edited(REPORT, ("files", "src/a.py"), 3), 'files["src/a.py"] must be an object, got 3'),
        (edited(REPORT, SUMMARY, DELETE), 'files["src/a.py"].summary must be an object, got no value'),
        (
            edited(REPORT, (*SUMMARY, "missing_lines"), -1),
            ".summary.missing_lines must be a non-negative integer, got -1",
        ),
        (
            edited(REPORT, (*SUMMARY, "missing_lines"), 1.0),
            ".summary.missing_lines must be a non-negative integer, got 1.0",
        ),
        (
            edited(REPORT, (*SUMMARY, "missing_lines"), True),
            ".summary.missing_lines must be a non-negative integer, got true",
        ),
        (
            edited(REPORT, (*SUMMARY, "missing_lines"), "2"),
            '.summary.missing_lines must be a non-negative integer, got "2"',
        ),
        (
            edited(REPORT, (*SUMMARY, "missing_lines"), None),
            ".summary.missing_lines must be a non-negative integer, got null",
        ),
        (
            edited(REPORT, (*SUMMARY, "missing_lines"), {}),
            ".summary.missing_lines must be a non-negative integer, got an object",
        ),
        *[
            (
                edited(REPORT, (*SUMMARY, field), DELETE),
                f".summary.{field} must be a non-negative integer, got no value",
            )
            for field in (
                "covered_lines",
                "num_statements",
                "missing_lines",
                "covered_branches",
                "num_branches",
                "missing_branches",
                "excluded_lines",
            )
        ],
    ],
)
def test_a_report_without_the_expected_shape_is_refused(run: Run, tmp_path: Path, report: Any, message: str) -> None:
    code, out, err = run(report, make_table(base_entries()))
    assert (code, out) == (2, "")
    assert message.format(path=shown(str(tmp_path / "report.json"))) in err


TABLE = make_table(base_entries())
MODULE = ("modules", "src/a.py")


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ([], "the table {path} must be an object, got an array"),
        (
            edited(TABLE, ("format",), DELETE),
            "the table {path} has the unknown format no value (missing key): this gate reads format 1",
        ),
        (edited(TABLE, ("format",), 2), "the table {path} has the unknown format 2: this gate reads format 1"),
        (edited(TABLE, ("format",), "1"), 'the table {path} has the unknown format "1"'),
        (edited(TABLE, ("format",), 1.0), "the table {path} has the unknown format 1.0"),
        (edited(TABLE, ("format",), True), "the table {path} has the unknown format true"),
        (edited(TABLE, ("cells",), DELETE), 'the table {path}: missing key "cells"'),
        (edited(TABLE, ("extra",), 0), 'the table {path}: unknown key "extra"'),
        (edited(TABLE, ("branch_coverage_version",), 7), "branch_coverage_version must be a non-empty string, got 7"),
        (edited(TABLE, ("branch_coverage_version",), ""), 'branch_coverage_version must be a non-empty string, got ""'),
        (edited(TABLE, ("cells",), "windows-3.14"), "cells must be a non-empty array of distinct cell names"),
        (edited(TABLE, ("cells",), []), "cells must be a non-empty array of distinct cell names"),
        (edited(TABLE, ("cells",), ["a", "a"]), "cells must be a non-empty array of distinct cell names"),
        (edited(TABLE, ("cells",), ["a", 3]), "cells must be a non-empty array of distinct cell names"),
        (edited(TABLE, ("cells",), ["a b"]), "cells must be a non-empty array of distinct cell names"),
        (edited(TABLE, ("modules",), []), "the table {path}: modules must be an object, got an array"),
        (edited(TABLE, MODULE, [2, 1, 0, 0]), 'modules["src/a.py"] must be an object, got an array'),
        (edited(TABLE, (*MODULE, "pragmas"), DELETE), 'modules["src/a.py"]: missing key "pragmas"'),
        (edited(TABLE, (*MODULE, "missing_line"), 2), 'modules["src/a.py"]: unknown key "missing_line"'),
        (
            edited(TABLE, (*MODULE, "missing_lines"), -1),
            'modules["src/a.py"].missing_lines must be a non-negative integer, got -1',
        ),
        (
            edited(TABLE, (*MODULE, "missing_branches"), 1.5),
            ".missing_branches must be a non-negative integer, got 1.5",
        ),
        (edited(TABLE, (*MODULE, "excluded_lines"), True), ".excluded_lines must be a non-negative integer, got true"),
        (edited(TABLE, (*MODULE, "pragmas"), "0"), '.pragmas must be a non-negative integer, got "0"'),
    ],
)
def test_a_table_without_the_expected_shape_is_refused(run: Run, tmp_path: Path, table: Any, message: str) -> None:
    code, out, err = run(make_report(base_summaries()), table)
    assert (code, out) == (2, "")
    assert message.format(path=shown(str(tmp_path / "table.json"))) in err


# ============================================================================
# The coverage.py version of the branch ceilings
# ============================================================================


@pytest.mark.parametrize("python", [(3, 10), (3, 14)])
def test_a_report_of_another_coverage_version_is_refused_from_python_3_10_on(
    run: Run, tmp_path: Path, python: tuple[int, int]
) -> None:
    code, out, err = run(make_report(base_summaries(), version="7.16.3"), make_table(base_entries()), python=python)
    assert (code, out) == (2, "")
    assert (
        f"ERROR: the report {shown(str(tmp_path / 'report.json'))} comes from coverage 7.16.3, the table's branch "
        f"ceilings from coverage 7.16.2: on Python {python[0]}.{python[1]} (>= 3.10) they must be the same version"
    ) in err


def test_the_coverage_version_is_not_compared_before_python_3_10(run: Run, tmp_path: Path) -> None:
    code, out, err = run(make_report(base_summaries(), version="7.16.3"), make_table(base_entries()), python=(3, 9))
    assert (code, err) == (0, "")
    assert out.splitlines()[:3] == header(tmp_path, python="3.9", version="7.16.3", gated=False)
    assert out.splitlines()[-1] == (
        "OK: 6 modules within their ceilings, 0 BETTER; structure equal (6 modules); branches not gated (Python 3.9)"
    )


def test_without_a_python_argument_the_running_interpreter_decides(run: Run, tmp_path: Path) -> None:
    gated = sys.version_info >= (3, 10)
    version = GATE_VERSION if gated else OLD_VERSION
    summaries = base_summaries()
    summaries["src/core/b.py"] = summary(missing_branches=2)
    code, out, err = run(make_report(summaries, version=version), make_table(base_entries()), python=None)
    label = f"{sys.version_info[0]}.{sys.version_info[1]}"
    assert out.splitlines()[:3] == header(tmp_path, python=label, version=version, gated=gated)
    assert (code, err) == ((1, "") if gated else (0, ""))


# ============================================================================
# Output and process
# ============================================================================


def test_the_output_is_plain_ascii(run: Run, tree: Path) -> None:
    name = "src/caf" + chr(0xE9) + ".py"
    (tree / name).write_bytes(b"")
    summaries = base_summaries()
    summaries[name] = summary()
    entries = base_entries()
    entries[name] = entry()
    code, out, err = run(make_report(summaries), make_table(entries))
    assert (code, err) == (0, "")
    assert out.isascii()
    assert base_line("src/caf\\xe9.py") in out.splitlines()
    assert out.splitlines()[-1] == (
        "OK: 7 modules within their ceilings, 0 BETTER; structure equal (7 modules); branches gated"
    )


def test_error_messages_are_plain_ascii(tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    table = write(tmp_path, "table.json", make_table(base_entries()))
    code = check.main([str(tmp_path / ("absent-" + chr(0x142) + ".json")), str(table)], python=NEW_PYTHON)
    captured = capsys.readouterr()
    assert (code, captured.out) == (2, "")
    assert captured.err.isascii()
    assert "absent-\\u0142.json: " in captured.err


def test_a_missing_argument_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        check.main(["report.json"])
    assert raised.value.code == 2
    assert "usage: python -m tools.coverage_gate.check" in capsys.readouterr().err


def test_the_exit_codes_reach_the_shell(tree: Path, tmp_path: Path) -> None:
    report = write(tmp_path, "report.json", make_report(base_summaries()))
    good = write(tmp_path, "good.json", make_table(base_entries()))
    entries = base_entries()
    entries["src/a.py"] = entry(missing=1)
    bad = write(tmp_path, "bad.json", make_table(entries))
    passed = run_module("tools.coverage_gate.check", [str(report), str(good)], tree)
    failed = run_module("tools.coverage_gate.check", [str(report), str(bad)], tree)
    broken = run_module("tools.coverage_gate.check", [str(tmp_path / "absent.json"), str(good)], tree)
    assert (passed.returncode, failed.returncode, broken.returncode) == (0, 1, 2)
    assert passed.stdout.splitlines()[-1].startswith("OK: 6 modules within their ceilings, 0 BETTER; structure equal")
    assert "FAIL OVER src/a.py: lines missing 2 > ceiling 1" in failed.stdout.splitlines()
    assert broken.stdout == ""
    assert "ERROR: cannot read the report " in broken.stderr
