"""
Traversal pipeline for repository analysis.

This module provides a modular, parallel repository traversal pipeline
that separates the traversal workflow into distinct stages:
  - Repository discovery
  - File filtering
  - Gitignore filtering
  - Metadata extraction
  - Language detection
  - Document creation

Each stage has a single responsibility. Independent CPU / I/O bound stages
can be executed in parallel via ThreadPoolExecutor while preserving
deterministic output ordering and thread safety.
"""

from .pipeline import TraversalPipeline
from .stages import (
    DiscoveryResult,
    FilteredFile,
    FileMetadata,
    DocumentResult,
    RepositoryMetadata,
    PipelineContext,
    ProgressEventType,
    TraversalProgressEvent,
    ProgressCallback,
)

__all__ = [
    "TraversalPipeline",
    "DiscoveryResult",
    "FilteredFile",
    "FileMetadata",
    "DocumentResult",
    "RepositoryMetadata",
    "PipelineContext",
    "ProgressEventType",
    "TraversalProgressEvent",
    "ProgressCallback",
]