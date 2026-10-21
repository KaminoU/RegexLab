"""
Tests of tools/coverage_gate/generate.py: the opening and the ratchet of the coverage gate's table.

opening: the ceiling of each module is the maximum over the cells (branches: over the cells of the table's coverage.py
version), the pragma count is read from disk, and an existing table is kept unless --replace. ratchet: every value
becomes min(its value, the maximum measured), never higher, over exactly the table's cells and modules.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from tools.coverage_gate import check, generate

from tests.unit.test_coverage_gate_check import (
    GATE_VERSION,
    OLD_VERSION,
    base_summaries,
    build_tree,
    entry,
    make_report,
    make_table,
    run_module,
    shown,
    summary,
    write,
)


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The temporary repository of the checker's tests, as the current directory."""
    root = build_tree(tmp_path / "repo")
    monkeypatch.chdir(root)
    return root


def cell(tmp_path: Path, name: str, summaries: dict[str, Any], version: str) -> str:
    """Write the report of a cell; return its --cell value."""
    path = write(tmp_path, f"{name}.json", make_report(summaries, version=version))
    return f"{name}={path}"


def generate_run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    """Run the generator; return (exit code, stdout, stderr)."""
    code = generate.main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def names(directory: Path) -> list[str]:
    """The names in the directory, sorted."""
    return sorted(path.name for path in directory.iterdir())


def canonical(document: Any) -> bytes:
    """The bytes of a table as the generator writes it (pinned by the opening's own test)."""
    return json.dumps(document, indent=2, sort_keys=True).encode("utf-8") + b"\n"


# ============================================================================
# opening
# ============================================================================


def test_opening_takes_the_maximum_over_the_cells_branches_from_the_gate_version_only(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tree / "src" / "core" / "b.py").write_bytes(b"if B:  # pragma: no branch\n    pass\n")
    old = cell(
        tmp_path,
        "windows-3.8",
        {
            "src/a.py": summary(missing=5, branches=10, missing_branches=9, excluded=1),
            "src/core/b.py": summary(missing=0, branches=10, missing_branches=9),
        },
        OLD_VERSION,
    )
    first = cell(
        tmp_path,
        "windows-3.14",
        {
            "src/a.py": summary(missing=3, missing_branches=2),
            "src/core/b.py": summary(missing=1, missing_branches=0, excluded=2),
        },
        GATE_VERSION,
    )
    second = cell(
        tmp_path,
        "ubuntu-3.14",
        {"src/a.py": summary(missing=4, missing_branches=3), "src/core/b.py": summary(missing=0, missing_branches=1)},
        GATE_VERSION,
    )
    out_path = tmp_path / "table.json"
    code, out, err = generate_run(
        capsys,
        "opening",
        "--out",
        str(out_path),
        "--branch-coverage-version",
        GATE_VERSION,
        "--cell",
        old,
        "--cell",
        first,
        "--cell",
        second,
    )
    assert (code, err) == (0, "")
    assert json.loads(out_path.read_bytes()) == {
        "branch_coverage_version": "7.16.2",
        "cells": ["ubuntu-3.14", "windows-3.14", "windows-3.8"],
        "format": 1,
        "modules": {
            "src/a.py": {"excluded_lines": 1, "missing_branches": 3, "missing_lines": 5, "pragmas": 0},
            "src/core/b.py": {"excluded_lines": 2, "missing_branches": 1, "missing_lines": 1, "pragmas": 1},
        },
    }
    assert out.splitlines() == [
        "src/a.py: missing lines 5, missing branches 3, excluded lines 1, pragmas 0",
        "src/core/b.py: missing lines 1, missing branches 1, excluded lines 2, pragmas 1",
        f"opening: wrote {shown(str(out_path))}: 2 modules; cells ubuntu-3.14, windows-3.14, windows-3.8; "
        "branch ceilings from ubuntu-3.14, windows-3.14 (coverage 7.16.2)",
    ]


def test_the_table_file_is_sorted_json_indented_by_2_with_a_final_newline(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = cell(
        tmp_path, "linux-3.14", {"src\\a.py": summary(missing=3, missing_branches=2, excluded=1)}, GATE_VERSION
    )
    out_path = tmp_path / "table.json"
    code, out, err = generate_run(
        capsys, "opening", "--out", str(out_path), "--branch-coverage-version", GATE_VERSION, "--cell", report
    )
    assert (code, err) == (0, "")
    assert out_path.read_bytes() == (
        b"{\n"
        b'  "branch_coverage_version": "7.16.2",\n'
        b'  "cells": [\n'
        b'    "linux-3.14"\n'
        b"  ],\n"
        b'  "format": 1,\n'
        b'  "modules": {\n'
        b'    "src/a.py": {\n'
        b'      "excluded_lines": 1,\n'
        b'      "missing_branches": 2,\n'
        b'      "missing_lines": 3,\n'
        b'      "pragmas": 0\n'
        b"    }\n"
        b"  }\n"
        b"}\n"
    )
    assert out.splitlines() == [
        "src/a.py: missing lines 3, missing branches 2, excluded lines 1, pragmas 0",
        f"opening: wrote {shown(str(out_path))}: 1 module; cells linux-3.14; branch ceilings from linux-3.14 "
        "(coverage 7.16.2)",
    ]


def test_opening_keeps_an_existing_table_unless_replace(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = cell(tmp_path, "linux-3.14", {"src/a.py": summary(missing=3)}, GATE_VERSION)
    out_path = write(tmp_path, "table.json", b"keep me\n")
    args = ["opening", "--out", str(out_path), "--branch-coverage-version", GATE_VERSION, "--cell", report]
    code, out, err = generate_run(capsys, *args)
    assert (code, out) == (2, "")
    assert f"ERROR: the table {shown(str(out_path))} exists: pass --replace to overwrite it" in err
    assert out_path.read_bytes() == b"keep me\n"
    code, out, err = generate_run(capsys, *args, "--replace")
    assert (code, err) == (0, "")
    assert out_path.read_bytes() == canonical(make_table({"src/a.py": entry(missing=3)}, cells=["linux-3.14"]))
    assert out.splitlines()[0] == "src/a.py: missing lines 3, missing branches 1, excluded lines 0, pragmas 0"
    assert names(tmp_path) == ["linux-3.14.json", "repo", "table.json"]  # no temporary file left


def test_the_table_is_written_through_a_temporary_file_next_to_it(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    created: list[str] = []
    real_mkstemp = tempfile.mkstemp

    def spy(*args: Any, **kwargs: Any) -> tuple[int, str]:
        handle, name = real_mkstemp(*args, **kwargs)
        created.append(name)
        return handle, name

    monkeypatch.setattr(tempfile, "mkstemp", spy)
    report = cell(tmp_path, "linux-3.14", {"src/a.py": summary(missing=3)}, GATE_VERSION)
    out_path = tmp_path / "table.json"
    code, out, err = generate_run(
        capsys, "opening", "--out", str(out_path), "--branch-coverage-version", GATE_VERSION, "--cell", report
    )
    assert (code, err) == (0, "")
    assert out.splitlines()[-1].startswith(f"opening: wrote {shown(str(out_path))}: 1 module; ")
    assert [Path(name).parent for name in created] == [out_path.parent]  # one directory: os.replace stays atomic
    assert not Path(created[0]).exists()
    assert json.loads(out_path.read_bytes())["modules"]["src/a.py"]["missing_lines"] == 3


def test_opening_refuses_reports_of_different_modules(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = cell(tmp_path, "a", {"src/a.py": summary(), "src/core/b.py": summary()}, GATE_VERSION)
    second = cell(tmp_path, "b", {"src/a.py": summary(), "tools/gate.py": summary()}, GATE_VERSION)
    out_path = tmp_path / "table.json"
    code, out, err = generate_run(
        capsys,
        "opening",
        "--out",
        str(out_path),
        "--branch-coverage-version",
        GATE_VERSION,
        "--cell",
        first,
        "--cell",
        second,
    )
    assert (code, out) == (2, "")
    assert (
        "ERROR: the reports do not hold the same modules: cell b, against cell a: missing src/core/b.py; "
        "unexpected tools/gate.py"
    ) in err
    assert not out_path.exists()


def test_opening_needs_a_report_of_the_branch_coverage_version(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old = cell(tmp_path, "windows-3.8", {"src/a.py": summary()}, OLD_VERSION)
    other = cell(tmp_path, "linux-3.14", {"src/a.py": summary()}, "7.16.3")
    out_path = tmp_path / "table.json"
    code, out, err = generate_run(
        capsys,
        "opening",
        "--out",
        str(out_path),
        "--branch-coverage-version",
        GATE_VERSION,
        "--cell",
        old,
        "--cell",
        other,
    )
    assert (code, out) == (2, "")
    assert (
        "ERROR: no report comes from coverage 7.16.2 (linux-3.14: 7.16.3, windows-3.8: 7.6.1): the branch ceilings "
        "need at least one"
    ) in err
    assert not out_path.exists()


def test_opening_needs_the_source_files_on_disk(tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report = cell(tmp_path, "linux-3.14", {"src/gone.py": summary()}, GATE_VERSION)
    out_path = tmp_path / "table.json"
    code, out, err = generate_run(
        capsys, "opening", "--out", str(out_path), "--branch-coverage-version", GATE_VERSION, "--cell", report
    )
    assert (code, out) == (2, "")
    assert "ERROR: cannot read the source file src/gone.py: " in err
    assert not out_path.exists()


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("linux-3.14", "expected NAME=REPORT"),
        ("=report.json", "a cell name is made of letters, digits, '.', '_' and '-'"),
        ("linux 3.14=report.json", "a cell name is made of letters, digits, '.', '_' and '-'"),
        ("linux-3.14=", "no report path after '='"),
    ],
)
def test_a_malformed_cell_is_refused(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str, message: str
) -> None:
    out_path = tmp_path / "table.json"
    code, out, err = generate_run(
        capsys, "opening", "--out", str(out_path), "--branch-coverage-version", GATE_VERSION, "--cell", value
    )
    assert (code, out) == (2, "")
    assert f"ERROR: --cell {value}: {message}" in err
    assert not out_path.exists()


def test_a_cell_given_twice_is_refused(tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report = cell(tmp_path, "linux-3.14", {"src/a.py": summary()}, GATE_VERSION)
    out_path = tmp_path / "table.json"
    code, out, err = generate_run(
        capsys,
        "opening",
        "--out",
        str(out_path),
        "--branch-coverage-version",
        GATE_VERSION,
        "--cell",
        report,
        "--cell",
        report,
    )
    assert (code, out) == (2, "")
    assert f"ERROR: --cell {shown(report)}: the cell linux-3.14 is given twice" in err
    assert not out_path.exists()


def test_a_table_that_cannot_be_written_is_an_input_error_and_leaves_nothing(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = cell(tmp_path, "linux-3.14", {"src/a.py": summary()}, GATE_VERSION)
    nowhere = tmp_path / "no-such-directory" / "table.json"
    code, out, err = generate_run(
        capsys, "opening", "--out", str(nowhere), "--branch-coverage-version", GATE_VERSION, "--cell", report
    )
    assert (code, out) == (2, "")
    assert f"ERROR: cannot write the table {shown(str(nowhere))}: " in err
    directory = tmp_path / "a-directory"
    directory.mkdir()
    before = names(tmp_path)
    code, out, err = generate_run(
        capsys,
        "opening",
        "--out",
        str(directory),
        "--branch-coverage-version",
        GATE_VERSION,
        "--cell",
        report,
        "--replace",
    )
    assert (code, out) == (2, "")
    assert f"ERROR: cannot write the table {shown(str(directory))}: " in err
    assert names(tmp_path) == before  # the temporary file is removed
    assert names(directory) == []


def test_an_opened_table_passes_the_checker_on_each_of_its_reports(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old_summaries = base_summaries()
    old_summaries["src/a.py"] = summary(missing=4, branches=10, missing_branches=9)
    new_summaries = base_summaries()
    new_summaries["src/core/b.py"] = summary(missing=3, missing_branches=2)
    old = cell(tmp_path, "windows-3.8", old_summaries, OLD_VERSION)
    new = cell(tmp_path, "windows-3.14", new_summaries, GATE_VERSION)
    table = tmp_path / "table.json"
    code, _, err = generate_run(
        capsys, "opening", "--out", str(table), "--branch-coverage-version", GATE_VERSION, "--cell", old, "--cell", new
    )
    assert (code, err) == (0, "")
    assert check.main([str(tmp_path / "windows-3.8.json"), str(table)], python=(3, 8)) == 0
    assert capsys.readouterr().out.splitlines()[-1] == (
        "OK: 6 modules within their ceilings, 1 BETTER; structure equal (6 modules); branches not gated (Python 3.8)"
    )
    assert check.main([str(tmp_path / "windows-3.14.json"), str(table)], python=(3, 14)) == 0
    assert capsys.readouterr().out.splitlines()[-1] == (
        "OK: 6 modules within their ceilings, 1 BETTER; structure equal (6 modules); branches gated"
    )


# ============================================================================
# ratchet
# ============================================================================


def test_ratchet_lowers_each_value_to_the_maximum_measured_and_never_raises(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tree / "src" / "core" / "b.py").write_bytes(b"B = 2  # pragma: no cover\n")
    cells = ["windows-3.14", "windows-3.8"]
    table = write(
        tmp_path,
        "table.json",
        make_table(
            {
                "src/a.py": entry(missing=5, missing_branches=3, excluded=2, pragmas=1),
                "src/core/b.py": entry(missing=2, missing_branches=1, excluded=0, pragmas=0),
            },
            cells=cells,
        ),
    )
    old = cell(
        tmp_path,
        "windows-3.8",
        {
            "src/a.py": summary(missing=4, branches=10, missing_branches=9, excluded=1),
            "src/core/b.py": summary(missing=3, missing_branches=0),
        },
        OLD_VERSION,
    )
    new = cell(
        tmp_path,
        "windows-3.14",
        {"src/a.py": summary(missing=3, missing_branches=2), "src/core/b.py": summary(missing=1, missing_branches=0)},
        GATE_VERSION,
    )
    before = names(tmp_path)
    code, out, err = generate_run(capsys, "ratchet", "--table", str(table), "--cell", new, "--cell", old)
    assert (code, err) == (0, "")
    assert table.read_bytes() == canonical(
        make_table(
            {
                "src/a.py": entry(missing=4, missing_branches=2, excluded=1, pragmas=0),
                "src/core/b.py": entry(missing=2, missing_branches=0, excluded=0, pragmas=0),
            },
            cells=cells,
        )
    )
    assert names(tmp_path) == before  # in place: no other file, no temporary file left
    assert out.splitlines() == [
        "src/a.py: missing lines 5 -> 4 (max measured 4), missing branches 3 -> 2 (max measured 2), "
        "excluded lines 2 -> 1 (max measured 1), pragmas 1 -> 0 (on disk 0)",
        "src/core/b.py: missing lines 2 -> 2 (max measured 3), missing branches 1 -> 0 (max measured 0), "
        "excluded lines 0 -> 0 (max measured 0), pragmas 0 -> 0 (on disk 1)",
        f"ratchet: wrote {shown(str(table))}: 2 modules; 5 values lowered, 2 measured above the table and kept "
        "(never raised)",
    ]


@pytest.mark.parametrize(
    "given",
    [["windows-3.14"], ["windows-3.14", "linux-3.14"], ["windows-3.14", "windows-3.8", "linux-3.14"]],
)
def test_ratchet_takes_exactly_the_cells_of_the_table(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], given: list[str]
) -> None:
    table = write(
        tmp_path, "table.json", make_table({"src/a.py": entry(missing=5)}, cells=["windows-3.14", "windows-3.8"])
    )
    before = table.read_bytes()
    args = ["ratchet", "--table", str(table)]
    for name in given:
        args += ["--cell", cell(tmp_path, name, {"src/a.py": summary()}, GATE_VERSION)]
    code, out, err = generate_run(capsys, *args)
    assert (code, out) == (2, "")
    assert "ERROR: a ratchet takes exactly the cells of the table: given " in err
    assert "; the table has windows-3.14, windows-3.8" in err
    assert table.read_bytes() == before


@pytest.mark.parametrize(
    ("modules", "difference"),
    [
        (["src/a.py"], "missing src/core/b.py; unexpected none"),
        (["src/a.py", "src/core/b.py", "tools/gate.py"], "missing none; unexpected tools/gate.py"),
    ],
)
def test_ratchet_refuses_reports_whose_modules_differ_from_the_table(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], modules: list[str], difference: str
) -> None:
    table = write(tmp_path, "table.json", make_table({"src/a.py": entry(), "src/core/b.py": entry()}))
    before = table.read_bytes()
    report = cell(tmp_path, "windows-3.14", {module: summary() for module in modules}, GATE_VERSION)
    code, out, err = generate_run(capsys, "ratchet", "--table", str(table), "--cell", report)
    assert (code, out) == (2, "")
    assert (
        f"ERROR: cell windows-3.14: the modules differ from the table ({difference}): NEW and GONE modules need an "
        "explicit opening"
    ) in err
    assert table.read_bytes() == before


def test_ratchet_needs_a_report_of_the_table_branch_coverage_version(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    table = write(tmp_path, "table.json", make_table({"src/a.py": entry(missing=5)}, cells=["windows-3.8"]))
    before = table.read_bytes()
    report = cell(tmp_path, "windows-3.8", {"src/a.py": summary()}, OLD_VERSION)
    code, out, err = generate_run(capsys, "ratchet", "--table", str(table), "--cell", report)
    assert (code, out) == (2, "")
    assert (
        "ERROR: no report comes from coverage 7.16.2 (windows-3.8: 7.6.1), the version of the table's branch "
        "ceilings: open a new table"
    ) in err
    assert table.read_bytes() == before


def test_ratchet_refuses_an_invalid_table(tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    table = write(tmp_path, "table.json", b'{"format": 2}')
    report = cell(tmp_path, "windows-3.14", {"src/a.py": summary()}, GATE_VERSION)
    code, out, err = generate_run(capsys, "ratchet", "--table", str(table), "--cell", report)
    assert (code, out) == (2, "")
    assert f"ERROR: the table {shown(str(table))} has the unknown format 2: this gate reads format 1" in err
    assert table.read_bytes() == b'{"format": 2}'


# ============================================================================
# Process
# ============================================================================


@pytest.mark.parametrize("argv", [[], ["opening"], ["ratchet", "--table", "table.json"], ["other"]])
def test_a_usage_error_exits_2(capsys: pytest.CaptureFixture[str], argv: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        generate.main(argv)
    assert raised.value.code == 2
    assert "usage: python -m tools.coverage_gate.generate" in capsys.readouterr().err


def test_the_generator_exit_codes_reach_the_shell(tree: Path, tmp_path: Path) -> None:
    report = cell(tmp_path, "windows-3.14", {"src/a.py": summary()}, GATE_VERSION)
    table = tmp_path / "table.json"
    opening = ["opening", "--out", str(table), "--branch-coverage-version", GATE_VERSION, "--cell", report]
    opened = run_module("tools.coverage_gate.generate", opening, tree)
    again = run_module("tools.coverage_gate.generate", opening, tree)
    ratchet = run_module("tools.coverage_gate.generate", ["ratchet", "--table", str(table), "--cell", report], tree)
    assert (opened.returncode, again.returncode, ratchet.returncode) == (0, 2, 0)
    assert opened.stdout.splitlines()[-1].startswith(f"opening: wrote {shown(str(table))}: 1 module; ")
    assert again.stdout == ""
    assert "exists: pass --replace to overwrite it" in again.stderr
    assert ratchet.stdout.splitlines()[-1] == (
        f"ratchet: wrote {shown(str(table))}: 1 module; 0 values lowered, 0 measured above the table and kept "
        "(never raised)"
    )
    assert json.loads(table.read_bytes()) == make_table({"src/a.py": entry()}, cells=["windows-3.14"])
