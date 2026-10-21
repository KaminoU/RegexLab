"""
Coverage gate: every measured module within its ceilings of missing lines and missing branches.

Run from the repository root, on the coverage.py JSON report of the tests (measured with branch coverage):

    python -m tools.coverage_gate.check REPORT TABLE

The ceilings are whole counts, never percentages: no rounding anywhere. Missing branches are compared from Python 3.10
on only, where the report must come from the coverage.py version of the table's branch ceilings; before 3.10 they are
printed, never compared. Excluded lines and lines holding a coverage pragma are frozen: neither may rise. The structure
witness requires the report to hold exactly the .py files found under src/ and tools/, and RegexLab.py.

Exit 0: every module within its ceilings. Exit 1: a gate failure, every failure listed. Exit 2: an input cannot be used.
"""

from __future__ import annotations

import argparse
import sys

from tools.coverage_gate._report import (
    Entry,
    InputError,
    Report,
    Summary,
    Table,
    count_pragmas,
    load_report,
    load_table,
    modules_on_disk,
    plural,
    printable,
)

# Missing branches are compared from this Python version on. Before it, pip resolves coverage.py 7.6.1, whose branch
# counts are not those of the version the table's branch ceilings come from.
BRANCH_GATE_PYTHON = (3, 10)

KINDS = ("OVER", "EXCLUDED", "PRAGMAS", "NEW", "GONE", "STRUCTURE")


def _percent(covered: int, total: int) -> str:
    """covered/total in percent, rounded down to 2 decimals; 100.00% when there is nothing to cover."""
    if total == 0:
        return "100.00%"
    whole, hundredths = divmod(10000 * covered // total, 100)
    return f"{whole}.{hundredths:02d}%"


def structure_failures(on_disk: set[str], measured: set[str]) -> list[tuple[str, str]]:
    """The structure witness: the report holds exactly the measured files found on disk."""
    failures = [
        ("STRUCTURE", f"FAIL STRUCTURE {printable(module)}: on disk, missing from the report")
        for module in sorted(on_disk - measured)
    ]
    failures += [
        ("STRUCTURE", f"FAIL STRUCTURE {printable(module)}: in the report, not on disk")
        for module in sorted(measured - on_disk)
    ]
    return failures


def judge(
    module: str, summary: Summary, entry: Entry, pragmas: int | None, gated: bool
) -> tuple[str, list[tuple[str, str]], bool]:
    """The line of a module that is in the report and in the table, its failures, and whether it is BETTER."""
    name = printable(module)
    failures = []
    if summary.missing_lines > entry.missing_lines:
        failures.append(
            ("OVER", f"FAIL OVER {name}: lines missing {summary.missing_lines} > ceiling {entry.missing_lines}")
        )
    if gated and summary.missing_branches > entry.missing_branches:
        failures.append(
            (
                "OVER",
                f"FAIL OVER {name}: branches missing {summary.missing_branches} > ceiling {entry.missing_branches}",
            )
        )
    if summary.excluded_lines > entry.excluded_lines:
        failures.append(
            (
                "EXCLUDED",
                f"FAIL EXCLUDED {name}: excluded lines {summary.excluded_lines} > frozen {entry.excluded_lines}",
            )
        )
    if pragmas is not None and pragmas > entry.pragmas:
        failures.append(
            ("PRAGMAS", f"FAIL PRAGMAS {name}: lines with a coverage pragma {pragmas} > frozen {entry.pragmas}")
        )
    better = summary.missing_lines < entry.missing_lines or (
        gated and summary.missing_branches < entry.missing_branches
    )
    status = "OVER" if failures else "BETTER" if better else "OK"
    branch_ceiling = f"ceiling {entry.missing_branches}" if gated else "not gated"
    pragma_count = "n/a (not on disk)" if pragmas is None else str(pragmas)
    line = (
        f"{status:<6} {name}: lines missing {summary.missing_lines} / ceiling {entry.missing_lines} "
        f"({_percent(summary.covered_lines, summary.num_statements)}); branches missing {summary.missing_branches} / "
        f"{branch_ceiling} ({_percent(summary.covered_branches, summary.num_branches)}); excluded "
        f"{summary.excluded_lines} / frozen {entry.excluded_lines}; pragmas {pragma_count} / frozen {entry.pragmas}"
    )
    return line, failures, status == "BETTER"


def new_module(module: str, summary: Summary, pragmas: int | None) -> tuple[str, list[tuple[str, str]]]:
    """The line of a measured module without a table entry, and its failure."""
    name = printable(module)
    pragma_count = "n/a (not on disk)" if pragmas is None else str(pragmas)
    line = (
        f"NEW    {name}: lines missing {summary.missing_lines} / no entry "
        f"({_percent(summary.covered_lines, summary.num_statements)}); branches missing {summary.missing_branches} / "
        f"no entry ({_percent(summary.covered_branches, summary.num_branches)}); excluded {summary.excluded_lines} / "
        f"no entry; pragmas {pragma_count} / no entry"
    )
    return line, [("NEW", f"FAIL NEW {name}: measured, without a table entry")]


def gone_module(module: str, entry: Entry) -> tuple[str, list[tuple[str, str]]]:
    """The line of a table entry without a measured module, and its failure."""
    name = printable(module)
    line = (
        f"GONE   {name}: not in the report; ceilings: lines {entry.missing_lines}, branches {entry.missing_branches}; "
        f"frozen: excluded {entry.excluded_lines}, pragmas {entry.pragmas}"
    )
    return line, [("GONE", f"FAIL GONE {name}: in the table, not in the report")]


def evaluate(
    report: Report, table: Table, on_disk: set[str], pragmas: dict[str, int], gated: bool
) -> tuple[list[str], list[tuple[str, str]], int]:
    """The module lines, the failures (structure first, then module by module) and the number of BETTER modules."""
    failures = structure_failures(on_disk, set(report.files))
    lines = []
    better = 0
    for module in sorted(set(report.files) | set(table.modules)):
        summary = report.files.get(module)
        entry = table.modules.get(module)
        if summary is None:
            line, module_failures = gone_module(module, table.modules[module])
        elif entry is None:
            line, module_failures = new_module(module, summary, pragmas.get(module))
        else:
            line, module_failures, is_better = judge(module, summary, entry, pragmas.get(module), gated)
            better += is_better
        lines.append(line)
        failures += module_failures
    return lines, failures, better


def main(argv: list[str] | None = None, python: tuple[int, int] | None = None) -> int:
    """Run the gate; python stands for the running interpreter's (major, minor), for the tests."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.coverage_gate.check",
        description="Check every measured module against its ceilings of missing lines and missing branches.",
    )
    parser.add_argument("report", help="coverage.py JSON report of the tests, measured with branch coverage")
    parser.add_argument("table", help="table of ceilings, written by python -m tools.coverage_gate.generate")
    args = parser.parse_args(argv)
    version = sys.version_info[:2] if python is None else python
    gated = version >= BRANCH_GATE_PYTHON
    label = f"{version[0]}.{version[1]}"
    try:
        report = load_report(args.report)
        table = load_table(args.table)
        if gated and report.version != table.branch_coverage_version:
            raise InputError(
                f"the report {report.path} comes from coverage {report.version}, the table's branch ceilings from "
                f"coverage {table.branch_coverage_version}: on Python {label} (>= 3.10) they must be the same version"
            )
        on_disk = modules_on_disk()
        concerned = (set(report.files) | set(table.modules)) & on_disk
        pragmas = {module: count_pragmas(module) for module in sorted(concerned)}
    except InputError as exc:
        print(f"ERROR: {printable(str(exc))}", file=sys.stderr)
        return 2

    lines, failures, better = evaluate(report, table, on_disk, pragmas, gated)
    print(
        f"coverage gate: report {printable(report.path)} (coverage {printable(report.version)}); table "
        f"{printable(args.table)} (branch ceilings for coverage {printable(table.branch_coverage_version)}; cells "
        f"{', '.join(table.cells)}); Python {label}"
    )
    if gated:
        print(f"branches: gated (Python {label} >= 3.10, report and table on coverage {printable(report.version)})")
    else:
        print(f"branches: NOT GATED on Python {label} (< 3.10): missing branches are printed, never compared")
    print(
        f"structure: {len(on_disk)} modules on disk (.py files under src/ and tools/, and RegexLab.py), "
        f"{len(report.files)} in the report"
    )
    for line in lines:
        print(line)
    branches = "branches gated" if gated else f"branches not gated (Python {label})"
    if not failures:
        print(
            f"OK: {plural(len(lines), 'module')} within their ceilings, {better} BETTER; structure equal "
            f"({plural(len(on_disk), 'module')}); {branches}"
        )
        return 0
    for _, failure in failures:
        print(failure)
    counts = ", ".join(f"{kind} {sum(1 for found, _ in failures if found == kind)}" for kind in KINDS)
    print(
        f"FAIL: {plural(len(failures), 'failure')} ({counts}); {plural(len(report.files), 'module')} in the report, "
        f"{len(table.modules)} in the table, {len(on_disk)} on disk; {branches}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
