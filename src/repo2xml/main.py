from __future__ import annotations

from repo2xml.cli.main import app

# This entrypoint wrapper allows `python -m repo2xml` to work
# while keeping logic in the cli package.

if __name__ == "__main__":
    app()