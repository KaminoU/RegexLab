"""
Write the table of the coverage gate from coverage.py JSON reports, one report per cell (an OS and a Python version).

Run from the repository root (the pragma counts are read from the source files):

    python -m tools.coverage_gate.generate opening --out TABLE --branch-coverage-version V --cell NAME=REPORT [...]
        [--replace]
    python -m tools.coverage_gate.generate ratchet --table TABLE --cell NAME=REPORT [...]

opening: every report holds the same modules. Per module, the ceiling of missing lines and the frozen count of excluded
lines are the maximum over all the cells; the ceiling of missing branches is the maximum over the cells whose report
comes from coverage.py V (one at least); the frozen count of pragma lines is counted in the source file. An existing
table is replaced only with --replace.

ratchet: the cells are exactly those of the table, and every report holds exactly its modules (a new or a removed
module needs an explicit opening). Every value becomes min(its value, its maximum measured now), branches over the
cells of the table's coverage.py version: a ratchet never raises a value. The table is rewritten in place.

Exit 0: the table is written. Exit 2: an input cannot be used, and nothing is written.
"""

from __future__ import annotations

import argparse
import sys

from tools.coverage_gate._report import (
    CELL_NAME,
    Entry,
    InputError,
    Report,
    Table,
    count_pragmas,
    load_report,
    load_table,
    plural,
    printable,
    write_table,
)


def parse_cells(values: list[str]) -> list[tuple[str, str]]:
    """The (name, report path) of each --cell NAME=REPORT, every name valid and given once."""
    cells: list[tuple[str, str]] = []
    for value in values:
        name, separator, path = value.partition("=")
        if not separator:
            raise InputError(f"--cell {value}: expected NAME=REPORT")
        if not CELL_NAME.fullmatch(name):
            raise InputError(f"--cell {value}: a cell name is made of letters, digits, '.', '_' and '-'")
        if not path:
            raise InputError(f"--cell {value}: no report path after '='")
        if any(name == known for known, _ in cells):
            raise InputError(f"--cell {value}: the cell {name} is given twice")
        cells.append((name, path))
    return cells


def _difference(expected: set[str], actual: set[str]) -> str:
    """What actual lacks and adds, against expected."""
    missing = ", ".join(sorted(expected - actual)) or "none"
    unexpected = ", ".join(sorted(actual - expected)) or "none"
    return f"missing {missing}; unexpected {unexpected}"


def _versions(reports: list[tuple[str, Report]]) -> str:
    """The coverage.py version of each cell's report."""
    return ", ".join(f"{name}: {report.version}" for name, report in sorted(reports))


def opening(out: str, version: str, cells: list[tuple[str, str]], replace: bool) -> int:
    """Write a new table: the maximum over the cells, branches over the cells of coverage.py version."""
    reports = [(name, load_report(path)) for name, path in cells]
    first_name, first = reports[0]
    modules = set(first.files)
    for name, report in reports[1:]:
        if set(report.files) != modules:
            raise InputError(
                f"the reports do not hold the same modules: cell {name}, against cell {first_name}: "
                f"{_difference(modules, set(report.files))}"
            )
    branch_reports = [report for _, report in reports if report.version == version]
    if not branch_reports:
        raise InputError(
            f"no report comes from coverage {version} ({_versions(reports)}): the branch ceilings need at least one"
        )
    entries = {
        module: Entry(
            missing_lines=max(report.files[module].missing_lines for _, report in reports),
            missing_branches=max(report.files[module].missing_branches for report in branch_reports),
            excluded_lines=max(report.files[module].excluded_lines for _, report in reports),
            pragmas=count_pragmas(module),
        )
        for module in sorted(modules)
    }
    names = sorted(name for name, _ in cells)
    write_table(out, Table(version, names, entries), replace)
    for module, entry in entries.items():
        print(
            f"{printable(module)}: missing lines {entry.missing_lines}, missing branches {entry.missing_branches}, "
            f"excluded lines {entry.excluded_lines}, pragmas {entry.pragmas}"
        )
    branch_names = sorted(name for name, report in reports if report.version == version)
    print(
        f"opening: wrote {printable(out)}: {plural(len(entries), 'module')}; cells {', '.join(names)}; branch "
        f"ceilings from {', '.join(branch_names)} (coverage {printable(version)})"
    )
    return 0


def ratchet(path: str, cells: list[tuple[str, str]]) -> int:
    """Lower every value of the table to the maximum measured over its cells, never above its value; write in place."""
    table = load_table(path)
    given = sorted(name for name, _ in cells)
    if given != sorted(table.cells):
        raise InputError(
            f"a ratchet takes exactly the cells of the table: given {', '.join(given)}; the table has "
            f"{', '.join(sorted(table.cells))}"
        )
    reports = [(name, load_report(report)) for name, report in cells]
    for name, report in reports:
        if set(report.files) != set(table.modules):
            raise InputError(
                f"cell {name}: the modules differ from the table ({_difference(set(table.modules), set(report.files))}): "
                "NEW and GONE modules need an explicit opening"
            )
    branch_reports = [report for _, report in reports if report.version == table.branch_coverage_version]
    if not branch_reports:
        raise InputError(
            f"no report comes from coverage {table.branch_coverage_version} ({_versions(reports)}), the version of "
            "the table's branch ceilings: open a new table"
        )
    entries: dict[str, Entry] = {}
    lines = []
    lowered = above = 0
    for module, old in sorted(table.modules.items()):
        measured = Entry(
            missing_lines=max(report.files[module].missing_lines for _, report in reports),
            missing_branches=max(report.files[module].missing_branches for report in branch_reports),
            excluded_lines=max(report.files[module].excluded_lines for _, report in reports),
            pragmas=count_pragmas(module),
        )
        new = Entry(*(min(value, now) for value, now in zip(old, measured)))
        lowered += sum(1 for value, kept in zip(old, new) if kept < value)
        above += sum(1 for value, now in zip(old, measured) if now > value)
        entries[module] = new
        lines.append(
            f"{printable(module)}: missing lines {old.missing_lines} -> {new.missing_lines} (max measured "
            f"{measured.missing_lines}), missing branches {old.missing_branches} -> {new.missing_branches} (max "
            f"measured {measured.missing_branches}), excluded lines {old.excluded_lines} -> {new.excluded_lines} (max "
            f"measured {measured.excluded_lines}), pragmas {old.pragmas} -> {new.pragmas} (on disk {measured.pragmas})"
        )
    write_table(path, Table(table.branch_coverage_version, table.cells, entries), replace=True)
    for line in lines:
        print(line)
    print(
        f"ratchet: wrote {printable(path)}: {plural(len(entries), 'module')}; {plural(lowered, 'value')} lowered, "
        f"{above} measured above the table and kept (never raised)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the generator."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.coverage_gate.generate",
        description="Write the table of the coverage gate from coverage.py JSON reports, one report per cell.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    opening_parser = commands.add_parser("opening", help="write a new table from the reports of the cells")
    opening_parser.add_argument("--out", required=True, help="the table to write")
    opening_parser.add_argument(
        "--branch-coverage-version", required=True, help="the coverage.py version the branch ceilings come from"
    )
    opening_parser.add_argument(
        "--cell", action="append", required=True, metavar="NAME=REPORT", help="a cell and its JSON report"
    )
    opening_parser.add_argument("--replace", action="store_true", help="replace an existing table")
    ratchet_parser = commands.add_parser("ratchet", help="lower the values of a table to what the cells measure")
    ratchet_parser.add_argument("--table", required=True, help="the table to lower, rewritten in place")
    ratchet_parser.add_argument(
        "--cell", action="append", required=True, metavar="NAME=REPORT", help="a cell of the table and its JSON report"
    )
    args = parser.parse_args(argv)
    try:
        cells = parse_cells(args.cell)
        if args.command == "opening":
            return opening(args.out, args.branch_coverage_version, cells, args.replace)
        return ratchet(args.table, cells)
    except InputError as exc:
        print(f"ERROR: {printable(str(exc))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
