"""JSON Schema to Code Generator

A Python package for generating code from JSON Schema definitions.
Supports Python, C# and Swift code generation with AST-based pipeline,
code merging, and configurable output options.
"""

__version__ = "1.1.0"
__author__ = "François Lagunas"

from .pipeline import (
    AtomicWriter,
    CodeGeneratorConfig,
    CodeMergeError,
    FormatterConfig,
    MergeStrategy,
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
    "MergeStrategy",
    "CodeMergeError",
    "PythonAstMerger",
    "AtomicWriter",
]
