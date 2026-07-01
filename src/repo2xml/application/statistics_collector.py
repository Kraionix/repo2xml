# src/repo2xml/application/statistics_collector.py
from __future__ import annotations

from typing import Dict, List, Optional, Any

from repo2xml.contracts import StatsProvider
from repo2xml.domain.model import ExportStats, TokenStats, SkipCode, ErrorCode, ClassificationStats
from repo2xml.services.ingest.redact.models import RedactionStats
from repo2xml.services.scan.scanner import ScanStats


class StatisticsCollector:
    """
    Aggregates statistics during the export process.

    Maintains counters for processed, skipped, and errored files,
    as well as token‑related statistics. It also collects statistics
    from any registered StatsProvider components.
    """

    def __init__(
        self,
        *,
        token_counting_enabled: bool = False,
        providers: Optional[List[StatsProvider]] = None,
    ):
        # Counters
        self._total_processed = 0
        self._total_skipped = 0
        self._total_errors = 0
        self._skipped_by_code: Dict[str, int] = {}
        self._errors_by_code: Dict[str, int] = {}

        # Token statistics (optional)
        self._token_stats: Optional[TokenStats] = TokenStats() if token_counting_enabled else None
        self._token_counting_enabled = token_counting_enabled

        # Stats providers – will be queried when building final stats
        self._providers: List[StatsProvider] = providers or []

    def record_success(self, token_count: Optional[int] = None, ext: str = "") -> None:
        """Record a successfully processed file."""
        self._total_processed += 1
        if self._token_counting_enabled and token_count is not None and self._token_stats is not None:
            self._token_stats.files_processed += 1
            self._token_stats.total_tokens += token_count
            if ext:
                self._token_stats.tokens_by_extension[ext] = (
                    self._token_stats.tokens_by_extension.get(ext, 0) + token_count
                )
            if token_count > self._token_stats.max_tokens:
                self._token_stats.max_tokens = token_count
            if self._token_stats.min_tokens == 0 or token_count < self._token_stats.min_tokens:
                self._token_stats.min_tokens = token_count

    def record_skipped(self, skip_code: SkipCode, message: Optional[str] = None) -> None:
        self._total_skipped += 1
        self._skipped_by_code[skip_code.value] = self._skipped_by_code.get(skip_code.value, 0) + 1

    def record_error(self, error_code: ErrorCode, message: Optional[str] = None) -> None:
        self._total_errors += 1
        self._errors_by_code[error_code.value] = self._errors_by_code.get(error_code.value, 0) + 1

    def get_export_stats(self, scan_warning_summary: Optional[str] = None) -> ExportStats:
        """Return the final ExportStats object, including stats from all providers."""
        # Build the base stats object from our counters
        export_stats = ExportStats(
            files_total=self._total_processed + self._total_skipped + self._total_errors,
            files_emitted=self._total_processed,
            files_skipped=self._total_skipped,
            files_errors=self._total_errors,
            skipped_by_code=dict(self._skipped_by_code),
            errors_by_code=dict(self._errors_by_code),
            scan_warning_summary=scan_warning_summary,
            redaction_stats=None,
            classification_stats=None,
            token_stats=self._token_stats,
            scan_stats=None,
        )

        # Let each provider update the stats object
        for provider in self._providers:
            provider.apply_to(export_stats)

        return export_stats

    def reset(self) -> None:
        self._total_processed = 0
        self._total_skipped = 0
        self._total_errors = 0
        self._skipped_by_code.clear()
        self._errors_by_code.clear()
        if self._token_counting_enabled:
            self._token_stats = TokenStats()
        else:
            self._token_stats = None