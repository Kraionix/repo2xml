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
- **Formatting modes**: `compact` (default), `pretty` (indented), or `minify`.
- **Output**: File or stdout; optional gzip/zstd compression.
- **Deterministic output option**: `--no-timestamp` omits `generated_at_utc` for stable diffs.

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

Generate full XML with explicit path and settings:

```bash
repo2xml --mode full --formatting compact --newline lf -o context.xml ./my-project
```

Deterministic output (omit timestamp):

```bash
repo2xml --no-timestamp -o context.xml .
```

Structure only (fast, no file reads, useful for initial LLM prompts):

```bash
repo2xml --mode structure -o structure.xml .
```

**Pipe to clipboard** (using stdout + minify):

```bash
# Windows (Powershell)
repo2xml --stdout --formatting minify | Set-Clipboard

# Linux (xclip)
repo2xml --stdout --formatting minify | xclip -sel clip
```

Compressed output (save disk space):

```bash
repo2xml --compress gzip -o context.xml.gz .
```

## CLI Options

Show help:

```bash
repo2xml --help
```

### Key Arguments

- `PATH`: Root path of the project to serialize. Defaults to current directory (`.`).

### Key Options

- `--mode [full|metadata|structure]`
  Output mode. **Default:** `full`.

- `--output`, `-o PATH`
  Output path. Ignored if `--stdout` is set. **Default:** `context.xml`.

- `--formatting [compact|pretty|minify]`
  XML formatting. `compact` uses newlines but no indentation (token efficient). **Default:** `compact`.

- `--newline [preserve|lf]`
  Normalize line endings. `lf` is **highly recommended** for LLM ingestion to save tokens and improve diff stability. **Default:** `preserve`.

- `--no-timestamp`
  Omit `<generated_at_utc>` from the XML meta block, for deterministic output.

### Filtering

- `--gitignore / --no-gitignore`
  Enable/disable reading `.gitignore` files. **Default:** `enabled`.

- `--ignore TEXT`, `-i TEXT`
  Additional ignore patterns (gitignore syntax). Can be repeated.

- `--include TEXT`
  **Force include** patterns (overrides gitignore). Implemented as negation patterns. Use this to explicitly include files that are otherwise ignored.

- `--hard-exclude TEXT`
  Directory **names** to always exclude. **Default:** `.git`.
  *Note: Matches directory name only, not full path.*

### Symlinks & content

- `--symlinks-files [follow|skip|as-link]`
  How to handle symlink files. **Default:** `follow`.
  - `follow`: read target content.
  - `skip`: ignore the file.
  - `as-link`: emit `<file link_only="true" link_target="..." />`. **Best for LLMs.**

- `--max-size INTEGER`
  Max file size in bytes to include content. Larger files are marked as skipped. **Default:** `100000` (100KB).

- `--binary [skip|base64|hash]`
  How to handle binary files. **Default:** `skip`.

## Output Format

The output is a single XML document.

**Structure:**
```xml
<repository_context version="1.0" tool_version="...">
  <meta>
    <root_path>...</root_path>
    <generated_at_utc>...</generated_at_utc>
  </meta>

  <!-- Complete Directory Tree -->
  <project_structure>
    <dir name="src" path="src">
      <file name="main.py" path="src/main.py" />
    </dir>
  </project_structure>

  <!-- File Contents -->
  <files mode="full">
    <file path="src/main.py" size="1024" ext=".py" mtime_utc="...">
      <content><![CDATA[ ... file content ... ]]]]><![CDATA[></content>
    </file>

    <!-- Example of skipped/error file -->
    <file path="bin/image.png" size="..." ext=".png" mtime_utc="..." skipped="true">
       <error>Skipped: Binary file detected</error>
    </file>
  </files>
</repository_context>
```

If `--no-timestamp` is used, `<generated_at_utc>` is omitted.

Paths in XML are always repository-relative and use POSIX separators (`/`), even on Windows.

## Fault Tolerance

`repo2xml` employs a "fail-soft" strategy:
1.  **Access Errors:** If a file cannot be read (permissions, locks), it is reported as an `<error>` in the XML, but processing continues.
2.  **Directory Access Errors:** If a directory cannot be listed (permissions, transient errors), it is skipped and a warning is logged.
3.  **Encoding:** It attempts to detect encodings (BOM) and falls back to UTF-8 with replacement characters. It does not crash on binary garbage in text files.
4.  **XML Safety:** Content is wrapped in CDATA.

## Performance Notes

- **Memory Usage:** The tool currently indexes the entire file list in memory before writing the XML (to generate the `<project_structure>` block first). Very large repositories (millions of files) may require significant RAM.
- **Concurrency:** Traversal and ingestion are currently single-threaded.

## Validate the XML

Quick check using Python's standard library:

```bash
python -c "import xml.etree.ElementTree as ET; ET.parse('context.xml'); print('XML OK')"
```