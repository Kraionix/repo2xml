# repo2xml

Convert a source code repository into a single, structured context document for LLM ingestion.
Supports the reverse operation: restore a full repository from an XML export.

**Version 0.4.0**

---

## Features

- **Export** a repository to XML:
  - Directory tree and file metadata
  - Full file contents (text, base64‑encoded binaries, hashes)
  - Symbolic link handling (`as-link`, `follow`, `skip`)
  - Gitignore‑compatible filtering
  - Fault‑tolerant scanning and reading
  - Configurable output (compact/pretty/minified), compression (gzip/zstd)
  - Deterministic output options (omit timestamps, redact paths, etc.)
- **Token counting** (optional):
  - Count tokens in text files using Hugging Face tokenizers (lazy‑loaded)
  - Per‑file token counts stored in XML (attribute `tokens`)
  - Aggregated statistics (`<statistics total_tokens="..."/>`)
  - CLI report with breakdown by extension
- **Restore** a repository from an XML export:
  - Recreate the exact directory structure
  - Write text and binary files (base64)
  - Restore symbolic links
  - Restore modification times (optional)
  - Skip or overwrite existing files
  - Comprehensive statistics and error reporting
  - Strict XML validation (optional)
- **Pluggable classification engine**
  - Fast binary/text detection using extension whitelists and content heuristics
  - Configurable via `.repo2xml-classify.yml` – override extensions, adjust binary threshold
  - Built‑in support for common text and binary formats
- **Extensible secret redaction**
  - Detect and replace API keys, tokens, private keys before export
  - Built‑in patterns grouped by type (API keys, tokens, private keys, generic)
  - Custom rules via `.repo2xml-redact.yml` – add patterns, override built‑ins, exclude files
  - Supports backreferences in replacements (e.g. `password=…` → `password=<redacted:password>`)
  - Redaction statistics in report
- **Internal scanner registry**
  - Default `filesystem` scanner; new backends (e.g. Git history, S3) can be added later
- **Cross‑platform CLI** with rich progress bars, detailed reports

---

## Installation

```bash
pip install -e .
```

For zstd compression support:

```bash
pip install -e ".[zstd]"
```

For token counting support:

```bash
pip install -e ".[tokens]"
```

Python 3.10+ is required.

---

## Quick Start

### Export a repository

```bash
# Full XML export
repo2xml -o context.xml

# Export with redacted secrets and a classification config
repo2xml --redact-secrets --redact-config .repo2xml-redact.yml -o context.xml

# Export with token counting (requires 'tokens' extra)
repo2xml --count-tokens -o context.xml

# See all options
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

---

## CLI Commands

```
repo2xml [EXPORT OPTIONS] [PATH]
repo2xml restore [RESTORE OPTIONS] XML_FILE
```

### Export options (default command)

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output file (default: `context.xml`) |
| `--mode {full,metadata,structure}` | Output mode |
| `--binary {skip,base64,hash}` | Binary file handling |
| `--formatting {compact,pretty,minify}` | XML formatting style |
| `--dry-run` | Show files that would be processed |
| `--report` | Detailed skip/error breakdown plus redaction/classification/extension token statistics |
| `--no-timestamp` / `--no-mtime` / `--no-size` | Deterministic output |
| `--source` | Scanner source (default: `filesystem`) |
| `--source-option` | Key=value pairs for the scanner (repeatable) |
| `--classify-config` | Path to YAML file overriding classification rules |
| `--redact-secrets` | Enable secret redaction |
| `--redact-config` | Path to YAML file overriding redaction rules |
| `--compress {none,gzip,zstd}` | Output stream compression |
| `--stdout` / `--clipboard` | Alternative output targets |
| `--count-tokens` / `--no-count-tokens` | Count tokens in text files using Hugging Face tokenizers |
| `--tokenizer-model TEXT` | Hugging Face model for tokenization (default: `deepseek-ai/DeepSeek-V4-Pro`) |

### Restore options

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Target directory (default: current dir) |
| `--overwrite` | Overwrite existing files |
| `--no-mtime` | Do not restore modification times |
| `--create-empty` | Create empty files for skipped/errored entries |
| `--report` | Detailed skip/error breakdown |
| `--quiet` | Suppress non‑error output |
| `--no-strict-validation` | Disable strict XML validation (useful for recovery) |

---

## Library Usage

```python
from pathlib import Path
from repo2xml import RepoXML, ExportConfig, RestoreConfig

# Export
config = ExportConfig()
engine = RepoXML(config)
with open("context.xml", "wb") as f:
    stats = engine.export(Path("."), f)
print(stats)

# Restore
config = RestoreConfig(overwrite=True)
engine = RepoXML(config)
with open("context.xml", "rb") as f:
    stats = engine.restore(f, Path("./restored"))
print(stats)
```

---

## Configuration Files

### `.repo2xml-redact.yml`

Place this file in your project root to customise secret redaction.  
It is automatically discovered unless you specify `--redact-config`.

```yaml
# .repo2xml-redact.yml
builtin_rules: all   # all | none | [api_keys, tokens, ...]

rules:
  - name: my-custom-token
    pattern: '\bmysecret-\d{10}\b'
    replacement: '<redacted:custom>'

  - name: aws-access-key   # override built‑in
    pattern: '\bAKIA[0-9A-Z]{16}\b'
    replacement: '<redacted:aws-key-custom>'

  - name: slack-token      # disable built‑in
    enabled: false

exclude_files:
  - 'tests/**'
  - '*.test.*'
```

### `.repo2xml-classify.yml`

Customise which file extensions are treated as text or binary, and tweak the
binary detection heuristic.

```yaml
# .repo2xml-classify.yml

# Add extensions to built‑in lists
text_ext_add: [".graphql", ".vue"]
binary_ext_remove: [".dat"]

# Or replace entire lists
text_extensions:
  - .py
  - .js
  - .txt

# Compound suffixes (e.g. .tar.gz)
compound_binary_add: [".parquet"]

# Adjust binary threshold (default 0.30)
binary_threshold: 0.35
```

---

## Output Format

The XML schema (version 1.2) is fully described inside the generated `<meta>` block.
The same format is accepted by the `restore` command.

Notable additions in schema 1.2:
- Each `<file>` element (for text files) may contain a `tokens` attribute with the number of tokens counted for that file (if `--count-tokens` is used).
- An optional `<statistics total_tokens="..."/>` element at the end of the document provides the total token count across all processed text files.

---

## Architecture

`repo2xml` is built with a layered, extensible architecture:

- **Domain** – stable models (`FileEntry`, `Payload`, `ExportStats`, `RestoreStats`, `TokenStats`)
- **Services** – IO‑bound components:
  - `scan` – filesystem scanner and gitignore engine
  - `classify` – pluggable binary/text classification engine
  - `ingest` – safe file reading, redaction engine
  - `serialize` – XML serializer/deserializer (other formats planned)
  - `restore` – filesystem restorer
  - `output` – output targets (file, stdout, clipboard, /dev/null)
  - `tokenize` – lazy‑loaded token counters with registry‑based factories
- **Application** – use‑case orchestrators (`ExportPipeline`, `RestorePipeline`, policies)
- **Facade** – `RepoXML` exposes a clean public API
- **CLI** – Typer‑based command line interface with Rich progress reporting

Adding a new scanner backend, output format, or redaction rule requires
implementing well‑defined abstract base classes, ensuring consistency and
extensibility.

---

## Security

Secret redaction is enabled via `--redact-secrets`. The engine uses
regular expressions to identify common credentials. You can control which
patterns are active and add your own through a YAML configuration file.

Redaction is best‑effort and should not be relied upon as the sole
protection against credential leakage. Always review the exported context
before sharing with third parties.

---

## License

MIT