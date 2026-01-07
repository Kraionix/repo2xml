from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable, Generator, List, Optional

from repo2xml.config import BinaryMode, Mode, Repo2XMLConfig, RootPathMode, SymlinkFilesMode
from repo2xml.core.domain import FileNode
from repo2xml.core.filters import FilterEngine
from repo2xml.core.scanner import RepositoryScanner
from repo2xml.ingest.reader import FileIngestor
from repo2xml.output.xml_builder import XMLSerializer

logger = logging.getLogger("repo2xml.api")


class Repo2XML:
    """
    Main API Facade for repo2xml.

    This class orchestrates the scanning, filtering, reading, and serializing
    process. It is designed to be IO-agnostic regarding the output stream.
    """

    def __init__(self, root_path: Path, config: Repo2XMLConfig):
        self.root_path = root_path.resolve()
        self.config = config

        # Initialize core components
        self.filter_engine = FilterEngine(
            self.root_path,
            user_ignore=self.config.ignore_patterns,
            user_include=self.config.include_patterns,
        )
        self.scanner = RepositoryScanner(
            self.root_path,
            self.filter_engine,
            use_gitignore=self.config.use_gitignore,
            follow_symlinks_dirs=self.config.follow_symlinks_dirs,
            symlinks_files=self.config.symlinks_files.value,
            hard_exclude_dirs=set(self.config.hard_exclude_dirs),
        )

    def scan(self) -> Generator[FileNode, None, None]:
        """
        Yield file nodes found in the repository.
        Useful for dry-runs or inspecting structure before processing.
        """
        yield from self.scanner.scan()

    def _root_path_for_meta(self) -> str:
        """
        Format the <root_path> meta field based on config.

        - absolute: full resolved path
        - relative: relative to CWD when possible, else fall back to directory name
        - redact: hide the path (privacy-friendly)
        """
        mode = self.config.root_path_mode

        if mode == RootPathMode.absolute:
            return str(self.root_path)

        if mode == RootPathMode.relative:
            try:
                rel = self.root_path.relative_to(Path.cwd().resolve())
                rel_str = rel.as_posix()
                return rel_str if rel_str else "."
            except Exception:
                # Fall back to directory name (still more private than full absolute).
                return self.root_path.name or "."

        if mode == RootPathMode.redact:
            return "<redacted>"

        # Defensive fallback (should not happen).
        return str(self.root_path)

    def export(
        self,
        output_stream: BinaryIO,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> None:
        """
        Execute the full pipeline and write XML bytes to the output_stream.

        Args:
            output_stream: A writable binary stream (file, stdout, BytesIO).
            progress_callback: Optional function called with incremented count (processed files).
        """
        # Wrap the binary stream into a buffered text writer.
        # This reduces the number of small encode() calls and usually reduces small writes.
        #
        # Important:
        # TextIOWrapper *owns* the underlying buffer and will close it on GC/close.
        # In clipboard mode we write into a BytesIO and need it to remain open after export().
        # Therefore we always detach() the buffer at the end.
        text_out = io.TextIOWrapper(output_stream, encoding="utf-8", newline="")

        def write(s: str) -> None:
            text_out.write(s)

        try:
            # Phase 1: Indexing
            # We need to collect all nodes first to emit the <project_structure> block
            # at the top of the XML file.
            logger.info("Scanning repository: %s", self.root_path)
            all_nodes: List[FileNode] = list(self.scan())

            # Emit a single summary warning for entry-level filesystem errors (no spam).
            if getattr(self.scanner, "stats", None) is not None and self.scanner.stats.has_issues():
                logger.warning(
                    "Scan encountered filesystem errors (some entries skipped): %s",
                    self.scanner.stats.summary(),
                )

            # Keep ordering consistent across <project_structure> and <files>.
            # This also improves diff stability for LLM prompts.
            all_nodes.sort(key=lambda n: n.rel_path)

            total_files = len(all_nodes)
            logger.info("Found %d files.", total_files)

            generated_at = None
            if self.config.include_timestamp:
                generated_at = datetime.now(timezone.utc).isoformat()

            serializer = XMLSerializer(
                root_path_str=self._root_path_for_meta(),
                generated_at_utc=generated_at,
                tool_version="0.1.0",  # Ideally injected or read from package metadata
                formatting=self.config.formatting.value,
            )

            # Write Header & Structure
            write(serializer.stream_header())
            write(serializer.project_structure_xml(all_nodes))

            if self.config.mode == Mode.structure:
                write(serializer.stream_footer())
                text_out.flush()
                return

            # Phase 2: Content Processing
            write(serializer.files_open(self.config.mode.value))

            for node in all_nodes:
                self._process_node(node, serializer, write)
                if progress_callback:
                    progress_callback(1)

            write(serializer.files_close())
            write(serializer.stream_footer())

            # Ensure all buffered text is pushed to the underlying stream.
            text_out.flush()

        finally:
            # Prevent closing the underlying binary stream (BytesIO/stdout/gzip writer, etc.)
            # when TextIOWrapper is destroyed.
            try:
                text_out.detach()
            except Exception:
                pass

    def _process_node(self, node: FileNode, serializer: XMLSerializer, write_fn: Callable[[str], None]) -> None:
        """Handle individual file serialization logic based on configuration."""

        # Link-only mode for symlinks overrides content reading
        if node.is_symlink and self.config.symlinks_files == SymlinkFilesMode.as_link:
            write_fn(serializer.serialize_link(node))
            return

        # Metadata mode: no reading
        if self.config.mode == Mode.metadata:
            write_fn(serializer.serialize_metadata(node))
            return

        # Full mode: Read content
        res = FileIngestor.read(
            node.path,
            max_size=self.config.max_file_size,
            newline_mode=self.config.newline.value,
        )

        if res.kind == "text":
            write_fn(serializer.serialize_text(node, res.text or ""))
            return

        if res.kind == "binary":
            self._handle_binary(node, serializer, write_fn)
            return

        if res.kind in ("skip", "error"):
            write_fn(serializer.serialize_error(node, res.error or "Skipped"))
            return

    def _handle_binary(self, node: FileNode, serializer: XMLSerializer, write_fn: Callable[[str], None]) -> None:
        """Dispatch binary handling based on config."""
        if self.config.binary == BinaryMode.skip:
            write_fn(serializer.serialize_error(node, "Skipped: Binary file detected"))
            return

        if self.config.binary == BinaryMode.hash:
            try:
                h = FileIngestor.sha256_file(node.path)
            except OSError as e:
                write_fn(serializer.serialize_error(node, f"Error hashing file: {e}"))
                return
            write_fn(serializer.serialize_binary_hash(node, h))
            return

        if self.config.binary == BinaryMode.base64:
            try:
                write_fn(serializer.serialize_binary_base64_open(node))
                for chunk in FileIngestor.iter_base64_chunks(node.path):
                    write_fn(chunk)
                write_fn(serializer.serialize_binary_base64_close())
            except OSError as e:
                write_fn(serializer.serialize_error(node, f"Error base64-encoding file: {e}"))
            return