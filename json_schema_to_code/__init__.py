"""JSON Schema to Code Generator

A Python package for generating code from JSON Schema definitions.
Supports Python and C# code generation with AST-based pipeline,
code merging, and configurable output options.
"""

__version__ = "1.0.1"
__author__ = "François Lagunas"

from .pipeline import (
    AtomicWriter,
    CodeGeneratorConfig,
    CodeMergeError,
    FormatterConfig,
    OutputConfig,
    OutputMode,
    PipelineGenerator,
    PythonAstMerger,
)

__all__ = [
    "PipelineGenerator",
    "CodeGeneratorConfig",
    "FormatterConfig",
    "OutputConfig",
    "OutputMode",
    "CodeMergeError",
    "PythonAstMerger",
    "AtomicWriter",
]
