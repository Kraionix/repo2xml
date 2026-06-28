# src/repo2xml/application/__init__.py
"""
Application layer.

This layer implements the repo2xml use-cases (orchestration), without being tied
to a specific presentation interface (CLI, gRPC, web, etc.).
"""

from repo2xml.application.factories import ExportComponentFactory
from repo2xml.application.pipeline import Pipeline
from repo2xml.application.pipeline_orchestrator import PipelineOrchestrator
from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.services import ProcessingServices
from repo2xml.application.statistics_collector import StatisticsCollector
from repo2xml.application.step import Step
from repo2xml.application.step_factory import StepFactory

__all__ = [
    "ExportComponentFactory",
    "Pipeline",
    "PipelineOrchestrator",
    "ProcessingContext",
    "ProcessingServices",
    "StatisticsCollector",
    "Step",
    "StepFactory",
]