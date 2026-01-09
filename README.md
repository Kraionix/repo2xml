# repo2xml

Convert a source code repository into a single, structured context document for LLM ingestion.

`repo2xml` walks a repository, applies `.gitignore` filtering (recursively, via a Git-compatible scoped gitignore stack), emits a directory tree, and (optionally) embeds file contents with metadata in a deterministic format.

The internal architecture is pipeline-based (Scan → Ingest → Serialize → Write). This makes it easier to add future output formats (JSON), API layers (gRPC/HTTP), and agent integrations, while keeping the current CLI behavior stable.

## Features

- **Project structure** as an XML tree (`<project_structure>` with `<dir>` / `<file>`).
- **File metadata**: relative path, extension(s), UTC mtime (optional), size (optional), symlink info.
- **Content modes**:
  - `full`: metadata + content (default)
  - `metadata`: metadata only (no content reads; not treated as "skipped")
  - `structure`: structure only

- **Robust Filtering**:
  - Respects `.gitignore` with correct scoping rules (patterns are applied relative to the directory containing the `.gitignore`).
  - Extra `--ignore` patterns (gitignore syntax).
  - **Force Include** (`--include`) to override ignore rules (un-ignore, gitignore syntax).
  - **Hard excludes** (e.g. `.git`) preventing accidental traversal.

- **Smart Symlink Handling**:
  - Can treat symlink files as links (`as-link`) to save tokens and avoid touching link targets.
  - Broken symlink files are still included in output in `as-link` mode.
  - Safe directory traversal with cycle protection (when following symlink dirs).

- **Fault Tolerance**: Read errors (permissions, encoding) do not crash the tool; they are reported as `<error>` tags within the output.

- **Binary handling**: skip, embed as base64, or store SHA-256 hash.
  - `base64` and `hash` are computed in a streaming fashion (no full binary read into memory).

- **Binary extension fast-path** (configurable):
  - Case-insensitive (PNG == png).
  - Can be disabled or extended via CLI options.

- **Formatting modes**: `compact` (default), `pretty` (indented), or `minify`.

- **Output**: File or stdout; optional gzip/zstd compression; clipboard support.

- **Deterministic output options**:
  - `--no-timestamp` omits `generated_at_utc` for stable diffs.
  - `--no-mtime` omits `mtime_utc` attributes for stable diffs.
  - `--no-size` omits `size` attributes (determinism / privacy).
  - `--root-path-mode relative|redact` avoids leaking absolute paths.
  - `<root_path>` always uses POSIX separators (`/`) for reproducibility.

- **Built-in safety**:
  - `--redact-secrets` redacts common secret-like patterns (best-effort) from embedded text.

## Installation

From the repository root (where `pyproject.toml` lives):

```bash
pip install -e .
```

### Optional: zstd compression

`--compress zstd` requires `zstandard`:

```bash
pip install -e ".[zstd]"
```

## Quick Start

> Note: This CLI is implemented as a Typer app. To ensure arguments are parsed correctly, place options before the PATH.

Generate full XML for the current directory (default):

```bash
repo2xml -o context.xml
```

Run as a module:

```bash
python -m repo2xml -o context.xml .
```

Deterministic output (omit timestamp and redact root path):

```bash
repo2xml --no-timestamp --root-path-mode redact -o context.xml .
```

More deterministic output (omit timestamp + mtime + size):

```bash
repo2xml --no-timestamp --no-mtime --no-size --root-path-mode redact -o context.xml .
```

Show version:

```bash
repo2xml --version
```

Compute stats only (discard output bytes):

```bash
repo2xml --stats-only --report .
```

## CLI Options

Show help:

```bash
repo2xml --help
```

### Output selection

These are mutually exclusive:
- `--stdout`
- `--clipboard`
- `--stats-only`

### Meta and determinism

- `--no-timestamp`  
  Omit `<generated_at_utc>` from the output meta block, for deterministic output.

- `--no-mtime`  
  Omit `mtime_utc` file attributes, for deterministic output.

- `--no-size`  
  Omit `size` file attributes (determinism / privacy).

- `--root-path-mode [absolute|relative|redact]`  
  How to emit `<root_path>`:
  - `absolute` (default): full resolved path (POSIX separators)
  - `relative`: relative path from current working directory when possible (POSIX separators)
  - `redact`: emit `<redacted>`

### Size limits

- `--max-size BYTES`  
  Maximum size for embedding:
  - text content
  - base64 content (when `--binary base64`)

  Larger files are emitted as skipped entries (with a reason).

  Note: binary hashing (`--binary hash`) is allowed beyond `--max-size` by default.

### Decoding

- `--decode-errors [replace|strict]`  
  Text decoding policy:
  - `replace` (default): best-effort decode with replacement characters
  - `strict`: fail on decode errors (emitted as `<file skipped="true" error_code="text_decode_error">...`)

### Reporting

- `--report / --no-report`  
  Print a detailed post-run report with a breakdown of skip/error causes.

- `--stats-only`  
  Compute and print statistics, but discard generated output bytes.

### Progress

- `--progress / --no-progress`  
  Show progress bars.

  Progress is multi-phase:
  - **Scanning**: indeterminate (no total), counts discovered files
  - **Processing**: determinate, counts processed files

### Redaction

- `--redact-secrets / --no-redact-secrets`  
  Redact common secret-like patterns from embedded text content (best-effort).

### Binary detection fast-path

- `--ext-binary-detect / --no-ext-binary-detect`  
  Enable/disable binary extension fast-path (default: enabled).

- `--binary-ext-add TEXT`  
  Add extensions to treat as binary (repeatable). Case-insensitive.  
  Examples: `--binary-ext-add PSD`, `--binary-ext-add .psd`, `--binary-ext-add .tar.zst`

- `--binary-ext-remove TEXT`  
  Remove extensions from the default binary fast-path set (repeatable).  
  Example: `--binary-ext-remove .pdf`

## Output Format

The output is a single XML document.

Paths in output are always repository-relative and use POSIX separators (`/`), even on Windows.

### Machine-readable skip/error codes

When a file is skipped or fails processing, the XML includes machine-readable attributes:

Skipped (intentional omission):

```xml
<file ... skipped="true" skip_code="text_size_limit">
```

Error (failed attempt):

```xml
<file ... skipped="true" error_code="text_read_error">
```

If available, a machine-readable `<detail>` block is also emitted (deterministic JSON inside CDATA).

## Gitignore compatibility

`repo2xml` implements Git-compatible `.gitignore` scoping:

- Each `.gitignore` applies to files under its directory.
- Patterns are matched against paths relative to the directory containing that `.gitignore`.
- The last matching pattern wins across all applicable `.gitignore` files.
- `.git` is not traversed by default (hard excluded), and ignore files inside `.git` are not considered.

Note: compatibility with Git index (tracked files ignoring `.gitignore`) is intentionally out of scope.

## Fault Tolerance

`repo2xml` employs a "fail-soft" strategy:

1. **Access Errors:** If a file cannot be read (permissions, locks), it is reported as an `<error>` in the output, but processing continues.
2. **Directory Access Errors:** If a directory cannot be listed (permissions, transient errors), it is skipped and a warning is logged.
3. **Scanner Entry Errors:** If a directory entry fails `is_file/stat/readlink`, it is skipped. A summary warning is logged after scanning (without spamming per file).

## Validate the XML

Quick check using Python's standard library:

```bash
python -c "import xml.etree.ElementTree as ET; ET.parse('context.xml'); print('XML OK')"
```

## Library Usage

Minimal example:

```python
from pathlib import Path
from repo2xml import Repo2XML, Repo2XMLConfig

engine = Repo2XML(Path("."), Repo2XMLConfig())
with open("context.xml", "wb") as f:
    stats = engine.export(f)

print(stats)
```