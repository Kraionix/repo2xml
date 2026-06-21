# repo2xml

Convert a source code repository into a single, structured context document for LLM ingestion.
Now also supports the reverse operation: restore a full repository from an XML export.

## Features

- **Export** a repository to XML:
  - Directory tree and file metadata
  - Full file contents (text, base64‑encoded binaries, hashes)
  - Symbolic link handling (`as-link`, `follow`, `skip`)
  - Gitignore‑compatible filtering
  - Fault‑tolerant scanning and reading
  - Configurable output (compact/pretty/minified), compression (gzip/zstd)
  - Deterministic output options (omit timestamps, redact paths, etc.)
- **Restore** a repository from an XML export:
  - Recreate the exact directory structure
  - Write text and binary files (base64)
  - Restore symbolic links
  - Restore modification times (optional)
  - Skip or overwrite existing files
  - Comprehensive statistics and error reporting

## Installation

```bash
pip install -e .
```

For zstd compression support:

```bash
pip install -e ".[zstd]"
```

## Quick Start

### Export a repository

```bash
# Full XML export
repo2xml -o context.xml

# Export with `--help` to see all options
repo2xml --help
```

### Restore a repository from XML

```bash
# Restore into a directory named "restored_project"
repo2xml restore context.xml -o restored_project

# Restore with overwriting and a detailed report
repo2xml restore context.xml -o restored_project --overwrite --report
```

### Validate the XML

```bash
python -c "import xml.etree.ElementTree as ET; ET.parse('context.xml'); print('XML OK')"
```

## CLI Commands

```
repo2xml [EXPORT OPTIONS] [PATH]
repo2xml restore [RESTORE OPTIONS] XML_FILE
```

### Export options (default command)

See `repo2xml --help` for the complete list. Key options:

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output file (default: `context.xml`) |
| `--mode {full,metadata,structure}` | Output mode |
| `--binary {skip,base64,hash}` | Binary file handling |
| `--formatting {compact,pretty,minify}` | XML formatting style |
| `--dry-run` | Show files that would be processed |
| `--report` | Detailed skip/error breakdown |
| `--no-timestamp` / `--no-mtime` / `--no-size` | Deterministic output |

### Restore options

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Target directory (default: current dir) |
| `--overwrite` | Overwrite existing files |
| `--no-mtime` | Do not restore modification times |
| `--create-empty` | Create empty files for skipped/errored entries |
| `--report` | Detailed skip/error breakdown |
| `--quiet` | Suppress non‑error output |

## Library Usage

```python
from pathlib import Path
from repo2xml import RepoXML, ExportConfig

# Export
config = ExportConfig()
engine = RepoXML(config)
with open("context.xml", "wb") as f:
    stats = engine.export(Path("."), f)
print(stats)

# Restore
from repo2xml import RestoreConfig

config = RestoreConfig(overwrite=True)
engine = RepoXML(config)
with open("context.xml", "rb") as f:
    stats = engine.restore(f, Path("./restored"))
print(stats)
```

## Output Format

The XML schema (version 1.1) is fully described inside the generated `<meta>` block.
The same format is accepted by the `restore` command.

## Architecture

`repo2xml` is built with a layered, extensible architecture:

- **Domain** – stable models (`FileEntry`, `Payload`, `ExportStats`, `RestoreStats`)
- **Services** – IO‑bound components (filesystem scanner, ingestor, serializer/deserializer, restorer)
- **Application** – use‑case orchestrators (`ExportPipeline`, `RestorePipeline`, policies)
- **Facade** – `RepoXML` exposes a clean public API
- **CLI** – Typer‑based command line interface

Adding a new output format or a new content payload type requires implementing well‑defined abstract base classes, ensuring consistency and exhaustiveness.