# src/repo2xml/services/scan/scanner.py
from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Optional, Set, Union, Sequence, Dict, List, Tuple

from repo2xml.contracts import IgnoreProvider
from repo2xml.config import SymlinkFilesMode
from repo2xml.domain.model import FileEntry
from repo2xml.domain.ignore import IgnoreRuleset

logger = logging.getLogger("repo2xml.scanner")


@dataclass(slots=True)
class ScanStats:
    """
    Scanner statistics for visibility without log spam.

    We avoid logging per-file errors, because on some systems (Windows locks, permissions)
    this can easily produce thousands of lines. Instead we collect counters and emit a
    single summary warning after scanning.

    Extended with detailed error tracking.
    """
    dirs_scandir_errors: int = 0
    entry_is_symlink_errors: int = 0
    entry_is_dir_errors: int = 0
    entry_is_file_errors: int = 0
    entry_stat_errors: int = 0
    entry_readlink_errors: int = 0

    errors_by_type: Dict[str, int] = field(default_factory=dict)
    error_examples: List[Tuple[str, str]] = field(default_factory=list)
    _max_examples: int = 10

    def record_error(self, rel_path: str, error: Exception) -> None:
        error_type = type(error).__name__
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
        if len(self.error_examples) < self._max_examples:
            self.error_examples.append((rel_path, str(error)))

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
        ) or bool(self.errors_by_type)

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
        if self.errors_by_type:
            by_type = ", ".join(f"{k}={v}" for k, v in self.errors_by_type.items())
            parts.append(f"by_type: {by_type}")
        return ", ".join(parts) if parts else "no issues"


@dataclass(slots=True, frozen=True)
class _DirFrame:
    dir_abs: Path
    dir_rel: str


@dataclass(slots=True, frozen=True)
class _ExitFrame:
    pop_ruleset: bool


_WorkFrame = Union[_DirFrame, _ExitFrame]


class FileSystemScanner:
    """
    Single-pass filesystem scanner with a Git-compatible .gitignore stack.

    Design notes:
    - We do not traverse ".git" by default (hard exclude).
    - We implement correct .gitignore scoping rules using pathspec's gitwildmatch matcher.
    - We use an iterative DFS with a work stack and exit markers to support streaming
      scandir() without accumulating open directory handles across recursion depth.
    - For correctness, ignore decisions for directories require knowing whether an entry is a directory,
      so we generally call is_dir() before ignore checks (still avoiding stat() for ignored entries).
    """

    def __init__(
        self,
        *,
        root: Path,
        ignore_provider: IgnoreProvider,
        use_gitignore: bool = True,
        follow_symlinks_dirs: bool = False,
        symlinks_files: str = "follow",
        hard_exclude_dirs: Optional[Set[str]] = None,
    ):
        self.root = root.resolve()
        self.ignore_provider = ignore_provider
        self.use_gitignore = use_gitignore
        self.follow_symlinks_dirs = follow_symlinks_dirs
        self.symlinks_files = SymlinkFilesMode(symlinks_files)
        self.hard_exclude_dirs = set(hard_exclude_dirs or {".git"})

        self._visited_dir_keys: set[tuple[int, int] | str] = set()
        self.stats = ScanStats()

    def _dir_key(self, p: Path) -> tuple[int, int] | str:
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
        self._visited_dir_keys = set()
        self.stats = ScanStats()

        ignore_stack: list[IgnoreRuleset] = [self.ignore_provider.base_ruleset()]
        self._visited_dir_keys.add(self._dir_key(self.root))

        work_stack: list[_WorkFrame] = [_DirFrame(dir_abs=self.root, dir_rel="")]

        while work_stack:
            frame = work_stack.pop()

            if isinstance(frame, _ExitFrame):
                if frame.pop_ruleset:
                    ignore_stack.pop()
                continue

            dir_abs = frame.dir_abs
            dir_rel = frame.dir_rel

            pushed = False
            if self.use_gitignore:
                rs = self.ignore_provider.load_dir_ruleset(dir_abs=dir_abs, dir_rel_posix=dir_rel)
                if rs is not None:
                    ignore_stack.append(rs)
                    pushed = True

            if pushed:
                work_stack.append(_ExitFrame(pop_ruleset=True))

            try:
                it = os.scandir(dir_abs)
            except OSError as e:
                self.stats.dirs_scandir_errors += 1
                self.stats.record_error(dir_rel, e)
                logger.debug("Cannot read directory: %s (%s)", dir_abs, e)
                continue

            with it:
                for entry in it:
                    name = entry.name
                    if name in self.hard_exclude_dirs:
                        continue

                    rel = f"{dir_rel}/{name}" if dir_rel else name

                    try:
                        is_symlink = entry.is_symlink()
                    except OSError as e:
                        self.stats.entry_is_symlink_errors += 1
                        self.stats.record_error(rel, e)
                        logger.debug("is_symlink error for %s: %s", rel, e)
                        is_symlink = False

                    try:
                        if is_symlink:
                            is_dir = entry.is_dir(follow_symlinks=self.follow_symlinks_dirs)
                        else:
                            is_dir = entry.is_dir(follow_symlinks=False)
                    except OSError as e:
                        self.stats.entry_is_dir_errors += 1
                        self.stats.record_error(rel, e)
                        logger.debug("is_dir error for %s: %s", rel, e)
                        is_dir = False

                    if self.ignore_provider.is_ignored(rel_path_posix=rel, is_dir=is_dir, stack=ignore_stack):
                        continue

                    if is_dir:
                        if is_symlink and not self.follow_symlinks_dirs:
                            continue
                        child_dir = Path(entry.path)
                        key = self._dir_key(child_dir)
                        if key in self._visited_dir_keys:
                            continue
                        self._visited_dir_keys.add(key)
                        work_stack.append(_DirFrame(dir_abs=child_dir, dir_rel=rel))
                        continue

                    if is_symlink and self.symlinks_files == SymlinkFilesMode.skip:
                        continue

                    if is_symlink and self.symlinks_files == SymlinkFilesMode.as_link:
                        symlink_target: Optional[str] = None
                        try:
                            symlink_target = os.readlink(entry.path)
                        except OSError as e:
                            self.stats.entry_readlink_errors += 1
                            self.stats.record_error(rel, e)
                            logger.debug("readlink error for %s: %s", rel, e)
                            symlink_target = None

                        try:
                            st = entry.stat(follow_symlinks=False)
                        except OSError as e:
                            self.stats.entry_stat_errors += 1
                            self.stats.record_error(rel, e)
                            logger.debug("stat error for %s: %s", rel, e)
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

                    try:
                        st = entry.stat(follow_symlinks=True)
                    except OSError as e:
                        self.stats.entry_stat_errors += 1
                        self.stats.record_error(rel, e)
                        logger.debug("stat error for %s: %s", rel, e)
                        continue

                    if not stat.S_ISREG(st.st_mode):
                        continue

                    symlink_target = None
                    if is_symlink:
                        try:
                            symlink_target = os.readlink(entry.path)
                        except OSError as e:
                            self.stats.entry_readlink_errors += 1
                            self.stats.record_error(rel, e)
                            logger.debug("readlink error for %s: %s", rel, e)
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