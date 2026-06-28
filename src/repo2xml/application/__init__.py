# src/repo2xml/application/__init__.py
"""
Application layer.

This layer implements the repo2xml use-cases (orchestration), without being tied
to a specific presentation interface (CLI, gRPC, web, etc.).
"""

from repo2xml.application.factories import ExportComponentFactory
from repo2xml.application.pipeline_orchestrator import PipelineOrchestrator
from repo2xml.application.statistics_collector import StatisticsCollector

__all__ = [
    "ExportComponentFactory",
    "PipelineOrchestrator",
    "StatisticsCollector",
]