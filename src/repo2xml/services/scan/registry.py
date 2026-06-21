# src/repo2xml/services/scan/registry.py
"""Internal registry for scanner implementations.

New scanners can be registered here and become available via the
`--source` CLI option. The registry is populated at import time with
the built‑in filesystem scanner.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict

from repo2xml.domain.exceptions import ConfigurationError

if TYPE_CHECKING:
    from repo2xml.application.contracts import ScannerLike

# Type alias for factory functions that create a ScannerLike instance.
ScannerFactory = Callable[..., "ScannerLike"]

# Module-level registry: source name → factory callable.
_SCANNER_REGISTRY: Dict[str, ScannerFactory] = {}


def register_scanner(name: str, factory: ScannerFactory) -> None:
    """Register a new scanner factory under a unique name.

    Args:
        name: Short identifier, e.g. "filesystem", "git".
        factory: Callable that returns a ScannerLike instance.
    """
    if name in _SCANNER_REGISTRY:
        raise ConfigurationError(f"Scanner '{name}' is already registered")
    _SCANNER_REGISTRY[name] = factory


def create_scanner(name: str, **kwargs: Any) -> "ScannerLike":
    """Look up a scanner factory by name and invoke it.

    Args:
        name: Scanner identifier (must be registered).
        **kwargs: Arbitrary keyword arguments forwarded to the factory.

    Returns:
        A ScannerLike instance created by the corresponding factory.

    Raises:
        ConfigurationError: If the scanner name is unknown.
    """
    factory = _SCANNER_REGISTRY.get(name)
    if factory is None:
        available = ", ".join(sorted(_SCANNER_REGISTRY))
        raise ConfigurationError(
            f"Unknown scanner source: '{name}'. Available: {available}"
        )
    return factory(**kwargs)


def list_scanners() -> Dict[str, ScannerFactory]:
    """Return a copy of the current registry (useful for diagnostics)."""
    return dict(_SCANNER_REGISTRY)


# ----------------------------------------------------------------------
# Register built‑in filesystem scanner
# ----------------------------------------------------------------------

def _filesystem_factory(
    root_path,
    ignore_provider=None,
    use_gitignore=True,
    follow_symlinks_dirs=False,
    symlinks_files="follow",
    hard_exclude_dirs=None,
    **options,
) -> "ScannerLike":
    """Factory for FileSystemScanner.

    All parameters match the constructor of FileSystemScanner.
    Extra `**options` are accepted and silently ignored so that
    common source-option forwarding works without per-source hacks.
    """
    from repo2xml.services.scan.scanner import FileSystemScanner

    return FileSystemScanner(
        root=root_path,
        ignore_provider=ignore_provider,
        use_gitignore=use_gitignore,
        follow_symlinks_dirs=follow_symlinks_dirs,
        symlinks_files=symlinks_files,
        hard_exclude_dirs=hard_exclude_dirs or {".git"},
    )


register_scanner("filesystem", _filesystem_factory)