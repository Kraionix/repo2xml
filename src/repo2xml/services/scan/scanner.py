from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional, Set

from repo2xml.domain.model import FileEntry
from repo2xml.services.scan.gitignore import GitignoreEngine, IgnoreRuleset

logger = logging.getLogger("repo2xml.scanner")


@dataclass(slots=True)
class ScanStats:
    """
    Scanner statistics for visibility without log spam.

    We avoid logging per-file errors, because on some systems (Windows locks, permissions)
    this can easily produce thousands of lines. Instead we collect counters and emit a
    single summary warning after scanning.
    """
    dirs_scandir_errors: int = 0
    entry_is_symlink_errors: int = 0
    entry_is_dir_errors: int = 0
    entry_is_file_errors: int = 0
    entry_stat_errors: int = 0
    entry_readlink_errors: int = 0

    def has_issues(self) -> bool:
        return any(
            x > 0
            for x in (
                self.dirs_scandir_errors,
                self.entry_is_symlink_errors,
                self.entry_is_dir_errors,
                self.entry_is_file_errors,
                self.entry_stat_errors,
                self.entry_readlink_errors,
            )
        )

    def summary(self) -> str:
        parts: list[str] = []
        if self.dirs_scandir_errors:
            parts.append(f"dirs_scandir_errors={self.dirs_scandir_errors}")
        if self.entry_is_symlink_errors:
            parts.append(f"entry_is_symlink_errors={self.entry_is_symlink_errors}")
        if self.entry_is_dir_errors:
            parts.append(f"entry_is_dir_errors={self.entry_is_dir_errors}")
        if self.entry_is_file_errors:
            parts.append(f"entry_is_file_errors={self.entry_is_file_errors}")
        if self.entry_stat_errors:
            parts.append(f"entry_stat_errors={self.entry_stat_errors}")
        if self.entry_readlink_errors:
            parts.append(f"entry_readlink_errors={self.entry_readlink_errors}")
        return ", ".join(parts) if parts else "no issues"


class FileSystemScanner:
    """
    Single-pass filesystem scanner with a Git-compatible .gitignore stack.

    Design notes:
    - We do not traverse ".git" by default (hard exclude).
    - We implement correct .gitignore scoping rules using pathspec's gitwildmatch matcher.
    - For correctness, ignore decisions for directories require knowing whether an entry is a directory,
      so we generally call is_dir() before ignore checks (still avoiding stat() for ignored entries).
    """

    def __init__(
        self,
        *,
        root: Path,
        gitignore_engine: GitignoreEngine,
        use_gitignore: bool = True,
        follow_symlinks_dirs: bool = False,
        symlinks_files: str = "follow",  # follow|skip|as-link
        hard_exclude_dirs: Optional[Set[str]] = None,
    ):
        self.root = root.resolve()
        self.ge = gitignore_engine
        self.use_gitignore = use_gitignore
        self.follow_symlinks_dirs = follow_symlinks_dirs
        self.symlinks_files = symlinks_files
        self.hard_exclude_dirs = set(hard_exclude_dirs or {".git"})

        # Cycle protection: track visited directories by (dev, ino) when available,
        # otherwise by resolved path string. This matters when following symlink dirs.
        self._visited_dir_keys: set[tuple[int, int] | str] = set()

        self.stats = ScanStats()

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

    def scan(self) -> Generator[FileEntry, None, None]:
        """
        Yield FileEntry entries lazily.

        A single FileSystemScanner instance may be reused (library usage), so we reset
        per-run state (visited set and stats) at the start of each scan.
        """
        self._visited_dir_keys = set()
        self.stats = ScanStats()

        # Start stack with root-scoped base patterns (ALWAYS_IGNORE + user overrides).
        stack: list[IgnoreRuleset] = [self.ge.base_ruleset()]

        # Mark root as visited to avoid pathological loops.
        self._visited_dir_keys.add(self._dir_key(self.root))

        yield from self._scan_dir(self.root, "", stack)

    def _scan_dir(
        self,
        dir_abs: Path,
        dir_rel: str,
        stack: list[IgnoreRuleset],
    ) -> Generator[FileEntry, None, None]:
        # Push local .gitignore rules (if enabled and present).
        pushed = False
        if self.use_gitignore:
            rs = self.ge.load_dir_ruleset(dir_abs=dir_abs, dir_rel_posix=dir_rel)
            if rs is not None:
                stack.append(rs)
                pushed = True

        try:
            entries = list(os.scandir(dir_abs))
        except OSError as e:
            self.stats.dirs_scandir_errors += 1
            logger.warning("Cannot read directory: %s (%s)", dir_abs, e)
            if pushed:
                stack.pop()
            return

        # Performance:
        # - Do not sort entries here. The export pipeline collects and sorts all FileEntry
        #   objects globally by rel_path, so per-directory sorting is redundant overhead.

        for entry in entries:
            name = entry.name

            # Hard exclude by directory name (never traverse / include).
            if name in self.hard_exclude_dirs:
                continue

            rel = f"{dir_rel}/{name}" if dir_rel else name

            try:
                is_symlink = entry.is_symlink()
            except OSError:
                self.stats.entry_is_symlink_errors += 1
                is_symlink = False

            # Directory detection:
            # - For regular entries: do not follow symlinks
            # - For symlink entries: follow only if enabled
            try:
                if is_symlink:
                    is_dir = entry.is_dir(follow_symlinks=self.follow_symlinks_dirs)
                else:
                    is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                self.stats.entry_is_dir_errors += 1
                is_dir = False

            # Git-compatible ignore check (scoped).
            if self.ge.is_ignored(rel_path_posix=rel, is_dir=is_dir, stack=stack):
                continue

            if is_dir:
                # If it's a symlinked directory and following is disabled, skip it.
                if is_symlink and not self.follow_symlinks_dirs:
                    continue

                child_dir = Path(entry.path)

                # Cycle protection (especially important when following symlink dirs).
                key = self._dir_key(child_dir)
                if key in self._visited_dir_keys:
                    continue
                self._visited_dir_keys.add(key)

                yield from self._scan_dir(child_dir, rel, stack)
                continue

            # Symlink file handling.
            if is_symlink and self.symlinks_files == "skip":
                continue

            # Special case: symlink file in "as-link" mode.
            #
            # Goal: do NOT touch the symlink target (no follow_symlinks=True checks).
            # This also ensures broken symlinks are still included in output.
            if is_symlink and self.symlinks_files == "as-link":
                symlink_target: Optional[str] = None
                try:
                    symlink_target = os.readlink(entry.path)
                except OSError:
                    self.stats.entry_readlink_errors += 1
                    symlink_target = None

                try:
                    st = entry.stat(follow_symlinks=False)
                except OSError:
                    self.stats.entry_stat_errors += 1
                    continue

                yield FileEntry(
                    abs_path=Path(entry.path),
                    rel_path=rel,
                    name=name,
                    size=st.st_size,
                    mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)),
                    is_symlink=True,
                    symlink_target=symlink_target,
                )
                continue

            # Regular file handling (including symlink files in "follow" mode).
            #
            # Performance:
            # - Avoid extra stat-like work by using a single stat() call and checking st_mode
            #   instead of calling entry.is_file() and then entry.stat() again.
            try:
                st = entry.stat(follow_symlinks=True)
            except OSError:
                self.stats.entry_stat_errors += 1
                continue

            if not stat.S_ISREG(st.st_mode):
                continue

            symlink_target = None
            if is_symlink:
                try:
                    symlink_target = os.readlink(entry.path)
                except OSError:
                    self.stats.entry_readlink_errors += 1
                    symlink_target = None

            yield FileEntry(
                abs_path=Path(entry.path),
                rel_path=rel,
                name=name,
                size=st.st_size,
                mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)),
                is_symlink=is_symlink,
                symlink_target=symlink_target,
            )

        # Pop local rules before returning to parent.
        if pushed:
            stack.pop()