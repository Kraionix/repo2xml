from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Generator, Optional, Set

from .domain import FileNode
from .filters import FilterEngine

logger = logging.getLogger("repo2xml.scanner")


class RepositoryScanner:
    """
    Single-pass repository scanner with an on-the-fly gitignore stack.

    Key behaviors:
    - Only one filesystem traversal (no pre-scan for .gitignore files).
    - When entering a directory, read its .gitignore (if enabled) and push rules.
    - When leaving a directory, pop those rules.
    - Supports:
        - follow / not follow symlink directories (with cycle protection)
        - symlink file handling: follow | skip | as-link
        - hard-exclude directory names (always skipped)
    """

    def __init__(
        self,
        root: Path,
        filter_engine: FilterEngine,
        *,
        use_gitignore: bool = True,
        follow_symlinks_dirs: bool = False,
        symlinks_files: str = "follow",  # follow|skip|as-link
        hard_exclude_dirs: Optional[Set[str]] = None,
    ):
        self.root = root.resolve()
        self.fe = filter_engine
        self.use_gitignore = use_gitignore
        self.follow_symlinks_dirs = follow_symlinks_dirs
        self.symlinks_files = symlinks_files
        self.hard_exclude_dirs = set(hard_exclude_dirs or {".git"})

        # Cycle protection: track visited directories by (dev, ino) when available,
        # otherwise by resolved path string. This matters when following symlink dirs.
        self._visited_dir_keys: set[tuple[int, int] | str] = set()

    def _dir_key(self, p: Path) -> tuple[int, int] | str:
        """
        Return a stable-ish identity key for a directory:
        - Prefer (st_dev, st_ino) if present.
        - Fallback to resolved path string.
        """
        try:
            st = p.stat()
            ino = getattr(st, "st_ino", 0) or 0
            dev = getattr(st, "st_dev", 0) or 0
            if ino != 0 or dev != 0:
                return (int(dev), int(ino))
        except OSError:
            pass

        try:
            return str(p.resolve())
        except Exception:
            return str(p)

    def scan(self) -> Generator[FileNode, None, None]:
        """
        Yield FileNode entries lazily.

        Implementation detail:
        We keep a single mutable list of patterns (stack-like) and extend/delete
        as we traverse directories. This avoids repeated list allocations.
        """
        patterns: list[str] = list(self.fe.base_patterns)
        spec = self.fe.compile(patterns)

        # Mark root as visited to avoid pathological loops.
        self._visited_dir_keys.add(self._dir_key(self.root))

        yield from self._scan_dir(self.root, "", patterns, spec)

    def _scan_dir(self, dir_abs: Path, dir_rel: str, patterns: list[str], spec) -> Generator[FileNode, None, None]:
        # Push local .gitignore rules (if enabled and present).
        pushed = 0
        if self.use_gitignore:
            local_rules = self.fe.read_dir_gitignore_prefixed(dir_abs, dir_rel)
            if local_rules:
                patterns.extend(local_rules)
                pushed = len(local_rules)
                spec = self.fe.compile_child_cached(spec, local_rules, patterns)

        try:
            entries = list(os.scandir(dir_abs))
        except OSError as e:
            # Permissions / transient filesystem errors: skip this directory.
            # Keep scanning other directories (fail-soft), but make it visible to users.
            logger.warning("Cannot read directory: %s (%s)", dir_abs, e)
            if pushed:
                del patterns[-pushed:]
            return

        # Deterministic order: stable output is helpful for diffs and LLM prompts.
        entries.sort(key=lambda e: e.name)

        for entry in entries:
            name = entry.name

            # Hard exclude by directory name (never traverse / include).
            if name in self.hard_exclude_dirs:
                continue

            rel = f"{dir_rel}/{name}" if dir_rel else name
            rel = rel.replace("\\", "/")

            try:
                is_symlink = entry.is_symlink()
            except OSError:
                is_symlink = False

            # Directory handling (do not follow symlink dirs unless enabled).
            try:
                is_dir_no_follow = entry.is_dir(follow_symlinks=False)
            except OSError:
                is_dir_no_follow = False

            if is_dir_no_follow:
                if is_symlink and not self.follow_symlinks_dirs:
                    continue

                # Pruning: if the directory is ignored, do not descend.
                if spec.match_file(rel) or spec.match_file(rel + "/"):
                    continue

                child_dir = Path(entry.path)

                # Cycle protection (especially important when following symlink dirs).
                key = self._dir_key(child_dir)
                if key in self._visited_dir_keys:
                    continue
                self._visited_dir_keys.add(key)

                yield from self._scan_dir(child_dir, rel, patterns, spec)
                continue

            # Symlink file handling.
            # Important note:
            # - For "as-link" mode we still need to *discover* symlinked files.
            #   Using is_file(follow_symlinks=False) often returns False for symlink entries,
            #   so we always classify files with follow_symlinks=True and control "content reads"
            #   later in the API layer.
            if is_symlink and self.symlinks_files == "skip":
                continue

            try:
                is_file = entry.is_file(follow_symlinks=True)
            except OSError:
                continue

            if not is_file:
                continue

            if spec.match_file(rel):
                continue

            symlink_target: Optional[str] = None
            if is_symlink:
                try:
                    symlink_target = os.readlink(entry.path)
                except OSError:
                    symlink_target = None

            # File stat: we follow symlinks here to get stable metadata about the target file.
            # The actual content read is controlled later (Repo2XML._process_node).
            try:
                st = entry.stat(follow_symlinks=True)
            except OSError:
                continue

            yield FileNode(
                path=Path(entry.path),
                rel_path=rel,
                name=name,
                size=st.st_size,
                mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)),
                is_symlink=is_symlink,
                symlink_target=symlink_target,
            )

        # Pop local rules before returning to parent.
        if pushed:
            del patterns[-pushed:]