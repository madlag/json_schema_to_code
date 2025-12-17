"""
Pipeline-based JSON Schema to Code generator.

This module provides a clean, multi-phase architecture for generating
code from JSON schemas:

1. Phase 1 (Parser): Parse JSON Schema into an AST
2. Phase 2 (Analyzer): Resolve references and build IR
3. Phase 3 (Backend): Generate language-specific code
"""

from __future__ import annotations

from .generator import PipelineGenerator

__all__ = ["PipelineGenerator"]
