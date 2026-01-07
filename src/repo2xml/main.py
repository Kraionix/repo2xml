from __future__ import annotations

from repo2xml.cli.main import app

# Kept for convenience if someone does `python -m repo2xml.main`.
# The canonical entrypoint for `python -m repo2xml` is repo2xml/__main__.py.

if __name__ == "__main__":
    app()