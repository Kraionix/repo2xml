from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable, Generator, List, Optional

from repo2xml.config import BinaryMode, Mode, Repo2XMLConfig, SymlinkFilesMode
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
        # Phase 1: Indexing
        # We need to collect all nodes first to emit the <project_structure> block
        # at the top of the XML file.
        logger.info("Scanning repository: %s", self.root_path)
        all_nodes: List[FileNode] = list(self.scan())
        total_files = len(all_nodes)
        logger.info("Found %d files.", total_files)

        # Initialize Serializer
        generated_at = datetime.now(timezone.utc).isoformat()
        serializer = XMLSerializer(
            root_path_str=str(self.root_path),
            generated_at_utc=generated_at,
            tool_version="0.1.0",  # Ideally injected or read from package metadata
            formatting=self.config.formatting.value,
        )

        def write(s: str) -> None:
            output_stream.write(s.encode("utf-8"))

        # Write Header & Structure
        write(serializer.stream_header())
        write(serializer.project_structure_xml(all_nodes))

        if self.config.mode == Mode.structure:
            write(serializer.stream_footer())
            return

        # Phase 2: Content Processing
        write(serializer.files_open(self.config.mode.value))

        for node in all_nodes:
            self._process_node(node, serializer, write)
            if progress_callback:
                progress_callback(1)

        write(serializer.files_close())
        write(serializer.stream_footer())

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
            self._handle_binary(node, res.binary_bytes or b"", serializer, write_fn)
            return

        if res.kind in ("skip", "error"):
            write_fn(serializer.serialize_error(node, res.error or "Skipped"))
            return

    def _handle_binary(self, node: FileNode, data: bytes, serializer: XMLSerializer, write_fn: Callable[[str], None]) -> None:
        """Dispatch binary handling based on config."""
        if self.config.binary == BinaryMode.skip:
            write_fn(serializer.serialize_error(node, "Skipped: Binary file detected"))
        elif self.config.binary == BinaryMode.base64:
            b64 = FileIngestor.to_base64(data)
            write_fn(serializer.serialize_binary_base64(node, b64))
        elif self.config.binary == BinaryMode.hash:
            h = FileIngestor.sha256_hex(data)
            write_fn(serializer.serialize_binary_hash(node, h))