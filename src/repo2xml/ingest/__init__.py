"""
File ingestion (content reading).

This package is responsible for reading file content safely and efficiently:
- size limits
- binary detection
- BOM-aware decoding (UTF-8/16/32)
- optional newline normalization
"""