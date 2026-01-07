```markdown
# repo2xml

Convert a source code repository into a single, structured XML context for LLM ingestion.

`repo2xml` walks a repository, applies `.gitignore`-style filtering (recursively, via a gitignore stack), emits a directory tree, and (optionally) embeds file contents with metadata in a deterministic XML format.

## Features

- **Project structure** as an XML tree (`<project_structure>` with `<dir>` / `<file>`).
- **File metadata**: relative path, size, extension(s), UTC mtime, symlink info.
- **Content modes**:
  - `full`: metadata + content (default)
  - `metadata`: metadata only (no content reads)
  - `structure`: structure only
- **Robust Filtering**:
  - Respects `.gitignore` (enabled by default).
  - Extra `--ignore` patterns.
  - **Force Include** (`--include`) to override gitignore rules (un-ignore).
  - **Hard excludes** (e.g. `.git`) preventing accidental traversal.
- **Smart Symlink Handling**:
  - Can treat symlink files as links (`as-link`) to save tokens, avoiding content duplication.
  - Safe directory traversal with cycle protection.
- **Fault Tolerance**: Read errors (permissions, encoding) do not crash the tool; they are reported as `<error>` tags within the XML.
- **Binary handling**: skip, embed as base64, or store SHA-256 hash.
  - `base64` and `hash` are computed in a streaming fashion (no full binary read into memory).
- **Binary extension fast-path** (configurable):
  - Case-insensitive (PNG == png).
  - Can be disabled or extended via CLI options.
- **Formatting modes**: `compact` (default), `pretty` (indented), or `minify`.
- **Output**: File or stdout; optional gzip/zstd compression.
- **Deterministic output options**:
  - `--no-timestamp` omits `generated_at_utc` for stable diffs.
  - `--root-path-mode relative|redact` avoids leaking absolute paths.
  - `<root_path>` always uses POSIX separators (`/`) for reproducibility.

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

> **Note:** This CLI is implemented as a Typer app. To ensure arguments are parsed correctly, place **options before the PATH**.

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

## CLI Options

Show help:

```bash
repo2xml --help
```

### Meta and determinism

- `--no-timestamp`
  Omit `<generated_at_utc>` from the XML meta block, for deterministic output.

- `--root-path-mode [absolute|relative|redact]`
  How to emit `<root_path>`:
  - `absolute` (default): full resolved path (POSIX separators)
  - `relative`: relative path from current working directory when possible (POSIX separators)
  - `redact`: emit `<redacted>`

### Binary detection fast-path

- `--ext-binary-detect / --no-ext-binary-detect`
  Enable/disable binary extension fast-path (default: enabled).

- `--binary-ext-add TEXT`
  Add extensions to treat as binary (repeatable). Case-insensitive.
  Examples: `--binary-ext-add PSD`, `--binary-ext-add .psd`, `--binary-ext-add .tar.zst`

- `--binary-ext-remove TEXT`
  Remove extensions from the default fast-path set (repeatable). Case-insensitive.
  Example: `--binary-ext-remove .pdf`

## Output Format

The output is a single XML document.

Paths in XML are always repository-relative and use POSIX separators (`/`), even on Windows.

## Fault Tolerance

`repo2xml` employs a "fail-soft" strategy:
1. **Access Errors:** If a file cannot be read (permissions, locks), it is reported as an `<error>` in the XML, but processing continues.
2. **Directory Access Errors:** If a directory cannot be listed (permissions, transient errors), it is skipped and a warning is logged.
3. **Scanner Entry Errors:** If a directory entry fails `is_file/stat/readlink`, it is skipped. A summary warning is logged after scanning (without spamming per file).

## Validate the XML

Quick check using Python's standard library:

```bash
python -c "import xml.etree.ElementTree as ET; ET.parse('context.xml'); print('XML OK')"
```