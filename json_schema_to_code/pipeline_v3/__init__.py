"""
Pipeline V3 - AST-based JSON Schema to Code generator.

This module provides a clean, multi-phase architecture for generating
code from JSON schemas using language-native AST representations:

1. Phase 1 (Parser): Parse JSON Schema into Schema AST
2. Phase 2 (Analyzer): Resolve references and build IR
3. Phase 3 (AST Backend): Generate language-native AST from IR
4. Phase 4 (Serializer): Convert AST to source code
5. Phase 5 (Formatter): Optional post-processing (e.g., black for Python)
6. Phase 6 (Merger): Optional merge with existing file to preserve custom code
"""

from __future__ import annotations

from .config import CodeGeneratorConfig, FormatterConfig, OutputConfig, OutputMode
from .generator import PipelineGeneratorV3
from .merger import AtomicWriter, CodeMergeError, PythonAstMerger

__all__ = [
    "PipelineGeneratorV3",
    "CodeGeneratorConfig",
    "FormatterConfig",
    "OutputConfig",
    "OutputMode",
    "CodeMergeError",
    "PythonAstMerger",
    "AtomicWriter",
]
