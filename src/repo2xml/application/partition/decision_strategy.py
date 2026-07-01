# src/repo2xml/application/partition/decision_strategy.py
from __future__ import annotations

from abc import ABC, abstractmethod

from .buffer_manager import BufferManager


class IPartitionDecisionStrategy(ABC):
    @abstractmethod
    def should_start_new_part(self, buffer_manager: BufferManager, next_file_tokens: int) -> bool:
        ...


class TokenBasedStrategy(IPartitionDecisionStrategy):
    def should_start_new_part(self, buffer_manager: BufferManager, next_file_tokens: int) -> bool:
        # If buffer is empty, we never need to start a new part just for this file.
        if buffer_manager.is_empty():
            return False
        # Check if adding this file would exceed the limit.
        # We rely on the caller to have already added the file, so we check the over-limit flag.
        return buffer_manager.is_over_limit()