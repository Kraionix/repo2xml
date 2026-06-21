# src/repo2xml/services/serialize/base.py
from __future__ import annotations

from typing import Callable

WriteFn = Callable[[str], None]