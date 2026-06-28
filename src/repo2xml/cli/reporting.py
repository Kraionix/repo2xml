# src/repo2xml/cli/reporting.py
"""Rich‑based reporting helpers (tree, tables)."""
from __future__ import annotations

from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from repo2xml.domain.model import FileEntry
from repo2xml.services.scan.scanner import ScanStats


def print_breakdown(title: str, data: Dict[str, int], console: Console) -> None:
    """Print a two‑column Rich table with a cause breakdown."""
    if not data:
        return
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Code", style="dim")
    table.add_column("Count", justify="right")
    for k, v in sorted(data.items(), key=lambda kv: (-kv[1], kv[0])):
        table.add_row(k, str(v))
    console.print(table)


def print_scan_error_breakdown(
    stats: ScanStats,
    console: Console,
    *,
    verbose: bool = False,
) -> None:
    """Print detailed scan error statistics."""
    if not stats.errors_by_type and not stats.has_issues():
        return

    table = Table(title="Scan Errors", show_header=True, header_style="bold")
    table.add_column("Type", style="dim")
    table.add_column("Count", justify="right")

    # Show all error types
    for error_type, count in sorted(stats.errors_by_type.items(), key=lambda x: -x[1]):
        table.add_row(error_type, str(count))

    # Also show the legacy counters if they have values
    legacy_issues = []
    if stats.dirs_scandir_errors:
        legacy_issues.append(("dirs_scandir_errors", stats.dirs_scandir_errors))
    if stats.entry_is_symlink_errors:
        legacy_issues.append(("entry_is_symlink_errors", stats.entry_is_symlink_errors))
    if stats.entry_is_dir_errors:
        legacy_issues.append(("entry_is_dir_errors", stats.entry_is_dir_errors))
    if stats.entry_is_file_errors:
        legacy_issues.append(("entry_is_file_errors", stats.entry_is_file_errors))
    if stats.entry_stat_errors:
        legacy_issues.append(("entry_stat_errors", stats.entry_stat_errors))
    if stats.entry_readlink_errors:
        legacy_issues.append(("entry_readlink_errors", stats.entry_readlink_errors))

    for label, count in legacy_issues:
        if count:
            table.add_row(label, str(count))

    console.print(table)

    if verbose and stats.error_examples:
        examples = Table(title="Error Examples (first 10)", show_header=True, header_style="bold")
        examples.add_column("Path", style="dim")
        examples.add_column("Error", style="red")
        for path, error in stats.error_examples:
            examples.add_row(path, error)
        console.print(examples)


def build_tree(entries: List[FileEntry], console: Console) -> None:
    """Render a filtered file list as a Rich Tree."""
    tree = Tree("Project structure (dry-run)")
    root: dict = {}
    for entry in sorted(entries, key=lambda e: e.rel_path):
        parts = entry.rel_path.split("/")
        current = root
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current.setdefault("__files__", []).append(parts[-1])

    def add_branch(tree_node: Tree, subtree: dict) -> None:
        for name, value in sorted(subtree.items()):
            if name == "__files__":
                for fname in sorted(value):
                    tree_node.add(fname)
            else:
                branch = tree_node.add(name)
                add_branch(branch, value)

    add_branch(tree, root)
    console.print(tree)