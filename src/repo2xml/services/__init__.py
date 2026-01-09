"""
Services layer.

This package contains reusable, mostly-IO-bound components:
- scan: filesystem traversal + gitignore stack
- ingest: safe reading and classification
- serialize: format writers (XML now, JSON later)
- output: output stream targets (file/stdout/clipboard) and compression wrappers
"""