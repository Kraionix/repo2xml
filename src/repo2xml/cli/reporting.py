# src/repo2xml/cli/reporting.py
"""Rich‑based reporting helpers (tree, tables)."""
from __future__ import annotations

from typing import Dict, List

from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from repo2xml.domain.model import FileEntry


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